# Secondary School Management System - Configuration

> Last Updated: March 2026

## Overview

The Secondary School Management System is configured through environment variables, core configuration modules, and data directory conventions. This document covers all configurable parameters and the modules that manage them.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SCHOOL_API_HOST` | `127.0.0.1` | API server bind address |
| `SCHOOL_API_PORT` | `5001` | API server port |
| `SESSION_TIMEOUT` | `1800` (30 min) | Session timeout in seconds |
| `MAX_LOGIN_ATTEMPTS` | `5` | Failed login attempts before account lockout |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `LOG_FILE` | `data/logs/secondary_school.log` | Log file path |
| `DB_PATH` | `data/db_files/secondary_school.db` | Domain database path |
| `AUTH_DB_PATH` | `shared/data/db_files/auth.db` | Shared auth database path |
| `BACKUP_DIR` | `data/backups/` | Database backup directory |
| `EXPORT_DIR` | `data/exports/` | Data export output directory |

Environment variables can be set in the shell before launching the application:

```bash
export SCHOOL_API_PORT=5002
export LOG_LEVEL=DEBUG
python -m secondary_school.main
```

## Core Modules

### `defaults.py`

Defines default values and system-wide constants used across the application.

**Location**: `secondary_school/core/defaults.py`

Key constants include:

| Constant | Value | Description |
|----------|-------|-------------|
| `SYSTEM_NAME` | `"Secondary School"` | Display name for the system |
| `SYSTEM_ID` | `"school"` | Identifier in `user_systems` table |
| `YEAR_GROUPS` | `[7, 8, 9, 10, 11]` | Valid year groups |
| `KEY_STAGES` | `{"KS3": [7,8,9], "KS4": [10,11]}` | Key stage to year group mapping |
| `GCSE_GRADES` | `[9,8,7,6,5,4,3,2,1]` | Valid GCSE grade values |
| `STUDENT_ID_PREFIX` | `"SEC"` | Student ID prefix (e.g., SEC0001) |
| `STAFF_ID_PREFIX` | `"STF"` | Staff ID prefix (e.g., STF0001) |
| `SESSION_TIMEOUT` | `1800` | Default session timeout (seconds) |
| `MAX_LOGIN_ATTEMPTS` | `5` | Default max failed logins |
| `API_PORT` | `5001` | Default API server port |

### `paths.py`

Centralises all file and directory paths used by the application.

**Location**: `secondary_school/core/paths.py`

Provides path resolution for:

- Database files (`data/db_files/`)
- Log files (`data/logs/`)
- Backup directory (`data/backups/`)
- Export directory (`data/exports/`)
- Configuration files
- Shared auth database path

All paths are resolved relative to the secondary school root directory, ensuring consistent behaviour regardless of the working directory.

```python
from core.paths import DB_PATH, LOG_DIR, BACKUP_DIR

# Paths are absolute, resolved at import time
# DB_PATH = /home/.../education_system/secondary_school/data/db_files/secondary_school.db
```

### `logs.py`

Configures the logging subsystem for the application.

**Location**: `secondary_school/core/logs.py`

Features:

- **File logging**: Rotated log files in `data/logs/` with configurable retention.
- **Console logging**: Coloured output for development use.
- **Log levels**: Configurable via `LOG_LEVEL` environment variable.
- **Structured fields**: Logs include timestamp, module name, level, and message.
- **Audit integration**: Security-relevant events are logged to both the log file and the `audit_log` database table.

```python
from core.logs import get_logger

logger = get_logger(__name__)
logger.info("Student record updated", extra={"student_id": "SEC0001"})
```

### `exceptions.py`

Defines custom exception classes for consistent error handling.

**Location**: `secondary_school/core/exceptions.py`

Common exception types:

| Exception | Usage |
|-----------|-------|
| `ValidationError` | Input validation failures |
| `AuthenticationError` | Login and session failures |
| `AuthorisationError` | Insufficient role/permissions |
| `NotFoundError` | Record not found |
| `DuplicateError` | Unique constraint violations |
| `DatabaseError` | Database connection or query failures |

## Data Directories

```
secondary_school/
  data/
    db_files/
      secondary_school.db          # Main domain database
    logs/
      secondary_school.log         # Application log (rotated)
    backups/
      secondary_school_YYYYMMDD.db # Database backups
    exports/
      export_YYYYMMDD_HHMMSS.csv   # Data export files
```

All data directories are created automatically on first run if they do not exist.

## Infrastructure Modules

### `infrastructure/auth/`

Thin wrapper around the shared auth module at `education_system/shared/auth/`. Re-exports authentication functions with the system identifier set to `"school"`.

### `infrastructure/database/`

Database connection management, schema initialisation, and migration utilities. Provides the `connect()` function used by all service modules.

### `infrastructure/validation/`

Input validation utilities for common data types:

- Student/staff ID format validation
- Year group range checks (7-11)
- GCSE grade validation (1-9)
- Email format validation
- Date and time format validation

## GUI Configuration

GUI-specific settings are stored in `data/gui_settings.json` (created on first launch):

| Setting | Default | Description |
|---------|---------|-------------|
| `theme` | `"default"` | GUI colour theme |
| `window_width` | `1200` | Main window width (pixels) |
| `window_height` | `800` | Main window height (pixels) |
| `sidebar_width` | `250` | Sidebar width (pixels) |
| `font_size` | `10` | Base font size |
| `language` | `"en"` | Interface language |

## Production Configuration Checklist

Before deploying to a production environment:

1. Change all default account passwords (see AUTHENTICATION.md).
2. Enable MFA for all staff accounts (see MFA_GUIDE.md).
3. Set `SCHOOL_API_HOST` to the appropriate network interface (not `0.0.0.0` unless behind a reverse proxy).
4. Configure `LOG_LEVEL=WARNING` to reduce log volume.
5. Set up automated database backups.
6. Ensure the database file and `data/` directory have restrictive file permissions.
7. Review GDPR compliance settings for student data retention.
