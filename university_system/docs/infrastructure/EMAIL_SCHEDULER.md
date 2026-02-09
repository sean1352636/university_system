# Email Scheduler

The University Management System includes an automated email scheduler that handles periodic email tasks.

## Features

The scheduler automatically handles the following tasks:

### Daily Tasks

1. **Satisfaction Surveys** (09:00 daily)
   - Sends satisfaction surveys to users whose support tickets were resolved in the last 24 hours
   - Only sends to tickets that haven't received surveys yet
   - Uses template: `satisfaction_survey.txt`

2. **Book Return Reminders** (08:00 daily)
   - Sends reminders to users with library books due in 3 days
   - Only sends one reminder per book per day
   - Helps reduce overdue returns

3. **Overdue Book Notifications** (10:00 daily)
   - Sends notifications for books that are currently overdue
   - Includes days overdue count
   - Only sends one notification per book per day

### Periodic Tasks

4. **SLA Breach Alerts** (Every 30 minutes)
   - Checks for support tickets that have exceeded their SLA due date
   - Sends alerts to assigned staff and department managers
   - Only alerts for tickets not yet resolved or closed
   - Prevents duplicate alerts within 1 hour

## Installation & Setup

### Basic Usage

#### Start the Scheduler (Background)

```bash
python -m university_system.utils.email_scheduler_control start
```

#### Check Scheduler Status

```bash
python -m university_system.utils.email_scheduler_control status
```

#### Stop the Scheduler

```bash
python -m university_system.utils.email_scheduler_control stop
```

#### Run in Foreground (Testing)

```bash
python -m university_system.utils.email_scheduler_control run
```

Or directly:

```bash
python -m university_system.infrastructure.email.email_scheduler
```

### Production Deployment - Systemd Service

For production environments, it's recommended to run the scheduler as a systemd service.

#### 1. Create Service File

Create `/etc/systemd/system/university-email-scheduler.service`:

```ini
[Unit]
Description=University Management System Email Scheduler
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/path/to/university_system
Environment="PYTHONPATH=/path/to/university_system"
ExecStart=/path/to/venv/bin/python -m university_system.infrastructure.email.email_scheduler
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Important**: Update the paths:
- `/path/to/university_system` → Your project directory
- `/path/to/venv/bin/python` → Your Python virtual environment

#### 2. Enable and Start the Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable university-email-scheduler

# Start the service
sudo systemctl start university-email-scheduler

# Check status
sudo systemctl status university-email-scheduler

# View logs
sudo journalctl -u university-email-scheduler -f
```

#### 3. Service Management

```bash
# Stop service
sudo systemctl stop university-email-scheduler

# Restart service
sudo systemctl restart university-email-scheduler

# Disable service
sudo systemctl disable university-email-scheduler
```

### Docker Deployment

If using Docker, add the scheduler as a separate service in `docker-compose.yml`:

```yaml
services:
  email-scheduler:
    build: .
    command: python -m university_system.infrastructure.email.email_scheduler
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - SMTP_HOST=${SMTP_HOST}
      - SMTP_PORT=${SMTP_PORT}
      - SMTP_USER=${SMTP_USER}
      - SMTP_PASSWORD=${SMTP_PASSWORD}
    restart: unless-stopped
    depends_on:
      - db
```

## Configuration

### Adjusting Schedule Times

Edit `university_system/infrastructure/email/email_scheduler.py`:

```python
def setup_schedules():
    """Configure all scheduled tasks"""

    # Adjust times as needed (24-hour format)
    schedule.every().day.at("09:00").do(send_daily_satisfaction_surveys)
    schedule.every().day.at("08:00").do(check_book_return_reminders)
    schedule.every().day.at("10:00").do(check_overdue_books)

    # Adjust frequency (minutes, hours, days)
    schedule.every(30).minutes.do(check_sla_breaches)
```

### Adjusting Book Reminder Lead Time

By default, reminders are sent 3 days before the due date. To change this, edit the `check_book_return_reminders()` function:

```python
# Change from 3 days to 5 days
reminder_date = (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d')
```

### Adjusting Satisfaction Survey Window

