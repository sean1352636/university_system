# Admin Monitoring Guide

Quick guide for system administrators to access and use monitoring features.

## 🔐 Access Requirements

- **Role**: Admin
- **Interface**: CLI (Command Line Interface)
- **Credentials**: Admin username and password

## 🚀 Quick Access

### 1. Launch CLI

```bash
source venv/bin/activate
python run.py --cli
```

### 2. Login as Admin

```
Username: admin
Password: [your admin password]
```

### 3. Access Monitoring

From the main menu, look for:
```
📱 INFRASTRUCTURE & SYSTEM
   ...
   [N]. System Monitoring    <-- Select this number
```

## 📊 Monitoring Menu Options

### 1️⃣ View System Health

**What it shows:**
- Overall system status (Healthy/Degraded/Unhealthy)
- Database connectivity and performance
- Disk space usage (warnings at 80%, critical at 90%)
- Email service availability
- Critical files validation

**Example Output:**
```
✅ Overall Status: HEALTHY

Subsystem Health:
  ✅ Database: healthy
     Response time: 12.45ms
     Database size: 11.6 MB

  ✅ Disk Space: healthy
     Free space: 42.8 GB / 50.0 GB
     Used: 14.4%

  ⚠️  Email Service: degraded
     Email service not configured (optional)

  ✅ Critical Files: healthy
     All critical files exist
```

**When to check:** Daily, or when users report issues

---

### 2️⃣ View Application Metrics

**What it shows:**
- Operation counters (login attempts, API calls)
- Current gauge values (active users, queue sizes)
- Response time statistics (p50, p95, p99 percentiles)
- Active operations
- Error rates per operation

**Example Output:**
```
📊 Counters:
  login.attempts: 45
  student_enrollment.success: 12
  grade_submission.attempts: 89

📈 Gauges (Current Values):
  active_users: 23.00
  database_connections: 3.00

⏱️  Response Times:
  student_enrollment:
    Count: 12
    Average: 0.25s
    P50: 0.21s
    P95: 0.45s
    P99: 0.78s
```

**When to check:** To identify slow operations or high error rates

---

### 3️⃣ View Recent Alerts

**What it shows:**
- Last 24 hours of system alerts
- Alerts by severity (INFO, WARNING, ERROR, CRITICAL)
- Recent critical alerts
- Alert timestamps and messages

**Example Output:**
```
Total Alerts: 3

By Severity:
  ⚠️  WARNING: 2
  ❌ ERROR: 1

📋 All Recent Alerts (last 10):
  ⚠️  WARNING: disk_space_low
      Time: 2026-02-01T22:15:30
      Disk space below 20%

  ❌ ERROR: database_connection_slow
      Time: 2026-02-01T22:30:45
      Database response time >5 seconds
```

**When to check:** Daily, or when system issues occur

---

### 4️⃣ Backup Management

**What it shows:**
- Total number of backups
- Total backup storage size
- Backups by type (manual, daily, weekly, monthly)
- Recent backups with age and size
- Backup schedule information

**Example Output:**
```
📦 Total Backups: 5
💾 Total Size: 58.0 MB

Backups by Type:
  MANUAL: 1 backups, 11.6 MB
  DAILY: 3 backups, 34.8 MB
  WEEKLY: 1 backups, 11.6 MB

Recent Backups (last 10):
Name                                          Type       Size    Age
backup_manual_20260201_223015.db              manual     11.6 MB  0d
backup_daily_20260201_020000.db               daily      11.6 MB  0d
backup_daily_20260131_020000.db               daily      11.6 MB  1d

Backup Schedule:
  • Daily at 02:00 (kept 7 days)
  • Weekly on Sunday at 03:00 (kept 30 days)
  • Monthly on 1st at 04:00 (kept 365 days)
```

**When to check:** Weekly, or before major system changes

---

### 5️⃣ Cache Statistics

**What it shows:**
- Current cache size and capacity
- Cache hit rate percentage
- Total requests, hits, misses
- Number of evictions
- Cache effectiveness rating

**Example Output:**
```
📊 Cache Usage:
  Current Size: 234 / 1000 items
  Usage: 23.4%

📈 Performance:
  Total Requests: 1,247
  Hits: 989
  Misses: 258
  Hit Rate: 79.31%

⚙️  Operations:
  Sets: 258
  Evictions: 24

💡 Cache Effectiveness:
  ⚠️  Good (60-80% hit rate)
```

**When to check:** When investigating performance issues

---

### 6️⃣ Performance Monitoring

**What it shows:**
- Slowest operations ranked by P95 response time
- Operations with errors
- Performance dashboard

**Example Output:**
```
⏱️  Slowest Operations (P95 response time):
  ⚠️  grade_calculation: 2.450s
  ✅ student_lookup: 0.125s
  ✅ course_enrollment: 0.089s

⚠️  Operations with Errors:
  ⚠️  database_query: 2.50 errors/minute

  ✅ No other errors detected
```

**When to check:** When users report slow performance

---

### 7️⃣ Create Manual Backup

**What it does:**
- Creates an immediate backup of the database
- Verifies backup integrity
- Shows backup details (name, size, location)

**Example Session:**
```
Create a backup now? (y/n): y

📦 Creating backup...

✅ Backup created successfully!
   Name: backup_manual_20260201_225530.db
   Size: 11.6 MB
   Verified: Yes
   Location: university_system/data/backups/backup_manual_20260201_225530.db
```

