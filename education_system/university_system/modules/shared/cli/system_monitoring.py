"""
System monitoring for CLI system.

Handles system health checks, performance metrics, backups, and monitoring.
"""

from .imports import (
    logging, sqlite3, datetime, os, DB_PATH, logger, _t,
    log_activity, get_auth, paths
)

auth = None

def get_db_connection():
    """Get database connection"""
    return sqlite3.connect(DB_PATH)


def view_system_health():
    """Display system health status"""
    try:
        from education_system.university_system.infrastructure.monitoring import check_system_health

        print("\n" + "="*80)
        print("SYSTEM HEALTH CHECK".center(80))
        print("="*80)

        health = check_system_health()

        # Overall status
        status_icon = {
            'healthy': '✅',
            'degraded': '⚠️ ',
            'unhealthy': '❌',
            'unknown': '❓'
        }
        icon = status_icon.get(health['status'], '❓')
        print(f"\n{icon} Overall Status: {health['status'].upper()}")
        print(f"   Timestamp: {health['timestamp']}")

        # Individual checks
        print("\nSubsystem Health:")
        print("-" * 80)
        for subsystem, result in health['checks'].items():
            status = result.get('status', 'unknown')
            icon = status_icon.get(status, '❓')
            print(f"  {icon} {subsystem.replace('_', ' ').title()}: {status}")

            if 'message' in result:
                print(f"     → {result['message']}")

            # Show additional details for specific checks
            if subsystem == 'database' and status == 'healthy':
                if 'response_time_ms' in result:
                    print(f"     Response time: {result['response_time_ms']:.2f}ms")
                if 'db_size_mb' in result:
                    print(f"     Database size: {result['db_size_mb']} MB")

            elif subsystem == 'disk_space':
                if 'free_gb' in result:
                    print(f"     Free space: {result['free_gb']:.2f} GB / {result['total_gb']:.2f} GB")
                    print(f"     Used: {result['percent_used']:.1f}%")

        print("="*80)

    except Exception as e:
        print(f"\n❌ Error checking system health: {e}")

    input("\nPress Enter to continue...")


def view_application_metrics():
    """Display application metrics"""
    try:
        from education_system.university_system.infrastructure.monitoring import get_metrics_collector

        print("\n" + "="*80)
        print("APPLICATION METRICS".center(80))
        print("="*80)

        metrics = get_metrics_collector()
        all_metrics = metrics.get_all_metrics()

        # Counters
        if all_metrics.get('counters'):
            print("\n📊 Counters:")
            print("-" * 80)
            for metric, value in sorted(all_metrics['counters'].items()):
                print(f"  {metric}: {value}")

        # Gauges
        if all_metrics.get('gauges'):
            print("\n📈 Gauges (Current Values):")
            print("-" * 80)
            for metric, value in sorted(all_metrics['gauges'].items()):
                print(f"  {metric}: {value:.2f}")

        # Histograms (Response Times)
        if all_metrics.get('histograms'):
            print("\n⏱️  Response Times:")
            print("-" * 80)
            for metric, stats in sorted(all_metrics['histograms'].items()):
                if stats:
                    print(f"\n  {metric}:")
                    print(f"    Count: {stats.get('count', 0)}")
                    print(f"    Average: {stats.get('avg', 0):.2f}s")
                    print(f"    P50: {stats.get('p50', 0):.2f}s")
                    print(f"    P95: {stats.get('p95', 0):.2f}s")
                    print(f"    P99: {stats.get('p99', 0):.2f}s")
                    print(f"    Min: {stats.get('min', 0):.2f}s")
                    print(f"    Max: {stats.get('max', 0):.2f}s")

        # Active Operations
        if all_metrics.get('active_operations'):
            print("\n🔄 Active Operations:")
            print("-" * 80)
            for operation, count in sorted(all_metrics['active_operations'].items()):
                if count > 0:
                    print(f"  {operation}: {count}")

        # Error Rates
        if all_metrics.get('error_rates'):
            print("\n⚠️  Error Rates (per minute):")
            print("-" * 80)
            for operation, rate in sorted(all_metrics['error_rates'].items()):
                if rate > 0:
                    print(f"  {operation}: {rate:.2f}")

        print("="*80)

    except Exception as e:
        print(f"\n❌ Error retrieving metrics: {e}")

    input("\nPress Enter to continue...")


