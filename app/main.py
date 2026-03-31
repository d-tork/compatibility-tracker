"""
Flask web application for the mobile-phone compatibility tracker.

The app exposes two routes:

* ``GET /`` – serves the main HTML page.
* ``GET /api/data`` – returns the full compatibility dataset as JSON, consumed
  by the page's client-side JavaScript.

The data backend is injected via :func:`app.data_layer.create_data_layer`,
so swapping to a different storage layer requires only an environment-variable
change and no application-code edits.
"""

from __future__ import annotations

import os

from flask import Flask, jsonify, render_template
from flask.wrappers import Response

from app.data_layer import DataLayer, create_data_layer

app = Flask(__name__)

_DATA_SOURCE_TYPE = os.environ.get("DATA_SOURCE_TYPE", "json")
_JSON_FILE_PATH = os.environ.get(
    "JSON_FILE_PATH",
    os.path.join(os.path.dirname(__file__), "..", "data", "compatibility.json"),
)
_DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///data/compatibility.db")

_layer_kwargs: dict[str, str] = (
    {"database_url": _DATABASE_URL}
    if _DATA_SOURCE_TYPE == "sql"
    else {"json_file_path": _JSON_FILE_PATH}
)

_data_layer: DataLayer = create_data_layer(
    data_source_type=_DATA_SOURCE_TYPE,
    **_layer_kwargs,
)


@app.route("/")
def index() -> str:
    """Render and return the main compatibility-tracker HTML page.

    Returns:
        Rendered HTML string for the index template.
    """
    return render_template("index.html")


@app.route("/api/data")
def api_data() -> Response:
    """Return the compatibility dataset as a JSON response.

    The client-side JavaScript fetches this endpoint on page load to populate
    the sortable, searchable compatibility table.

    Returns:
        A Flask :class:`~flask.wrappers.Response` containing the compatibility
        data serialised as JSON with the ``application/json`` content-type.
    """
    compatibility_data = _data_layer.get_compatibility_data()
    return jsonify(compatibility_data)


def create_app(data_layer: DataLayer | None = None) -> Flask:
    """Application factory used by tests and alternative entry-points.

    Args:
        data_layer: Optional pre-configured :class:`~app.data_layer.DataLayer`
            instance.  When *None*, the module-level ``_data_layer`` singleton
            (configured from environment variables) is used.

    Returns:
        The configured :class:`~flask.Flask` application instance.
    """
    if data_layer is not None:
        app.config["DATA_LAYER"] = data_layer

        @app.route("/api/data", endpoint="api_data_override")  # type: ignore[misc]
        def _api_data_override() -> Response:
            return jsonify(app.config["DATA_LAYER"].get_compatibility_data())

    return app


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)
