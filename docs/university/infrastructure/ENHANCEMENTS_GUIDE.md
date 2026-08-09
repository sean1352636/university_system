# System Enhancements Guide

Comprehensive guide to the newly added monitoring, data management, and performance features.

## 📊 Observability & Monitoring

### 1. Application Metrics

**Location**: `university_system/infrastructure/monitoring/metrics.py`

Track performance metrics for any operation:

```python
from university_system.infrastructure.monitoring import track_operation, record_metric

# Decorator approach - tracks everything automatically
@track_operation('student_enrollment')
def enroll_student(student_id, course_id):
    # This function is now monitored:
    # - Response time (with percentiles)
    # - Success/failure count
    # - Active operations
    # - Error tracking
    pass

# Manual metric recording
record_metric('active_users', 150, 'gauge')
record_metric('login_attempts', 1, 'counter')
record_metric('database_query_time', 0.25, 'histogram')

# Get all metrics
from university_system.infrastructure.monitoring import get_metrics_collector

metrics = get_metrics_collector()
all_metrics = metrics.get_all_metrics()

print(f"Login attempts: {all_metrics['counters']['login_attempts']}")
print(f"Active users: {all_metrics['gauges']['active_users']}")
print(f"P95 response time: {all_metrics['histograms']['student_enrollment']['p95']}")
```

**Metric Types**:
- **Counters**: Incrementing values (login attempts, API calls, errors)
- **Gauges**: Current values (active users, queue sizes, memory usage)
- **Histograms**: Response times with percentiles (p50, p95, p99)

### 2. Health Checks

**Location**: `university_system/infrastructure/monitoring/health_checks.py`

Monitor system health in real-time:

```python
from university_system.infrastructure.monitoring import check_system_health

# Check all subsystems
health_status = check_system_health()

print(health_status['status'])  # 'healthy', 'degraded', or 'unhealthy'

# Check individual subsystems
for subsystem, result in health_status['checks'].items():
    print(f"{subsystem}: {result['status']}")
    if 'message' in result:
        print(f"  → {result['message']}")
```

**What's Monitored**:
- ✅ Database connectivity (connection test, WAL mode, size)
- ✅ Disk space (warning at 80%, critical at 90%)
- ✅ Email service availability
- ✅ Critical files existence

**Kubernetes/Docker Ready**:
```python
from university_system.infrastructure.monitoring import get_health_checker

health = get_health_checker()

# Readiness probe - can serve requests?
if health.check_readiness():
    # Application ready
    pass

# Liveness probe - is application alive?
if health.check_liveness():
    # Application alive
    pass
```

### 3. Alerting System

**Location**: `university_system/infrastructure/monitoring/alerts.py`

Send alerts for critical events:

```python
from university_system.infrastructure.monitoring import send_alert, AlertLevel

# Send different severity levels
send_alert(
    'database_connection_lost',
    AlertLevel.CRITICAL,
    'Cannot connect to database',
    {'error': 'Connection timeout after 30s'}
)

send_alert(
    'disk_space_low',
    AlertLevel.WARNING,
    'Disk space below 20%',
    {'free_gb': 5.2, 'total_gb': 50.0}
)

# Get alert history
from university_system.infrastructure.monitoring import get_alert_manager

alerts = get_alert_manager()
recent_alerts = alerts.get_alert_history(hours=24)
summary = alerts.get_alert_summary()

print(f"Total alerts (24h): {summary['total_alerts']}")
print(f"Critical alerts: {summary['by_level']['critical']}")
```

**Features**:
- Rate limiting (max 10 alerts per hour per type)
- Multiple channels (logs, email, webhooks)
- Anomaly detection (unusual logins, database errors)
- Alert history tracking

## 💾 Data Management

### 1. Automated Backup Scheduler

**Location**: `university_system/infrastructure/data_management/backup_scheduler.py`

Never lose data again with automated backups:

