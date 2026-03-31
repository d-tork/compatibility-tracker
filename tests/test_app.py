"""
Unit tests for the compatibility-tracker application.

Covers:
* :mod:`app.data_layer` – data layer factory, JSON loading, and error cases.
* :mod:`app.main` – HTTP routes (HTML page and JSON API endpoint).
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.data_layer import DataLayer, JSONDataLayer, create_data_layer
from app.main import app as flask_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_COMPATIBILITY_DATA: dict[str, Any] = {
    "software_columns": ["AppAlpha", "AppBeta"],
    "phones": [
        {
            "name": "Test Phone A",
            "os": "Android 14",
            "released": "2024",
            "software": {"AppAlpha": "1.0", "AppBeta": "2.5"},
        },
        {
            "name": "Test Phone B",
            "os": "iOS 17",
            "released": "2023",
            "software": {"AppAlpha": "0.9", "AppBeta": None},
        },
    ],
}


@pytest.fixture
def sample_json_file() -> str:
    """Create a temporary JSON file with sample data and return its path."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as temp_file:
        json.dump(SAMPLE_COMPATIBILITY_DATA, temp_file)
        return temp_file.name


@pytest.fixture
def flask_test_client(sample_json_file: str):
    """Return a Flask test client configured with the sample JSON data layer."""
    flask_app.config["TESTING"] = True

    # Override the module-level data layer with our sample data
    test_data_layer = JSONDataLayer(sample_json_file)
    original_data_layer = None

    import app.main as main_module

    original_data_layer = main_module._data_layer
    main_module._data_layer = test_data_layer

    with flask_app.test_client() as client:
        yield client

    # Restore original data layer after the test
    main_module._data_layer = original_data_layer


# ---------------------------------------------------------------------------
# DataLayer tests
# ---------------------------------------------------------------------------


