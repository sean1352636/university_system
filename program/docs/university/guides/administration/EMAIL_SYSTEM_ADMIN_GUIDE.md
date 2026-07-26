# Email System Admin Guide

This guide covers email configuration, templates, scheduling, queue management, and SMTP integration within the University Management System.

## Table of Contents

- [Overview](#overview)
- [Email Architecture](#email-architecture)
- [Configuration](#configuration)
- [SMTP Setup](#smtp-setup)
- [Sending Emails](#sending-emails)
- [Email Templates](#email-templates)
- [Email Queue & Batch Processing](#email-queue--batch-processing)
- [Email Scheduler](#email-scheduler)
- [Email Database & Logging](#email-database--logging)
- [Admin Panel](#admin-panel)
- [Notification Emails](#notification-emails)
- [Security](#security)
- [Troubleshooting](#troubleshooting)

## Overview

The Email System provides asynchronous email delivery with database-only mode (default), optional SMTP integration, template rendering, scheduled tasks, and comprehensive audit logging. All emails are stored in the database for inbox access and compliance.

**Key files:**
- Email Service: `infrastructure/email/email_service.py`
- Configuration: `infrastructure/email/config.py`
- Email Manager: `infrastructure/email/email_manager.py`
- Scheduler: `infrastructure/email/email_scheduler.py`
- DB Utilities: `infrastructure/email/email_db_utilities.py`
- Admin Panel: `infrastructure/email/admin.py`
- Templates: `infrastructure/email/templates.py`
- SMTP: `infrastructure/email/smtp.py`
- State: `infrastructure/email/state.py`
- Template Utils: `infrastructure/email/template_utils.py`

## Email Architecture

```
┌──────────────────────────────────────────────────┐
│                 Email Service                     │
│  send_email() / send_email_as_user()             │
├──────────────────────────────────────────────────┤
│          ┌─────────────┬──────────────┐          │
│          │ DB-Only Mode│  SMTP Mode   │          │
│          │  (default)  │  (optional)  │          │
│          └──────┬──────┴──────┬───────┘          │
│                 │             │                    │
│          ┌──────▼──────┐ ┌───▼─────┐             │
│          │ stored_emails│ │  SMTP   │             │
│          │ messages     │ │ Server  │             │
│          │ email_log    │ └─────────┘             │
│          └─────────────┘                          │
├──────────────────────────────────────────────────┤
│              Email Scheduler                      │
│  Surveys | Book Reminders | SLA Alerts           │
├──────────────────────────────────────────────────┤
│              Email Manager                        │
│  Queue | Batch Processing | Notifications        │
└──────────────────────────────────────────────────┘
```

### Operating Modes

| Mode | Description | Default |
|------|-------------|---------|
| **Database-Only** | Emails stored in DB, accessible via inbox | Yes |
| **SMTP** | Emails sent via SMTP server + stored in DB | No |

## Configuration

### Loading Configuration

Configuration is loaded from a JSON file at `data/config/email_config.json`:

```python
from university_system.infrastructure.email.config import load_config, save_config

# Load configuration
config = load_config()

# Update settings
from university_system.infrastructure.email.config import configure_email_settings
configure_email_settings(
    sender_email='noreply@university.edu',
    sender_name='University System',
    database_only_mode=True
)

# Save configuration
save_config()
```

### Configuration Options

| Setting | Default | Description |
|---------|---------|-------------|
| `database_only_mode` | `True` | Store emails in DB only (no SMTP) |
| `templates_dir` | `templates/email` | Email template directory |
| `sender_email` | `''` | Default sender email address |
| `sender_name` | `''` | Default sender display name |
| `smtp_server` | `''` | SMTP server hostname |
| `smtp_port` | `25` | SMTP port (25, 465, or 587) |
| `use_tls` | `True` | Enable TLS encryption |
| `use_authentication` | `True` | Require SMTP authentication |
| `username` | env `SMTP_USERNAME` | SMTP username |
| `email_signature` | `''` | Appended to all outgoing emails |
| `send_delay` | `1.0` | Seconds between sends (rate limiting) |
| `max_threads` | `3` | Concurrent email worker threads |
| `max_retries` | `3` | Retry attempts on failure |
| `retry_delay` | `5` | Seconds between retries |
| `attachment_size_limit` | `10485760` | Max attachment size (10 MB) |
| `enable_logging` | `True` | Enable email audit logging |
| `log_level` | `INFO` | Logging verbosity |

### Ensuring Database Mode

```python
from university_system.infrastructure.email.config import ensure_email_config_for_database_mode

# Validate and set up database-only mode
ensure_email_config_for_database_mode()
```

## SMTP Setup

### Configuring SMTP

To enable actual email delivery:

```python
configure_email_settings(
    database_only_mode=False,
    smtp_server='smtp.gmail.com',
    smtp_port=587,
    use_tls=True,
    use_authentication=True,
    username='your_email@university.edu',
    sender_email='noreply@university.edu',
    sender_name='University System'
)
```

### Password Management

Passwords are **never** stored in configuration files. The system uses secure storage:

```python
from university_system.infrastructure.email.config import (
    set_smtp_password,
    get_smtp_password,
    delete_smtp_password
)

# Store password in system keyring
set_smtp_password('your_email@university.edu', 'your_password')

# Retrieve password
password = get_smtp_password('your_email@university.edu')

# Remove stored password
delete_smtp_password('your_email@university.edu')
```

**Password resolution order:**
1. System keyring (`keyring` library)
2. Environment variable: `SMTP_PASSWORD`

### Environment Variables

```bash
export SMTP_USERNAME=your_email@university.edu
export SMTP_PASSWORD=your_secure_password
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
```

## Sending Emails

### Basic Email

```python
from university_system.infrastructure.email.email_service import send_email

send_email(
    recipient_email='student@university.edu',
    subject='Course Registration Confirmation',
    body='Your enrollment in CS101 has been confirmed.'
)
```

### Send as Specific User

```python
from university_system.infrastructure.email.email_service import send_email_as_user

send_email_as_user(
    recipient_email='student@university.edu',
    subject='Office Hours Update',
    body='My office hours have changed to Tuesdays 2-4pm.',
    sender_user_id=42
)
```

### Send as System

```python
from university_system.infrastructure.email.email_service import send_email_as_system

send_email_as_system(
    recipient_email='student@university.edu',
    subject='Password Reset',
    body='Click the link below to reset your password...',
    system_name='Authentication Service'
)
```

### Email with CC, BCC, and Attachments

```python
send_email(
    recipient_email='student@university.edu',
    subject='Meeting Minutes',
    body='Please find attached the meeting minutes.',
    cc='advisor@university.edu',
    bcc='records@university.edu',
    attachments=['/path/to/minutes.pdf']
)
```

### Sender Resolution Logic

When sending, the system resolves the sender in this priority:
1. **Authenticated user** - Currently logged-in user
2. **Real user match** - Looks up user by email/name in the database
3. **System user creation** - Creates a system user descriptor via `generate_system_username()`

## Email Templates

### Template Directory

Templates are stored in the configured `templates_dir` (default: `templates/email/`).

### Template Rendering

```python
from university_system.infrastructure.email.template_utils import render_template

body = render_template('welcome.html', {
    'student_name': 'John Doe',
    'course_name': 'Introduction to Computer Science',
    'start_date': '2025-01-15'
})
```

### Variable Substitution

Templates support variable substitution using placeholder syntax. Variables are replaced at render time with the provided context dictionary.

## Email Queue & Batch Processing

### Queuing Emails

The Email Manager provides in-memory queuing for batch operations:

```python
from university_system.infrastructure.email.email_manager import EmailManager

manager = EmailManager()

# Queue emails for batch processing
manager._queue_email(
    email_type='notification',
    recipient='student@university.edu',
    subject='Grade Posted',
    body='Your grade for CS101 has been posted.'
)
```

### Processing the Queue

```python
# Retrieve queued emails (max 1000 in-memory)
queued = manager.get_queued_emails(limit=100)

# Clear the queue after processing
manager.clear_email_queue()
```

### Notification Shortcuts

```python
from university_system.infrastructure.email.email_manager import (
    send_ticket_notification,
    send_confirmation_email,
    send_reply_notification,
    send_sla_alert,
    send_satisfaction_survey
)

# Helpdesk ticket notification
send_ticket_notification(
    ticket_id='T-1001',
    recipient='support@university.edu',
    ticket_subject='Login Issue'
)

# Confirmation email
send_confirmation_email(
    recipient='student@university.edu',
    confirmation_type='enrollment',
    details={'course': 'CS101', 'section': 'A'}
)

# SLA breach alert
send_sla_alert(
    ticket_id='T-1001',
    recipient='manager@university.edu',
    sla_breach_type='response_time',
    time_remaining='15 minutes'
)

# Satisfaction survey
send_satisfaction_survey(
    ticket_id='T-1001',
    recipient='student@university.edu',
    survey_link='https://university.edu/survey/123'
)
```

## Email Scheduler

### Scheduled Tasks

The scheduler runs four automated tasks:

| Task | Schedule | Description |
|------|----------|-------------|
| Satisfaction Surveys | Daily at 09:00 | Sends surveys for tickets resolved 1 day ago |
| Book Return Reminders | Daily at 08:00 | Reminds users 3 days before book due date |
| Overdue Book Notices | Daily at 10:00 | Notifies users with overdue library books |
| SLA Breach Alerts | Every 30 minutes | Checks support tickets approaching SLA breach |

### Starting the Scheduler

**Background mode (production):**

```bash
python -m university_system.scripts.email_scheduler_control start
```

**Foreground mode (debugging):**

```bash
python -m university_system.scripts.email_scheduler_control run
```

**Programmatic start:**

```python
from university_system.infrastructure.email.email_scheduler import start_scheduler

start_scheduler()  # Runs in a daemon thread
```

### Managing the Scheduler

```bash
# Check status
python -m university_system.scripts.email_scheduler_control status

# Stop scheduler
python -m university_system.scripts.email_scheduler_control stop
```

```python
from university_system.infrastructure.email.email_scheduler import (
    stop_scheduler,
    is_scheduler_running,
    get_scheduled_jobs
)

# Check status
if is_scheduler_running():
    jobs = get_scheduled_jobs()
    for job in jobs:
        print(f"Job: {job}")

# Graceful shutdown
stop_scheduler(timeout=10)
```

## Email Database & Logging

### Three-Table Storage Model

| Table | Purpose |
|-------|---------|
| `stored_emails` | Admin/storage view with all email metadata |
| `messages` | User inbox messages (sender_id, recipient_id, subject, body, is_read, sent_at) |
| `email_log` | Audit trail (recipient, subject, sent_date, status, extended metadata) |

### Email Flow

1. **Validation** - Check recipient format, subject, and body
2. **Store in `stored_emails`** - Full email record for admin access
3. **Create inbox entry** - If recipient has an account, create a `messages` row
4. **Resolve sender** - Map to a user ID (authenticated, real, or system user)
5. **Log to `email_log`** - Audit trail entry
6. **SMTP send** - If not in database-only mode, deliver via SMTP
7. **Return status** - Success or failure with details

### Querying Email Logs

```python
from university_system.infrastructure.email.email_db_utilities import (
    get_email_logs,
    get_email_stats
)

# Retrieve recent logs
logs = get_email_logs(limit=50)

# Get statistics
stats = get_email_stats()
```

### Fixing Inbox Issues

```python
from university_system.infrastructure.email.email_service import fix_inbox_display_issue

# Repair missing inbox messages
fix_inbox_display_issue()
```

## Admin Panel

The Email Admin panel (`infrastructure/email/admin.py`) provides a comprehensive management interface with:

- **Email Configuration** - View and modify SMTP settings
- **Email Logs** - Browse sent email history with filters
- **Template Management** - View and edit email templates
- **Scheduler Status** - Monitor scheduled task execution
- **Queue Management** - View and process pending emails
- **Statistics** - Email volume and delivery metrics

Access the admin panel through the main GUI's administration section.

## Notification Emails

### Audit Trail Integration

All emails are logged to the immutable audit log:

```python
# Automatically logged on send:
# Action: EMAIL_SEND
# Resource: recipient_email
# Metadata: subject, sender, cc, bcc, attachments, template_name
```

### Safe Logging

The `safe_log_email()` function handles schema mismatches gracefully by falling back from extended columns to basic columns, ensuring email logging never fails silently.

## Security

### Password Protection

- SMTP passwords are **never** stored in configuration files
- Passwords are stored in the system keyring or read from environment variables
- The `_SecureConfig` class prevents plaintext password storage

### Attachment Security

- Maximum attachment size: 10 MB (configurable)
- Attachments are validated before sending

### Rate Limiting

- Configurable delay between sends (`send_delay`: 1.0 seconds default)
- Maximum concurrent workers (`max_threads`: 3 default)
- Retry logic with configurable attempts and delays

### TLS Encryption

- TLS is enabled by default for SMTP connections
- Supports ports 25, 465 (SSL), and 587 (STARTTLS)

## Troubleshooting

### Emails Not Appearing in Inbox

1. Verify the recipient has a user account in the system
2. Run `fix_inbox_display_issue()` to repair missing inbox entries
3. Check the `email_log` table for delivery status

### SMTP Connection Failures

1. Verify SMTP server hostname and port
2. Check TLS settings match the server requirements
3. Verify credentials are stored correctly in keyring or environment
4. The system falls back to database-only mode if SMTP fails

### Scheduler Not Running

1. Check status: `python -m university_system.scripts.email_scheduler_control status`
2. Review logs for errors: `logs/app.log`
3. Ensure the `schedule` library is installed
4. Try running in foreground mode for debugging

### Schema Mismatch Errors

The email service handles schema mismatches gracefully with fallback column strategies. If errors persist:
1. Check the database migration status
2. Run the database initialization to create missing tables
3. The `safe_log_email()` function ensures logging continues even with schema issues

### High Email Volume

- Increase `max_threads` for more concurrent processing
- Adjust `send_delay` to reduce time between sends
- Use the queue system for batch operations
- Monitor the `email_log` table size and archive old entries
