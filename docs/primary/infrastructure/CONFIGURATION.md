# Primary School Configuration Guide

> Last Updated: October 2026

## Overview

The Primary School Management System is configured through a combination of environment variables, shared Python modules, and settings stored in the database. This guide covers all configuration surfaces and their default values.

---

## Environment Variables

The following environment variables control runtime behaviour. There are no primary-only variables other than the data directory and the fallback API token; the rest are shared by every system.

| Variable | Default | Description |
|---|---|---|
| `EDU_PRIMARY_DATA_DIR` | `var/data/primary` | Override the directory that holds `primary.db`. |
| `API_HOST` | `0.0.0.0` | Host address for the unified API server to bind to. |
| `API_PORT` | `5000` | Port for the unified API server. All systems share it. |
| `API_DEBUG` | `false` | Enable the Flask debugger. Refused when `APP_ENV` is production. **Never enable in production.** |
| `APP_ENV` | Production if unset | Deployment environment. The launcher sets a development default for a source checkout. |
| `JWT_SECRET_KEY` | None | Secret key for signing JWT tokens. Must be set explicitly in production. |
| `EDU_SESSION_TIMEOUT` | `30` | Session lifetime in minutes. |
| `EDU_IDLE_TIMEOUT_MINUTES` | `30` | Minutes of inactivity before the GUI and CLI log out. `0` turns this off. |
| `EDU_MAX_SESSIONS` | `5` | Concurrent sessions per user. |
| `EDU_DEV_SEED` | Unset | Set to `true` to seed the demo accounts. Never enable in production. |
| `EDU_VERBOSE` | Unset | Set to `1` to show INFO on the console, the same as `--verbose`. |
| `LOG_LEVEL` | `INFO` | API server logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL. |
| `LOG_FORMAT` | `text` | API server log format. |
| `PRIMARY_API_TOKEN` | Unset | Fallback service token, used by routes only if the platform JWT check cannot be imported. |

### Setting Environment Variables

```bash
# Linux/macOS — for the current session
export API_PORT=5002
export EDU_VERBOSE=1

# Or inline when running
EDU_VERBOSE=1 python -m education_system
```

---

## Shared Configuration Modules

The Primary School has no `core/` package. Values it used to define there now live in the owning module.

### `src/education_system/platform/identity/auth/defaults.py`

Authentication defaults, shared by every system:

| Constant | Value | Purpose |
|---|---|---|
| `SESSION_TIMEOUT_MINUTES` | `30` | Session lifetime in minutes. |
| `MAX_SESSIONS_PER_USER` | `5` | Concurrent sessions per user. |
| `MIN_PASSWORD_LENGTH` | `12` | Minimum password length. |
| `MAX_LOGIN_ATTEMPTS` | `3` | Failed login attempts before lockout. |
| `LOCKOUT_DURATION_MINUTES` | `15` | Lockout duration in minutes. |

### Domain constants

These sit beside the code that uses them:

| Constant | Value | Module |
|---|---|---|
| `YEAR_GROUPS` | `("R", "1", "2", "3", "4", "5", "6")` | `domain/learners/pupils/pupils.py` |
| `ID_PREFIX` | `"P"` | `domain/learners/pupils/pupils.py` (pupil IDs) |
| `ID_PREFIX` | `"T"` | `domain/staff/staff.py` (staff IDs) |

### `src/education_system/paths.py`

Centralised path definitions for every system. All file and directory references should use paths from this module to ensure consistency and portability. Every constant carries the owning system's prefix.

```python
from education_system.paths import (
    PRIMARY_DATA_DIR,      # var/data/primary, or EDU_PRIMARY_DATA_DIR
    PRIMARY_PUPILS_DB,     # var/data/primary/primary.db
    PRIMARY_BACKUP_DIR,    # var/backups/primary
    PLATFORM_AUTH_DB_FILE, # var/data/platform/db_files/auth.db
)
```

Each module also has a named alias such as `PRIMARY_STAFF_DB`, and all of them point at the same `primary.db`. Directories are never created on import; `ensure_primary_directories()` creates them.

**Rule:** Never hardcode file paths in domain or GUI modules. Always import from `education_system.paths`.

### Logging

The launcher sets up Python's `logging` module in `src/education_system/launcher/main.py`:

- **Console handler** only. The Primary School does not write a log file of its own.
- **Console level** of WARNING, or INFO with `--verbose` or `EDU_VERBOSE=1`. Use `--quiet` to hold the root logger at WARNING.
- **Format** of timestamp and message.

Usage in modules:

```python
import logging

logger = logging.getLogger(__name__)
logger.info("Pupil %s enrolled in class %s", pupil_id, class_id)
```

### Exceptions

There is no system-wide exception hierarchy for the Primary School. Domain modules raise `ValidationError`, either their own or the one in `domain/learners/pupils/pupils.py`. The hierarchy in `src/education_system/platform/kernel/exceptions.py` belongs to the University.

### Settings

Runtime-configurable settings are kept in the `settings_kv` table and managed from **System → Settings**. They are defined in `src/education_system/systems/primary/interfaces/settings.py`.

---

## Data Directories

The Primary School system uses the following directories for runtime data:

```
var/
  data/
    primary/
      primary.db               # Main domain database
    platform/
      db_files/
        auth.db                # Shared authentication database
  backups/
    primary/                   # Backups
```

### `var/data/primary/`

Contains the SQLite database file. See [DATABASE.md](DATABASE.md) for full schema details.

---

## Infrastructure Modules

`src/education_system/systems/primary/infrastructure/` is currently only an `__init__.py`. Its former roles are handled elsewhere:

### Authentication

`src/education_system/platform/identity/auth/`. See [AUTHENTICATION.md](AUTHENTICATION.md) for details.

### Database

Each domain module creates its own tables from its `init_db()`. Most connect through `_connect()` in `domain/learners/pupils/pupils.py`.

### Validation

Domain modules validate their own input. Shared validators are in `src/education_system/platform/kernel/validation/validators.py`, for:

- Date formats (ISO 8601)
- Times and time ranges
- Email addresses
- Required field presence
- Positive integers

---

## Port Allocation

The systems do not have ports of their own. One unified API server hosts all seven on `API_PORT` (default 5000), each under its own URL prefix:

| System | Prefix |
|---|---|
| University | `/api/v1/university` |
| Sixth Form College | `/api/v1/sixthform` |
| Secondary School | `/api/v1/school` |
| Primary School | `/api/v1/primary` |
| Nursery | `/api/v1/nursery` |
| FE College | `/api/v1/fecollege` |
| Apprenticeships | `/api/v1/apprentice` |

Ensure no other services are using port 5000 (or your configured port) before starting the API server.
