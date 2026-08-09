# Database Management Guide (Admin)

This guide covers database backups, recovery, maintenance, migrations, and monitoring within the University Management System.

## Table of Contents

- [Overview](#overview)
- [Database Architecture](#database-architecture)
- [Connection Management](#connection-management)
- [Backups](#backups)
- [Restoring from Backup](#restoring-from-backup)
- [Backup Scheduling](#backup-scheduling)
- [Encryption & Security](#encryption--security)
- [Cloud Storage](#cloud-storage)
- [Database Maintenance](#database-maintenance)
- [Migrations](#migrations)
- [Export & Import](#export--import)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

## Overview

The database layer is the foundation of the University Management System. It uses SQLite with Write-Ahead Logging (WAL), thread-safe connection pooling, and comprehensive backup/recovery capabilities including encryption, cloud storage, and scheduled automation.

**Key files:**
- Core: `infrastructure/database/db.py`
- Backup: `infrastructure/database/data_backup.py`
- Utilities: `infrastructure/database/utilities.py`
- Migrations: `infrastructure/database/migrations/`
- GUI: `modules/shared/gui/database/data_backup_gui.py`

**Database location:** `data/db_files/student_records.db`

## Database Architecture

### Single Unified Database

All system data resides in a single SQLite database file. This simplifies backup, recovery, and maintenance operations.

### PRAGMA Configuration

The database is configured with these settings for optimal performance:

| PRAGMA | Value | Purpose |
|--------|-------|---------|
| `foreign_keys` | ON | Enforce referential integrity |
| `journal_mode` | WAL | Better concurrent read/write performance |
| `synchronous` | NORMAL | Balance between safety and speed |
| `busy_timeout` | 30000ms | Wait before returning "database locked" |

### Connection Pooling

The system uses a thread-safe connection pool:
- **Min connections**: 2
- **Max connections**: 10 (configurable)
- **Max connection age**: 3600 seconds
- **Cleanup interval**: 300 seconds
- Thread-local storage ensures each thread has its own connection

## Connection Management

### Using Connections

Always use context managers for database operations:

```python
from university_system.infrastructure.database.db import get_connection, transaction

# Read-only queries
with get_connection() as conn:
    result = conn.execute("SELECT * FROM students").fetchall()

# Write operations with automatic commit/rollback
with transaction() as conn:
    conn.execute("INSERT INTO students ...")
    conn.execute("INSERT INTO enrollments ...")
    # Auto-commits on success, auto-rollbacks on exception
```

### Environment Variables

Configure the database layer via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_TIMEOUT` | 30.0 | Connection timeout (seconds) |
| `DB_BUSY_TIMEOUT` | 30000 | SQLite busy timeout (ms) |
| `DB_MAX_RETRIES` | 3 | Retry attempts for failed connections |
| `DB_RETRY_DELAY` | 0.5 | Delay between retries (seconds) |
| `DB_MAX_CONNECTIONS` | 10 | Maximum pool connections |
| `DB_MIN_CONNECTIONS` | 2 | Minimum pool connections |
| `DB_POOL_TIMEOUT` | 30.0 | Pool connection timeout (seconds) |
| `DB_MAX_CONNECTION_AGE` | 3600 | Max connection lifetime (seconds) |

## Backups

### Backup Types

| Type | Description | Use Case |
|------|-------------|----------|
| Full | Complete database snapshot | Initial backups, disaster recovery |
| Incremental | Changes since last full backup | Efficient daily backups |
| Differential | Changes since last backup of any type | Hybrid approach |
| Schema-Only | Table structures without data | Documentation, migration planning |
| Selective | Specific tables only | Targeted backups of critical data |

### Creating a Backup via CLI

```bash
# Using Makefile
make db-backup

# Using the enhanced backup menu
python run.py --cli
# Navigate to: System Administration > Backup & Recovery
```

The enhanced CLI backup menu provides:
1. Create Backup (Full/Incremental/Differential/Schema/Selective)
2. Restore from Backup
3. Backup Management (list, delete, cleanup, compare)
4. Validation & Verification
5. Export Data (CSV, JSON, XML)
6. Configuration
7. Scheduling
8. Templates
9. Database Maintenance
10. Advanced Options

### Creating a Backup via GUI

1. Launch the Backup GUI from the admin panel
2. Select the **Backup** tab
3. Choose the backup type
4. Configure options (compression, encryption)
5. Click **Create Backup**
6. Progress bar shows completion status

### Backup Storage

Backups are stored in the `backups/` directory with naming convention:
```
student_records_manual_full_20260208_153000.db
student_records_auto_incremental_20260208_020000.db.gz
```

### Backup Metadata

All backups are tracked in `data/backup_metadata.json`:
- File path and timestamp
- Backup type and size
- Hash for integrity verification
- Encryption status
- Compression status

## Restoring from Backup

### Full Restore

1. Select **Restore from Backup** in the CLI or GUI
2. Choose the backup file from the list
3. Confirm the restoration
4. The system replaces the current database with the backup
5. A pre-restore backup is automatically created for safety

### Partial Restore

Restore specific tables without affecting the rest:
1. Select **Partial Restore**
2. Choose the backup file
3. Select the tables to restore
4. The system replaces only the selected tables

### Verification

After restoring:
1. Run an integrity check
2. Verify table counts match expectations
3. Test critical queries

## Backup Scheduling

### Configuring Automatic Backups

1. Navigate to backup configuration (CLI option 6 or Settings tab in GUI)
2. Set parameters:
   - **Frequency**: Daily, Weekly, Monthly
   - **Time**: When to run (e.g., "02:00" for 2 AM)
   - **Backup Type**: Full or Incremental
   - **Retention Policy**: How many backups to keep
3. Enable auto-backup

### Retention Policies

Configure how long backups are kept:

| Policy | Default | Description |
|--------|---------|-------------|
| `daily_keep` | 7 | Keep 7 days of daily backups |
| `weekly_keep` | 4 | Keep 4 weeks of weekly backups |
| `monthly_keep` | 12 | Keep 12 months of monthly backups |
| `yearly_keep` | 5 | Keep 5 years of yearly backups |

### Storage Quota

Set a maximum storage quota (default: 10 GB). The system warns when approaching the limit and can automatically clean old backups.

## Encryption & Security

### Enabling Encryption

1. Open backup configuration
2. Enable encryption
3. Set an encryption password
4. All new backups will be encrypted

### Encryption Details

- **Algorithm**: Fernet (AES-128-CBC)
- **Key Derivation**: PBKDF2-SHA256 with 100,000 iterations
- **Salt**: Unique per backup

### Integrity Verification

Every backup includes a SHA-256 hash. Verify integrity:
1. Select **Verify Backup** in the CLI or GUI
2. Choose the backup file
3. The system computes the hash and compares with the stored value
4. Reports pass/fail status

### Secure Deletion

Enable secure deletion to overwrite backup files before removing them:
- Configurable multi-pass overwrite
- Prevents recovery of deleted backup data

## Cloud Storage

### AWS S3

Configure S3 for off-site backup storage:

1. Set configuration values:
   - `aws_bucket`: S3 bucket name
   - `aws_access_key`: AWS access key
   - `aws_secret_key`: AWS secret key
   - `aws_region`: AWS region (default: us-east-1)
2. Enable cloud storage
3. Backups automatically upload after creation

### FTP/SFTP

Configure remote storage via FTP or SFTP:

1. Set configuration values:
   - `remote_type`: ftp or sftp
   - `remote_host`: Server hostname
   - `remote_username` and `remote_password`
   - `remote_path`: Destination directory
2. Enable remote storage

### Webhook Notifications

Receive notifications about backup status:
- **Slack**: Configure a Slack webhook URL
- **Discord**: Configure a Discord webhook URL
- Notifications sent on backup success or failure

### Email Notifications

Enable email notifications for backup events:
- Configure SMTP settings
- Set recipient list
- Receive reports on backup completion or failure

## Database Maintenance

### Optimization

Run periodic database optimization from the Management tab or CLI:

| Operation | Command | Purpose |
|-----------|---------|---------|
| VACUUM | `optimize_database()` | Reclaim unused disk space |
| ANALYZE | Included in optimize | Update query planner statistics |
| REINDEX | Included in optimize | Rebuild all indexes |

### Integrity Checks

Run integrity checks to verify database health:

1. Navigate to **Database Maintenance** or use the admin GUI
2. Click **Run Integrity Check**
3. The system runs `PRAGMA integrity_check`
4. Results show any issues found

### Duplicate Detection

Find and fix duplicate records:
1. Select **Fix Duplicates** from the admin panel
2. The system scans for duplicates across key tables
3. Review detected duplicates
4. Choose to merge or delete duplicates

### Statistics

View database statistics:
- Total tables and record counts
- Database file size
- Index status
- Connection pool statistics

## Migrations

### Available Migrations

Migrations are located in `infrastructure/database/migrations/`:

| Migration | Purpose |
|-----------|---------|
| `add_mfa_system.py` | Add MFA tables and columns |
| `add_security_features.py` | Add security-related tables |
| `add_student_modules_columns.py` | Add missing student_modules columns |
| `add_unique_mfa_contacts.py` | Add unique constraints to MFA contacts |
| `fix_campus_events_tables.py` | Fix campus events schema |
| `fix_facilities_schema.py` | Fix facilities management schema |
| `fix_job_postings_schema.py` | Fix job postings schema |
| `fix_rooms_foreign_keys.py` | Fix foreign key constraints |
| `separate_staff_hr_job_postings.py` | Separate job postings from staff HR |

### Running a Migration

```bash
# From project root
PYTHONPATH=. python3 university_system/infrastructure/database/migrations/add_student_modules_columns.py
```

### Migration Best Practices

1. **Always backup first**: Create a backup before running any migration
2. **Test on a copy**: Run the migration on a backup copy first
3. **Check idempotency**: Migrations should be safe to run multiple times
4. **Verify results**: Check affected tables after migration
5. **Update changelog**: Document the migration in CHANGELOG.md

### Schema Initialization

Initialize all database schemas at once:

```python
from university_system.infrastructure.database.utilities import initialize_all_schemas
initialize_all_schemas()
```

Or initialize specific schemas:

```python
from university_system.infrastructure.database.utilities import (
    init_grade_system_db,
    init_finance_system_db,
    init_student_union_db,
    init_email_system_db
)
```

## Export & Import

### Export Formats

| Format | Function | Description |
|--------|----------|-------------|
| CSV | `export_to_csv()` | Each table as a separate CSV file |
| JSON | `export_to_json()` | Entire database as JSON |
| XML | `export_to_xml()` | Structured XML with schema |
| TXT | `export_to_txt()` | Human-readable text summary |
| PDF | `export_to_pdf()` | Formatted PDF report |

### Exporting Data

1. Select **Export Data** from the backup menu
2. Choose the export format
3. Select the output directory
4. The system exports all tables (or selected tables)

## Monitoring

### Connection Pool Metrics

Monitor the connection pool health:

```python
from university_system.infrastructure.database.db import get_connection_pool

pool = get_connection_pool()
stats = pool.get_stats()
# Returns: active connections, total count, idle count
```

### Query Performance

The query monitor (`infrastructure/database/query_monitor.py`) tracks:
- Slow query detection
- Query execution times
- Most frequent queries
- Performance trends

### Pool Metrics

The pool metrics module (`infrastructure/database/pool_metrics.py`) provides:
- Connection utilization rates
- Wait times
- Connection lifecycle statistics

## Troubleshooting

### Database Locked Errors

**Symptoms**: Operations fail with "database is locked" errors.

**Solutions**:
1. Ensure only one write operation happens at a time
2. Always use context managers (`with get_connection()` or `with transaction()`)
3. Check that WAL mode is enabled: `PRAGMA journal_mode` should return `wal`
4. Increase the busy timeout via `DB_BUSY_TIMEOUT` environment variable
5. Check the connection pool for leaked connections
6. Restart the application to clear stale connections

### Backup Failures

**Symptoms**: Backup creation fails or produces empty files.

**Solutions**:
1. Verify the `backups/` directory exists and has write permissions
2. Check available disk space
3. If encrypting, verify the encryption password is set correctly
4. Check database file permissions (should be 644)
5. Ensure the database is not being modified during backup

### Restore Issues

**Symptoms**: Restore operation fails or data is incomplete.

**Solutions**:
1. Stop all application instances before restoring
2. Verify the backup file integrity (run verification check)
3. Check that the backup file is not encrypted with a different password
4. For encrypted backups, ensure the decryption password matches
5. Try a partial restore of specific tables if full restore fails

### Migration Failures

**Symptoms**: Migration script fails partway through.

**Solutions**:
1. Check the error message for specific table or column issues
2. Verify the database has not already been migrated (run migration again - should be idempotent)
3. Restore from backup and retry
4. Check Python path is set correctly: `PYTHONPATH=.`
5. Verify all required tables exist before migration

### Connection Timeout

**Symptoms**: Operations hang or timeout waiting for a connection.

**Solutions**:
1. Increase `DB_TIMEOUT` environment variable
2. Check for long-running queries monopolizing connections
3. Reduce `DB_MAX_CONNECTIONS` if the pool is exhausted
4. Run `cleanup_database_connections()` to clear stale connections
5. Verify no deadlocks exist in concurrent operations

### Permission Errors

```bash
# Fix directory permissions
chmod -R 755 data/ logs/ backups/

# Fix database file permissions
chmod 644 data/db_files/student_records.db
```
