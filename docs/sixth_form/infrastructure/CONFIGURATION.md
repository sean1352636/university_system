# Configuration Reference

This document covers all configurable values for the Sixth Form College Management System, including server settings, authentication defaults, database paths, and domain constants.

Source files:

- `src/education_system/paths.py` -- file and directory path definitions
- `src/education_system/platform/identity/auth/defaults.py` -- authentication defaults
- `src/education_system/platform/delivery/api/unified_server.py` -- API server environment variables
- `src/education_system/platform/delivery/api/security/authentication.py` -- JWT lifetime

---

## API Server Settings

All seven systems are served by one unified server, launched with `python -m education_system --college --api`, which mounts the sixth form at `/api/v1/sixthform`. A smaller standalone sixth form app also exists, in `src/education_system/api/sixth_form/server.py`, with staff endpoints protected by `EDU_SIXTHFORM_API_KEY`.

| Environment Variable | Default | Description |
|---|---|---|
| `API_PORT` | `5000` | Port number for the API server |
| `API_SECRET_KEY` | None | Flask secret key |
| `API_CORS_ORIGINS` | None | Comma-separated allowed origins. Required in production; a wildcard is refused |
| `API_MAX_CONTENT_LENGTH` | 16 MB | Largest accepted request body, in bytes |
| `APP_ENV` | `production` (`development` when started by the launcher) | Unset counts as production, and fail-closed secret checks apply |


---

## Authentication Defaults

Authentication is shared across the seven systems, so these values are not sixth form settings.

### Session and Token Configuration

| Setting | Environment Variable | Default | Description |
|---|---|---|---|
| `SESSION_TIMEOUT_MINUTES` | `EDU_SESSION_TIMEOUT` | `30` | GUI/CLI session token lifetime in minutes |
| `MAX_SESSIONS_PER_USER` | `EDU_MAX_SESSIONS` | `5` | Concurrent sessions per user |
| `_JWT_EXPIRY_HOURS` | `JWT_EXPIRY_HOURS` | `24` | API JWT access token lifetime in hours |
| `_JWT_REFRESH_DAYS` | `JWT_REFRESH_DAYS` | `7` | API refresh token lifetime in days |
| JWT secret | `JWT_SECRET_KEY` | None | Secret key for signing JWT tokens |

**Important:** Production deployments must set `JWT_SECRET_KEY`. Outside development and test, the server refuses to fall back to a value stored in the auth database.

The separate idle logout in the sixth form GUI and CLI is set by `EDU_SIXTHFORM_IDLE_TIMEOUT_MINUTES` (default `30`). See [SESSION_TIMEOUT.md](../security/SESSION_TIMEOUT.md).

### Password Policy

| Setting | Value | Description |
|---|---|---|
| `MIN_PASSWORD_LENGTH` | `12` | Minimum number of characters |
| `MAX_LOGIN_ATTEMPTS` | `3` | Failed attempts before account lockout |
| `LOCKOUT_DURATION_MINUTES` | `15` | Lockout duration |

All three are defined in `platform/identity/auth/defaults.py`. Password strength rules (uppercase, lowercase, digit, special character) are enforced in `platform/identity/auth/password_manager.py`. See the [Authentication documentation](AUTHENTICATION.md) for details.

### Secure Password Generation

`generate_secure_password(length=16)` in `src/education_system/platform/kernel/core/defaults.py` produces a cryptographically random password containing uppercase letters, lowercase letters, digits, and special characters (`!@#$%^&*`). The function loops until all character categories are represented.


---

## Default User Accounts

These accounts are defined in `_DEFAULT_ACCOUNTS` in `platform/identity/auth/schema.py` and are created in the central `auth.db` **only** when `EDU_DEV_SEED=true`. They exist for development and demonstration purposes.

| Username | Password | Role | Notes |
|---|---|---|---|
| `superadmin` | `SuperAdmin@123` | Admin | Spans all seven systems |
| `admin1` | `admin1234` | Admin | Sixth form admin |
| `staff1` | `staff1234` | Teacher | Teaching staff access |
| `student1` | `student1234` | Student | Student access |
| `parent1` | `parent1234` | Parent | Parent access |

To bootstrap a production deployment, leave `EDU_DEV_SEED` unset and set `EDU_INITIAL_ADMIN_USER` and `EDU_INITIAL_ADMIN_PASSWORD` (at least 12 characters). See [DEFAULT_ACCOUNTS.md](../../reference/DEFAULT_ACCOUNTS.md) for all systems.


---

## Student and Staff ID Formats

| Setting | Value | Description |
|---|---|---|
| `ID_PREFIX` | `"C"` | Prefix for student IDs, in `domain/learners/students/students.py` |
| `ID_DIGITS` | `7` | Digits after the prefix (e.g., `C1470977`) |
| `STAFF_ID_PREFIX` | `"STF"` | Prefix for staff IDs, in `platform/kernel/core/defaults.py` |


---

