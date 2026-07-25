# Primary School Management System -- Development Guide

Last Updated: March 2026

## Overview

The Primary School Management System is one of four subsystems in the Education System platform. It manages Reception through Year 6, covering EYFS, KS1, and KS2 key stages. Built with Python, tkinter (GUI), CLI menus, and SQLite.

---

## Setting Up the Development Environment

### Prerequisites

- Python 3.11+
- The project virtualenv at `./venv/`

### Install Dependencies

```bash
./venv/bin/pip install -r requirements.txt
```

Key dependencies: `tkinter` (stdlib), `sqlite3` (stdlib), `flask`, `bcrypt`, `pyotp`, `pytest`, `black`, `ruff`.

### Verify Setup

```bash
python -c "from education_system.primary_school.core.paths import DB_FILE; print(DB_FILE)"
```

---

## Running the Application

### GUI Mode

```bash
# Via the universal launcher (shared login across all 4 systems)
python run.py

# Directly (standalone login)
python -m education_system.primary_school
```

### CLI Mode

```bash
python -m education_system.primary_school.cli.cli_main
```

### Running Tests

```bash
# All primary school tests
python -m pytest education_system/primary_school/tests/ -v

# Specific test file
python -m pytest education_system/primary_school/tests/test_pupil_service.py -v

# With coverage
python -m pytest education_system/primary_school/tests/ --cov=education_system.primary_school -v
```

### Default Login Credentials

| Username   | Password      | Role    |
|------------|---------------|---------|
| `admin3`   | `admin1234`   | admin   |
| `staff3`   | `staff1234`   | teacher |
| `student3` | `student1234` | student |
| `parent`   | `Parent@123`  | parent  |

---

## Project Structure

```
education_system/primary_school/
├── core/                          # Cross-cutting concerns
│   ├── defaults.py                # Constants (year groups, key stages, assessment levels, IDs)
│   ├── exceptions.py              # Exception hierarchy rooted at SchoolSystemError
│   ├── logs.py                    # Logging configuration
│   └── paths.py                   # Centralised file paths (DB_FILE, DATA_DIR, etc.)
├── infrastructure/                # Technical foundations
│   ├── auth/                      # Authentication (wraps shared auth module)
│   ├── database/
│   │   ├── db.py                  # connect(), transaction(), set_db_path()
│   │   ├── schema.py              # CREATE TABLE IF NOT EXISTS definitions
│   │   └── constants.py           # DB-level constants (SEND statuses, etc.)
│   └── validation/                # Input validators
├── modules/domain/                # Business domain modules (7 categories)
│   ├── academics/                 # pupils, subjects, classes, assessment, attendance,
│   │                              # timetable, homework, sats, phonics, reading_records, progress
│   ├── pastoral_care/             # behaviour, rewards, safeguarding, send, pastoral
│   ├── staff/                     # hr, cpd, cover, staff_directory
│   ├── admin/                     # users, settings, admissions, finance, data_export,
│   │                              # audit_log, policies, documents
│   ├── pupil_life/                # clubs, meals, transport, trips, library, medical,
│   │                              # class_groups, consent
│   ├── communication/             # email, notifications, announcements, calendar,
│   │                              # parents_evening, communication_log
│   └── facilities/                # room_booking, assets, visitors, incidents
├── cli/                           # CLI interface
│   ├── cli_main.py                # Entry point, login prompt, menu routing
│   └── menus/                     # One *_cli.py per domain module
├── api/                           # Flask REST API
├── main_gui.py                    # GUI entry point, login window, sidebar navigation
├── data/
│   ├── db_files/primary_school.db # SQLite database
│   └── config/                    # Runtime configuration
├── logs/                          # Application log files
└── tests/                         # Test suite
```

---

## Architecture

The system follows a layered architecture with strict dependency direction:

