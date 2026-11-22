# Primary School Management System -- Development Guide

Last Updated: October 2026

## Overview

The Primary School Management System is one of seven systems in the Education System platform. It manages Reception through Year 6, covering EYFS, KS1, and KS2 key stages. Built with Python, tkinter (GUI), CLI menus, and SQLite.

---

## Setting Up the Development Environment

### Prerequisites

- Python 3.11+
- A virtualenv with the project installed

### Install Dependencies

```bash
make install-dev
```

This installs from `requirements-dev.lock`. Key dependencies: `tkinter` (stdlib), `sqlite3` (stdlib), `flask`, `bcrypt`, `pyotp`, `pytest`, `ruff`.

### Verify Setup

```bash
python -c "from education_system.paths import PRIMARY_PUPILS_DB; print(PRIMARY_PUPILS_DB)"
```

---

## Running the Application

### GUI Mode

```bash
# Via the universal launcher (shared login across all 7 systems)
python -m education_system

# Directly
python -m education_system --primary --gui
```

### CLI Mode

```bash
python -m education_system --primary --cli
```

`gui_main.py` and `cli_main.py` refuse to start standalone: they need the session the launcher creates.

### Running Tests

```bash
# All primary school unit tests
python -m pytest tests/unit/systems/primary/ -v

# Specific test file
python -m pytest tests/unit/systems/primary/test_paths.py -v

# Smoke test
python -m pytest tests/smoke/primary/ -v

# With coverage
python -m pytest tests/unit/systems/primary/ --cov=education_system.systems.primary -v
```

### Default Login Credentials

| Username   | Password      | Role    |
|------------|---------------|---------|
| `admin3`   | `admin1234`   | admin   |
| `staff3`   | `staff1234`   | teacher |
| `student3` | `student1234` | student |
| `parent3`  | `parent1234`  | parent  |

These are seeded only when `EDU_DEV_SEED=true`. See [DEFAULT_ACCOUNTS.md](../../reference/DEFAULT_ACCOUNTS.md).

---

## Project Structure

```
src/education_system/systems/primary/
├── manifest.py                    # Key, display name and interfaces
├── cli_main.py                    # CLI entry point, CATEGORIES and menu routing
├── gui_main.py                    # GUI entry point, NAV_CATEGORIES and sidebar
├── domain/                        # Business domain modules, by area
│   ├── academics/                 # academic_year, attendance, calendar, classes, enrichment,
│   │                              # homework, lesson_plans, library, subjects, timetable, year_groups
│   ├── admissions/                # admissions, enrolment
│   ├── assessment/                # assessment, early_warning, eyfs_profile, intervention_tracking,
│   │                              # ks1_sats, ks2_sats, mtc, observations, phonics, phonics_screening,
│   │                              # progress, reading_levels, target_setting
│   ├── finance/                   # dinner_money, expense_claims, funding, pupil_premium, receipts, trips
│   ├── governance/                # audit, compliance, gdpr, governance, health_safety, mfa,
│   │                              # policies, risk_management, user_management
│   ├── learners/pupils/           # pupils, onboarding, leavers, bulk_operations
│   ├── operations/                # assets, attachments, communications, daily_care, document_hub,
│   │                              # reporting, todo, visitors
│   ├── pastoral/                  # absence_requests, accessibility, attendance_concerns, behaviour,
│   │                              # complaints, emergency, equality_diversity, feedback, health,
│   │                              # house_points, pupil_support, school_council, send, surveys,
│   │                              # transport, wellbeing
│   ├── safeguarding/              # safeguarding, prevent_duty
│   └── staff/                     # appraisals, class_teachers, cover, cpd, dbs_checks, departments,
│                                  # recruitment, staff, staff_absence, staff_hr, staff_wellbeing,
│                                  # teaching_assistants
├── infrastructure/                # Currently only __init__.py
└── interfaces/
    ├── cli/                       # Terminal menus, mirroring the domain areas
    ├── gui/                       # tkinter windows, mirroring the domain areas
    └── about.py, change_password.py, settings.py, user_accounts.py

src/education_system/api/primary/
├── routes/                        # One Flask blueprint per module (ALL_BLUEPRINTS)
└── schemas/                       # Scaffolded, not yet implemented

src/education_system/paths.py      # Every path, including PRIMARY_PUPILS_DB
var/data/primary/primary.db        # SQLite database (shared by all modules)
var/backups/primary/               # Backups

tests/unit/systems/primary/        # Unit tests
tests/smoke/primary/               # Smoke test
```

