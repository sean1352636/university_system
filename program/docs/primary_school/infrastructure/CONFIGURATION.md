# Primary School Configuration Guide

> Last Updated: March 2026

## Overview

The Primary School Management System is configured through a combination of environment variables, Python configuration modules, and JSON config files. This guide covers all configuration surfaces and their default values.

---

## Environment Variables

The following environment variables control runtime behaviour. All are optional and fall back to sensible defaults.

| Variable | Default | Description |
|---|---|---|
| `PRIMARY_SCHOOL_API_HOST` | `127.0.0.1` | Host address for the API server to bind to. |
| `PRIMARY_SCHOOL_API_PORT` | `5002` | Port for the API server. Each system uses a different port (University: 5000, College: 5001, Primary: 5002). |
| `PRIMARY_SCHOOL_DEBUG` | `false` | Enable debug mode. Set to `true` for verbose logging and auto-reload in development. **Never enable in production.** |
| `PRIMARY_SCHOOL_JWT_SECRET` | Auto-generated | Secret key for signing JWT tokens. Must be set explicitly in production. |
| `PRIMARY_SCHOOL_SESSION_TIMEOUT` | `1800` | Session timeout in seconds (default: 30 minutes). |
| `PRIMARY_SCHOOL_DB_PATH` | `data/db_files/primary_school.db` | Override the default database file location. |
| `PRIMARY_SCHOOL_LOG_LEVEL` | `INFO` | Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL. |
| `PRIMARY_SCHOOL_LOG_DIR` | `logs/` | Directory for log file output. |

### Setting Environment Variables

```bash
# Linux/macOS — for the current session
export PRIMARY_SCHOOL_API_PORT=5002
export PRIMARY_SCHOOL_DEBUG=true

# Or inline when running
PRIMARY_SCHOOL_DEBUG=true python run.py
```

---

## Core Configuration Modules

### `core/defaults.py`

Centralised default values used throughout the Primary School system. This module defines constants that other modules import rather than hardcoding values.

Typical contents:

| Constant | Value | Purpose |
|---|---|---|
| `DEFAULT_YEAR_GROUPS` | `["Reception", "Year 1", ..., "Year 6"]` | Valid year groups for the primary school. |
| `KEY_STAGES` | `{"EYFS": ["Reception"], "KS1": ["Year 1", "Year 2"], "KS2": ["Year 3", ..., "Year 6"]}` | Key stage to year group mappings. |
| `ASSESSMENT_LEVELS` | `["Emerging", "Developing", "Expected", "Greater Depth"]` | Standard assessment levels. |
| `PUPIL_ID_PREFIX` | `"PRI"` | Prefix for auto-generated pupil IDs (e.g., PRI0001). |
| `STAFF_ID_PREFIX` | `"STF"` | Prefix for auto-generated staff IDs (e.g., STF0001). |
| `SESSION_TIMEOUT` | `1800` | Default session timeout in seconds. |
| `MAX_LOGIN_ATTEMPTS` | `5` | Failed login attempts before lockout. |
| `LOCKOUT_DURATION` | `900` | Lockout duration in seconds (15 minutes). |
| `API_PORT` | `5002` | Default API server port. |

### `core/paths.py`

Centralised path definitions. All file and directory references throughout the codebase should use paths from this module to ensure consistency and portability.

```python
# Typical path definitions
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_DIR = os.path.join(BASE_DIR, "data", "db_files")
DB_PATH = os.path.join(DB_DIR, "primary_school.db")

CONFIG_DIR = os.path.join(BASE_DIR, "data", "config")
LOG_DIR = os.path.join(BASE_DIR, "logs")

SHARED_DIR = os.path.join(os.path.dirname(BASE_DIR), "shared")
SHARED_AUTH_DB = os.path.join(SHARED_DIR, "data", "db_files", "auth.db")
```

**Rule:** Never hardcode file paths in service or GUI modules. Always import from `core.paths`.

### `core/logs.py`

Logging configuration for the Primary School system. Sets up Python's `logging` module with:

- **Console handler** for real-time output during development.
- **File handler** writing to the `logs/` directory with rotation.
- **Configurable log level** via `PRIMARY_SCHOOL_LOG_LEVEL` environment variable.
- **Structured format** including timestamp, module name, log level, and message.

```python
import logging

# Typical log format
FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
```

Usage in modules:

```python
from core.logs import get_logger

logger = get_logger(__name__)
logger.info("Pupil %s enrolled in class %s", pupil_id, class_id)
```

### `core/exceptions.py`

Custom exception classes for the Primary School system. Provides a hierarchy of domain-specific exceptions for clear error handling:

```python
class PrimarySchoolError(Exception):
    """Base exception for all Primary School errors."""

class ValidationError(PrimarySchoolError):
    """Raised when input validation fails."""

class NotFoundError(PrimarySchoolError):
    """Raised when a requested record does not exist."""

class AuthorisationError(PrimarySchoolError):
    """Raised when a user lacks permission for an operation."""

class DatabaseError(PrimarySchoolError):
    """Raised on database operation failures."""
```

---

## Data Directories

The Primary School system uses the following directory structure for data storage:

```
primary_school/
  data/
    db_files/
      primary_school.db        # Main domain database
    config/
      *.json                   # JSON configuration files
  logs/
    primary_school.log         # Application log (rotated)
```

### `data/db_files/`

Contains the SQLite database file. This directory is created automatically on first run if it does not exist. See [DATABASE.md](DATABASE.md) for full schema details.

### `data/config/`

Contains JSON configuration files for features that require runtime-configurable settings without code changes. Examples include email configuration, notification templates, and feature flags.

### `logs/`

Contains application log files. Log rotation is configured to prevent unbounded growth. Typical rotation policy:

- Maximum file size: 10 MB
- Backup count: 5 rotated files retained

---

## Infrastructure Modules

### `infrastructure/auth/`

Thin wrapper around `shared/auth/`. See [AUTHENTICATION.md](AUTHENTICATION.md) for details.

### `infrastructure/database/`

Database connection factory and schema initialization. Provides the `connect()` function used by all service layers.

### `infrastructure/validation/`

Input validation utilities. Common validators for:

- Pupil ID format (`PRI` prefix + 4 digits)
- Staff ID format (`STF` prefix + 4 digits)
- Date formats (ISO 8601)
- Year group values (Reception through Year 6)
- Email addresses
- Required field presence

---

## Port Allocation

Each Education System subsystem uses a dedicated API port to allow co-hosting:

| System | Default Port |
|---|---|
| University | 5000 |
| College | 5001 |
| Primary School | 5002 |
| Secondary School | 5003 |

Ensure no other services are using port 5002 (or your configured port) before starting the Primary School API server.