```
infrastructure  -->  core  -->  domain modules  -->  service layer  -->  gui / cli
     |                |              |                     |
  database         paths          module dir          business logic     presentation
  auth             exceptions     __init__.py         CRUD operations    tkinter frames
  validation       defaults                           DB queries         CLI menus
                   logs
```

### Layer Responsibilities

| Layer              | Location                       | Purpose                                         |
|--------------------|--------------------------------|--------------------------------------------------|
| **Infrastructure** | `infrastructure/`              | Database connections, authentication, validation |
| **Core**           | `core/`                        | Paths, exceptions, logging, constants            |
| **Domain Modules** | `modules/domain/<category>/`   | Business logic organised by domain               |
| **Service**        | `<module>/services/`           | CRUD operations, DB queries, business rules      |
| **GUI**            | `<module>/gui/`                | tkinter frames, Treeview tables, dialogs         |
| **CLI**            | `cli/menus/`                   | Text-based menus for each module                 |

### Data Flow

1. GUI/CLI calls service method (e.g., `PupilService.create_pupil()`)
2. Service validates input via `infrastructure/validation/`
3. Service calls `connect()` from `infrastructure/database/db.py`
4. Service executes parameterized SQL, commits, closes connection
5. Service raises domain exception (e.g., `PupilError`) on failure
6. GUI/CLI catches exception and displays error to user

---

## Key Conventions

### Service-First Design

All business logic lives in service classes. GUI and CLI are thin presentation layers that call service methods. Never put SQL or business rules in GUI/CLI code.

### Database Connection Pattern

Every service method manages its own connection with `try/finally`:

```python
def some_operation(self):
    conn = self._conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT ...", (param,))
        return cursor.fetchall()
    finally:
        conn.close()
```

For write operations, call `conn.commit()` before the `finally` block. Alternatively, use the `transaction()` context manager from `db.py`.

### Parameterized Queries

Always use `?` placeholders. Never use f-strings or `.format()` to build SQL:

```python
# Correct
cursor.execute("SELECT * FROM pupils WHERE year_group = ?", (year_group,))

# NEVER do this
cursor.execute(f"SELECT * FROM pupils WHERE year_group = '{year_group}'")
```

### Exception Handling

Raise domain-specific exceptions from `core/exceptions.py`. All exceptions inherit from `SchoolSystemError`:

```python
from education_system.primary_school.core.exceptions import PupilError

if not first_name:
    raise PupilError("First name is required")
```

### Centralised Paths

Import paths from `core/paths.py`. Never hardcode file paths:

```python
from education_system.primary_school.core.paths import DB_FILE, DATA_DIR, LOGS_DIR
```

### ID Formats

- Pupil IDs: `PRI0001`, `PRI0002`, ... (prefix from `PUPIL_ID_PREFIX`)
- Staff IDs: `STF0001`, `STF0002`, ... (prefix from `STAFF_ID_PREFIX`)

---

## Code Style

### Formatting and Linting

```bash
# Format code with Black
python -m black education_system/primary_school/

# Lint with Ruff
python -m ruff check education_system/primary_school/

# Auto-fix linting issues
python -m ruff check --fix education_system/primary_school/
```

### Style Rules

- PEP 8 naming: `snake_case` for functions/variables, `PascalCase` for classes
- Line length: 88 characters (Black default)
- Imports: standard library, then third-party, then local (Ruff enforces order)
- Docstrings: required on all modules, classes, and public methods
- Type hints: encouraged on public APIs

---

## Common Development Commands

```bash
# Run the full application (GUI)
python run.py

# Run CLI
python -m education_system.primary_school.cli.cli_main

# Format + lint
python -m black education_system/primary_school/ && \
python -m ruff check education_system/primary_school/

# Run tests with coverage
python -m pytest education_system/primary_school/tests/ \
    --cov=education_system.primary_school --cov-report=term-missing -v

# Check database schema
python -c "
from education_system.primary_school.infrastructure.database.db import connect
conn = connect()
tables = conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()
for t in tables: print(t['name'])
conn.close()
"
```
