# College System -- Development Guide

This document covers setting up, running, and contributing to the Sixth Form College Management System.

## Prerequisites

- **Python 3.11 or 3.12** (see `pyproject.toml` for the exact constraint `>=3.11`)
- **SQLite** (bundled with Python; no external database required)
- **tkinter** (ships with most Python distributions; needed for the GUI)

Install the project and its development dependencies from the repository root:

```bash
make install-dev
```

Optional dependency groups include:

| Group   | Purpose                                | Install                    |
|---------|----------------------------------------|----------------------------|
| `dev`   | pytest, black, ruff, mypy, pre-commit  | `pip install -e ".[dev]"`  |
| `test`  | pytest + coverage + xdist              | `pip install -e ".[test]"` |
| `desktop` | Tkinter desktop extras               | `pip install -e ".[desktop]"` |

See `pyproject.toml` for the full list.

### Virtual Environment

The project expects a virtual environment. Always use the venv's Python when running commands outside of an activated environment.


## Project Layout

```
src/education_system/systems/sixth_form/
    manifest.py                 # System key, display name and interfaces
    assets/templates/email/     # Email templates
    domain/                     # Business rules, one folder per module
        academics/  admissions/  assessment/  governance/  learners/
        operations/  pastoral/  progression/  safeguarding/  staff/
    domains/                    # Vertical slices, each with domain/ and interfaces/
        communications/
        finance/                # Also has infrastructure/
        operations/
    infrastructure/
        database.py             # sqlite3 names for the domain layer
        log_store.py            # Log capture to the system_logs table
        record_links.py
        soft_delete.py
        adapters/               # Cross-system adapter
        integrations/
        scheduler/              # Background jobs
    interfaces/
        cli/cli_main.py         # CLI entry point
        gui/gui_main.py         # GUI entry point
        cli/<area>/<module>/    # CLI menus, mirroring domain/
        gui/<area>/<module>/    # tkinter windows, mirroring domain/

src/education_system/api/sixth_form/
    __init__.py                 # create_app for the standalone app, used by tests
    server.py                   # Standalone app, with the parent portal
    tokens.py                   # Signed tokens for the parent portal
    access_gate.py              # Capability rule for every route
    routes/                     # Flask blueprints, one module per area
        __init__.py             # ALL_BLUEPRINTS
        students_routes.py
        academics_routes.py
        ...
        menu/                   # Main-menu routes
    schemas/                    # Placeholder modules

tests/unit/systems/sixth_form/  # domain/, domains/, infrastructure/, interfaces/
tests/smoke/sixth_form/         # Smoke test

var/data/sixth_form/            # Runtime data, including sixthform.db
```

Shared capabilities (auth, API hosting, validation, audit) live in `src/education_system/platform/`, and every filesystem path is in `src/education_system/paths.py`. See [PROJECT_STRUCTURE.md](../../reference/PROJECT_STRUCTURE.md).


## Running the Application

The package-native unified launcher (`python -m education_system`) can start
any system/interface combination.

### CLI

```bash
python -m education_system --college --cli
```

### GUI

```bash
python -m education_system --college --gui
```

### REST API Server

```bash
python -m education_system --college --api
```

This starts the unified server for all seven systems on port 5000 by default (configurable via the `API_PORT` environment variable). The sixth form is mounted at `/api/v1/sixthform`.

### Tests

```bash
python -m education_system --college --test
```

Or run pytest directly:

```bash
python -m pytest tests/unit/systems/sixth_form/ -v --tb=short
```


## Architecture Overview

### Domain Layer

Every domain module exposes module-level functions that encapsulate its business logic and database access, and returns dataclasses. Modules follow a consistent pattern:

1. Hold the database location in a module-level `DB_PATH`, taken from `education_system.paths`.
2. Provide a `_connect()` helper that returns a fresh SQLite connection with `sqlite3.Row` rows and foreign keys on.
3. Create their tables in an idempotent `init_db()`, called at the start of each public function.
4. Raise the module's own `ValidationError` on bad input.

Example:

```python
def get_award(award_id: int) -> Award | None:
    init_db()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM awards WHERE award_id = ?", (award_id,)).fetchone()
    return _row(row) if row else None
```

### Flask API (Blueprints)

Each route module creates a `Blueprint` with a URL prefix (e.g., `/api/academics`), and wraps its views so that they check a JWT and then a capability rule in `api/sixth_form/access_gate.py`. The `api/sixth_form/routes/__init__.py` file aggregates the blueprints into `ALL_BLUEPRINTS`, which the unified server mounts under `/api/v1/sixthform`.

### GUI

The GUI is built with `tkinter` and `ttk`. Each domain module provides a window, opened by a function such as `open_enrichment_window(parent)`, and built on `SidebarBook` rather than top tabs. The main GUI window (`interfaces/gui/gui_main.py`) lists them in `NAV_CATEGORIES` and provides navigation.

### CLI

Each domain module optionally provides a CLI menu with a `dispatch(label)` function. The CLI main (`interfaces/cli/cli_main.py`) provides menu-driven navigation across all modules.


## Coding Standards

- **Line length**: 100 characters (configured for both Black and Ruff).
- **Formatter**: Ruff (`make format`).
- **Linter**: Ruff (see `pyproject.toml` for ignored rules).
- **Type checking**: mypy.
- **Security scanning**: Bandit.

### Running Linters

```bash
# Format
make format

# Lint
make lint

# Type check
make type-check

# Security scan
make security-scan
```

To limit a tool to the sixth form, pass the package path, for example `ruff check src/education_system/systems/sixth_form/`.


## Git Workflow

1. Create a feature branch from `main`.
2. Make changes following the module structure and coding standards documented above.
3. Run the test suite and linters before committing.
4. Write a concise commit message describing the "why" of the change.
5. Open a pull request against `main`.


## Database

The system uses **SQLite** with the following characteristics:

- Each module creates its own tables automatically through its `init_db()`. There is no central schema file, and Alembic does not manage this database.
- Modules turn on foreign keys per connection with `PRAGMA foreign_keys=ON`.
- Default accounts live in the central `auth.db`, not in `sixthform.db`, and are seeded only when `EDU_DEV_SEED=true`.
- For tests, redirect a module's `DB_PATH` with `monkeypatch`, and reset its `_DB_READY` flag.


## Exception Handling

There is no system-wide exception hierarchy. Each domain module defines its own `ValidationError`, usually a `ValueError` subclass, and route handlers turn it into an HTTP 400:

```python
try:
    course = data.update_course(course_id, request.get_json(silent=True) or {})
except data.ValidationError as e:
    return jsonify({"error": str(e)}), 400
```

Authentication failures use `AuthError` and `MFAError` from `education_system.platform.identity.auth.exceptions`. Common HTTP errors are handled in `src/education_system/platform/delivery/api/errors.py`.
