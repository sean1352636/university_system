"""Backup comparison, validation, and statistics."""

import datetime
import os
import tempfile

from education_system.post_18.university_system.infrastructure.database.db import get_connection, sqlite3
from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging
from education_system.post_18.university_system.infrastructure.database.data_backup.config import config
from education_system.post_18.university_system.infrastructure.database.data_backup.metadata import metadata_manager
from education_system.post_18.university_system.infrastructure.database.data_backup.security import (
    calculate_file_hash,
    decrypt_file,
)
from education_system.post_18.university_system.infrastructure.database.data_backup.compression import decompress_file
from education_system.post_18.university_system.infrastructure.database.data_backup.operations import validate_table_name

logger = configure_logging(name=__name__)


# ── Backup comparison ─────────────────────────────────────────────────────────

def compare_backups(backup1_path, backup2_path):
    """Compare two backup files and return differences"""
    try:
        differences = {
            "tables_added": [],
            "tables_removed": [],
            "tables_modified": [],
            "record_changes": {}
        }

        conn1 = get_connection(db_path=backup1_path, row_factory=False)
        conn2 = get_connection(db_path=backup2_path, row_factory=False)

        # Get table lists
        tables1 = set(get_database_tables_from_connection(conn1))
        tables2 = set(get_database_tables_from_connection(conn2))

        differences["tables_added"] = list(tables2 - tables1)
        differences["tables_removed"] = list(tables1 - tables2)

        # Check common tables for changes
        common_tables = tables1 & tables2

        for table in common_tables:
            changes = compare_table_data(conn1, conn2, table)
            if changes["records_added"] or changes["records_removed"] or changes["records_modified"]:
                differences["tables_modified"].append(table)
                differences["record_changes"][table] = changes

        conn1.close()
        conn2.close()

        return differences

    except sqlite3.Error as e:
        logger.error(f"Database error comparing backups: {e}")
        return None
    except (OSError, IOError) as e:
        logger.error(f"I/O error comparing backups: {e}")
        return None


def get_database_tables_from_connection(conn):
    """Get table list from database connection"""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    return [row[0] for row in cursor.fetchall()]


def compare_table_data(conn1, conn2, table):
    """Compare data in a specific table between two databases"""
    try:
        # Validate table name to prevent SQL injection
        validate_table_name(table, conn1)
        validate_table_name(table, conn2)

        changes = {
            "records_added": 0,
            "records_removed": 0,
            "records_modified": 0
        }

        # Get row counts (simplified comparison)
        cursor1 = conn1.cursor()
        cursor2 = conn2.cursor()

        # Table name validated above - use bracket quoting for safety
        cursor1.execute("SELECT COUNT(*) FROM [" + table + "]")
        count1 = cursor1.fetchone()[0]

        cursor2.execute("SELECT COUNT(*) FROM [" + table + "]")
        count2 = cursor2.fetchone()[0]

        # This is a simplified comparison
        # A full implementation would compare actual record contents
        if count2 > count1:
            changes["records_added"] = count2 - count1
        elif count1 > count2:
            changes["records_removed"] = count1 - count2

        return changes

    except ValueError as ve:
        logger.error(f"Invalid table name comparing table data: {ve}")
        return {"records_added": 0, "records_removed": 0, "records_modified": 0}
    except sqlite3.Error as e:
        logger.error(f"Database error comparing table data: {e}")
        return {"records_added": 0, "records_removed": 0, "records_modified": 0}


# ── Backup validation ─────────────────────────────────────────────────────────