def view_recent_alerts():
    """Display recent system alerts"""
    try:
        from education_system.university_system.infrastructure.monitoring import get_alert_manager

        print("\n" + "="*80)
        print("RECENT SYSTEM ALERTS (Last 24 Hours)".center(80))
        print("="*80)

        alerts = get_alert_manager()
        summary = alerts.get_alert_summary()

        print(f"\nTotal Alerts: {summary['total_alerts']}")

        if summary['by_level']:
            print("\nBy Severity:")
            print("-" * 80)
            for level, count in summary['by_level'].items():
                level_icon = {
                    'info': 'ℹ️ ',
                    'warning': '⚠️ ',
                    'error': '❌',
                    'critical': '🚨'
                }
                icon = level_icon.get(level, '  ')
                print(f"  {icon} {level.upper()}: {count}")

        if summary['recent_critical']:
            print("\n🚨 Recent Critical Alerts:")
            print("-" * 80)
            for alert in summary['recent_critical'][-5:]:  # Last 5 critical
                print(f"\n  Type: {alert['type']}")
                print(f"  Time: {alert['timestamp']}")
                print(f"  Message: {alert['message']}")

        recent_alerts = alerts.get_alert_history(hours=24)
        if recent_alerts:
            print("\n📋 All Recent Alerts (last 10):")
            print("-" * 80)
            for alert in recent_alerts[-10:]:  # Last 10 alerts
                level_icon = {
                    'info': 'ℹ️ ',
                    'warning': '⚠️ ',
                    'error': '❌',
                    'critical': '🚨'
                }
                icon = level_icon.get(alert['level'], '  ')
                print(f"\n  {icon} {alert['level'].upper()}: {alert['type']}")
                print(f"      Time: {alert['timestamp']}")
                print(f"      {alert['message']}")

        print("="*80)

    except Exception as e:
        print(f"\n❌ Error retrieving alerts: {e}")

    input("\nPress Enter to continue...")


def manage_backups():
    """Manage system backups"""
    try:
        from education_system.university_system.infrastructure.data_management import get_backup_scheduler

        scheduler = get_backup_scheduler()

        print("\n" + "="*80)
        print("BACKUP MANAGEMENT".center(80))
        print("="*80)

        # Get backup stats
        stats = scheduler.get_backup_stats()
        backups = scheduler.list_backups()

        print(f"\n📦 Total Backups: {stats['total_backups']}")
        print(f"💾 Total Size: {stats['total_size_mb']:.2f} MB")

        if stats['by_type']:
            print("\nBackups by Type:")
            print("-" * 80)
            for backup_type, type_stats in stats['by_type'].items():
                print(f"  {backup_type.upper()}: {type_stats['count']} backups, {type_stats['size_mb']:.2f} MB")

        if backups:
            print("\n📋 Recent Backups (last 10):")
            print("-" * 80)
            print(f"{'Name':<45} {'Type':<10} {'Size':>10} {'Age':>8}")
            print("-" * 80)
            for backup in backups[:10]:
                name = backup['name'][:44]
                backup_type = backup['type'][:9]
                size = f"{backup['size_mb']:.1f} MB"
                age = f"{backup['age_days']}d"
                print(f"{name:<45} {backup_type:<10} {size:>10} {age:>8}")

        print("\n" + "="*80)
        print("Backup Schedule:")
        print("  • Daily at 02:00 (kept 7 days)")
        print("  • Weekly on Sunday at 03:00 (kept 30 days)")
        print("  • Monthly on 1st at 04:00 (kept 365 days)")
        print("="*80)

    except Exception as e:
        print(f"\n❌ Error managing backups: {e}")

    input("\nPress Enter to continue...")


def view_cache_statistics():
    """Display cache statistics"""
    try:
        from education_system.university_system.infrastructure.performance import get_cache_manager

        print("\n" + "="*80)
        print("CACHE STATISTICS".center(80))
        print("="*80)

        cache = get_cache_manager()
        stats = cache.get_stats()

        print(f"\n📊 Cache Usage:")
        print("-" * 80)
        print(f"  Current Size: {stats['size']} / {stats['max_size']} items")
        print(f"  Usage: {(stats['size'] / stats['max_size'] * 100):.1f}%")

        print(f"\n📈 Performance:")
        print("-" * 80)
        print(f"  Total Requests: {stats['total_requests']}")
        print(f"  Hits: {stats['hits']}")
        print(f"  Misses: {stats['misses']}")
        print(f"  Hit Rate: {stats['hit_rate_percent']:.2f}%")

        print(f"\n⚙️  Operations:")
        print("-" * 80)
        print(f"  Sets: {stats['sets']}")
        print(f"  Evictions: {stats['evictions']}")

        # Show effectiveness
        print(f"\n💡 Cache Effectiveness:")
        print("-" * 80)
        if stats['hit_rate_percent'] >= 80:
            print("  ✅ Excellent (≥80% hit rate)")
        elif stats['hit_rate_percent'] >= 60:
            print("  ⚠️  Good (60-80% hit rate)")
        elif stats['hit_rate_percent'] >= 40:
            print("  ⚠️  Fair (40-60% hit rate)")
        else:
            print("  ❌ Poor (<40% hit rate - consider adjusting TTL)")

        print("="*80)

    except Exception as e:
        print(f"\n❌ Error retrieving cache statistics: {e}")

    input("\nPress Enter to continue...")


