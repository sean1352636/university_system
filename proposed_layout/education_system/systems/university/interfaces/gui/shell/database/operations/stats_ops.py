"""Backup statistics and log utilities."""
import datetime

from education_system.systems.university.interfaces.gui.shell.database.shared_imports import LOG_DIR, logger
from education_system.systems.university.interfaces.gui.shell.database.metadata import metadata_manager


def generate_backup_statistics():
    """Generate comprehensive backup statistics"""
    try:
        backups = metadata_manager.get_backups()

        stats = {
            'total_backups': len(backups),
            'total_size': sum(b.get("size", 0) for b in backups),
            'backup_types': {},
            'average_size': 0,
            'recent_activity': 0,
            'storage_usage': {}
        }

        if backups:
            # Backup type distribution
            for backup in backups:
                backup_type = backup.get('backup_type', 'unknown')
                stats['backup_types'][backup_type] = stats['backup_types'].get(backup_type, 0) + 1

            # Average size
            stats['average_size'] = stats['total_size'] / len(backups)

            # Recent activity (last 30 days)
            thirty_days_ago = datetime.datetime.now() - datetime.timedelta(days=30)
            recent_backups = []

            for backup in backups:
                try:
                    backup_date = datetime.datetime.strptime(backup["timestamp"], "%Y%m%d_%H%M%S")
                    if backup_date >= thirty_days_ago:
                        recent_backups.append(backup)
                except (ValueError, KeyError):
                    pass

            stats['recent_activity'] = len(recent_backups)

            # Storage usage by month
            monthly_usage = {}
            for backup in backups:
                try:
                    backup_date = datetime.datetime.strptime(backup["timestamp"], "%Y%m%d_%H%M%S")
                    month_key = backup_date.strftime("%Y-%m")
                    monthly_usage[month_key] = monthly_usage.get(month_key, 0) + backup.get("size", 0)
                except (ValueError, KeyError):
                    pass

            stats['storage_usage'] = monthly_usage

        # Update metadata with statistics
        metadata_manager.update_statistics(stats)

        return stats

    except Exception as e:
        logger.error(f"Error generating backup statistics: {e}")
        return {'total_backups': 0, 'total_size': 0, 'average_size': 0,
                'recent_activity': 0, 'backup_types': {}, 'storage_usage': {}}

def get_log_file(filename):
    """Get log file path using centralized LOG_DIR"""
    # Use centralized LOG_DIR from paths module
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return LOG_DIR / filename
