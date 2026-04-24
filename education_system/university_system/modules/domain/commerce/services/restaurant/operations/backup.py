from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime

from education_system.university_system.modules.domain.commerce.services.restaurant.operations import restaurant_context as ctx
from education_system.university_system.modules.domain.commerce.services.restaurant.operations.restaurant_context import (
    DATABASE_FILE,
    get_log_file,
)
from education_system.university_system.modules.domain.commerce.services.restaurant.operations.audit import log_audit_action
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

def system_backup():
    """Perform system backup"""
    try:
        print("\n" + "="*50)
        print(_t("restaurant.backup.system_backup_title"))
        print("="*50)

        backup_type = input(_t("restaurant.backup.choose_backup_type"))

        if backup_type == '1':
            backup_database()
        elif backup_type == '2':
            backup_full_system()
        else:
            print(_t("restaurant.backup.invalid_backup_type"))

    except Exception as e:
        logging.error(f"Error in system_backup: {e}")
        print(_t("restaurant.backup.error_occurred", error=str(e)))

def backup_database():
    """Backup database only"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"restaurant_db_backup_{timestamp}.sql"

        # Simple backup by copying the database file
        import shutil
        shutil.copy2(DATABASE_FILE, backup_filename)

        print(_t("restaurant.backup.database_backup_created", filename=backup_filename))

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
        print(_t("restaurant.backup.error_occurred", error=str(e)))

def backup_full_system():
    """Backup full system - FIXED"""

    if not ctx.auth or not ctx.auth.current_user:
        print(_t("restaurant.backup.login_required"))
        return

    if not ctx.auth.check_permission('admin'):
        print(_t("restaurant.backup.permission_denied"))
        return

    try:
        print(f"\n{_t('restaurant.backup.performing_full_backup')}")

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = f"restaurant_backup_{timestamp}"

        # Create backup directory
        os.makedirs(backup_dir, exist_ok=True)

        # Backup database
        import shutil
        db_backup_path = os.path.join(backup_dir, f"database_{timestamp}.db")
        shutil.copy2(DATABASE_FILE, db_backup_path)

        # Backup log files
        log_dir = os.path.dirname(get_log_file("app.log"))
        if os.path.exists(log_dir):
            log_backup_dir = os.path.join(backup_dir, "logs")
            shutil.copytree(log_dir, log_backup_dir, ignore_errors=True)

        # Create backup manifest
        manifest_path = os.path.join(backup_dir, "backup_manifest.txt")
        with open(manifest_path, 'w') as f:
            f.write(f"{_t('restaurant.backup.manifest_title')}\n")
            f.write(f"{_t('restaurant.backup.manifest_created')}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{_t('restaurant.backup.manifest_created_by')}: {ctx.auth.current_user['username']}\n")
            f.write(f"{_t('restaurant.backup.manifest_database')}: {DATABASE_FILE}\n")
            f.write(f"{_t('restaurant.backup.manifest_backup_type')}: {_t('restaurant.backup.full_system')}\n")
            f.write(f"\n{_t('restaurant.backup.manifest_contents')}:\n")
            f.write(f"- {_t('restaurant.backup.manifest_db_backup')}: database_{timestamp}.db\n")
            f.write(f"- {_t('restaurant.backup.manifest_log_files')}: logs/\n")
            f.write(f"- {_t('restaurant.backup.manifest_this_manifest')}: backup_manifest.txt\n")

        # Calculate backup size
        backup_size = 0
        for root, dirs, files in os.walk(backup_dir):
            for file in files:
                backup_size += os.path.getsize(os.path.join(root, file))

        print(_t("restaurant.backup.full_backup_completed"))
        print(_t("restaurant.backup.backup_location", location=backup_dir))
        print(_t("restaurant.backup.backup_size", size=f"{backup_size / 1024 / 1024:.2f}"))
        print(_t("restaurant.backup.files_backed_up"))
        print(f"  - {_t('restaurant.backup.database_label')}: {os.path.basename(DATABASE_FILE)}")
        print(f"  - {_t('restaurant.backup.log_files_label')}: {_t('restaurant.backup.multiple_log_files')}")
        print(f"  - {_t('restaurant.backup.backup_manifest_label')}")

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
        print(_t("restaurant.backup.backup_error", error=str(e)))