class TestJSONDataLayer:
    """Tests for :class:`app.data_layer.JSONDataLayer`."""

    def test_loads_valid_json_file(self, sample_json_file: str) -> None:
        """JSONDataLayer correctly reads and parses a valid JSON file."""
        data_layer = JSONDataLayer(sample_json_file)
        result = data_layer.get_compatibility_data()
        assert result == SAMPLE_COMPATIBILITY_DATA

    def test_returns_phones_list(self, sample_json_file: str) -> None:
        """Returned data contains a 'phones' key with the expected list."""
        data_layer = JSONDataLayer(sample_json_file)
        result = data_layer.get_compatibility_data()
        assert "phones" in result
        assert len(result["phones"]) == 2

    def test_returns_software_columns(self, sample_json_file: str) -> None:
        """Returned data contains the 'software_columns' key."""
        data_layer = JSONDataLayer(sample_json_file)
        result = data_layer.get_compatibility_data()
        assert "software_columns" in result
        assert result["software_columns"] == ["AppAlpha", "AppBeta"]

    def test_raises_file_not_found_for_missing_file(self) -> None:
        """JSONDataLayer raises FileNotFoundError for a non-existent path."""
        data_layer = JSONDataLayer("/nonexistent/path/data.json")
        with pytest.raises(FileNotFoundError):
            data_layer.get_compatibility_data()

    def test_raises_json_decode_error_for_invalid_json(self) -> None:
        """JSONDataLayer raises json.JSONDecodeError for malformed JSON content."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as bad_file:
            bad_file.write("{not valid json}")
            bad_file_path = bad_file.name

        data_layer = JSONDataLayer(bad_file_path)
        with pytest.raises(json.JSONDecodeError):
            data_layer.get_compatibility_data()

    def test_multiple_reads_return_consistent_data(self, sample_json_file: str) -> None:
        """Calling get_compatibility_data twice returns identical results."""
        data_layer = JSONDataLayer(sample_json_file)
        first_result = data_layer.get_compatibility_data()
        second_result = data_layer.get_compatibility_data()
        assert first_result == second_result


class TestCreateDataLayer:
    """Tests for the :func:`app.data_layer.create_data_layer` factory."""

    def test_creates_json_data_layer(self, sample_json_file: str) -> None:
        """Factory returns a JSONDataLayer instance for type 'json'."""
        data_layer = create_data_layer("json", json_file_path=sample_json_file)
        assert isinstance(data_layer, JSONDataLayer)

    def test_json_data_layer_returns_data(self, sample_json_file: str) -> None:
        """Factory-created JSONDataLayer can successfully load data."""
        data_layer = create_data_layer("json", json_file_path=sample_json_file)
        result = data_layer.get_compatibility_data()
        assert result["phones"][0]["name"] == "Test Phone A"

    def test_raises_value_error_for_unknown_type(self, sample_json_file: str) -> None:
        """Factory raises ValueError when an unsupported backend type is given."""
        with pytest.raises(ValueError, match="Unknown data source type"):
            create_data_layer("unsupported_backend", json_file_path=sample_json_file)

    def test_default_type_is_json(self, sample_json_file: str) -> None:
        """Factory defaults to 'json' when data_source_type is not specified."""
        data_layer = create_data_layer(json_file_path=sample_json_file)
        assert isinstance(data_layer, JSONDataLayer)


class TestDataLayerAbstractInterface:
    """Verify the DataLayer abstract base class contract."""

    def test_cannot_instantiate_abstract_class(self) -> None:
        """DataLayer cannot be instantiated directly."""
        with pytest.raises(TypeError):
            DataLayer()  # type: ignore[abstract]

    def test_subclass_must_implement_get_compatibility_data(self) -> None:
        """A subclass without get_compatibility_data cannot be instantiated."""

        class IncompleteDataLayer(DataLayer):
            pass

        with pytest.raises(TypeError):
            IncompleteDataLayer()  # type: ignore[abstract]

    def test_concrete_subclass_can_be_instantiated(self) -> None:
        """A complete subclass can be instantiated and satisfies the interface."""

        class StubDataLayer(DataLayer):
            def get_compatibility_data(self) -> dict[str, Any]:
                return {"phones": [], "software_columns": []}

        stub = StubDataLayer()
        assert stub.get_compatibility_data() == {"phones": [], "software_columns": []}


# ---------------------------------------------------------------------------
# Flask route tests
# ---------------------------------------------------------------------------


class TestIndexRoute:
    """Tests for the ``GET /`` HTML endpoint."""

    def test_returns_200_status(self, flask_test_client) -> None:
        """The index route returns HTTP 200."""
        response = flask_test_client.get("/")
        assert response.status_code == 200

    def test_returns_html_content_type(self, flask_test_client) -> None:
        """The index route returns an HTML content-type header."""
        response = flask_test_client.get("/")
        assert "text/html" in response.content_type

    def test_response_contains_page_title(self, flask_test_client) -> None:
        """The HTML response contains the application title."""
        response = flask_test_client.get("/")
        assert b"Compatibility Tracker" in response.data

    def test_response_contains_search_input(self, flask_test_client) -> None:
        """The HTML response contains a search input element."""
        response = flask_test_client.get("/")
        assert b'id="search-input"' in response.data

    def test_response_contains_compatibility_table(self, flask_test_client) -> None:
        """The HTML response contains the compatibility table element."""
        response = flask_test_client.get("/")
        assert b'id="compatibility-table"' in response.data


class TestApiDataRoute:
    """Tests for the ``GET /api/data`` JSON endpoint."""

    def test_returns_200_status(self, flask_test_client) -> None:
        """The API data route returns HTTP 200."""
        response = flask_test_client.get("/api/data")
        assert response.status_code == 200

    def test_returns_json_content_type(self, flask_test_client) -> None:
        """The API data route returns an application/json content-type."""
        response = flask_test_client.get("/api/data")
        assert "application/json" in response.content_type

    def test_response_contains_phones_key(self, flask_test_client) -> None:
        """The API response JSON contains the 'phones' key."""
        response = flask_test_client.get("/api/data")
        data = json.loads(response.data)
        assert "phones" in data

    def test_response_contains_software_columns_key(self, flask_test_client) -> None:
        """The API response JSON contains the 'software_columns' key."""
        response = flask_test_client.get("/api/data")
        data = json.loads(response.data)
        assert "software_columns" in data

    def test_phones_list_matches_sample_data(self, flask_test_client) -> None:
        """The phones list in the API response matches the sample data."""
        response = flask_test_client.get("/api/data")
        data = json.loads(response.data)
        assert len(data["phones"]) == 2
        phone_names = [phone["name"] for phone in data["phones"]]
        assert "Test Phone A" in phone_names
        assert "Test Phone B" in phone_names

    def test_software_columns_match_sample_data(self, flask_test_client) -> None:
        """The software columns in the API response match the sample data."""
        response = flask_test_client.get("/api/data")
        data = json.loads(response.data)
        assert data["software_columns"] == ["AppAlpha", "AppBeta"]

    def test_phone_software_versions_are_present(self, flask_test_client) -> None:
        """Each phone's software dictionary is included in the response."""
        response = flask_test_client.get("/api/data")
        data = json.loads(response.data)
        phone_a = next(p for p in data["phones"] if p["name"] == "Test Phone A")
        assert phone_a["software"]["AppAlpha"] == "1.0"
        assert phone_a["software"]["AppBeta"] == "2.5"
