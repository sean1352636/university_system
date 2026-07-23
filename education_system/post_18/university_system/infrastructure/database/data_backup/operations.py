"""Core backup operations: create, restore, and database helpers."""

import datetime
import os
import shutil
import tempfile
import time
from pathlib import Path

from education_system.post_18.university_system.core.paths import DEFAULT_DB_PATH
from education_system.post_18.university_system.infrastructure.database.db import DatabaseManager, get_connection, sqlite3
from education_system.post_18.university_system.core.sql_safety import (
    validate_table_name as _sql_validate_table_name,
    SQLIdentifierError,
)
from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging
from education_system.post_18.university_system.infrastructure.database.data_backup.config import config, ensure_backup_directory
from education_system.post_18.university_system.infrastructure.database.data_backup.metadata import metadata_manager
from education_system.post_18.university_system.infrastructure.database.data_backup.security import (
    calculate_file_hash,
    decrypt_file,
    encrypt_file,
)
from education_system.post_18.university_system.infrastructure.database.data_backup.compression import (
    compress_file,
    decompress_file,
)
from education_system.post_18.university_system.infrastructure.database.data_backup.storage.cloud import upload_to_aws_s3
from education_system.post_18.university_system.infrastructure.database.data_backup.storage.remote import (
    upload_to_ftp,
    upload_to_sftp,
)
from education_system.post_18.university_system.infrastructure.database.data_backup.notifications import notify_backup_result

logger = configure_logging(name=__name__)

# Import immutable audit logging for compliance
try:
    from education_system.post_18.university_system.infrastructure.security.audit_helpers import (
        safe_log_security_event,
        get_gui_context,
    )
    from education_system.post_18.university_system.infrastructure.security.immutable_audit_log import AuditAction
    IMMUTABLE_AUDIT_AVAILABLE = True
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False


# ── Database helpers ──────────────────────────────────────────────────────────

def get_database_tables() -> list:
    """Get list of all tables in the database"""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            return tables
    except sqlite3.Error as e:
        logger.error(f"Database error getting tables: {e}")
        return []
    except (OSError, IOError) as e:
        logger.error(f"I/O error accessing database: {e}")
        return []


def validate_table_name(table_name: str, connection=None) -> bool:
    """
    Validate that a table name exists in the database to prevent SQL injection.

    Args:
        table_name: The table name to validate
        connection: Optional database connection to use for validation

    Returns:
        bool: True if table name is valid, False otherwise

    Raises:
        ValueError: If table name is invalid
    """
    if connection:
        cursor = connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        valid_tables = [row[0] for row in cursor.fetchall()]
    else:
        valid_tables = get_database_tables()

    if table_name not in valid_tables:
        raise ValueError(f"Invalid table name: {table_name}. Not found in database.")

    return True


# ── Backup type creators ─────────────────────────────────────────────────────

def create_selective_backup(tables: list, backup_path: str) -> bool:
    """Create backup of selected tables only"""
    source_conn = None
    backup_conn = None
    try:
        source_conn = get_connection()
        backup_conn = get_connection(db_path=backup_path, row_factory=False)

        for table in tables:
            # Validate table name to prevent SQL injection
            validate_table_name(table, source_conn)

            # Copy table structure - using parameterized query
            cursor = source_conn.cursor()
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?;", (table,))
            create_sql = cursor.fetchone()

            if create_sql:
                backup_conn.execute(create_sql[0])

                # Copy table data - table name validated above via validate_table_name
                # Use bracket quoting for additional safety
                cursor.execute("SELECT * FROM [" + table + "]")
                rows = cursor.fetchall()

                if rows:
                    placeholders = ','.join(['?' for _ in range(len(rows[0]))])
                    backup_conn.executemany("INSERT INTO [" + table + "] VALUES (" + placeholders + ")", rows)

        backup_conn.commit()
        return True
    except ValueError as ve:
        logger.error(f"Invalid table name in selective backup: {ve}")
        return False
    except sqlite3.Error as e:
        logger.error(f"Database error creating selective backup: {e}")
        return False
    except (OSError, IOError) as e:
        logger.error(f"I/O error creating selective backup: {e}")
        return False
    finally:
        # Ensure connections are always closed
        if backup_conn:
            try:
                backup_conn.close()
            except sqlite3.Error as e:
                logger.warning(f"Error closing backup connection: {e}")
        if source_conn:
            try:
                source_conn.close()
            except sqlite3.Error as e:
                logger.warning(f"Error closing source connection: {e}")