By default, surveys are sent for tickets resolved in the last day. To change this, edit the `setup_schedules()` function:

```python
# Send surveys for tickets resolved in last 2 days
schedule.every().day.at("09:00").do(lambda: send_bulk_satisfaction_surveys(days_old=2))
```

## Monitoring

### Logs

All scheduler activities are logged to:
- Application log files (via `logger`)
- Email log database table (`email_log`)
- System event log (via `log_event`)

### Check Recent Activity

```sql
-- Check recent scheduler emails
SELECT * FROM email_log
WHERE related_to LIKE '%Scheduler%'
ORDER BY sent_at DESC
LIMIT 20;

-- Check satisfaction surveys sent
SELECT * FROM email_log
WHERE subject LIKE '%Satisfaction Survey%'
ORDER BY sent_at DESC
LIMIT 10;

-- Check book reminders
SELECT * FROM email_log
WHERE subject LIKE '%Book Return Reminder%'
OR subject LIKE '%OVERDUE%'
ORDER BY sent_at DESC
LIMIT 10;

-- Check SLA alerts
SELECT * FROM email_log
WHERE subject LIKE '%SLA Alert%'
ORDER BY sent_at DESC
LIMIT 10;
```

## Troubleshooting

### Scheduler Won't Start

1. Check if another instance is running:
   ```bash
   python -m university_system.utils.email_scheduler_control status
   ```

2. Check for port conflicts or database locks

3. Verify database connectivity:
   ```bash
   python -c "from university_system.infrastructure.database.db import get_connection; get_connection()"
   ```

### Emails Not Sending

1. Check SMTP configuration in `.env` file
2. Verify email templates exist in `data/email_templates/`
3. Check email queue worker threads are running
4. Review logs for specific errors

### High CPU Usage

If the scheduler is using too much CPU:

1. Increase the sleep interval (default is 60 seconds):
   ```python
   # In _run_scheduler_loop() or run_scheduler()
   time.sleep(120)  # Check every 2 minutes instead
   ```

2. Reduce SLA check frequency:
   ```python
   schedule.every(60).minutes.do(check_sla_breaches)  # Check every hour
   ```

## Integration with Main Application

### Auto-start with Flask App

Add to your Flask app initialization:

```python
from university_system.infrastructure.email.email_scheduler import start_scheduler

@app.before_first_request
def start_email_scheduler():
    start_scheduler()
```

### Auto-start with CLI

Add to your main CLI entry point:

```python
from university_system.infrastructure.email.email_scheduler import start_scheduler
import atexit

# Start scheduler
start_scheduler()

# Ensure cleanup on exit
atexit.register(stop_scheduler)
```

## Manual Task Execution

You can manually trigger any scheduled task for testing:

```python
from university_system.infrastructure.email.email_scheduler import (
    send_daily_satisfaction_surveys,
    check_book_return_reminders,
    check_overdue_books,
    check_sla_breaches
)

# Run manually
send_daily_satisfaction_surveys()
check_book_return_reminders()
check_overdue_books()
check_sla_breaches()
```

## Best Practices

1. **Production**: Always run as a systemd service or Docker container
2. **Development**: Use `run` command in foreground for testing
3. **Monitoring**: Set up log monitoring/alerts for scheduler errors
4. **Testing**: Test schedule changes in development before deploying
5. **Email Limits**: Be aware of your SMTP provider's rate limits
6. **Database**: Ensure regular database backups before scheduler runs
7. **Timezone**: Scheduler uses system timezone - ensure it's set correctly

## Security Considerations

1. **Credentials**: Never commit SMTP credentials to version control
2. **Permissions**: Run service with minimum required permissions
3. **Database**: Ensure scheduler has read-only access where possible
4. **Logs**: Rotate logs regularly to prevent disk space issues
5. **Email Content**: Ensure no sensitive data is logged in email bodies

## Future Enhancements

Potential improvements for future versions:

- Web UI for managing scheduled tasks
- Dynamic schedule configuration via database
- Email rate limiting and throttling
- Batch processing for large volumes
- Multi-server coordination
- Health check endpoints
- Prometheus metrics export
- Slack/Teams notifications for failures