def validate_backup(backup_path):
    """Validate backup file integrity and restorability"""
    try:
        validation_results = {
            "file_exists": False,
            "file_readable": False,
            "database_valid": False,
            "tables_accessible": False,
            "hash_verified": False,
            "errors": []
        }

        # Check if file exists
        if os.path.exists(backup_path):
            validation_results["file_exists"] = True
        else:
            validation_results["errors"].append("Backup file does not exist")
            return validation_results

        # Check if file is readable
        try:
            with open(backup_path, 'rb') as f:
                f.read(1024)  # Try to read first 1KB
            validation_results["file_readable"] = True
        except (OSError, IOError, PermissionError) as e:
            validation_results["errors"].append(f"File read error: {e}")
            return validation_results

        # For encrypted/compressed files, we'd need to process them first
        test_file = backup_path
        temp_files = []

        try:
            # Handle encrypted files
            if backup_path.endswith('.encrypted'):
                if config["encryption_password"]:
                    fd, temp_decrypt = tempfile.mkstemp(suffix='.db')
                    os.close(fd)
                    test_file = decrypt_file(backup_path, config["encryption_password"], temp_decrypt)
                    temp_files.append(temp_decrypt)
                else:
                    validation_results["errors"].append("Cannot validate encrypted backup without password")
                    return validation_results

            # Handle compressed files
            if test_file and test_file.endswith(('.gz', '.zip')):
                fd, temp_decompress = tempfile.mkstemp(suffix='.db')
                os.close(fd)
                test_file = decompress_file(test_file, temp_decompress)
                temp_files.append(temp_decompress)

            if not test_file:
                validation_results["errors"].append("Failed to prepare backup file for validation")
                return validation_results

            # Test database connectivity
            try:
                conn = get_connection(db_path=test_file, row_factory=False)
                cursor = conn.cursor()

                # Try to get table list
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()

                validation_results["database_valid"] = True

                # Try to access each table
                table_errors = []
                for table_row in tables:
                    table_name = table_row[0]
                    try:
                        # Validate table name to prevent SQL injection
                        validate_table_name(table_name, conn)
                        # Table name validated above - use bracket quoting for safety
                        cursor.execute("SELECT COUNT(*) FROM [" + table_name + "]")
                        cursor.fetchone()
                    except ValueError as ve:
                        table_errors.append(f"Invalid table {table_name}: {ve}")
                    except sqlite3.Error as e:
                        table_errors.append(f"Table {table_name}: {e}")

                if not table_errors:
                    validation_results["tables_accessible"] = True
                else:
                    validation_results["errors"].extend(table_errors)

                conn.close()

            except sqlite3.Error as e:
                validation_results["errors"].append(f"Database validation error: {e}")

            # Verify file hash if available
            backup_metadata = None
            for backup in metadata_manager.get_backups():
                if backup["path"] == backup_path:
                    backup_metadata = backup
                    break

            if backup_metadata and "file_hash" in backup_metadata:
                current_hash = calculate_file_hash(test_file)
                if current_hash == backup_metadata["file_hash"]:
                    validation_results["hash_verified"] = True
                else:
                    validation_results["errors"].append("File hash mismatch - backup may be corrupted")

        finally:
            # Clean up temporary files
            for temp_file in temp_files:
                try:
                    os.remove(temp_file)
                except (OSError, FileNotFoundError) as e:
                    logger.debug(f"Failed to remove temporary file {temp_file}: {e}")
                    pass

        return validation_results

    except (OSError, IOError) as e:
        logger.error(f"I/O error validating backup: {e}")
        return {"errors": [str(e)]}
    except (KeyError, TypeError) as e:
        logger.error(f"Data error validating backup: {e}")
        return {"errors": [str(e)]}


# ── Statistics ────────────────────────────────────────────────────────────────

def generate_backup_statistics():
    """Generate comprehensive backup statistics"""
    try:
        backups = metadata_manager.get_backups()

        stats = {
            "total_backups": len(backups),
            "total_size": sum(b.get("size", 0) for b in backups),
            "backup_types": {},
            "success_rate": 0,
            "average_size": 0,
            "storage_usage": {},
            "recent_activity": []
        }

        if backups:
            # Backup type distribution
            for backup in backups:
                backup_type = backup.get("backup_type", "unknown")
                stats["backup_types"][backup_type] = stats["backup_types"].get(backup_type, 0) + 1

            # Average size
            stats["average_size"] = stats["total_size"] / len(backups)

            # Recent activity (last 30 days)
            thirty_days_ago = datetime.datetime.now() - datetime.timedelta(days=30)
            recent_backups = []

            for backup in backups:
                try:
                    backup_date = datetime.datetime.strptime(backup["timestamp"], "%Y%m%d_%H%M%S")
                    if backup_date >= thirty_days_ago:
                        recent_backups.append(backup)
                except (ValueError, KeyError, TypeError) as e:
                    logger.debug(f"Failed to parse backup timestamp for statistics: {e}")
                    pass

            stats["recent_activity"] = len(recent_backups)

            # Storage usage by month
            monthly_usage = {}
            for backup in backups:
                try:
                    backup_date = datetime.datetime.strptime(backup["timestamp"], "%Y%m%d_%H%M%S")
                    month_key = backup_date.strftime("%Y-%m")
                    monthly_usage[month_key] = monthly_usage.get(month_key, 0) + backup.get("size", 0)
                except (ValueError, KeyError, TypeError) as e:
                    logger.debug(f"Failed to calculate monthly usage for backup: {e}")
                    pass

            stats["storage_usage"] = monthly_usage

        # Update metadata with statistics
        metadata_manager.update_statistics(stats)

        return stats

    except (KeyError, TypeError, AttributeError) as e:
        logger.error(f"Error processing backup data for statistics: {e}")
        return {}
    except ZeroDivisionError as e:
        logger.error(f"Error calculating backup statistics: {e}")
        return {}
