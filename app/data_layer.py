"""
Abstract data layer and concrete implementations for the compatibility tracker.

This module provides a :class:`DataLayer` abstract base class that defines the
interface for all data backends, along with a :class:`JSONDataLayer` concrete
implementation backed by a local JSON file.  Swapping to a different backend
(YAML, SQLite, or a remote SQL server) only requires creating a new subclass
and passing it to the Flask application.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any


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


def create_data_layer(data_source_type: str = "json", **kwargs: Any) -> DataLayer:
    """Factory function that instantiates the appropriate :class:`DataLayer`.

    This is the single entry-point for selecting a backend, making it easy to
    switch implementations without touching application code.

    Args:
        data_source_type: One of ``"json"`` (default).  Future values such as
            ``"sqlite"`` or ``"postgres"`` can be added here alongside their
            corresponding :class:`DataLayer` subclasses.
        **kwargs: Additional keyword arguments forwarded to the chosen
            :class:`DataLayer` constructor (e.g. ``json_file_path`` for
            :class:`JSONDataLayer`).

    Returns:
        A fully initialised :class:`DataLayer` instance.

    Raises:
        ValueError: If *data_source_type* is not a recognised backend name.
    """
    constructors: dict[str, type[DataLayer]] = {
        "json": JSONDataLayer,
    }

    if data_source_type not in constructors:
        supported = ", ".join(f'"{k}"' for k in constructors)
        raise ValueError(
            f"Unknown data source type '{data_source_type}'. "
            f"Supported types: {supported}."
        )

    return constructors[data_source_type](**kwargs)