## Database Paths

All paths are defined in `src/education_system/paths.py`. Runtime state lives under `var/` at the repository root.

| Constant | Path | Description |
|---|---|---|
| `SIXTH_FORM_PACKAGE_ROOT` | `src/education_system/systems/sixth_form/` | Root of the sixth form package |
| `SIXTH_FORM_DATA_DIR` | `var/data/sixth_form/` | Data directory; override with `EDU_SIXTHFORM_DATA_DIR` |
| `SIXTH_FORM_STUDENTS_DB` | `var/data/sixth_form/sixthform.db` | The SQLite database file. Per-module constants such as `SIXTH_FORM_ENRICHMENTS_DB` alias it |
| `SIXTH_FORM_COURSEWORK_FILES_DIR` | `var/data/sixth_form/coursework_files/` | Submitted coursework files |
| `SIXTH_FORM_EMAIL_TEMPLATES_DIR` | `src/education_system/systems/sixth_form/assets/templates/email/` | Email templates, which ship with the code |
| `SIXTH_FORM_BACKUP_DIR` | `var/backups/sixth_form/` | Backups |
| `PLATFORM_AUTH_DB_FILE` | `var/data/platform/db_files/auth.db` | Central authentication database |

`ensure_sixth_form_directories()` creates `SIXTH_FORM_DATA_DIR` and `SIXTH_FORM_COURSEWORK_FILES_DIR` if they do not exist. Nothing is created on import.


---

## Database Connection Settings

Each domain module opens its own connection with `sqlite3.connect()`, directly or through `infrastructure/database.py`, using SQLite's default timeout. It sets `row_factory = sqlite3.Row` and:

| PRAGMA | Value | Effect |
|---|---|---|
| `foreign_keys` | `ON` | Enforce foreign key constraints |

There is no sixth form connection pool. See [DATABASE.md](DATABASE.md).


---

## Domain Constants

### Grade Scales

Grade scales are defined in `domain/academics/qualifications/grade_scales.py`, listed best first, with one scale per qualification type. Each scale's `points` value is an ordinal for comparing grades, and is not a DfE or UCAS tariff.

| Scale | Grades |
|---|---|
| A Level | A*, A, B, C, D, E, U |
| AS Level | A, B, C, D, E, U |
| GCSE | 9, 8, 7, 6, 5, 4, 3, 2, 1, U |
| BTEC single | D*, D, M, P, U |
| BTEC double | D\*D\*, D\*D, DD, DM, MM, MP, PP, U |
| T Level overall | Distinction*, Distinction, Merit, Pass, Partial achievement, Unclassified |
| T Level core | A*, A, B, C, D, E, U |
| T Level specialism | Distinction, Merit, Pass, Unclassified |

`validate_grade()` in the same module checks a grade against the qualification type of the learning aim. Use it rather than hardcoding a list.

### Other Domain Values

There is no central constants module. Each domain module declares its own values, for example `YEAR_GROUPS` and `STATUSES` in `domain/admissions/enrolments/enrolments.py`, and `QUALIFICATION_TYPES` in `grade_scales.py`.


---

## Logging

The system uses Python's standard `logging` module. Logger names follow the module hierarchy (e.g., `education_system.systems.sixth_form.domain.learners.students.students`).

The launcher configures console logging at WARNING and above. Pass `-v`/`--verbose` or set `EDU_VERBOSE=1` to see INFO on the console, or `-q`/`--quiet` to keep it to warnings. The API server also reads `LOG_LEVEL` and `LOG_FORMAT`.

No per-system log file is written. For durable records, `infrastructure/log_store.py` provides a handler that writes to the `system_logs` table in `sixthform.db`, once `log_store.install()` has been called. Class group logging currently installs it.


---

## Internationalization (i18n)

Translation is handled by the shared engine in `src/education_system/platform/features/i18n/`, which the launcher initialises at startup. It loads JSON files from `locales/` under `var/data/platform/`, with an English fallback. The sixth form has no locale directory of its own.


---

## Environment-Specific Settings

For production deployments, the following environment variables should be set:

| Variable | Purpose | Production Recommendation |
|---|---|---|
| `APP_ENV` | Environment name | `production` |
| `JWT_SECRET_KEY` | JWT signing secret | Generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `API_SECRET_KEY` | Flask secret key | Generate a separate random value |
| `API_CORS_ORIGINS` | Allowed origins | The specific domains that call the API |
| `API_PORT` | Port number | As needed |
| `EDU_SESSION_TIMEOUT` | Session duration | Adjust based on security requirements |
| `JWT_EXPIRY_HOURS` | JWT lifetime | Reduce for higher-security environments |
| `EDU_INITIAL_ADMIN_USER`, `EDU_INITIAL_ADMIN_PASSWORD` | First admin | Set once on a fresh `auth.db`, with a password of 12 or more characters |

Never set `EDU_DEV_SEED` on a production deployment. If demo accounts exist, change their passwords before use.
