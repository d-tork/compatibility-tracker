# Mobile Compatibility Tracker

A modern, searchable, and sortable web application that displays software
compatibility across mobile phone models.  The backend is a lightweight Python
[Flask](https://flask.palletsprojects.com/) application; the frontend is pure
HTML5 + CSS + vanilla JavaScript with **no external dependencies**.

---

## Table of Contents

1. [Features](#features)
2. [Project Structure](#project-structure)
3. [Quick Start – Docker](#quick-start--docker)
4. [Quick Start – Local Development](#quick-start--local-development)
5. [Running Tests](#running-tests)
6. [Updating the Data](#updating-the-data)
7. [Upgrading the Data Layer](#upgrading-the-data-layer)
   - [Switch to YAML](#switch-to-yaml)
   - [Switch to a Local SQLite Database](#switch-to-a-local-sqlite-database)
   - [Switch to a Remote SQL Database](#switch-to-a-remote-sql-database)
8. [CI/CD](#cicd)
9. [Contributing](#contributing)

---

## Features

- **Sortable columns** – click any column header to sort ascending or
  descending.
- **Fuzzy / partial search** – the search bar filters rows by phone name, OS,
  release year, software name, or version string.
- **Modern UI** – system-font stack, CSS custom properties, no framework
  dependencies.
- **Accessible** – ARIA roles, live-region result count, keyboard navigation
  for column sorting.
- **Dockerized** – single `docker compose up` to run the full stack.
- **Extensible data layer** – swap JSON → YAML → SQL without touching
  application code.

---

## Project Structure

```
compatibility-tracker/
├── app/
│   ├── __init__.py          # Package marker
│   ├── main.py              # Flask application and routes
│   ├── data_layer.py        # Abstract DataLayer + JSONDataLayer
│   └── templates/
│       └── index.html       # Single-page frontend
├── data/
│   └── compatibility.json   # Phone/software compatibility data
├── tests/
│   ├── __init__.py
│   └── test_app.py          # pytest unit tests
├── .github/
│   └── workflows/
│       └── ci.yml           # GitHub Actions CI pipeline
├── Dockerfile
├── compose.yaml
├── pyproject.toml           # pytest configuration
├── requirements.txt         # Production dependencies
├── requirements-dev.txt     # Development + testing dependencies
└── README.md
```

---

## Quick Start – Docker

**Prerequisites:** [Docker](https://docs.docker.com/get-docker/) and
[Docker Compose](https://docs.docker.com/compose/install/) (v2+).

```bash
# Clone the repository
git clone https://github.com/d-tork/compatibility-tracker.git
cd compatibility-tracker

# Build and start the container
docker compose up --build

# Open your browser at http://localhost:5000
```

To stop the container:

```bash
docker compose down
```

The `data/` directory is bind-mounted read-only into the container, so you can
edit `data/compatibility.json` and refresh the page **without rebuilding the
image**.

---

## Quick Start – Local Development

**Prerequisites:** Python 3.11 or 3.12.

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements-dev.txt

# 3. Run the development server
python -m app.main
# or
flask --app app.main run --debug

# Open http://localhost:5000
```

---

## Running Tests

```bash
# With a virtual environment already activated
pytest

# With coverage output in the terminal
pytest --cov=app --cov-report=term-missing
```

Tests are located in `tests/test_app.py` and cover:

- `JSONDataLayer` – loading valid JSON, error handling for missing or malformed
  files, and deterministic repeated reads.
- `create_data_layer` factory – type dispatch, default argument, and error for
  unknown backend names.
- `DataLayer` abstract interface – instantiation rules and subclass contract.
- Flask routes – HTTP status codes, content-type headers, and response body
  contents for both `/` and `/api/data`.

---

## Updating the Data

Edit `data/compatibility.json` to add phones or software columns.

### JSON schema

```json
{
  "software_columns": ["App A", "App B"],
  "phones": [
    {
      "name": "My Phone",
      "os": "Android 14",
      "released": "2024",
      "software": {
        "App A": "3.x",
        "App B": "1.2.x"
      }
    }
  ]
}
```

| Field              | Type            | Description                                   |
|--------------------|-----------------|-----------------------------------------------|
| `software_columns` | `string[]`      | Ordered list of software names (table headers)|
| `phones[].name`    | `string`        | Device display name                           |
| `phones[].os`      | `string`        | Operating system and version                  |
| `phones[].released`| `string`        | Release year (optional)                       |
| `phones[].software`| `object`        | Map of software name → supported version string; omit a key or set to `null` to indicate no support |

---

## Upgrading the Data Layer

The data access logic is isolated in `app/data_layer.py` behind the
`DataLayer` abstract base class.  The Flask application reads the
`DATA_SOURCE_TYPE` environment variable to choose a backend at startup.
Switching backends requires:

1. Creating a new `DataLayer` subclass.
2. Registering it in the `constructors` dict inside `create_data_layer`.
3. Setting the appropriate environment variables.

### Switch to YAML

Install PyYAML:

```bash
pip install pyyaml
```

Add to `app/data_layer.py`:

```python
import yaml

class YAMLDataLayer(DataLayer):
    """Compatibility-data backend that reads from a local YAML file."""

    def __init__(self, yaml_file_path: str) -> None:
        self._yaml_file_path = yaml_file_path

    def get_compatibility_data(self) -> dict[str, Any]:
        with open(self._yaml_file_path, encoding="utf-8") as f:
            return yaml.safe_load(f)
```

Register it in `create_data_layer`:

```python
constructors: dict[str, type[DataLayer]] = {
    "json": JSONDataLayer,
    "yaml": YAMLDataLayer,   # ← add this line
}
```

Set the environment variables (or update `compose.yaml`):

```bash
export DATA_SOURCE_TYPE=yaml
export YAML_FILE_PATH=/path/to/compatibility.yaml
```

### Switch to a Local SQLite Database

Install SQLAlchemy:

```bash
pip install sqlalchemy
```

Create a `SQLiteDataLayer` (or a generic `SQLAlchemyDataLayer`) subclass that
queries a `phones` table and a `software_versions` join table, then assembles
them into the same `{"phones": [...], "software_columns": [...]}` shape the
frontend expects.

Example table schema:

```sql
CREATE TABLE phones (
    id        INTEGER PRIMARY KEY,
    name      TEXT NOT NULL,
    os        TEXT,
    released  TEXT
);

CREATE TABLE software (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL UNIQUE
);

CREATE TABLE phone_software (
    phone_id    INTEGER REFERENCES phones(id),
    software_id INTEGER REFERENCES software(id),
    version     TEXT,
    PRIMARY KEY (phone_id, software_id)
);
```

Set:

```bash
export DATA_SOURCE_TYPE=sqlite
export DATABASE_URL=sqlite:////absolute/path/to/compatibility.db
```

### Switch to a Remote SQL Database

The approach is identical to SQLite but with a different connection string:

```bash
# PostgreSQL
export DATA_SOURCE_TYPE=postgres
export DATABASE_URL=postgresql://user:password@host:5432/dbname

# MySQL / MariaDB
export DATA_SOURCE_TYPE=mysql
export DATABASE_URL=mysql+pymysql://user:password@host:3306/dbname
```

Use SQLAlchemy's engine to connect; the `DATABASE_URL` is the only
configuration that changes between environments.

---

## CI/CD

A GitHub Actions workflow lives at `.github/workflows/ci.yml`.  It runs
automatically on every pull-request to `main`/`master` and on direct pushes,
testing against Python 3.11 and 3.12.

The pipeline:

1. Checks out the repository.
2. Sets up Python with pip caching.
3. Installs development dependencies.
4. Runs `pytest` with coverage.
5. Uploads the `coverage.xml` artifact (Python 3.12 run only).

---

## Contributing

1. Fork the repository and create a feature branch.
2. Make your changes and add or update tests.
3. Run `pytest` locally to confirm everything passes.
4. Open a pull request — the CI pipeline will run automatically.
