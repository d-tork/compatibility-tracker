"""Tests for the SQL database layer (models, CRUD helpers, and SQLDataLayer)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import (
    add_phone,
    add_software,
    get_compatibility_data,
    get_phone,
    get_software_by_name,
    init_db,
    update_phone,
    upsert_phone,
)
from app.data_layer import SQLDataLayer, create_data_layer
from app.models import Base, Phone, PhoneSoftware, Software


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def engine():
    """Create a fresh in-memory SQLite engine for each test."""
    eng = create_engine("sqlite://", echo=False)
    init_db(eng)
    return eng


@pytest.fixture()
def session(engine):
    """Provide a transactional session that is rolled back after each test."""
    with Session(engine) as sess:
        yield sess
        sess.rollback()


# ---------------------------------------------------------------------------
# Software CRUD
# ---------------------------------------------------------------------------


class TestAddSoftware:
    """Tests for add_software()."""

    def test_adds_new_software(self, session):
        sw = add_software(session, "WhatsApp")
        assert sw.id is not None
        assert sw.name == "WhatsApp"

    def test_duplicate_software_raises_integrity_error(self, session):
        add_software(session, "Spotify")
        session.commit()
        with pytest.raises(IntegrityError):
            add_software(session, "Spotify")

    def test_get_software_by_name_returns_match(self, session):
        add_software(session, "Chrome")
        session.commit()
        result = get_software_by_name(session, "Chrome")
        assert result is not None
        assert result.name == "Chrome"

    def test_get_software_by_name_returns_none_for_missing(self, session):
        assert get_software_by_name(session, "NonExistent") is None


# ---------------------------------------------------------------------------
# Phone CRUD
# ---------------------------------------------------------------------------


class TestAddPhone:
    """Tests for add_phone()."""

    def test_adds_new_phone(self, session):
        phone = add_phone(session, "Pixel 8", "Android 14", "2023")
        assert phone.id is not None
        assert phone.name == "Pixel 8"
        assert phone.os == "Android 14"
        assert phone.released == "2023"

    def test_duplicate_phone_raises_integrity_error(self, session):
        add_phone(session, "Pixel 8", "Android 14", "2023")
        session.commit()
        with pytest.raises(IntegrityError):
            add_phone(session, "Pixel 8", "Android 14", "2024")

    def test_same_name_different_os_is_allowed(self, session):
        add_phone(session, "Pixel 8", "Android 14", "2023")
        phone2 = add_phone(session, "Pixel 8", "Android 15", "2024")
        session.commit()
        assert phone2.id is not None


class TestGetPhone:
    """Tests for get_phone()."""

    def test_returns_matching_phone(self, session):
        add_phone(session, "iPhone 15", "iOS 17", "2023")
        session.commit()
        result = get_phone(session, "iPhone 15", "iOS 17")
        assert result is not None
        assert result.name == "iPhone 15"

    def test_returns_none_for_missing(self, session):
        assert get_phone(session, "NoPhone", "NoOS") is None


class TestUpdatePhone:
    """Tests for update_phone()."""

    def test_updates_released_field(self, session):
        phone = add_phone(session, "Pixel 7", "Android 13", "2022")
        session.commit()
        update_phone(session, phone, released="2023")
        session.commit()
        assert phone.released == "2023"

    def test_rejects_unknown_field(self, session):
        phone = add_phone(session, "Pixel 7", "Android 13", "2022")
        with pytest.raises(ValueError, match="unknown field"):
            update_phone(session, phone, colour="black")


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------


class TestUpsertPhone:
    """Tests for upsert_phone()."""

    def test_inserts_new_phone(self, session):
        phone = upsert_phone(session, "Galaxy S24", "Android 14", "2024")
        session.commit()
        assert phone.id is not None
        assert phone.name == "Galaxy S24"

    def test_updates_existing_phone(self, session):
        upsert_phone(session, "Galaxy S24", "Android 14", "2024")
        session.commit()
        phone = upsert_phone(session, "Galaxy S24", "Android 14", "2025")
        session.commit()
        assert phone.released == "2025"

    def test_inserts_software_versions(self, session):
        add_software(session, "WhatsApp")
        session.commit()
        phone = upsert_phone(
            session,
            "Galaxy S24",
            "Android 14",
            "2024",
            software_versions={"WhatsApp": "2.24.x"},
        )
        session.commit()
        assert len(phone.software_entries) == 1
        assert phone.software_entries[0].version == "2.24.x"

    def test_creates_missing_software_on_upsert(self, session):
        phone = upsert_phone(
            session,
            "Galaxy S24",
            "Android 14",
            "2024",
            software_versions={"NewApp": "1.0"},
        )
        session.commit()
        sw = get_software_by_name(session, "NewApp")
        assert sw is not None
        assert len(phone.software_entries) == 1

    def test_updates_existing_software_version(self, session):
        upsert_phone(
            session,
            "Galaxy S24",
            "Android 14",
            "2024",
            software_versions={"WhatsApp": "2.24.x"},
        )
        session.commit()
        phone = upsert_phone(
            session,
            "Galaxy S24",
            "Android 14",
            "2024",
            software_versions={"WhatsApp": "2.25.x"},
        )
        session.commit()
        assert phone.software_entries[0].version == "2.25.x"

    def test_upsert_with_none_version(self, session):
        phone = upsert_phone(
            session,
            "Galaxy S24",
            "Android 14",
            "2024",
            software_versions={"WhatsApp": None},
        )
        session.commit()
        assert phone.software_entries[0].version is None


# ---------------------------------------------------------------------------
# get_compatibility_data
# ---------------------------------------------------------------------------


class TestGetCompatibilityData:
    """Tests for get_compatibility_data()."""

    def test_empty_database_returns_empty_structure(self, session):
        data = get_compatibility_data(session)
        assert data == {"software_columns": [], "phones": []}

    def test_returns_software_columns(self, session):
        add_software(session, "AppAlpha")
        add_software(session, "AppBeta")
        session.commit()
        data = get_compatibility_data(session)
        assert data["software_columns"] == ["AppAlpha", "AppBeta"]

    def test_returns_phone_entries(self, session):
        add_software(session, "AppAlpha")
        session.commit()
        upsert_phone(
            session,
            "Test Phone",
            "Android 14",
            "2024",
            software_versions={"AppAlpha": "1.0"},
        )
        session.commit()
        data = get_compatibility_data(session)
        assert len(data["phones"]) == 1
        phone = data["phones"][0]
        assert phone["name"] == "Test Phone"
        assert phone["os"] == "Android 14"
        assert phone["released"] == "2024"
        assert phone["software"] == {"AppAlpha": "1.0"}

    def test_missing_software_shows_as_none(self, session):
        add_software(session, "AppAlpha")
        add_software(session, "AppBeta")
        session.commit()
        upsert_phone(
            session,
            "Test Phone",
            "Android 14",
            "2024",
            software_versions={"AppAlpha": "1.0"},
        )
        session.commit()
        data = get_compatibility_data(session)
        phone = data["phones"][0]
        assert phone["software"]["AppAlpha"] == "1.0"
        assert phone["software"]["AppBeta"] is None


# ---------------------------------------------------------------------------
# SQLDataLayer integration
# ---------------------------------------------------------------------------


class TestSQLDataLayer:
    """Tests for the SQLDataLayer class."""

    def test_creates_tables_on_init(self):
        layer = SQLDataLayer(database_url="sqlite://")
        data = layer.get_compatibility_data()
        assert "software_columns" in data
        assert "phones" in data

    def test_returns_data_after_seeding(self):
        engine = create_engine("sqlite://")
        init_db(engine)
        with Session(engine) as session:
            add_software(session, "AppAlpha")
            upsert_phone(
                session,
                "Phone A",
                "Android 14",
                "2024",
                software_versions={"AppAlpha": "1.0"},
            )
            session.commit()

        layer = SQLDataLayer.__new__(SQLDataLayer)
        layer._engine = engine

        data = layer.get_compatibility_data()
        assert data["software_columns"] == ["AppAlpha"]
        assert len(data["phones"]) == 1
        assert data["phones"][0]["software"]["AppAlpha"] == "1.0"


class TestCreateDataLayerSQL:
    """Tests for create_data_layer() with SQL backend."""

    def test_creates_sql_data_layer(self):
        layer = create_data_layer("sql", database_url="sqlite://")
        assert isinstance(layer, SQLDataLayer)

    def test_sql_data_layer_returns_data(self):
        layer = create_data_layer("sql", database_url="sqlite://")
        data = layer.get_compatibility_data()
        assert "software_columns" in data
        assert "phones" in data

    def test_raises_value_error_for_unknown_type(self):
        with pytest.raises(ValueError, match="Unknown data source type"):
            create_data_layer("nosql")