```python
from university_system.infrastructure.data_management import schedule_backups

# Start automated backups (runs in background)
scheduler = schedule_backups()

# Manual backup
result = scheduler.create_backup('manual')
print(f"Backup created: {result['backup_name']}")
print(f"Size: {result['size_mb']} MB")
print(f"Verified: {result['verified']}")

# List all backups
backups = scheduler.list_backups()
for backup in backups:
    print(f"{backup['name']} - {backup['size_mb']} MB - {backup['age_days']} days old")

# Get backup statistics
stats = scheduler.get_backup_stats()
print(f"Total backups: {stats['total_backups']}")
print(f"Total size: {stats['total_size_mb']} MB")
print(f"Oldest backup: {stats['oldest_backup']['name']}")
```

**Backup Schedule** (runs automatically):
- **Daily**: 02:00 (kept for 7 days)
- **Weekly**: Sunday at 03:00 (kept for 30 days)
- **Monthly**: 1st day at 04:00 (kept for 365 days)
- **Cleanup**: Daily at 05:00 (removes expired backups)

**Features**:
- Automatic backup verification (integrity check)
- Smart retention policies
- Space-efficient storage
- Non-blocking background scheduler

### 2. Backup Restoration

To restore from a backup:

```bash
# Stop the application first
make db-restore BACKUP_FILE=university_system/data/backups/backup_daily_20260201.db

# Or manually:
cp university_system/data/backups/backup_daily_20260201.db university_system/data/db_files/student_records.db
```

## 🚀 Performance Optimization

### 1. Caching Layer

**Location**: `university_system/infrastructure/performance/cache.py`

Speed up repeated operations with intelligent caching:

```python
from university_system.infrastructure.performance import cached, invalidate_cache

# Cache expensive calculations
@cached(ttl=600)  # Cache for 10 minutes
def get_student_gpa(student_id):
    # Expensive database query
    with get_connection() as conn:
        # ... complex query
        return gpa

# Custom cache key for better control
@cached(ttl=300, key_func=lambda sid: f"gpa:{sid}")
def get_student_gpa(student_id):
    return calculated_gpa

# First call - cache miss (queries database)
gpa1 = get_student_gpa(123)  # Takes 50ms

# Second call - cache hit (instant!)
gpa2 = get_student_gpa(123)  # Takes <1ms

# Invalidate cache when data changes
invalidate_cache('gpa:123')  # Clear specific pattern
invalidate_cache()            # Clear entire cache

# Get cache statistics
from university_system.infrastructure.performance import get_cache_manager

cache = get_cache_manager()
stats = cache.get_stats()
print(f"Hit rate: {stats['hit_rate_percent']}%")
print(f"Cache size: {stats['size']}/{stats['max_size']}")
```

**Pre-cached Operations**:
- `get_student_gpa(student_id)` - 10 minute cache
- `get_course_enrollment_count(course_id)` - 30 minute cache

**When to Invalidate Cache**:
```python
# After updating grades
def update_student_grade(student_id, grade):
    # ... update database
    invalidate_cache(f'gpa:{student_id}')  # Refresh GPA cache

# After student enrollment
def enroll_student(student_id, course_id):
    # ... enrollment logic
    invalidate_cache(f'course_enrollment:{course_id}')  # Refresh count
```

## 🎯 Integration Examples

### Example 1: Monitor Critical Operation

```python
from university_system.infrastructure.monitoring import track_operation
from university_system.infrastructure.monitoring import send_alert, AlertLevel
from university_system.infrastructure.performance import cached

@track_operation('grade_submission')
@cached(ttl=60)
def submit_grade(student_id, course_id, grade):
    try:
        # Submit grade to database
        result = _submit_to_db(student_id, course_id, grade)

        # Check for unusual grade changes
        if grade < 50 and previous_grade > 80:
            send_alert(
                'unusual_grade_change',
                AlertLevel.WARNING,
                f'Large grade drop detected for student {student_id}',
                {'old': previous_grade, 'new': grade}
            )

        return result

    except Exception as e:
        # Alert on critical errors
        send_alert(
            'grade_submission_failed',
            AlertLevel.ERROR,
            f'Failed to submit grade: {e}',
            {'student_id': student_id, 'course_id': course_id}
        )
        raise
```

### Example 2: Scheduled Health Check with Alerts