def create_schema_only_backup(backup_path: str) -> bool:
    """Create backup of database schema only (no data)"""
    source_conn = None
    backup_conn = None
    try:
        source_conn = get_connection()
        backup_conn = get_connection(db_path=backup_path, row_factory=False)

        cursor = source_conn.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table';")

        for row in cursor.fetchall():
            if row[0]:
                backup_conn.execute(row[0])

        backup_conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Database error creating schema backup: {e}")
        return False
    except (OSError, IOError) as e:
        logger.error(f"I/O error creating schema backup: {e}")
        return False
    finally:
        # Ensure connections are always closed
        if backup_conn:
            try:
                backup_conn.close()
            except sqlite3.Error as e:
                logger.warning(f"Error closing backup connection: {e}")
        if source_conn:
            try:
                source_conn.close()
            except sqlite3.Error as e:
                logger.warning(f"Error closing source connection: {e}")


def has_database_changed() -> bool:
    """Check if database has changed since last backup"""
    try:
        if not os.path.exists(str(DEFAULT_DB_PATH)):
            return False

        current_hash = calculate_file_hash(str(DEFAULT_DB_PATH))

        # Check if we have a previous hash stored
        last_backup = metadata_manager.get_backups(limit=1)
        if last_backup and "file_hash" in last_backup[0]:
            return current_hash != last_backup[0]["file_hash"]

        return True  # If no previous backup, assume changed
    except (OSError, IOError) as e:
        logger.error(f"Error accessing database file for change detection: {e}")
        return True
    except (KeyError, IndexError, TypeError) as e:
        logger.error(f"Error reading backup metadata: {e}")
        return True


def create_incremental_backup(backup_path: str) -> bool:
    """Create incremental backup (changes since last full backup)"""
    try:
        # This is a simplified incremental backup
        # In a real implementation, you'd track changes at the record level

        last_full = metadata_manager.metadata.get("last_full")
        if not last_full or not os.path.exists(last_full):
            logger.warning("No previous full backup found. Creating full backup instead.")
            return False

        # For SQLite, we'll create a backup and compare sizes
        # This is a basic implementation - more sophisticated tracking would be needed
        # Get the database path from the connection
        with get_connection() as conn:
            if hasattr(conn, 'execute'):
                db_path = conn.execute("PRAGMA database_list").fetchone()[2]
            else:
                db_path = str(DEFAULT_DB_PATH)

        shutil.copy2(db_path, backup_path)
        return True

    except sqlite3.Error as e:
        logger.error(f"Database error creating incremental backup: {e}")
        return False
    except (OSError, IOError) as e:
        logger.error(f"I/O error creating incremental backup: {e}")
        return False
    except shutil.Error as e:
        logger.error(f"File copy error creating incremental backup: {e}")
        return False


# ── Progress tracking ─────────────────────────────────────────────────────────

class ProgressTracker:
    def __init__(self, total_size: int):
        self.total_size = total_size
        self.current_size = 0
        self.start_time = time.time()

    def update(self, bytes_transferred: int):
        self.current_size += bytes_transferred
        elapsed = time.time() - self.start_time
        if elapsed > 0:
            speed = self.current_size / elapsed
            percentage = (self.current_size / self.total_size) * 100
            eta = (self.total_size - self.current_size) / speed if speed > 0 else 0

            print(f"\rProgress: {percentage:.1f}% ({self.current_size}/{self.total_size} bytes) "
                  f"Speed: {speed/1024/1024:.1f} MB/s ETA: {eta:.0f}s", end="")


# ── Enhanced backup creation ──────────────────────────────────────────────────

