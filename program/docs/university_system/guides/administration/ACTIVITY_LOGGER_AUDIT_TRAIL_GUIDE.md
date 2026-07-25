# Activity Logger & Audit Trail Guide

This guide covers compliance logging, audit trails, immutable audit logs, and activity tracking within the University Management System.

## Table of Contents

- [Overview](#overview)
- [Logging Architecture](#logging-architecture)
- [Simple Activity Logger](#simple-activity-logger)
- [Advanced Audit Trail](#advanced-audit-trail)
- [Immutable Audit Log](#immutable-audit-log)
- [Audit Helpers](#audit-helpers)
- [Enterprise Activity Logger](#enterprise-activity-logger)
- [Compliance Standards](#compliance-standards)
- [Querying & Exporting](#querying--exporting)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

## Overview

The University Management System provides a multi-layered logging and audit system designed for regulatory compliance. It includes a simple file-based activity logger for general use, a database-backed audit trail for structured queries, and an immutable blockchain-style audit log for tamper-proof compliance records.

**Key files:**
- Simple Activity Logger: `modules/shared/utils/activity_logger.py`
- Enterprise Activity Logger: `modules/shared/utils/simple_activity_logger.py`
- Audit Trail: `infrastructure/security/audit_trail.py`
- Immutable Audit Log: `infrastructure/security/immutable_audit_log.py`
- Audit Helpers: `infrastructure/security/audit_helpers.py`

## Logging Architecture

```
┌──────────────────────────────────────────────────────────┐
│                  Application Layer                        │
│  log_activity() / log_login() / log_create() / etc.      │
├──────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │ Simple Logger   │  │ Audit Trail  │  │ Immutable   │ │
│  │ (File-based)    │  │ (Database)   │  │ Audit Log   │ │
│  │                 │  │              │  │ (Hash Chain) │ │
│  │ activity.log    │  │ audit_trail  │  │ immutable_  │ │
│  │ Rotation: Daily │  │ table        │  │ audit_log   │ │
│  └─────────────────┘  └──────────────┘  └─────────────┘ │
│         ▲                     ▲                ▲         │
│         │                     │                │         │
│    General Use          Compliance       Critical Ops    │
│    (All modules)        (Query/Export)   (Tamper-proof)  │
└──────────────────────────────────────────────────────────┘
```

### When to Use Each Logger

| Logger | Use Case | Storage | Tamper Detection |
|--------|----------|---------|------------------|
| Simple Activity Logger | General activity tracking | File | No |
| Audit Trail | Compliance queries and reporting | Database | No |
| Immutable Audit Log | Critical operations, regulatory compliance | Database | Yes (hash chain) |

## Simple Activity Logger

The default activity logger for general-purpose logging across all modules. Uses a singleton pattern for a global instance.

### Setting the User Context

```python
from university_system.modules.shared.utils.activity_logger import set_user, get_user

# Set the current user (persists for subsequent log calls)
set_user('admin')

# Get the current user
current = get_user()  # Returns 'admin' (default: 'System')
```

### Logging Activities

```python
from university_system.modules.shared.utils.activity_logger import (
    log_activity,
    log_login,
    log_logout,
    log_create,
    log_read,
    log_update,
    log_delete,
    log_search,
    log_export,
    log_import,
    log_error,
    log_access,
    log_permission_denied
)

# General activity log
log_activity('create', 'student', user='admin', details={'name': 'John Doe'})
log_activity('update', 'grade', user='admin', details={'old': 'B', 'new': 'A'})
log_activity('delete', 'course', user='admin')

# Convenience methods
log_login('admin', success=True)
log_logout('admin')
log_create('student', 'John Doe')
log_read('student_records', 'S-12345')
log_update('grade', 'CS101 Final')
log_delete('course', 'MATH201')
log_search('students', 'Dean\'s List')
log_export('grades', 'PDF')
log_import('students', 'CSV upload')
log_error('Database connection timeout')
log_access('financial_reports')
log_permission_denied('admin_dashboard')
```

### Log File Format

```
admin - Logged in successfully - 2025-10-19 14:30:45
admin - Created student: John Doe - 2025-10-19 14:35:12
admin - Updated grade: CS101 Final - 2025-10-19 14:40:20
admin - Exported grades: PDF - 2025-10-19 14:45:00
System - Permission denied: admin_dashboard - 2025-10-19 14:50:15
```

### Log File Location and Rotation

| Setting | Value |
|---------|-------|
| Directory | `logs/` (via `paths.LOG_DIR`) |
| Active File | `activity.log` |
| Rotation | Daily at midnight |
| Backup Format | `activity_YYYY-MM-DD.log` |
| Retention | 90 days |

## Advanced Audit Trail

The database-backed audit trail provides structured, queryable audit records for compliance reporting.

### Setting User Context

```python
from university_system.infrastructure.security.audit_trail import AuditLogger, AuditAction

logger = AuditLogger()

# Set persistent user context
logger.set_user_context(
    user_id=123,
    username='admin',
    ip_address='192.168.1.1'
)

# Or use context manager for scoped context
with logger.user_context(user_id=123, username='admin', ip_address='192.168.1.1'):
    # All logs within this block use this context
    logger.log(AuditAction.READ, 'student_record', resource_id='S-12345')

# Clear context when done
logger.clear_user_context()
```

### Logging Actions

```python
# Log with full details
entry_id = logger.log(
    action=AuditAction.UPDATE,
    resource_type='student_record',
    resource_id='S-001234',
    user_id=123,
    username='admin',
    ip_address='192.168.1.1',
    details={'field': 'gpa', 'old': 3.5, 'new': 3.8},
    function_name='update_gpa',
    module_name='academics.grading',
    success=True,
    error_message=None,
    data_for_hash={'gpa': 3.8}  # Optional data integrity hash
)
```

### Standard Audit Actions

```python
class AuditAction(Enum):
    ACCESS = 'access'               # Resource access
    CREATE = 'create'               # Record creation
    READ = 'read'                   # Data read
    UPDATE = 'update'               # Data modification
    DELETE = 'delete'               # Record deletion
    EXPORT = 'export'               # Data export
    IMPORT = 'import'               # Data import
    LOGIN = 'login'                 # User login
    LOGOUT = 'logout'               # User logout
    PERMISSION_CHANGE = 'permission_change'  # Permission modification
    CONFIG_CHANGE = 'config_change'          # Configuration change
```

### Audit Trail Database Schema

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key (auto-increment) |
| timestamp | TEXT | ISO format timestamp |
| action | VARCHAR | Action type (from AuditAction) |
| resource_type | VARCHAR | Type of resource affected |
| resource_id | VARCHAR | Identifier of specific resource |
| user_id | INTEGER | User who performed the action |
| username | VARCHAR | Username for display |
| ip_address | VARCHAR | Client IP address |
| details | JSON | Additional action details |
| function_name | VARCHAR | Function that triggered the action |
| module_name | VARCHAR | Module containing the function |
| success | BOOLEAN | Whether the action succeeded |
| error_message | VARCHAR | Error details if action failed |
| data_hash | VARCHAR | SHA-256 hash for data integrity |

**Indexes:**
- `timestamp DESC` - Chronological queries
- `user_id, timestamp DESC` - Per-user history
- `resource_type, resource_id` - Resource lookup
- `action, timestamp DESC` - Action-type filtering

## Immutable Audit Log

The immutable audit log uses a blockchain-style hash chain for tamper-proof compliance records. Any modification to a log entry breaks the chain and is detectable via integrity verification.

### How the Hash Chain Works

```
Entry 1:                     Entry 2:                     Entry 3:
┌──────────────┐            ┌──────────────┐            ┌──────────────┐
│ previous_hash│◄───────────│ previous_hash│◄───────────│ previous_hash│
│ = NULL       │            │ = hash(E1)   │            │ = hash(E2)   │
│              │            │              │            │              │
│ current_hash │────────►   │ current_hash │────────►   │ current_hash │
│ = SHA256(    │            │ = SHA256(    │            │ = SHA256(    │
│   data+NULL) │            │   data+h1)   │            │   data+h2)   │
│              │            │              │            │              │
│ hmac_sig     │            │ hmac_sig     │            │ hmac_sig     │
│ = HMAC(data) │            │ = HMAC(data) │            │ = HMAC(data) │
└──────────────┘            └──────────────┘            └──────────────┘
```

- **SHA-256 hash**: Each entry's hash depends on its data and the previous entry's hash
- **HMAC-SHA256 signature**: Each entry is signed with a secret key
- **Tampering detection**: Modifying any entry invalidates all subsequent hashes

### Adding Entries

```python
from university_system.infrastructure.security.immutable_audit_log import immutable_audit_log

entry_hash = immutable_audit_log.add_entry(
    user_id='admin_123',
    action='DATA_EXPORT',
    resource_type='student_records',
    resource_id='batch_500',
    details={'record_count': 500, 'format': 'csv'},
    ip_address='192.168.1.1',
    user_agent='Mozilla/5.0',
    session_id='sess_abc123'
)
print(f"Entry hash: {entry_hash}")
```

### Verifying Integrity

```python
result = immutable_audit_log.verify_integrity()

if result['valid']:
    print("Audit log integrity verified - no tampering detected")
else:
    print(f"TAMPERING DETECTED! Invalid entries: {result['invalid_entries']}")
    # Alert security team
```

### Querying Entries

```python
# Query with filters
entries = immutable_audit_log.query_entries(
    user_id='admin_123',
    action='DATA_EXPORT',
    since='2025-01-01T00:00:00',
    until='2025-12-31T23:59:59'
)
```

### Exporting for Audit

```python
# Export for external auditors
immutable_audit_log.export_for_audit(
    format='csv',
    filename='compliance_audit_2025.csv'
)
```

### Immutable Audit Log Schema

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| timestamp | TEXT | ISO UTC timestamp |
| user_id | VARCHAR | User identifier |
| action | VARCHAR | Action performed |
| resource_type | VARCHAR | Resource category |
| resource_id | VARCHAR | Specific resource |
| details | JSON | Action metadata |
| ip_address | VARCHAR | Client IP |
| user_agent | VARCHAR | Client user agent |
| session_id | VARCHAR | Session identifier |
| previous_hash | VARCHAR | SHA-256 of previous entry |
| current_hash | VARCHAR | SHA-256 of this entry (UNIQUE) |
| hmac_signature | VARCHAR | HMAC-SHA256 signature |

## Audit Helpers

Safe wrapper functions that never raise exceptions, ensuring logging failures don't break application functionality.

### Safe Logging

```python
from university_system.infrastructure.security.audit_helpers import safe_log_security_event

# This never raises - returns True/False
success = safe_log_security_event(
    action='DATA_EXPORT',
    user_id='staff_123',
    resource_type='student_records',
    resource_id='batch_report',
    details={'record_count': 500, 'format': 'csv'},
    ip_address='192.168.1.1',
    user_agent='Mozilla/5.0',
    session_id='sess_abc'
)
```

### Context Extraction

```python
from university_system.infrastructure.security.audit_helpers import (
    get_gui_context,
    get_api_context,
    get_current_user_id
)

# Get GUI context (user_id, session_id)
user_id, session_id = get_gui_context()

# Get API context from request (ip_address, user_agent)
ip_address, user_agent = get_api_context(request)

# Get current user ID
current_user = get_current_user_id()
```

### Sensitive Data Masking

```python
from university_system.infrastructure.security.audit_helpers import mask_sensitive_data

data = {
    'username': 'admin',
    'password': 'secret123',
    'ssn': '123-45-6789',
    'credit_card': '4111-1111-1111-1111'
}

masked = mask_sensitive_data(data)
# Result: {'username': 'admin', 'password': '***', 'ssn': '***', 'credit_card': '***'}
```

Fields automatically masked: passwords, tokens, secrets, SSNs, credit cards, API keys.

## Enterprise Activity Logger

The enterprise logger (`modules/shared/utils/simple_activity_logger.py`) provides advanced features for large-scale deployments.

### Rich Log Entries

Each log entry captures extensive metadata:

| Field | Description |
|-------|-------------|
| timestamp | ISO format timestamp |
| user_id | User identifier |
| username | Display name |
| role | User role |
| action | Action performed |
| module | Source module |
| details | Action description |
| status | success, failure, warning |
| log_level | DEBUG, INFO, WARNING, ERROR |
| session_id | Session identifier |
| ip_address | Client IP |
| user_agent | Browser/client info |
| request_size | Request payload bytes |
| response_size | Response payload bytes |
| processing_time | Execution duration (seconds) |
| geolocation | IP geolocation data |
| security_level | LOW, MEDIUM, HIGH, CRITICAL |
| trace_id | Distributed tracing ID |
| stack_trace | Error stack trace |
| metadata | Custom key-value pairs |

### PII Detection and Masking

The enterprise logger automatically detects and masks personally identifiable information before logging:

- Email addresses
- Phone numbers
- Social Security Numbers
- Credit card numbers
- IP addresses

### Security Monitoring

```python
# The SecurityMonitor class tracks:
# - Failed login attempts (by user and IP)
# - Suspicious activity patterns
# - Rate limiting (requests per minute)
# - Privilege escalation attempts
# - IP reputation tracking
```

### Log Rotation

| Setting | Default |
|---------|---------|
| Max file size | 100 MB |
| Time-based retention | 30 days |
| Compression | gzip for archived logs |

### Output Formats

| Format | Description |
|--------|-------------|
| JSON | Structured, query-friendly |
| CSV | Spreadsheet compatible |
| DATABASE | SQL table storage |
| SYSLOG | System logging integration |
| CLOUD | CloudWatch, Stackdriver, etc. |

## Compliance Standards

The audit system supports compliance with:

| Standard | Coverage |
|----------|----------|
| **GDPR** (Article 30) | Records of processing activities, data access logs |
| **FERPA** | Educational records access logging, disclosure tracking |
| **SOX** | Financial transaction audit trails |
| **HIPAA** | Healthcare data access logs, breach detection |

### Required Logging

All data modifications must be logged for compliance:

```python
# Required pattern for all data changes
log_activity('create', 'student', user=current_user, details={'student_id': 'S-12345'})
log_activity('update', 'grade', user=current_user, details={'old': 'B', 'new': 'A'})
log_activity('delete', 'enrollment', user=current_user, details={'course': 'CS101'})
log_activity('export', 'student_records', user=current_user, details={'count': 500})
```

## Querying & Exporting

### Audit Trail Queries

```python
logger = AuditLogger()

# Recent entries
recent = logger.get_recent(limit=100)

# Per-user history
user_actions = logger.get_for_user(user_id=123, limit=50)

# Advanced query
results = logger.query(
    action='update',
    resource_type='student_record',
    since=datetime.now() - timedelta(days=7),
    until=datetime.now(),
    success_only=True,
    limit=100,
    offset=0
)

# Export as JSON
logger.export(format='json', filename='audit_export.json')

# Export as CSV
logger.export(format='csv', filename='audit_export.csv')
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AUDIT_LOG_SECRET` | - | HMAC secret key for immutable log (required in production) |
| `LOG_LEVEL` | `INFO` | Logging verbosity (DEBUG, INFO, WARNING, ERROR, CRITICAL) |

### Log Directories

All log files are stored under the centralized `paths.LOG_DIR` directory (typically `logs/`).

| File | Content |
|------|---------|
| `activity.log` | Current activity log |
| `activity_YYYY-MM-DD.log` | Rotated daily logs |
| `activity_logs.db` | Database-backed audit entries |
| `app.log` | Application logs |

## Troubleshooting

### Logs Not Being Written

1. Check write permissions on the `logs/` directory
2. Verify the `LOG_DIR` path in `modules/shared/constants/paths.py`
3. Ensure `set_user()` is called before logging user-specific activities

```bash
chmod -R 755 logs/
```

### Immutable Audit Log Integrity Failure

1. Run `verify_integrity()` to identify invalid entries
2. Compare against backup audit logs
3. Investigate the entries before and after the break in the chain
4. The `AUDIT_LOG_SECRET` must remain consistent - changing it invalidates HMAC signatures

### Missing Audit Entries

1. Ensure `safe_log_security_event()` is being used (it never raises)
2. Check the database connection - audit entries require active DB access
3. Verify the audit tables exist by checking the database schema

### High Log Volume

1. Increase log rotation frequency
2. Archive old logs with compression
3. Use the enterprise logger's configurable retention settings
4. Consider database partitioning for audit trail tables

### Sensitive Data in Logs

1. Use `mask_sensitive_data()` before logging dictionaries
2. The enterprise logger auto-detects PII patterns
3. Review logs periodically for accidental PII exposure
4. Configure the PII detection patterns for your specific data types