def view_performance_monitoring():
    """Display performance monitoring dashboard"""
    try:
        from education_system.university_system.infrastructure.monitoring import get_metrics_collector

        print("\n" + "="*80)
        print("PERFORMANCE MONITORING DASHBOARD".center(80))
        print("="*80)

        metrics = get_metrics_collector()
        all_metrics = metrics.get_all_metrics()

        # Show top slowest operations
        if all_metrics.get('histograms'):
            print("\n⏱️  Slowest Operations (P95 response time):")
            print("-" * 80)

            operations = []
            for metric, stats in all_metrics['histograms'].items():
                if stats and stats.get('count', 0) > 0:
                    operations.append((metric, stats.get('p95', 0)))

            operations.sort(key=lambda x: x[1], reverse=True)

            for operation, p95 in operations[:10]:
                status = "✅" if p95 < 1.0 else "⚠️ " if p95 < 3.0 else "❌"
                print(f"  {status} {operation}: {p95:.3f}s")

        # Show error rates
        if all_metrics.get('error_rates'):
            print("\n⚠️  Operations with Errors:")
            print("-" * 80)
            has_errors = False
            for operation, rate in all_metrics['error_rates'].items():
                if rate > 0:
                    has_errors = True
                    status = "⚠️ " if rate < 5 else "❌"
                    print(f"  {status} {operation}: {rate:.2f} errors/minute")

            if not has_errors:
                print("  ✅ No errors detected")

        print("="*80)

    except Exception as e:
        print(f"\n❌ Error viewing performance data: {e}")

    input("\nPress Enter to continue...")


def create_manual_backup():
    """Create a manual backup"""
    try:
        from education_system.university_system.infrastructure.data_management import get_backup_scheduler

        print("\n" + "="*80)
        print("CREATE MANUAL BACKUP".center(80))
        print("="*80)

        confirm = input("\nCreate a backup now? (y/n): ").strip().lower()

        if confirm == 'y':
            print("\n📦 Creating backup...")

            scheduler = get_backup_scheduler()
            result = scheduler.create_backup('manual')

            if result['success']:
                print(f"\n✅ Backup created successfully!")
                print(f"   Name: {result['backup_name']}")
                print(f"   Size: {result['size_mb']} MB")
                print(f"   Verified: {'Yes' if result['verified'] else 'No'}")
                print(f"   Location: {result['backup_path']}")
            else:
                print(f"\n❌ Backup failed: {result.get('error')}")
        else:
            print("\n✅ Backup cancelled.")

        print("="*80)

    except Exception as e:
        print(f"\n❌ Error creating backup: {e}")

    input("\nPress Enter to continue...")


def clear_cache():
    """Clear the application cache"""
    try:
        from education_system.university_system.infrastructure.performance import get_cache_manager

        print("\n" + "="*80)
        print("CLEAR CACHE".center(80))
        print("="*80)

        cache = get_cache_manager()
        stats = cache.get_stats()

        print(f"\nCurrent cache size: {stats['size']} items")
        confirm = input("\n⚠️  Are you sure you want to clear the entire cache? (y/n): ").strip().lower()

        if confirm == 'y':
            cache.clear()
            print("\n✅ Cache cleared successfully!")
            print("   All cached items have been removed.")
        else:
            print("\n✅ Cache clear cancelled.")

        print("="*80)

    except Exception as e:
        print(f"\n❌ Error clearing cache: {e}")

    input("\nPress Enter to continue...")



def display_system_monitoring_menu(auth):
    """Display system monitoring, backup, and performance menu (admin only)"""
    if not auth or not auth.current_user or auth.current_user.get('role') != 'admin':
        print("\n❌ Access denied. This feature requires admin privileges.")
        input("Press Enter to continue...")
        return

    while True:
        print("\n" + "="*80)
        print("SYSTEM MONITORING & ADMINISTRATION".center(80))
        print("="*80)
        print("\n1. View System Health")
        print("2. View Application Metrics")
        print("3. View Recent Alerts")
        print("4. Backup Management")
        print("5. Cache Statistics")
        print("6. Performance Monitoring")
        print("7. Create Manual Backup")
        print("8. Clear Cache")
        print("9. Back to Main Menu")
        print("="*80)

        choice = input("\nEnter your choice: ").strip()

        if choice == '1':
            view_system_health()
        elif choice == '2':
            view_application_metrics()
        elif choice == '3':
            view_recent_alerts()
        elif choice == '4':
            manage_backups()
        elif choice == '5':
            view_cache_statistics()
        elif choice == '6':
            view_performance_monitoring()
        elif choice == '7':
            create_manual_backup()
        elif choice == '8':
            clear_cache()
        elif choice == '9':
            break
        else:
            print("\n❌ Invalid choice. Please try again.")
            input("Press Enter to continue...")


__all__ = [
    'view_system_health',
    'view_application_metrics',
    'view_recent_alerts',
    'manage_backups',
    'view_cache_statistics',
    'view_performance_monitoring',
    'create_manual_backup',
    'clear_cache',
    'display_system_monitoring_menu',
]
