# College System -- Development Guide

This document covers setting up, running, and contributing to the Sixth Form College Management System.

## Prerequisites

- **Python 3.11 or 3.12** (see `pyproject.toml` for the exact constraint `>=3.11`)
- **SQLite** (bundled with Python; no external database required)
- **tkinter** (ships with most Python distributions; needed for the GUI)

Install the project in editable mode with development dependencies:

```bash
pip install -e ".[dev]"
```

Optional dependency groups:

| Group   | Purpose                                | Install                    |
|---------|----------------------------------------|----------------------------|
| `dev`   | pytest, black, ruff, mypy, pre-commit  | `pip install -e ".[dev]"`  |
| `test`  | pytest + coverage + xdist              | `pip install -e ".[test]"` |
| `ai`    | TensorFlow, transformers, spaCy, torch | `pip install -e ".[ai]"`   |
| `cloud` | boto3, azure-storage, gcs              | `pip install -e ".[cloud]"`|

### Virtual Environment

The project expects a virtual environment. On this machine, the venv is located at:

```
python
```

Always use the full venv path when running Python commands outside of an activated environment.


## Project Layout

```
education_system/college_system/
    api/                        # Flask REST API
        api_server.py           # App factory (create_app) and run_server
        auth.py                 # JWT token generation, decorators
        config.py               # Flask Config class
        errors.py               # Centralised error handlers
        pagination.py           # Pagination helpers
        validators.py           # Request body validation
        routes/                 # One blueprint per domain module (~59 files)
            __init__.py         # ALL_BLUEPRINTS and ALL_INIT_FUNCS lists
            student_routes.py
            course_routes.py
            ...
    core/
        defaults.py             # Constants (JWT_SECRET, API_HOST, API_PORT, etc.)
        exceptions.py           # Exception hierarchy (CollegeSystemError base)
        paths.py                # Filesystem paths, ensure_directories()
    infrastructure/
        auth/                   # UserAuth, MFAService, bcrypt hashing
        database/
            db.py               # connect(), set_db_path(), ConnectionPool, DatabaseManager
            schema.py           # init_db(), seed_default_data()
            constants.py        # PRAGMAS, pool sizes, timeouts
        validation/
            validators.py       # validate_email, validate_non_empty, etc.
    modules/
        domain/                 # ~107 domain modules, each with:
            <module>/
                __init__.py
                services/       # Business logic (Service classes)
                gui/            # tkinter GUI panels
                cli/            # CLI command handlers
        shared/
            cli/cli_main.py     # CLI entry point
            gui/main_gui.py     # GUI entry point (launch_gui)
    tests/                      # pytest test suite
        conftest.py             # Shared fixtures
        test_*.py               # One test file per service / feature
    data/                       # Runtime data, config files
    logs/                       # Application logs
```


## Running the Application

The unified launcher at the project root (`run.py`) can start any system/interface combination.

### CLI

```bash
python run.py --college --cli
```

### GUI

```bash
python run.py --college --gui
```

### REST API Server

```bash
python run.py --college --api
```

The API starts on `http://127.0.0.1:5000` by default (configurable via `core/defaults.py`).

### Tests

```bash
python run.py --college --test
```

Or run pytest directly:

```bash
python -m pytest education_system/college_system/tests/ -v --tb=short
```


## Architecture Overview

### Service Layer

Every domain module exposes one or more **Service** classes that encapsulate all business logic and database access. Services follow a consistent pattern:

1. Accept `db_path` in `__init__` and store it as `self._db_path`.
2. Provide a `_conn()` helper that calls `connect(self._db_path)` to get a fresh SQLite connection.
3. Use `try / finally` blocks to ensure `conn.close()` is always called.
4. Raise module-specific exceptions (e.g., `StudentError`, `CourseError`) on failure.

Example:

```python
class StudentService:
    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def get_student(self, student_pk: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM students WHERE id = ?", (student_pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
```

### Flask API (Blueprints)

Each route module creates a `Blueprint` with a URL prefix (e.g., `/api/students`) and an `init_*_routes(db_path)` function that stores the database path in a module-level global. The `api/routes/__init__.py` file aggregates all blueprints into `ALL_BLUEPRINTS` and all init functions into `ALL_INIT_FUNCS`, which the app factory iterates over at startup.

### GUI

The GUI is built with `tkinter` and `ttk`. Each domain module provides a GUI panel (typically a `tk.Frame` subclass). The main GUI window (`modules/shared/gui/main_gui.py`) assembles all panels and provides navigation.

### CLI

Each domain module optionally provides CLI command handlers. The shared CLI main (`modules/shared/cli/cli_main.py`) provides menu-driven navigation across all modules.


## Coding Standards

- **Line length**: 100 characters (configured for both Black and Ruff).
- **Formatter**: Black (`black --line-length 100`).
- **Linter**: Ruff with `E` and `F` rule sets enabled (see `pyproject.toml` for ignored rules).
- **Import sorting**: isort with the `black` profile.
- **Type checking**: mypy (optional; `ignore_missing_imports = true`).
- **Security scanning**: Bandit (test directories excluded).

### Running Linters

```bash
# Format
black education_system/college_system/

# Lint
ruff check education_system/college_system/

# Type check
mypy education_system/college_system/

# Security scan
bandit -r education_system/college_system/ -c pyproject.toml
```


## Git Workflow

1. Create a feature branch from `main`.
2. Make changes following the module structure and coding standards documented above.
3. Run the test suite and linters before committing.
4. Write a concise commit message describing the "why" of the change.
5. Open a pull request against `main`.


## Database

The system uses **SQLite** with the following characteristics:

- Schema initialisation and default data seeding happen automatically via `init_db()` and `seed_default_data()` in `infrastructure/database/schema.py`.
- PRAGMAs (WAL mode, foreign keys, etc.) are applied on every connection via `infrastructure/database/constants.py`.
- A `ConnectionPool` and `DatabaseManager` class are available for advanced use, but most services use the simple `connect()` function directly.
- For tests, `set_db_path()` redirects all connections to a temporary database.


## Exception Hierarchy

All domain exceptions inherit from `CollegeSystemError`:

```
CollegeSystemError
    DatabaseError          -> HTTP 500
    AuthError              -> HTTP 401
    ValidationError        -> HTTP 400
    StudentError           -> HTTP 400
    CourseError             -> HTTP 400
    EnrollmentError        -> HTTP 400
    GradeError             -> HTTP 400
    AttendanceError        -> HTTP 400
    TimetableError         -> HTTP 400
    AssignmentError        -> HTTP 400
    NotificationError      -> HTTP 400
    MFAError               -> HTTP 400
    ... (50+ more domain-specific errors)
```

Error handlers in `api/errors.py` map each exception to the appropriate HTTP status code and JSON response.
