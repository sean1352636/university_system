# Administrator Operations Manual

A consolidated guide for system administrators running the Education System in production.

## Table of Contents

- [System Overview](#system-overview)
- [First-Time Setup](#first-time-setup)
- [User Management](#user-management)
- [Security Configuration](#security-configuration)
- [Database Administration](#database-administration)
- [Backup & Recovery](#backup--recovery)
- [Monitoring & Health Checks](#monitoring--health-checks)
- [Email Configuration](#email-configuration)
- [API Server Management](#api-server-management)
- [Routine Maintenance](#routine-maintenance)
- [Troubleshooting](#troubleshooting)

## System Overview

The Education System runs seven systems from a single codebase:

| System | Key | Database | Users |
|--------|-----|----------|-------|
| University | `university` | `student_records.db` | Admin, Staff, Instructor, Student, Parent |
| Sixth Form College | `sixth_form` | `sixthform.db` | Admin, Teacher, Student, Parent |
| Secondary School | `secondary` | `secondary.db` | Admin, Teacher, Student, Parent |
| Primary School | `primary` | `primary.db` | Admin, Teacher, Pupil, Parent |
| Nursery / Early Years | `nursery` | `nursery.db` | Admin |
| FE College | `fe_college` | `fe_college.db` | Admin, Teacher, Student |
| Apprenticeships | `apprenticeships` | `apprenticeships.db` | Admin, Staff, Apprentice, Employer, End-point assessor |

**Shared infrastructure:**
- Authentication: `var/data/platform/db_files/auth.db` (all systems)
- Webhooks: `var/data/platform/db_files/webhooks.db`
- Offline sync: `var/data/platform/db_files/offline_sync.db`

## First-Time Setup

### 1. Install Dependencies

```bash
make install
```

### 2. Initialise Databases

Databases are auto-created on first run. A fresh `auth.db` starts empty: set `EDU_INITIAL_ADMIN_USER` and `EDU_INITIAL_ADMIN_PASSWORD` to create one admin. The demo accounts are seeded only with `EDU_DEV_SEED=true`, which is for development only.

```bash
python -m education_system --gui    # GUI mode
python -m education_system --cli    # CLI mode
```

### 3. Change Default Passwords

If the demo accounts were seeded, change their weak passwords immediately:

| Username | Default Password | System |
|----------|-----------------|--------|
| `superadmin` | `SuperAdmin@123` | All |
| `admin` | `admin123` | University |
| `admin1` | `admin1234` | Sixth Form |
| `admin2` | `admin1234` | Secondary |
| `admin3` | `admin1234` | Primary |
| `admin4` | `admin1234` | Nursery |
| `admin5` | `admin1234` | Apprenticeships |
| `admin6` | `admin1234` | FE College |

**GUI:** Login > My Account > Change Password
**CLI:** Login > Authentication > My Account > Change Password

### 4. Configure Environment

Copy `.env.example` to `.env` and set production values:

```bash
APP_ENV=production
DEBUG=False
JWT_SECRET_KEY=<random-64-char-hex>
EDU_DEV_SEED=false
EDU_PRODUCTION=true
```

## User Management

### Creating Users

**GUI:** Admin Panel > User Management > Create New User
**CLI:** Authentication > User Management > Create New User
**API:** `POST /api/v1/auth/register` (admin token required)

### Roles and Permissions

Each system defines its own roles. Users are assigned to systems via the `user_systems` table in `auth.db`.

A user can have access to multiple systems with different roles:
```
superadmin: university(admin), sixth_form(admin), secondary(admin), primary(admin), nursery(admin), fe_college(admin), apprenticeships(admin)
```

### Forced Password Reset

Admins can toggle forced password reset for all users:

**GUI:** System Administration > Configuration > Security Settings > toggle "Force password reset for expired passwords"

**CLI:** Authentication > User Management > Toggle Forced Password Reset

When enabled, users whose `password_changed_at` is older than 90 days (or NULL) must change their password on login. When disabled, the check is skipped.

The setting is stored in `auth_settings` table in `auth.db`.

### Account Lockout

After 3 failed login attempts, accounts are locked for 15 minutes. Admins can unlock accounts:

**CLI:** Authentication > User Management > Edit User (reset failed attempts)

### MFA (Multi-Factor Authentication)

MFA is available for all users:
- **TOTP** — Time-based one-time passwords (Google Authenticator, etc.)
- **Email OTP** — One-time codes sent via email
- **Recovery codes** — Backup codes for emergency access

**GUI:** Settings > MFA Settings
**CLI:** Authentication > My Account > MFA Settings

## Security Configuration

### Security Settings (GUI)

Admin Panel > System Administration > Configuration > Security Settings

Configurable items:
- Forced password reset toggle (on/off)
- Password policy display (min 12 chars, complexity requirements)
- MFA availability
- Session timeout settings

### Security Questions

Users can set up 3 security questions for password recovery:

**GUI:** Settings > Security Questions
**CLI:** My Account > Security Questions

### Audit Logging

All user actions are logged to the activity log:

**GUI:** System Administration > Activity Logger
**CLI:** Administrative Tools > Activity Logs

## Database Administration

### Database Locations

```
var/data/platform/db_files/auth.db          # Shared authentication
var/data/university/db_files/student_records.db  # University data
var/data/sixth_form/sixthform.db            # Sixth Form data
var/data/secondary/secondary.db             # Secondary data
var/data/primary/primary.db                 # Primary data
var/data/nursery/nursery.db                 # Nursery data
var/data/fe_college/fe_college.db           # FE College data
var/data/apprenticeships/apprenticeships.db # Apprenticeships data
```

All databases use SQLite with WAL mode for concurrent access.

### Integrity Checks

**CLI:** Administrative Tools > Admin Database Tools > Validate Database Integrity

Checks for:
- Duplicate emails and usernames
- Orphaned records (students without enrollments, etc.)
- Missing foreign key references

### Data Cleanup

**GUI:** System Administration > Database Admin > Cleanup
**CLI:** Administrative Tools > Admin Database Tools > Fix Orphaned Records

## Backup & Recovery

### Automatic Backups

- **Location:** `var/backups/` directory
- **Schedule:** Daily at 2 AM (configurable)
- **Retention:** 7-30 days (configurable)
- **Includes:** Database files, configuration, uploads

### Manual Backup

```bash
python -c "from education_system.systems.university.infrastructure.database.data_backup import create_enhanced_backup; create_enhanced_backup(manual=True)"
```

Or via GUI: Data Backup GUI > Create Backup

### Restore

```bash
python -c "from education_system.systems.university.infrastructure.database.data_backup import restore_from_backup; restore_from_backup('var/backups/university/database/<backup file>')"
```

### Backup Templates

6 pre-configured templates available:
1. **Daily Basic** — Standard daily with compression
2. **Secure Encrypted** — AES encryption with retention
3. **Incremental Fast** — Quick incremental for high-activity
4. **Cloud AWS** — S3 cloud storage
5. **Selective Tables** — Critical tables only
6. **Remote SFTP** — Off-site via SFTP

## Monitoring & Health Checks

### System Health

**GUI:** Admin Dashboard > System Health panel (CPU, memory, disk, DB metrics)
**CLI:** System Monitoring menu
**API:** `GET /api/v1/health`

### Active Sessions

**GUI:** Admin Panel > System Status tab (active sessions, connected users)

### Log Files

Logs are written under the centralised `var/logs/` directory, in a folder per owner (for example `var/logs/university/`):
- `app.log` — Application logs (rotating, 5 MB max, 5 backups)
- `enhanced_log_YYYY-MM-DD.json` — Chatbot conversation logs
- `backup.log` — Backup activity

**GUI:** System Administration > Log Management
**CLI:** Administrative Tools > Activity Logs

## Email Configuration

### Setup

Create a `.env` file with SMTP settings:

```env
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=noreply@example.com
SMTP_PASSWORD=your-password
```

### Features

- Async email queue with retry
- Template support (HTML and plain text)
- Bulk sending capability
- Email logging and receipts
- MFA verification codes
- Password reset notifications

**GUI:** System Administration > Configuration > Email Configuration

## API Server Management

### Starting the Server

```bash
python -m education_system --api
```

The unified server runs on port 5000 and serves all 7 systems.

### Rate Limiting

- Login: 10 attempts per IP per 60 seconds
- Per-username: 5 attempts per 60 seconds
- Registration: 5 per hour per IP

### CORS

Configure allowed origins via `API_CORS_ORIGINS` environment variable (comma-separated).

### Webhooks

See [WEBHOOKS.md](../reference/WEBHOOKS.md) for webhook configuration and management.

## Routine Maintenance

### Daily

- Check system health dashboard for CPU/memory/disk alerts
- Review failed login attempts in audit log
- Verify backup completion

### Weekly

- Review active sessions and force-logout stale ones
- Check database sizes and clean up old logs
- Review webhook delivery failures

### Monthly

- Rotate admin passwords
- Review user account list for inactive accounts
- Test backup restore procedure
- Update dependencies (`make lock`, then `make install`)

### On Upgrade

```bash
# 1. Backup databases
python -c "from education_system.systems.university.infrastructure.database.data_backup import create_enhanced_backup; create_enhanced_backup(manual=True)"

# 2. Pull latest code
git pull

# 3. Install dependencies
make install

# 4. Run database migrations (auto-applied on startup)
python -m education_system --cli  # Start and stop to trigger migrations

# 5. Verify
make test
```

## Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| "Database is locked" | Another process has the DB open. Check for stale processes. WAL mode handles most concurrency. |
| Login fails with correct password | Account may be locked (3 failed attempts). Wait 15 minutes or reset via admin CLI. |
| MFA code rejected | Check system clock synchronisation (TOTP requires accurate time). |
| Email not sending | Verify `.env` SMTP settings. Check `var/logs/` for SMTP errors. |
| API returns 401 | Token expired. Refresh via `POST /api/v1/auth/refresh`. |
| Forced password reset won't stop | Admin can disable it: Security Settings > toggle off "Force password reset". |

### Getting Help

- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — Detailed troubleshooting guide
- [CLI_REFERENCE.md](../reference/CLI_REFERENCE.md) — Complete CLI command reference
- [API_REFERENCE.md](../reference/API_REFERENCE.md) — REST API documentation