def create_enhanced_backup(manual=False, operation_name=None, backup_type="full", tables=None):
    """Enhanced backup creation with all new features"""
    try:
        # Check if database has changed (if change detection is enabled)
        if config["enable_change_detection"] and not manual and not has_database_changed():
            logger.info("No changes detected since last backup. Skipping backup.")
            return None

        # Ensure backup directory exists
        backup_dir = ensure_backup_directory()

        # Generate backup filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        if operation_name:
            filename = f"student_records_before_{operation_name}_{timestamp}.db"
        elif manual:
            filename = f"student_records_manual_{backup_type}_{timestamp}.db"
        else:
            filename = f"student_records_scheduled_{backup_type}_{timestamp}.db"

        backup_path = backup_dir / filename

        # Check if source database exists
        if not os.path.exists(str(DEFAULT_DB_PATH)):
            logger.warning("Database file not found. Nothing to backup.")
            return None

        # Progress tracking
        if config.get("show_progress", True):
            db_size = os.path.getsize(str(DEFAULT_DB_PATH))
            progress = ProgressTracker(db_size)

        # Create backup based on type
        success = False
        if backup_type == "schema":
            success = create_schema_only_backup(str(backup_path))
        elif backup_type == "selective" and tables:
            success = create_selective_backup(tables, str(backup_path))
        elif backup_type == "incremental":
            success = create_incremental_backup(str(backup_path))
        else:  # full backup
            # Get the database path from the connection
            with get_connection() as conn:
                if hasattr(conn, 'execute'):
                    db_path = conn.execute("PRAGMA database_list").fetchone()[2]
                else:
                    db_path = str(DEFAULT_DB_PATH)

            shutil.copy2(db_path, backup_path)
            success = True

        if not success:
            logger.error("Backup creation failed")
            return None

        # Calculate file hash for integrity
        file_hash = calculate_file_hash(str(backup_path))

        # Compress if enabled
        if config["compression_enabled"]:
            compressed_path = compress_file(
                str(backup_path),
                config["compression_format"],
                config["compression_level"]
            )
            if compressed_path:
                backup_path = Path(compressed_path)

        # Encrypt if enabled
        if config["encryption_enabled"] and config["encryption_password"]:
            encrypted_path = encrypt_file(str(backup_path), config["encryption_password"])
            if encrypted_path:
                backup_path = Path(encrypted_path)

        # Upload to cloud/remote if enabled
        upload_success = True
        if config["cloud_enabled"]:
            if config["cloud_provider"] == "aws":
                upload_success = upload_to_aws_s3(
                    str(backup_path),
                    config["aws_bucket"],
                    f"backups/{backup_path.name}"
                )

        if config["remote_enabled"]:
            if config["remote_type"] == "ftp":
                upload_success = upload_to_ftp(
                    str(backup_path),
                    config["remote_host"],
                    config["remote_username"],
                    config["remote_password"],
                    config["remote_path"]
                )
            elif config["remote_type"] == "sftp":
                upload_success = upload_to_sftp(
                    str(backup_path),
                    config["remote_host"],
                    config["remote_username"],
                    config["remote_password"],
                    config["remote_path"]
                )

        # Record backup metadata
        backup_info = {
            "path": str(backup_path),
            "filename": backup_path.name,
            "type": backup_type,
            "manual": manual,
            "operation": operation_name,
            "timestamp": timestamp,
            "size": os.path.getsize(backup_path),
            "file_hash": file_hash,
            "compressed": config["compression_enabled"],
            "encrypted": config["encryption_enabled"],
            "cloud_uploaded": config["cloud_enabled"] and upload_success,
            "remote_uploaded": config["remote_enabled"] and upload_success,
            "backup_type": backup_type
        }

        metadata_manager.add_backup(backup_info)

        logger.info(f"Backup created: {backup_path}")

        # Immutable audit log for backup creation
        if IMMUTABLE_AUDIT_AVAILABLE:
            user_id, _ = get_gui_context()
            safe_log_security_event(
                action=AuditAction.BACKUP_CREATE,
                user_id=user_id or 'system',
                resource_type='database_backup',
                resource_id=backup_path.name,
                details={
                    'backup_type': backup_type,
                    'manual': manual,
                    'operation': operation_name,
                    'size_bytes': backup_info['size'],
                    'compressed': backup_info['compressed'],
                    'encrypted': backup_info['encrypted'],
                    'cloud_uploaded': backup_info.get('cloud_uploaded', False),
                }
            )

        # Clean up old backups
        from education_system.post_18.university_system.infrastructure.database.data_backup.retention import cleanup_old_backups
        cleanup_old_backups()

        # Send notifications
        notify_backup_result(True, str(backup_path), f"{backup_type} backup")

        return str(backup_path)

    except sqlite3.Error as e:
        logger.error(f"Database error creating backup: {e}")
        notify_backup_result(False, "", f"{backup_type} backup")
        return None
    except (OSError, IOError) as e:
        logger.error(f"I/O error creating backup: {e}")
        notify_backup_result(False, "", f"{backup_type} backup")
        return None
    except shutil.Error as e:
        logger.error(f"File copy error creating backup: {e}")
        notify_backup_result(False, "", f"{backup_type} backup")
        return None
    except (KeyError, TypeError) as e:
        logger.error(f"Configuration error creating backup: {e}")
        notify_backup_result(False, "", f"{backup_type} backup")
        return None