```python
import schedule
import time
from university_system.infrastructure.monitoring import (
    check_system_health,
    send_alert,
    AlertLevel
)

def check_health_and_alert():
    health = check_system_health()

    if health['status'] == 'unhealthy':
        send_alert(
            'system_unhealthy',
            AlertLevel.CRITICAL,
            'System health check failed!',
            health['checks']
        )
    elif health['status'] == 'degraded':
        send_alert(
            'system_degraded',
            AlertLevel.WARNING,
            'System performance degraded',
            health['checks']
        )

# Check health every 5 minutes
schedule.every(5).minutes.do(check_health_and_alert)

while True:
    schedule.run_pending()
    time.sleep(60)
```

## 📈 Dashboard Integration

Create a monitoring dashboard:

```python
from university_system.infrastructure.monitoring import (
    get_metrics_collector,
    get_health_checker,
    get_alert_manager
)

def get_system_dashboard():
    """Get comprehensive system status"""
    metrics = get_metrics_collector()
    health = get_health_checker()
    alerts = get_alert_manager()

    return {
        'health': health.check_all(),
        'metrics': metrics.get_all_metrics(),
        'alerts': alerts.get_alert_summary(),
        'timestamp': datetime.now().isoformat()
    }

# Use in web interface
dashboard_data = get_system_dashboard()
```

## 🔧 Configuration

### Backup Configuration

Edit retention periods in `backup_scheduler.py`:
```python
scheduler.retention = {
    'daily': 14,    # Keep daily backups for 2 weeks
    'weekly': 60,   # Keep weekly backups for 2 months
    'monthly': 730, # Keep monthly backups for 2 years
}
```

### Cache Configuration

Adjust cache size and TTL:
```python
from university_system.infrastructure.performance import get_cache_manager

cache = get_cache_manager()
cache._max_size = 5000      # Store up to 5000 items
cache._default_ttl = 600    # Default 10 minute expiration
```

### Alert Configuration

Configure alert thresholds:
```python
from university_system.infrastructure.monitoring import get_alert_manager

alerts = get_alert_manager()
alerts._thresholds = {
    'failed_logins_per_minute': 20,  # Increase threshold
    'disk_usage_percent': 85,         # Alert earlier
}
```

## 🚀 Getting Started

### 1. Initialize All Features

```bash
source venv/bin/activate
python initialize_enhancements.py
```

This will:
- ✅ Initialize monitoring
- ✅ Create initial backup
- ✅ Start backup scheduler
- ✅ Configure caching
- ✅ Run system tests

### 2. Verify Health

```bash
python -c "
from university_system.infrastructure.monitoring import check_system_health
health = check_system_health()
print(f'System status: {health[\"status\"]}')
"
```

### 3. Check Metrics

```bash
python -c "
from university_system.infrastructure.monitoring import get_metrics_collector
metrics = get_metrics_collector()
stats = metrics.get_all_metrics()
print('Metrics:', stats)
"
```

### 4. View Backups

```bash
python -c "
from university_system.infrastructure.data_management import get_backup_scheduler
scheduler = get_backup_scheduler()
backups = scheduler.list_backups()
print(f'Found {len(backups)} backups')
for b in backups:
    print(f'  - {b[\"name\"]} ({b[\"size_mb\"]} MB)')
"
```

## 📚 Additional Resources

- **Metrics**: See `infrastructure/monitoring/metrics.py` for all available metric types
- **Health Checks**: See `infrastructure/monitoring/health_checks.py` for check details
- **Backups**: See `infrastructure/data_management/backup_scheduler.py` for backup options
- **Caching**: See `infrastructure/performance/cache.py` for caching patterns

## 🎯 Best Practices

1. **Always use `@track_operation` for critical operations**
2. **Monitor health checks regularly** (every 5-15 minutes)
3. **Set up alerts for critical failures** (database, disk space)
4. **Invalidate cache after data modifications**
5. **Test backup restoration quarterly**
6. **Review metrics weekly** for performance trends

## Version

These enhancements are part of University Management System **v5.12.0**.

For previous enhancements, see [CHANGELOG.md](../../../../CHANGELOG.md).
