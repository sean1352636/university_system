"""Backup restore operations."""
import os
import shutil
import tempfile

from university_system.modules.shared.gui.database.shared_imports import (
    DEFAULT_DB_PATH, logger, get_db_connection,
)
from university_system.modules.shared.gui.database.config import config

try:
    from university_system.infrastructure.database.db import sqlite3
    from university_system.modules.shared.utils.sql_safety import (
        validate_table_name,
        SQLIdentifierError,
    )
except ImportError:
    pass


def restore_from_backup(backup_path, target_tables=None, point_in_time=None):
    """Enhanced restore with partial and point-in-time options"""
    try:
        # Verify the backup file exists
        if not os.path.exists(backup_path):
            logger.error(f"Backup file not found: {backup_path}")
            return False

        # Late imports to avoid circular dependencies
        from university_system.modules.shared.gui.database.operations.backup_ops import (
            create_enhanced_backup, decrypt_file, decompress_file, notify_backup_result,
        )

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

            temp_decrypt = tempfile.mktemp(suffix='.db')
            restore_file = decrypt_file(backup_path, config["encryption_password"], temp_decrypt)
            temp_files.append(temp_decrypt)

            if not restore_file:
                logger.error("Failed to decrypt backup file")
                return False

        # Decompress if needed
        if restore_file.endswith(('.gz', '.zip')):
            temp_decompress = tempfile.mktemp(suffix='.db')
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
            except OSError:
                pass

        if success:
            logger.info(f"Database restored from: {backup_path}")
            if current_backup:
                logger.info(f"Previous database backed up to: {current_backup}")

            # Send notification
            notify_backup_result(True, backup_path, "restore")

        return success

    except Exception as e:
        logger.error(f"Error restoring from backup: {e}")
        try:
            from university_system.modules.shared.gui.database.operations.backup_ops import notify_backup_result
            notify_backup_result(False, backup_path, "restore")
        except Exception:
            pass
        return False

def restore_partial_tables(backup_path, tables):
    """Restore only specified tables from backup"""
    try:
        backup_conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        main_conn = get_db_connection()

        for table in tables:
            # Validate table name to prevent SQL injection
            try:
                validated_table = validate_table_name(table, conn=backup_conn)
            except SQLIdentifierError as e:
                logger.warning(f"Skipping invalid table name: {table} - {e}")
                continue

            # Drop existing table (using validated name with brackets)
            main_conn.execute(f"DROP TABLE IF EXISTS [{validated_table}]")

            # Get table schema using parameterized query
            cursor = backup_conn.cursor()
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?;", (validated_table,))
            create_sql = cursor.fetchone()

            if create_sql:
                # Create table
                main_conn.execute(create_sql[0])

                # Copy data
                cursor.execute(f"SELECT * FROM [{validated_table}]")
                rows = cursor.fetchall()

                if rows:
                    placeholders = ','.join(['?' for _ in range(len(rows[0]))])
                    main_conn.executemany(f"INSERT INTO [{validated_table}] VALUES ({placeholders})", rows)

        main_conn.commit()
        main_conn.close()
        backup_conn.close()

        return True
    except Exception as e:
        logger.error(f"Error restoring partial tables: {e}")
        return False
