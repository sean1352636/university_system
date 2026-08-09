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

The Education System runs four subsystems from a single codebase:

| System | Key | Database | Users |
|--------|-----|----------|-------|
| University | `university` | `student_records.db` | Admin, Staff, Instructor, Student, Parent |
| Sixth Form College | `college` | `college.db` | Admin, Teacher, Student, Parent |
| Secondary School | `school` | `secondary.db` | Admin, Teacher, Student, Parent |
| Primary School | `primary` | `primary.db` | Admin, Teacher, Pupil, Parent |

**Shared infrastructure:**
- Authentication: `shared/data/db_files/auth.db` (all systems)
- Webhooks: `shared/data/db_files/webhooks.db`
- Offline sync: `shared/data/db_files/offline_sync.db`

## First-Time Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Initialise Databases

Databases are auto-created on first run. Default accounts are seeded automatically.

```bash
python run.py --gui    # GUI mode
python run.py --cli    # CLI mode
```

### 3. Change Default Passwords

The system ships with weak demo passwords. Change them immediately:

| Username | Default Password | System |
|----------|-----------------|--------|
| `superadmin` | `SuperAdmin@123` | All |
| `admin` | `admin123` | University |
| `admin1` | `admin1234` | College |
| `admin2` | `admin1234` | Secondary |
| `admin3` | `admin1234` | Primary |

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
**API:** `POST /api/v1/auth/login` (admin token required)

### Roles and Permissions

Each system defines its own roles. Users are assigned to systems via the `user_systems` table in `auth.db`.

A user can have access to multiple systems with different roles:
```
superadmin: university(admin), college(admin), school(admin), primary(admin)
```

### Forced Password Reset

Admins can toggle forced password reset for all users:

**GUI:** System Administration > Configuration > Security Settings > toggle "Force password reset for expired passwords"

**CLI:** Authentication > User Management > Toggle Forced Password Reset

When enabled, users whose `password_changed_at` is older than 90 days (or NULL) must change their password on login. When disabled, the check is skipped.

The setting is stored in `auth_settings` table in `auth.db`.

### Account Lockout

After 5 failed login attempts, accounts are locked for 15 minutes. Admins can unlock accounts:

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
education_system/shared/data/db_files/auth.db          # Shared authentication
education_system/university_system/data/db_files/       # University data
education_system/college_system/data/db_files/          # College data
education_system/secondary_school/data/db_files/        # Secondary data
education_system/primary_school/data/db_files/          # Primary data
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

- **Location:** `backups/` directory
- **Schedule:** Daily at 2 AM (configurable)
- **Retention:** 7-30 days (configurable)
- **Includes:** Database files, configuration, uploads

### Manual Backup

```bash
make db-backup
```

Or via GUI: Data Backup GUI > Create Backup

### Restore

```bash
make db-restore BACKUP_FILE=backups/backup_20260406.db
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

Logs are written to the centralised `logs/` directory:
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
python run.py --api
```

The unified server runs on port 5000 and serves all 4 systems.

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
- Update dependencies (`pip install -r requirements.txt --upgrade`)

### On Upgrade

```bash
# 1. Backup databases
make db-backup

# 2. Pull latest code
git pull

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run database migrations (auto-applied on startup)
python run.py --cli  # Start and stop to trigger migrations

# 5. Verify
make test
```

## Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| "Database is locked" | Another process has the DB open. Check for stale processes. WAL mode handles most concurrency. |
| Login fails with correct password | Account may be locked (5 failed attempts). Wait 15 minutes or reset via admin CLI. |
| MFA code rejected | Check system clock synchronisation (TOTP requires accurate time). |
| Email not sending | Verify `.env` SMTP settings. Check `logs/app.log` for SMTP errors. |
| API returns 401 | Token expired. Refresh via `POST /api/v1/auth/refresh`. |
| Forced password reset won't stop | Admin can disable it: Security Settings > toggle off "Force password reset". |

### Getting Help

- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — Detailed troubleshooting guide
- [CLI_REFERENCE.md](../reference/CLI_REFERENCE.md) — Complete CLI command reference
- [API_REFERENCE.md](../reference/API_REFERENCE.md) — REST API documentation