---

## Architecture

The system follows a layered architecture with strict dependency direction:

```
gui / cli / api routes  -->  domain modules  -->  SQLite
                                  |
                          education_system.paths
                          education_system.platform
```

### Layer Responsibilities

| Layer              | Location                                 | Purpose                                         |
|--------------------|------------------------------------------|--------------------------------------------------|
| **Domain Modules** | `domain/<area>/`                         | Schema, validation, CRUD, business rules        |
| **GUI**            | `interfaces/gui/<area>/`                 | tkinter windows, Treeview tables, dialogs       |
| **CLI**            | `interfaces/cli/<area>/`                 | Text-based menus for each module                |
| **API**            | `education_system/api/primary/routes/`   | REST blueprints over the domain modules         |
| **Platform**       | `education_system/platform/`             | Shared auth, validators, messaging, delivery    |

### Data Flow

1. GUI/CLI calls a domain function (e.g., `pupils.create_pupil()`)
2. The function validates its input and raises `ValidationError` if it is wrong
3. The function calls `init_db()`, then opens a connection with `_connect()`
4. The function executes parameterized SQL and commits
5. The function returns a dataclass
6. GUI/CLI catches `ValidationError` and displays the error to the user

---

## Key Conventions

### Domain-First Design

All business logic lives in domain modules. GUI and CLI are thin presentation layers that call them. Never put SQL or business rules in GUI/CLI code, and keep domain modules free of Tkinter, Flask and CLI code.

### Database Connection Pattern

Every function opens its connection in a `with` block:

```python
def some_operation(pupil_id):
    init_db()
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM pupils WHERE pupil_id = ?", (pupil_id,)
        ).fetchone()
```

For write operations, call `conn.commit()` inside the block. The `with` block commits or rolls back the transaction; it does not close the connection.

### Parameterized Queries

Always use `?` placeholders. Never use f-strings or `.format()` to build SQL:

```python
# Correct
conn.execute("SELECT * FROM pupils WHERE year_group = ?", (year_group,))

# NEVER do this
conn.execute(f"SELECT * FROM pupils WHERE year_group = '{year_group}'")
```

Where an identifier must be dynamic, validate it with `education_system.platform.kernel.database.sql_safety`.

### Exception Handling

There is no system-wide exception hierarchy. Raise `ValidationError` for invalid input, using the class in `domain/learners/pupils/pupils.py` or the module's own:

```python
from education_system.systems.primary.domain.learners.pupils.pupils import ValidationError

if not first_name:
    raise ValidationError("First name is required")
```

### Centralised Paths

Import paths from `education_system.paths`. Never hardcode file paths:

```python
from education_system.paths import PRIMARY_DATA_DIR, PRIMARY_PUPILS_DB, PRIMARY_BACKUP_DIR
```

### ID Formats

- Pupil IDs: `P` followed by digits (`ID_PREFIX` in `domain/learners/pupils/pupils.py`)
- Staff IDs: `T` followed by digits (`ID_PREFIX` in `domain/staff/staff.py`)

---

## Code Style

### Formatting and Linting

```bash
# Format code with Ruff
make format

# Lint with Ruff
python -m ruff check src/education_system/systems/primary/

# Auto-fix linting issues
python -m ruff check --fix src/education_system/systems/primary/
```

### Style Rules

- PEP 8 naming: `snake_case` for functions/variables, `PascalCase` for classes
- Line length: 100 characters
- Imports: standard library, then third-party, then local (Ruff enforces order)
- Docstrings: required on all modules, classes, and public functions
- Type hints: encouraged on public APIs

---

## Common Development Commands

```bash
# Run the full application (GUI)
python -m education_system

# Run CLI
python -m education_system --primary --cli

# Format + lint
make format && python -m ruff check src/education_system/systems/primary/

# Run tests with coverage
python -m pytest tests/unit/systems/primary/ \
    --cov=education_system.systems.primary --cov-report=term-missing -v

# Check database schema (read-only)
python -c "
import sqlite3
from education_system.paths import PRIMARY_PUPILS_DB
conn = sqlite3.connect(f'file:{PRIMARY_PUPILS_DB}?mode=ro', uri=True)
for (name,) in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\"):
    print(name)
conn.close()
"
```