**When to use:** Before major changes, migrations, or bulk operations

---

### 8️⃣ Clear Cache

**What it does:**
- Clears all cached items
- Useful when cache contains stale data
- Confirms before clearing

**Example Session:**
```
Current cache size: 234 items

⚠️  Are you sure you want to clear the entire cache? (y/n): y

✅ Cache cleared successfully!
   All cached items have been removed.
```

**When to use:** After bulk data updates or when cache seems stale

---

## 🔔 Alert Levels Explained

| Level | Icon | Meaning | Action Required |
|-------|------|---------|----------------|
| INFO | ℹ️  | Informational | No action needed |
| WARNING | ⚠️  | Potential issue | Monitor closely |
| ERROR | ❌ | Operation failed | Investigate soon |
| CRITICAL | 🚨 | System failure | Immediate action |

## 📈 Performance Benchmarks

### Response Times (Good Targets)
- ✅ **Excellent**: <0.5s (P95)
- ⚠️  **Acceptable**: 0.5-2s (P95)
- ❌ **Needs Optimization**: >2s (P95)

### Cache Hit Rate
- ✅ **Excellent**: ≥80%
- ⚠️  **Good**: 60-80%
- ⚠️  **Fair**: 40-60%
- ❌ **Poor**: <40%

### Disk Space
- ✅ **Healthy**: <80% used
- ⚠️  **Warning**: 80-90% used
- ❌ **Critical**: >90% used

## 🛠️ Common Admin Tasks

### Daily Health Check
```
1. Login as admin
2. Select "System Monitoring"
3. Choose "1. View System Health"
4. Check all subsystems are healthy
5. Return to main menu
```

### Weekly Backup Verification
```
1. Login as admin
2. Select "System Monitoring"
3. Choose "4. Backup Management"
4. Verify recent backups exist
5. Check total backup size is reasonable
6. Optional: Create manual backup before weekend
```

### Performance Investigation
```
1. Login as admin
2. Select "System Monitoring"
3. Choose "6. Performance Monitoring"
4. Identify slow operations
5. Check error rates
6. Review cache hit rate (option 5)
7. Clear cache if needed (option 8)
```

### Pre-Maintenance Checklist
```
□ Create manual backup (option 7)
□ Check system health (option 1)
□ Review recent alerts (option 3)
□ Note current metrics (option 2)
□ Proceed with maintenance
□ Re-check health after maintenance
```

## 🚨 Troubleshooting

### Problem: High disk usage (>80%)
**Solution:**
1. Check backup management (old backups to clean?)
2. Review log files in `logs/` directory
3. Check database size
4. Clean old backups: Automatically done at 05:00 daily

### Problem: Low cache hit rate (<40%)
**Solution:**
1. Check if cache TTL is too short
2. Verify frequently accessed data is being cached
3. Consider increasing cache size
4. Review application code for cache usage

### Problem: Slow response times
**Solution:**
1. Check performance monitoring for slowest operations
2. Review database connection pool usage
3. Check disk space (slow I/O when disk full)
4. Consider adding more caching
5. Review error rates for failed queries

### Problem: System unhealthy status
**Solution:**
1. Check each subsystem individually
2. Database issues: Check connection, disk space
3. Disk space issues: Clean old files/backups
4. Review recent alerts for clues
5. Check application logs in `logs/app.log`

## 📝 Best Practices

1. **Check health daily** - Quick 30-second check each morning
2. **Review alerts daily** - Don't let issues accumulate
3. **Monitor metrics weekly** - Track performance trends
4. **Verify backups weekly** - Ensure backup system is working
5. **Test backup restoration quarterly** - Verify backups are restorable
6. **Create manual backup before major changes** - Safety first
7. **Clear cache after bulk data updates** - Prevent stale data
8. **Document unusual patterns** - Help diagnose recurring issues

## 🎓 Quick Reference Card

```
┌─────────────────────────────────────────────────────┐
│         ADMIN MONITORING QUICK REFERENCE            │
├─────────────────────────────────────────────────────┤
│ Daily:                                              │
│  → Check system health (option 1)                   │
│  → Review alerts (option 3)                         │
│                                                     │
│ Weekly:                                             │
│  → Verify backups (option 4)                        │
│  → Check metrics (option 2)                         │
│  → Review performance (option 6)                    │
│                                                     │
│ Before Major Changes:                               │
│  → Create manual backup (option 7)                  │
│  → Check system health (option 1)                   │
│                                                     │
│ When Issues Occur:                                  │
│  → Check alerts (option 3)                          │
│  → Review performance (option 6)                    │
│  → Check cache stats (option 5)                     │
│                                                     │
│ Emergency:                                          │
│  → Create backup immediately (option 7)             │
│  → Check system health (option 1)                   │
│  → Document all alerts (option 3)                   │
└─────────────────────────────────────────────────────┘
```

## 📞 Support

For issues not resolved by monitoring tools:
- Check logs in `logs/app.log`
- Review `ENHANCEMENTS_GUIDE.md` for detailed documentation
- Check `CHANGELOG.md` for recent changes

---

**Version**: University Management System v5.12.0
**Last Updated**: 2026-02-01
