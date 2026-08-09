# Shared Infrastructure

This document describes the shared modules in `education_system/shared/` that all four subsystems (university, college, secondary, primary) use.

---

## Overview

The shared directory provides centralised infrastructure so that common code is written once and consumed by all systems via thin wrappers. Each subsystem's wrapper can add system-specific behaviour (e.g. domain-specific exception types, locale directories) while delegating the core logic to shared.

```
shared/
    auth/           # Unified authentication (UserAuth, sessions, MFA, roles)
    base/           # Base classes for services and GUI frames
    cli/            # CLI login prompt and menu helpers
    core/           # Paths factory, logging setup, defaults
    database/       # DB constants, connection utilities, SQL safety
    gui/            # Universal login window, MFA dialogs
    i18n/           # Multi-language translation engine
    testing/        # Pytest fixture factories
    validation/     # Common input validators
```

---

## Authentication (`shared/auth/`)

Single auth system for all 4 subsystems. One database (`shared/data/db_files/auth.db`).

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

**Usage in subsystems:**
```python
# Each system's infrastructure/auth/core.py is a 1-line re-export:
from education_system.shared.auth.core import UserAuth
```

---

## Database Constants (`shared/database/constants.py`)

Common SQLite configuration shared by all systems:

- `PRAGMAS` -- WAL mode, foreign keys, cache size, synchronous mode
- `CONNECTION_TIMEOUT`, `BUSY_TIMEOUT`
- `POOL_MIN_SIZE`, `POOL_MAX_SIZE`
- `TERMS` -- UK academic calendar terms

Each system imports these and adds domain-specific constants (grade scales, year groups, etc.).

---

## SQL Safety (`shared/database/sql_safety.py`)

Safe SQL construction utilities to prevent injection:

- `validate_identifier()` -- whitelist-based column/table name validation
- `escape_like()` -- escape LIKE pattern wildcards
- `build_where_clause()` -- parameterised WHERE construction
- `build_set_clause()` -- parameterised SET construction

---

## Paths Factory (`shared/core/paths.py`)

`SystemPaths` dataclass and `get_system_paths()` factory:

```python
from education_system.shared.core.paths import get_system_paths

_paths = get_system_paths(__file__, "sixthform.db")
# _paths.system_root, _paths.db_file, _paths.logs_dir, etc.
```

Each system calls this from its `core/paths.py` and re-exports the standard path constants for backward compatibility.

---

## Logging (`shared/core/logging.py`)

`setup_logging()` function providing consistent file + console handlers:

```python
from education_system.shared.core.logging import setup_logging

setup_logging(
    logger_name="education_system.college_system",
    log_dir=LOGS_DIR,
    log_filename="app.log",
)
```

Each system's `core/logs.py` is a thin wrapper that calls this with system-specific parameters.

---

## i18n Engine (`shared/i18n/`)

Multi-language translation engine supporting 13 languages with JSON-based locale files.

- Deep-merges all `*.json` files under each language directory
- Dot-notation key lookups with English fallback
- Persistent language preferences
- `add_locale_dir()` to register system-specific locale directories

Each system calls `init_i18n()` then `add_locale_dir()` to load its own translations alongside shared ones.

---

## Validators (`shared/validation/validators.py`)

Common input validators used across all systems:

- `validate_email()`, `validate_non_empty()`, `validate_date()`
- `validate_grade_score()`, `validate_positive_int()`
- `validate_day_of_week()`, `validate_time()`, `validate_time_range()`

Each system wraps these to re-raise as its own `ValidationError` subclass, then adds domain-specific validators (e.g. `validate_student_id`, `validate_gcse_grade`).

---

## GUI (`shared/gui/`)

| File | Purpose |
|------|---------|
| `login_gui.py` | `UniversalLoginWindow` -- single login for all systems with system picker |
| `mfa_gui.py` | `MFAVerifyDialog` and `MFASettingsFrame` -- shared MFA UI |

---

## CLI Helpers (`shared/cli/`)

| File | Purpose |
|------|---------|
| `login_cli.py` | `cli_login_prompt()` -- universal CLI login |
| `cli_helpers.py` | `print_header()`, `print_menu()`, `get_choice()`, `run_submenu()` |

---

## Test Fixtures (`shared/testing/conftest_helpers.py`)

Factory functions for building pytest fixtures without duplicating boilerplate:

```python
from education_system.shared.testing.conftest_helpers import (
    make_template_db_fixture,
    make_db_path_fixture,
    make_auth_fixture,
)

_template_db = make_template_db_fixture(init_db, seed_default_data)
db_path = make_db_path_fixture(set_db_path, "test_sixthform.db")
auth = make_auth_fixture(UserAuth)
```

---

## Base Classes (`shared/base/`)

| File | Purpose |
|------|---------|
| `service.py` | `BaseService` -- standard `_conn()` context manager, CRUD patterns, pagination |
| `gui.py` | `BaseModuleGUI` -- standard tkinter Frame layout with notebook tabs and search |

---

## Adding to Shared

Before adding something to shared, ask:

1. **Is it used by 2+ systems?** If only one system needs it, keep it there.
2. **Is it infrastructure or domain logic?** Domain logic stays in the subsystem.
3. **Will it pull in system-specific dependencies?** If yes, it doesn't belong in shared.

The pattern: shared provides the engine/base, each system provides a thin wrapper that configures it for that system's needs.
