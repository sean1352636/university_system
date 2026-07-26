# Configuration Reference

This document covers all configurable values for the Sixth Form College Management System, including server settings, authentication defaults, database paths, and domain constants.

Source files:

- `core/defaults.py` -- core default values and environment variable overrides
- `core/paths.py` -- file and directory path definitions
- `api/config.py` -- Flask API configuration class
- `infrastructure/database/constants.py` -- database and domain constants

---

## API Server Settings

Defined in `core/defaults.py`. Each setting can be overridden via an environment variable.

| Setting | Environment Variable | Default | Description |
|---|---|---|---|
| `API_HOST` | `COLLEGE_API_HOST` | `127.0.0.1` | Host address the API server binds to |
| `API_PORT` | `COLLEGE_API_PORT` | `5000` | Port number for the API server |
| `API_DEBUG` | `COLLEGE_API_DEBUG` | `false` | Enable Flask debug mode (set to `"true"` to enable) |

The Flask `Config` class in `api/config.py` additionally sets:

| Setting | Value | Description |
|---|---|---|
| `SECRET_KEY` | Value of `COLLEGE_SECRET_KEY` env var, or `JWT_SECRET` | Flask secret key |
| `JSON_SORT_KEYS` | `False` | Preserve JSON key order in API responses |


---

## Authentication Defaults

### Session and Token Configuration

| Setting | Environment Variable | Default | Description |
|---|---|---|---|
| `SESSION_TIMEOUT_MINUTES` | `COLLEGE_SESSION_TIMEOUT` | `30` | GUI/CLI session token lifetime in minutes |
| `JWT_EXPIRY_HOURS` | `COLLEGE_JWT_EXPIRY` | `24` | API JWT token lifetime in hours |
| `JWT_SECRET` | `COLLEGE_JWT_SECRET` | `"change-me-in-production"` | Secret key for signing JWT tokens |

**Important:** The default `JWT_SECRET` value is not secure. It must be replaced with a strong random value in any non-development deployment by setting the `COLLEGE_JWT_SECRET` environment variable.

### Password Policy

| Setting | Value | Description |
|---|---|---|
| `MIN_PASSWORD_LENGTH` | `8` | Minimum number of characters |
| `MAX_LOGIN_ATTEMPTS` | `5` | Failed attempts before account lockout |
| Lockout duration | 15 minutes | Hardcoded in `core.py` |

Password strength rules (uppercase, lowercase, digit, special character) are enforced in `password_manager.py`. See the [Authentication documentation](AUTHENTICATION.md) for details.

### Secure Password Generation

`generate_secure_password(length=16)` in `core/defaults.py` produces a cryptographically random password containing uppercase letters, lowercase letters, digits, and special characters (`!@#$%^&*`). The function loops until all character categories are represented.


---

## Default User Accounts

These accounts are created by `seed_default_data()` on first database initialization. They exist for initial access and demonstration purposes. Passwords should be changed immediately in production.

| Username | Password | Role | Email | Notes |
|---|---|---|---|---|
| `admin` | `Admin@123` | `admin` | `admin@sixthform.ac.uk` | Full system access |
| `teacher` | `Teacher@123` | `teacher` | `teacher@sixthform.ac.uk` | Teaching staff access |
| `student` | `Student@123` | `student` | `student@sixthform.ac.uk` | Creates linked student record (SFC0001, "Demo Student", Year 12, Form 12A) |


---

## Student and Staff ID Formats

| Setting | Value | Description |
|---|---|---|
| `STUDENT_ID_PREFIX` | `"SFC"` | Prefix for student IDs |
| `STUDENT_ID_LENGTH` | `7` | Total length including prefix (e.g., `SFC0001`) |
| `STAFF_ID_PREFIX` | `"STF"` | Prefix for staff IDs |


---

## Database Paths

All paths are derived from the project root in `core/paths.py`.

| Constant | Path (relative to `college_system/`) | Description |
|---|---|---|
| `COLLEGE_SYSTEM_ROOT` | `.` | Root of the college system package |
| `PROJECT_ROOT` | `..` | Parent directory (education_system root) |
| `DATA_DIR` | `data/` | Top-level data directory |
| `DB_DIR` | `data/db_files/` | Database file directory |
| `DB_FILE` | `data/db_files/sixthform.db` | The SQLite database file |
| `LOCALES_DIR` | `data/locales/` | Internationalization translation files |
| `CONFIG_DIR` | `data/config/` | Runtime configuration files |
| `LOGS_DIR` | `logs/` | Application log files |

