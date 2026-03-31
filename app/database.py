"""Database interaction module for the compatibility tracker.

Provides helper functions for CRUD operations and upserts on the SQL
schema defined in :mod:`app.models`.

Example connection strings
--------------------------
- **SQLite (file)**:   ``sqlite:///data/compatibility.db``
- **SQLite (memory)**: ``sqlite://``
- **PostgreSQL**:      ``postgresql+psycopg2://user:pass@host:5432/dbname``
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.models import Base, Phone, PhoneSoftware, Software


# ---------------------------------------------------------------------------
# Engine / schema helpers
# ---------------------------------------------------------------------------


def init_db(engine: Engine) -> None:
    """Create all tables defined in *models* if they do not already exist."""
    Base.metadata.create_all(engine)


# ---------------------------------------------------------------------------
# Software CRUD
# ---------------------------------------------------------------------------


def add_software(session: Session, name: str) -> Software:
    """Add a new software entry and return the ORM instance.

    Raises :class:`sqlalchemy.exc.IntegrityError` if *name* already exists.
    """
    sw = Software(name=name)
    session.add(sw)
    session.flush()
    return sw


def get_software_by_name(session: Session, name: str) -> Software | None:
    """Return a :class:`Software` by *name*, or ``None``."""
    return session.execute(
        select(Software).where(Software.name == name)
    ).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Phone CRUD
# ---------------------------------------------------------------------------


def add_phone(
    session: Session,
    name: str,
    os: str,
    released: str,
) -> Phone:
    """Insert a new phone row and return the ORM instance.

    Raises :class:`sqlalchemy.exc.IntegrityError` if the ``(name, os)``
    pair already exists.
    """
    phone = Phone(name=name, os=os, released=released)
    session.add(phone)
    session.flush()
    return phone


def get_phone(session: Session, name: str, os: str) -> Phone | None:
    """Look up a phone by its unique ``(name, os)`` pair."""
    return session.execute(
        select(Phone).where(Phone.name == name, Phone.os == os)
    ).scalar_one_or_none()


def update_phone(
    session: Session,
    phone: Phone,
    **kwargs: Any,
) -> Phone:
    """Update mutable attributes on an existing *phone*.

    Accepted keyword arguments: ``name``, ``os``, ``released``.
    """
    allowed = {"name", "os", "released"}
    for key, value in kwargs.items():
        if key not in allowed:
            raise ValueError(f"Cannot update unknown field '{key}' on Phone.")
        setattr(phone, key, value)
    session.flush()
    return phone


# ---------------------------------------------------------------------------
# Upsert (phone + software versions)
# ---------------------------------------------------------------------------


def upsert_phone(
    session: Session,
    name: str,
    os: str,
    released: str,
    software_versions: dict[str, str | None] | None = None,
) -> Phone:
    """Insert or update a phone entry keyed on ``(name, os)``.

    If a phone with the same *name* and *os* already exists, its
    ``released`` field and software versions are updated.  Otherwise a new
    row is created.

    *software_versions* maps software names to version strings (or
    ``None`` for unsupported).  Any referenced software that does not yet
    exist in the ``software`` table is created automatically.
    """
    phone = get_phone(session, name, os)
    if phone is None:
        phone = Phone(name=name, os=os, released=released)
        session.add(phone)
        session.flush()
    else:
        phone.released = released
        session.flush()

    if software_versions is not None:
        _sync_software_versions(session, phone, software_versions)

    return phone


def _sync_software_versions(
    session: Session,
    phone: Phone,
    software_versions: dict[str, str | None],
) -> None:
    """Synchronise the software-version associations for *phone*."""
    existing: dict[int, PhoneSoftware] = {
        ps.software_id: ps for ps in phone.software_entries
    }

    for sw_name, version in software_versions.items():
        sw = get_software_by_name(session, sw_name)
        if sw is None:
            sw = Software(name=sw_name)
            session.add(sw)
            session.flush()

        if sw.id in existing:
            existing[sw.id].version = version
        else:
            ps = PhoneSoftware(
                phone_id=phone.id, software_id=sw.id, version=version
            )
            session.add(ps)

    session.flush()


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


def get_compatibility_data(session: Session) -> dict[str, Any]:
    """Return the full compatibility dataset in the same shape as the JSON.

    .. code-block:: python

        {
            "software_columns": ["WhatsApp", "Spotify", ...],
            "phones": [
                {
                    "name": "...",
                    "os": "...",
                    "released": "...",
                    "software": {"WhatsApp": "2.24.x", ...}
                },
                ...
            ]
        }
    """
    software_rows = session.execute(
        select(Software).order_by(Software.id)
    ).scalars().all()
    software_columns = [s.name for s in software_rows]

    phones = session.execute(
        select(Phone).order_by(Phone.id)
    ).scalars().all()

    phone_list: list[dict[str, Any]] = []
    for phone in phones:
        version_map: dict[str, str | None] = {
            ps.software.name: ps.version for ps in phone.software_entries
        }
        software_dict: dict[str, str | None] = {
            col: version_map.get(col) for col in software_columns
        }
        phone_list.append(
            {
                "name": phone.name,
                "os": phone.os,
                "released": phone.released,
                "software": software_dict,
            }
        )

    return {"software_columns": software_columns, "phones": phone_list}
