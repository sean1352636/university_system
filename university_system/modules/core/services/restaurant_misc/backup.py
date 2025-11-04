from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime

from . import restaurant_context as ctx
from university_system.modules.core.services.restaurant_misc.restaurant_context import (
    DATABASE_FILE,
    get_log_file,
)
from university_system.modules.core.services.restaurant_misc.audit import log_audit_action

def system_backup():
    """Perform system backup"""
    try:
        print("\n" + "="*50)
        print("SYSTEM BACKUP")
        print("="*50)

        backup_type = input("Choose backup type (1=Database only, 2=Full system): ")

        if backup_type == '1':
            backup_database()
        elif backup_type == '2':
            backup_full_system()
        else:
            print("Invalid backup type.")

    except Exception as e:
        logging.error(f"Error in system_backup: {e}")
        print(f"An error occurred: {e}")

def backup_database():
    """Backup database only"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"restaurant_db_backup_{timestamp}.sql"

        # Simple backup by copying the database file
        import shutil
        shutil.copy2(DATABASE_FILE, backup_filename)

        print(f"✅ Database backup created: {backup_filename}")

        # Log audit action
        log_audit_action(
            ctx.auth.current_user['id'],
            'DATABASE_BACKUP',
            None,
            None,
            None,
            {'backup_file': backup_filename}
        )

    except Exception as e:
        logging.error(f"Error in backup_database: {e}")
        print(f"An error occurred: {e}")

def backup_full_system():
    """Backup full system - FIXED"""
    
    if not ctx.auth or not ctx.auth.current_user:
        print("You must be logged in to perform system backup.")
        return

    if not ctx.auth.check_permission('admin'):
        print("You don't have permission to perform system backup.")
        return

    try:
        print("\nPerforming full system backup...")

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = f"restaurant_backup_{timestamp}"

        # Create backup directory
        os.makedirs(backup_dir, exist_ok=True)

        # Backup database
        import shutil
        db_backup_path = os.path.join(backup_dir, f"database_{timestamp}.db")
        shutil.copy2(DATABASE_FILE, db_backup_path)

        # Backup log files
        log_dir = os.path.dirname(get_log_file("restaurant_system.log"))
        if os.path.exists(log_dir):
            log_backup_dir = os.path.join(backup_dir, "logs")
            shutil.copytree(log_dir, log_backup_dir, ignore_errors=True)

        # Create backup manifest
        manifest_path = os.path.join(backup_dir, "backup_manifest.txt")
        with open(manifest_path, 'w') as f:
            f.write(f"Restaurant Management System Backup\n")
            f.write(f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Created by: {ctx.auth.current_user['username']}\n")
            f.write(f"Database: {DATABASE_FILE}\n")
            f.write(f"Backup type: Full System\n")
            f.write(f"\nContents:\n")
            f.write(f"- Database backup: database_{timestamp}.db\n")
            f.write(f"- Log files: logs/\n")
            f.write(f"- This manifest: backup_manifest.txt\n")

        # Calculate backup size
        backup_size = 0
        for root, dirs, files in os.walk(backup_dir):
            for file in files:
                backup_size += os.path.getsize(os.path.join(root, file))

        print(f"✅ Full system backup completed!")
        print(f"Backup location: {backup_dir}")
        print(f"Backup size: {backup_size / 1024 / 1024:.2f} MB")
        print(f"Files backed up:")
        print(f"  - Database: {os.path.basename(DATABASE_FILE)}")
        print(f"  - Log files: Multiple log files")
        print(f"  - Backup manifest")

        # Log audit action
        log_audit_action(
            ctx.auth.current_user['id'],
            'FULL_SYSTEM_BACKUP',
            None,
            None,
            None,
            {'backup_dir': backup_dir, 'backup_size_mb': backup_size / 1024 / 1024}
        )

    except Exception as e:
        logging.error(f"Error in backup_full_system: {e}")
        print(f"An error occurred during backup: {e}")
