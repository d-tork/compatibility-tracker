"""
Abstract data layer and concrete implementations for the compatibility tracker.

This module provides a :class:`DataLayer` abstract base class that defines the
interface for all data backends, along with a :class:`JSONDataLayer` concrete
implementation backed by a local JSON file and a :class:`SQLDataLayer`
implementation backed by a SQL database via SQLAlchemy.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.database import get_compatibility_data as _sql_get_data
from app.database import init_db


class DataLayer(ABC):
    """Abstract base class for all compatibility-data backends."""

    @abstractmethod
    def get_compatibility_data(self) -> dict[str, Any]:
        """Return the full compatibility dataset.

        Returns:
            A dictionary containing at least the keys ``"phones"`` (a list of
            phone objects) and ``"software_columns"`` (an ordered list of
            software-name strings used as table column headers).
        """


class JSONDataLayer(DataLayer):
    """Compatibility-data backend that reads from a local JSON file.

    Args:
        json_file_path: Absolute or relative path to the JSON data file.

    Example::

        data_layer = JSONDataLayer("data/compatibility.json")
        data = data_layer.get_compatibility_data()
    """

    def __init__(self, json_file_path: str) -> None:
        self._json_file_path = json_file_path

    def get_compatibility_data(self) -> dict[str, Any]:
        """Load and return compatibility data from the JSON file.

        Returns:
            Parsed JSON contents as a Python dictionary.

        Raises:
            FileNotFoundError: If the configured JSON file does not exist.
            json.JSONDecodeError: If the file contains invalid JSON.
        """
        with open(self._json_file_path, encoding="utf-8") as data_file:
            return json.load(data_file)


class SQLDataLayer(DataLayer):
    """Compatibility-data backend that reads from a SQL database.

    Args:
        database_url: SQLAlchemy connection string.

    Example connection strings::

        # SQLite (file-based)
        SQLDataLayer(database_url="sqlite:///data/compatibility.db")

        # SQLite (in-memory)
        SQLDataLayer(database_url="sqlite://")

        # PostgreSQL
        SQLDataLayer(database_url="postgresql+psycopg2://user:pass@host:5432/db")
    """

    def __init__(self, database_url: str | None = None, *, engine: Engine | None = None) -> None:
        if engine is not None:
            self._engine = engine
        elif database_url is not None:
            self._engine = create_engine(database_url)
        else:
            raise ValueError("Either 'database_url' or 'engine' must be provided.")
        init_db(self._engine)

    def get_compatibility_data(self) -> dict[str, Any]:
        """Query the database and return the compatibility dataset.

        Returns:
            A dictionary with ``"software_columns"`` and ``"phones"`` keys,
            matching the format produced by :class:`JSONDataLayer`.
        """
        with Session(self._engine) as session:
            return _sql_get_data(session)


def create_data_layer(data_source_type: str = "json", **kwargs: Any) -> DataLayer:
    """Factory function that instantiates the appropriate :class:`DataLayer`.

    This is the single entry-point for selecting a backend, making it easy to
    switch implementations without touching application code.

    Args:
        data_source_type: One of ``"json"`` (default) or ``"sql"``.
        **kwargs: Additional keyword arguments forwarded to the chosen
            :class:`DataLayer` constructor (e.g. ``json_file_path`` for
            :class:`JSONDataLayer`, ``database_url`` for
            :class:`SQLDataLayer`).

    Returns:
        A fully initialised :class:`DataLayer` instance.

    Raises:
        ValueError: If *data_source_type* is not a recognised backend name.
    """
    constructors: dict[str, type[DataLayer]] = {
        "json": JSONDataLayer,
        "sql": SQLDataLayer,
    }

    if data_source_type not in constructors:
        supported = ", ".join(f'"{k}"' for k in constructors)
        raise ValueError(
            f"Unknown data source type '{data_source_type}'. "
            f"Supported types: {supported}."
        )

    return constructors[data_source_type](**kwargs)