# ── Restore operations ────────────────────────────────────────────────────────

def restore_from_backup(backup_path, target_tables=None, point_in_time=None):
    """Enhanced restore with partial and point-in-time options"""
    try:
        # Verify the backup file exists
        if not os.path.exists(backup_path):
            logger.error(f"Backup file not found: {backup_path}")
            return False

        # Create a backup of the current database
        current_backup = create_enhanced_backup(manual=True, operation_name="restore")

        # Prepare the restore file
        restore_file = backup_path
        temp_files = []

        # Decrypt if needed
        if backup_path.endswith('.encrypted'):
            if not config["encryption_password"]:
                logger.error("Encryption password required for encrypted backup")
                return False

            fd, temp_decrypt = tempfile.mkstemp(suffix='.db')
            os.close(fd)
            restore_file = decrypt_file(backup_path, config["encryption_password"], temp_decrypt)
            temp_files.append(temp_decrypt)

            if not restore_file:
                logger.error("Failed to decrypt backup file")
                return False

        # Decompress if needed
        if restore_file.endswith(('.gz', '.zip')):
            fd, temp_decompress = tempfile.mkstemp(suffix='.db')
            os.close(fd)
            restore_file = decompress_file(restore_file, temp_decompress)
            temp_files.append(temp_decompress)

            if not restore_file:
                logger.error("Failed to decompress backup file")
                return False

        # Perform restore
        if target_tables:
            # Partial restore - only specified tables
            success = restore_partial_tables(restore_file, target_tables)
        else:
            # Full restore
            shutil.copy2(restore_file, str(DEFAULT_DB_PATH))
            success = True

        # Clean up temporary files
        for temp_file in temp_files:
            try:
                os.remove(temp_file)
            except (OSError, FileNotFoundError) as e:
                logger.debug(f"Failed to remove temporary file {temp_file}: {e}")
                pass

        if success:
            logger.info(f"Database restored from: {backup_path}")
            if current_backup:
                logger.info(f"Previous database backed up to: {current_backup}")

            # Immutable audit log for backup restore
            if IMMUTABLE_AUDIT_AVAILABLE:
                user_id, _ = get_gui_context()
                safe_log_security_event(
                    action=AuditAction.BACKUP_RESTORE,
                    user_id=user_id or 'system',
                    resource_type='database_backup',
                    resource_id=os.path.basename(backup_path),
                    details={
                        'source_path': backup_path,
                        'target_tables': target_tables,
                        'point_in_time': str(point_in_time) if point_in_time else None,
                        'previous_backup': current_backup,
                    }
                )

            # Send notification
            notify_backup_result(True, backup_path, "restore")

        return success

    except sqlite3.Error as e:
        logger.error(f"Database error restoring from backup: {e}")
        notify_backup_result(False, backup_path, "restore")
        return False
    except (OSError, IOError) as e:
        logger.error(f"I/O error restoring from backup: {e}")
        notify_backup_result(False, backup_path, "restore")
        return False
    except shutil.Error as e:
        logger.error(f"File copy error restoring from backup: {e}")
        notify_backup_result(False, backup_path, "restore")
        return False


def restore_partial_tables(backup_path, tables):
    """Restore only specified tables from backup"""
    try:
        backup_conn = get_connection(db_path=backup_path, row_factory=False)
        main_conn = get_connection()

        for table in tables:
            # Validate table name to prevent SQL injection
            validate_table_name(table, backup_conn)

            # Drop existing table - table name validated above, use bracket quoting
            main_conn.execute(f"DROP TABLE IF EXISTS [{table}]")

            # Get table schema - using parameterized query
            cursor = backup_conn.cursor()
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?;", (table,))
            create_sql = cursor.fetchone()

            if create_sql:
                # Create table
                main_conn.execute(create_sql[0])

                # Copy data - table name validated above, use bracket quoting
                cursor.execute("SELECT * FROM [" + table + "]")
                rows = cursor.fetchall()

                if rows:
                    placeholders = ','.join(['?' for _ in range(len(rows[0]))])
                    main_conn.executemany("INSERT INTO [" + table + "] VALUES (" + placeholders + ")", rows)

        main_conn.commit()
        main_conn.close()
        backup_conn.close()

        return True
    except ValueError as ve:
        logger.error(f"Invalid table name in partial restore: {ve}")
        return False
    except sqlite3.Error as e:
        logger.error(f"Database error restoring partial tables: {e}")
        return False
    except (OSError, IOError) as e:
        logger.error(f"I/O error restoring partial tables: {e}")
        return False