`ensure_directories()` creates `DB_DIR`, `LOCALES_DIR/en`, `CONFIG_DIR`, and `LOGS_DIR` if they do not exist.


---

## Database Connection Settings

Defined in `infrastructure/database/constants.py`.

| Setting | Value | Description |
|---|---|---|
| `CONNECTION_TIMEOUT` | `30` seconds | SQLite connection timeout |
| `BUSY_TIMEOUT` | `5000` ms | How long to wait when the database is locked |
| `POOL_MIN_SIZE` | `1` | Minimum pre-created connections in the pool |
| `POOL_MAX_SIZE` | `5` | Maximum connections the pool will create |

### SQLite PRAGMAs

Applied to every new connection:

| PRAGMA | Value | Effect |
|---|---|---|
| `journal_mode` | `WAL` | Write-Ahead Logging for concurrent access |
| `foreign_keys` | `ON` | Enforce foreign key constraints |
| `busy_timeout` | `5000` | Wait 5 seconds on lock contention |
| `cache_size` | `-8000` | 8 MB page cache |
| `synchronous` | `NORMAL` | Balanced durability/performance |


---

## Domain Constants

### Grade Scales

**A-Level grades** (`GRADE_SCALE`):

| Grade | Score Range | UCAS Tariff Points |
|---|---|---|
| A* | 90--100 | 56 |
| A | 80--89 | 48 |
| B | 70--79 | 40 |
| C | 60--69 | 32 |
| D | 50--59 | 24 |
| E | 40--49 | 16 |
| U | 0--39 | 0 |

**BTEC grades** (`BTEC_GRADE_SCALE`):

| Grade | Score Range | UCAS Tariff Points |
|---|---|---|
| D* | 90--100 | 56 |
| D | 75--89 | 48 |
| M | 55--74 | 32 |
| P | 40--54 | 16 |
| U | 0--39 | 0 |

### Other Domain Values

| Constant | Values |
|---|---|
| `QUALIFICATION_TYPES` | `A-Level`, `BTEC`, `T-Level`, `GCSE`, `Core Maths`, `EPQ` |
| `YEAR_GROUPS` | `12`, `13` |
| `TERMS` | `Autumn`, `Spring`, `Summer` |
| `ATTENDANCE_STATUSES` | `present`, `absent`, `late`, `excused` |


---

## Logging

The system uses Python's standard `logging` module. Logger names follow the module hierarchy (e.g., `education_system.college_system.infrastructure.database.db`).

Log output is directed to the `logs/` directory under the college system root. Database operations, authentication events (login success/failure, lockouts, MFA verification), and session lifecycle events are all logged at appropriate levels (DEBUG for routine operations, INFO for significant events, WARNING for failed authentication attempts, ERROR for exceptions).


---

## Internationalization (i18n)

Translation files are stored under `data/locales/` with language-code subdirectories (e.g., `data/locales/en/`). The `ensure_directories()` function creates the `en` locale directory by default.

Translation files are JSON format, organized by feature area.


---

## Environment-Specific Settings

For production deployments, the following environment variables should be set:

| Variable | Purpose | Production Recommendation |
|---|---|---|
| `COLLEGE_JWT_SECRET` | JWT signing secret | Generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `COLLEGE_SECRET_KEY` | Flask secret key | Generate a separate random value |
| `COLLEGE_API_HOST` | Bind address | `0.0.0.0` for network access, or behind a reverse proxy |
| `COLLEGE_API_PORT` | Port number | As needed |
| `COLLEGE_API_DEBUG` | Debug mode | Must be `"false"` in production |
| `COLLEGE_SESSION_TIMEOUT` | Session duration | Adjust based on security requirements |
| `COLLEGE_JWT_EXPIRY` | JWT lifetime | Reduce for higher-security environments |

Default credentials (`admin`/`Admin@123`, `teacher`/`Teacher@123`, `student`/`Student@123`) must be changed on first login in any non-development environment.
