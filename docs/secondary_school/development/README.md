# Secondary School Management System - Developer Guide

> Last Updated: March 2026

This guide covers environment setup, project architecture, coding conventions, and common development commands for the Secondary School Management System.

## Table of Contents

- [Environment Setup](#environment-setup)
- [Running the Application](#running-the-application)
- [Project Structure](#project-structure)
- [Architecture](#architecture)
- [Coding Conventions](#coding-conventions)
- [Common Commands](#common-commands)

---

## Environment Setup

### Prerequisites

- Python 3.12+
- SQLite 3 (bundled with Python)
- tkinter (for GUI mode)

### Virtual Environment

The project uses a shared virtual environment located at the repository root:

```bash
# The venv is at:
python

# Always use the full path -- there is no bare `python` on the system
python -m pip install -r requirements.txt
```

### Dependencies

Install from the project root:

```bash
python -m pip install -r requirements.txt
```

Key dependencies include:

| Package | Purpose |
|---------|---------|
| Flask | REST API server |
| bcrypt | Password hashing (shared auth) |
| pyotp | TOTP-based MFA |
| pytest | Test framework |
| black | Code formatting |
| ruff | Linting |

---

## Running the Application

The system supports three modes: GUI (default), CLI, and REST API.

```bash
# GUI mode (default)
python -m education_system.secondary_school

# CLI mode
python -m education_system.secondary_school --cli

# REST API server
python -m education_system.secondary_school --api
```

You can also launch through the universal login (all four systems):

```bash
python run.py
```

### Running Tests

```bash
# All secondary school tests
python -m pytest education_system/secondary_school/tests/ -v

# Single test file
python -m pytest education_system/secondary_school/tests/test_student_service.py -v

# With coverage
python -m pytest education_system/secondary_school/tests/ --cov=education_system.secondary_school -v
```

### Code Style

```bash
# Format with Black
python -m black education_system/secondary_school/

# Lint with Ruff
python -m ruff check education_system/secondary_school/
```

---

## Project Structure

```
education_system/
├── secondary_school/
│   ├── __init__.py
│   ├── __main__.py              # Entry point (--gui / --cli / --api)
│   ├── main_gui.py              # Tkinter GUI launcher
│   │
│   ├── core/                    # Core utilities (no external deps)
│   │   ├── exceptions.py        # SchoolSystemError hierarchy
│   │   ├── paths.py             # Centralized path constants
│   │   ├── defaults.py          # ID prefixes, defaults
│   │   └── logs.py              # Logging setup
│   │
│   ├── infrastructure/          # Technical foundation
│   │   ├── auth/                # Auth wrapper (delegates to shared/)
│   │   ├── database/
│   │   │   ├── db.py            # connect(), transaction(), set_db_path()
│   │   │   ├── schema.py        # CREATE TABLE definitions, initialise_database()
│   │   │   └── constants.py     # PRAGMAs, grade scales, year groups
│   │   └── validation/
│   │       └── validators.py    # Input validators (email, non-empty, etc.)
│   │
│   ├── modules/domain/          # Business logic (51 modules)
│   │   ├── academics/           # 12 modules
│   │   │   ├── students/
│   │   │   ├── subjects/
│   │   │   ├── enrollment/
│   │   │   ├── grades/
│   │   │   ├── attendance/
│   │   │   ├── timetable/
│   │   │   ├── homework/
│   │   │   ├── exams/
│   │   │   ├── progress/
│   │   │   ├── interventions/
│   │   │   ├── reports/
│   │   │   └── (dashboard)
│   │   ├── pastoral_care/       # 8 modules
│   │   │   ├── behaviour/
│   │   │   ├── detentions/
│   │   │   ├── exclusions/
│   │   │   ├── rewards/
│   │   │   ├── pastoral/
│   │   │   ├── safeguarding/
│   │   │   ├── send/
│   │   │   └── ...
│   │   ├── staff/               # 4 modules
│   │   │   ├── hr/
│   │   │   ├── cpd/
│   │   │   ├── cover/
│   │   │   └── staff_directory/
│   │   ├── admin/               # 9 modules
│   │   │   ├── users/
│   │   │   ├── settings/
│   │   │   ├── admissions/
│   │   │   ├── finance/
│   │   │   ├── data_export/
│   │   │   ├── audit_log/
│   │   │   ├── policies/
│   │   │   ├── documents/
│   │   │   └── ...
│   │   ├── student_life/        # 10 modules
│   │   │   ├── clubs/
│   │   │   ├── meals/
│   │   │   ├── transport/
│   │   │   ├── trips/
│   │   │   ├── careers/
│   │   │   ├── library/
│   │   │   ├── medical/
│   │   │   ├── form_groups/
│   │   │   ├── consent/
│   │   │   └── ...
│   │   ├── facilities/          # 6 modules
│   │   │   ├── room_booking/
│   │   │   ├── assets/
│   │   │   ├── seating_plans/
│   │   │   ├── visitors/
│   │   │   ├── incidents/
│   │   │   └── ...
│   │   └── communication/       # 7 modules
│   │       ├── email/
│   │       ├── notifications/
│   │       ├── announcements/
│   │       ├── calendar/
│   │       ├── communication_log/
│   │       ├── parents_evening/
│   │       └── ...
│   │
│   ├── cli/                     # CLI entry point and menus
│   │   └── cli_main.py
│   ├── api/                     # Flask REST API
│   │   └── api_server.py
│   ├── tests/                   # Test suite
│   │   ├── conftest.py          # Shared fixtures (db_path, services)
│   │   ├── test_student_service.py
│   │   └── ...
│   ├── data/
│   │   └── db_files/
│   │       └── secondary_school.db
│   └── logs/
│
├── shared/                      # Cross-system shared modules
│   ├── auth/                    # Unified authentication (bcrypt, MFA, sessions)
│   ├── gui/                     # Universal login GUI
│   ├── cli/                     # Shared CLI login
│   └── data/db_files/auth.db    # Central auth database
│
├── college_system/
├── primary_school/
└── university_system/
```

### Module Directory Layout

Each domain module follows a consistent internal structure:

```
modules/domain/<category>/<module_name>/
├── __init__.py
├── services/
│   └── <module>_service.py      # Business logic (DB access)
├── gui/
│   └── <module>_gui.py          # Tkinter GUI panel
└── cli/
    └── __init__.py              # CLI menu (if applicable)
```

---

## Architecture

The system follows a layered architecture with strict dependency direction:

```
infrastructure/ --> core/ --> modules/domain/ --> services/ --> gui/ / cli/ / api/
```

### Layer Responsibilities

| Layer | Directory | Responsibility |
|-------|-----------|---------------|
| **Infrastructure** | `infrastructure/` | Database connections, schema, auth wrappers, validators |
| **Core** | `core/` | Exceptions, paths, defaults, logging -- no external dependencies |
| **Domain Services** | `modules/domain/*/services/` | Business logic, data access, validation enforcement |
| **Presentation** | `gui/`, `cli/`, `api/` | User interface; calls services only |

### Key Principles

1. **Service-first**: All business logic lives in service classes. GUI/CLI/API layers call services and never access the database directly.

2. **Connection management**: Services use `_conn()` to get a connection and `try/finally` with `conn.close()` to ensure cleanup:

   ```python
   def _conn(self):
       return connect(self._db_path)

   def get_item(self, item_id: int) -> dict | None:
       conn = self._conn()
       try:
           row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
           return dict(row) if row else None
       finally:
           conn.close()
   ```

3. **Parameterized queries**: Always use `?` placeholders -- never string interpolation for SQL.

4. **Centralized paths**: All file paths come from `core/paths.py`. Never hard-code paths.

5. **Exception hierarchy**: Every module has a dedicated exception class inheriting from `SchoolSystemError` in `core/exceptions.py`.

### Database

- **Engine**: SQLite with WAL journal mode
- **File**: `secondary_school/data/db_files/secondary_school.db`
- **Connection**: `infrastructure/database/db.py` -- `connect()` applies PRAGMAs (WAL, foreign keys, cache size)
- **Row factory**: `sqlite3.Row` for dict-like access
- **Schema**: Defined in `infrastructure/database/schema.py` using `CREATE TABLE IF NOT EXISTS`
- **PRAGMAs**: WAL, foreign keys ON, busy timeout 5000ms, 8MB cache, synchronous NORMAL

### Authentication

Authentication is handled by the shared module at `education_system/shared/auth/`. The secondary school's `infrastructure/auth/` wraps the shared auth with thin re-exports.

- Central auth database: `shared/data/db_files/auth.db`
- Password hashing: bcrypt (legacy PBKDF2 auto-migrated on login)
- Sessions: DB-backed with token + expiry
- MFA: TOTP via pyotp with recovery codes
- Default accounts: `admin` / `Admin@School123`, `student` / `Student@School123`

### Domain Constants

Key school-specific constants are in `infrastructure/database/constants.py`:

- **Year groups**: 7, 8, 9, 10, 11
- **Key stages**: KS3 (Years 7-9), KS4 (Years 10-11)
- **GCSE grade scale**: 9 to 1 plus U (reformed scale)
- **Terms**: Autumn, Spring, Summer
- **Student ID prefix**: `SEC` (e.g. `SEC0001`)
- **Staff ID prefix**: `STF` (e.g. `STF0001`)

---

## Coding Conventions

### Code Style

- **Formatter**: Black (default settings)
- **Linter**: Ruff
- **Standard**: PEP 8

### Naming

| Item | Convention | Example |
|------|-----------|---------|
| Service class | `PascalCase` + `Service` | `StudentService` |
| GUI class | `PascalCase` + suffix | `_StudentDialog`, `StudentPanel` |
| Exception | `PascalCase` + `Error` | `StudentError` |
| Module directory | `snake_case` | `form_groups/` |
| Service file | `<module>_service.py` | `student_service.py` |
| Test file | `test_<module>_service.py` | `test_student_service.py` |
| DB table | `snake_case` plural | `students`, `form_groups` |
| Student ID | `SEC` + 4-digit | `SEC0001` |
| Staff ID | `STF` + 4-digit | `STF0001` |

### Import Style

```python
# Standard library
from datetime import datetime
import logging

# Project - infrastructure
from education_system.secondary_school.infrastructure.database.db import connect
from education_system.secondary_school.infrastructure.validation.validators import validate_non_empty

# Project - core
from education_system.secondary_school.core.exceptions import StudentError, ValidationError
from education_system.secondary_school.core.defaults import STUDENT_ID_PREFIX
```

### Error Handling

- Raise specific exception subclasses from `core/exceptions.py`
- Validate inputs at the top of service methods before any DB access
- Use `try/finally` (not `try/except`) for connection cleanup in services
- Let exceptions propagate to the GUI/CLI layer for user-facing messages

### GUI Conventions

- Panels inherit from `tk.Frame`
- Modal dialogs inherit from `tk.Toplevel` with `grab_set()`
- Use `ttk.Treeview` for tabular data
- Use `ttk.Notebook` for tabs
- Colour constants: `HEADER_BG = "#1a5276"`, `SIDEBAR_BG = "#2c3e50"`, `MAIN_BG = "#ecf0f1"`

---

## Common Commands

```bash
# Run the app (GUI)
python -m education_system.secondary_school

# Run all tests
python -m pytest education_system/secondary_school/tests/ -v

# Run a specific test class
python -m pytest education_system/secondary_school/tests/test_student_service.py::TestStudentService -v

# Format code
python -m black education_system/secondary_school/

# Lint code
python -m ruff check education_system/secondary_school/

# Auto-fix lint issues
python -m ruff check education_system/secondary_school/ --fix

# Initialize / reset the database
python -c "
from education_system.secondary_school.infrastructure.database.schema import initialise_database, seed_default_users
initialise_database()
seed_default_users()
"
```
