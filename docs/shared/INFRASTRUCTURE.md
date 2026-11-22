# Shared Infrastructure

This document describes the shared modules in `education_system/platform/` that all seven systems (nursery, primary, secondary, sixth form, FE college, apprenticeships, university) use.

---

## Overview

The platform package provides centralised infrastructure so that common code is written once and consumed by all systems, directly or through a thin wrapper. A wrapper can add system-specific behaviour (e.g. domain-specific exception types, locale directories) while delegating the core logic to the platform.

```
platform/
    identity/auth/      # Unified authentication (UserAuth, sessions, MFA, roles)
    kernel/base/        # Base classes for services and GUI frames
    kernel/core/        # Logging setup, defaults, system keys, tenancy
    kernel/database/    # DB constants, connection utilities, SQL safety
    kernel/validation/  # Common input validators
    delivery/cli/       # CLI login prompt and menu helpers
    delivery/gui/       # Universal login window, MFA dialogs
    features/i18n/      # Multi-language translation engine
    testing/            # Pytest fixture factories
```

---

## Authentication (`src/education_system/platform/identity/auth/`)

Single auth system for all 7 systems. One database (`var/data/platform/db_files/auth.db`).

| File | Purpose |
|------|---------|
| `core.py` | `UserAuth` class -- login, logout, MFA, session management |
| `schema.py` | Auth database tables and default account seeding |
| `password_manager.py` | bcrypt hashing, legacy PBKDF2 support with auto-migration |
| `session_manager.py` | Token-based sessions with 30min expiry |
| `role_manager.py` | Role hierarchy and per-system role mapping |
| `mfa_service.py` | TOTP setup/verify, recovery codes |
| `exceptions.py` | `AuthError`, `ValidationError`, `MFAError` |
| `db.py` | Auth DB connection with retry logic and file permissions |
| `defaults.py` | Configurable timeouts, lockout settings |

**Usage in systems:**
```python
from education_system.platform.identity.auth.core import UserAuth
```

---

## Database Constants (`src/education_system/platform/kernel/database/constants.py`)

Common SQLite configuration shared by all systems:

- `PRAGMAS` -- WAL mode, foreign keys, cache size, synchronous mode
- `CONNECTION_TIMEOUT`, `BUSY_TIMEOUT`
- `POOL_MIN_SIZE`, `POOL_MAX_SIZE`
- `TERMS` -- UK academic calendar terms

Each system imports these and adds domain-specific constants (grade scales, year groups, etc.).

---

## SQL Safety (`src/education_system/platform/kernel/database/sql_safety.py`)

Safe SQL construction utilities to prevent injection:

- `validate_identifier()` -- whitelist-based column/table name validation
- `escape_like()` -- escape LIKE pattern wildcards
- `build_where_clause()` -- parameterised WHERE construction
- `build_set_clause()` -- parameterised SET construction

---

## Paths (`src/education_system/paths.py`)

The single module defining every filesystem path. Each constant carries the prefix of the system that owns it:

```python
from education_system.paths import SIXTH_FORM_STUDENTS_DB, ensure_sixth_form_directories

ensure_sixth_form_directories()
# SIXTH_FORM_STUDENTS_DB is var/data/sixth_form/sixthform.db
```

Directories are never created on import. `SYSTEM_DB_PATHS` maps each system key to its database.

---

## Logging (`src/education_system/platform/kernel/core/logging.py`)

`setup_logging()` function providing consistent file + console handlers:

```python
from education_system.paths import UNIVERSITY_LOG_DIR
from education_system.platform.kernel.core.logging import setup_logging

setup_logging(
    logger_name="education_system.systems.university",
    log_dir=UNIVERSITY_LOG_DIR,
    log_filename="app.log",
)
```

Callers pass their own logger name and a log directory from `education_system.paths`.

---

## i18n Engine (`src/education_system/platform/features/i18n/`)

Multi-language translation engine supporting 13 languages with JSON-based locale files.

- Deep-merges all `*.json` files under each language directory
- Dot-notation key lookups with English fallback
- Persistent language preferences
- `add_locale_dir()` to register system-specific locale directories

Each system calls `init_i18n()` then `add_locale_dir()` to load its own translations alongside shared ones.

---

## Validators (`src/education_system/platform/kernel/validation/validators.py`)

Common input validators used across all systems:

- `validate_email()`, `validate_non_empty()`, `validate_date()`
- `validate_grade_score()`, `validate_positive_int()`
- `validate_day_of_week()`, `validate_time()`, `validate_time_range()`

Systems can wrap these to re-raise as their own `ValidationError` subclass and add domain-specific validators.

---

## GUI (`src/education_system/platform/delivery/gui/`)

| File | Purpose |
|------|---------|
| `login_gui.py` | `UniversalLoginWindow` -- single login for all systems with system picker |
| `mfa_setup_gui.py` | `MFASetupWizard` and `MFAVerificationDialog` -- shared MFA UI |

---

## CLI Helpers (`src/education_system/platform/delivery/cli/`)

| File | Purpose |
|------|---------|
| `login_cli.py` | `cli_login_prompt()` -- universal CLI login |
| `cli_helpers.py` | `print_header()`, `print_menu()`, `get_choice()`, `run_submenu()` |

---

## Test Fixtures (`src/education_system/platform/testing/conftest_helpers.py`)

Factory functions for building pytest fixtures without duplicating boilerplate:

```python
from education_system.platform.testing.conftest_helpers import (
    make_template_db_fixture,
    make_db_path_fixture,
    make_auth_fixture,
)

_template_db = make_template_db_fixture(init_db, seed_default_data)
db_path = make_db_path_fixture(set_db_path, "test_sixthform.db")
auth = make_auth_fixture(UserAuth)
```

---

## Base Classes (`src/education_system/platform/kernel/base/`)

| File | Purpose |
|------|---------|
| `service.py` | `BaseService` -- standard `_conn()` context manager, CRUD patterns, pagination |
| `gui.py` | `BaseModuleGUI` -- standard tkinter Frame layout with notebook tabs and search |

---

## Adding to the Platform

Before adding something to the platform, ask:

1. **Is it used by 2+ systems?** If only one system needs it, keep it there.
2. **Is it infrastructure or domain logic?** Domain logic stays in the system.
3. **Will it pull in system-specific dependencies?** If yes, it doesn't belong in the platform.

The pattern: the platform provides the engine/base, and a system adds a thin wrapper where it needs its own configuration.
