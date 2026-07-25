"""
Data backup package — split from the original monolithic data_backup.py.

All public names that were previously importable from
``university_system.infrastructure.database.data_backup`` are re-exported
here so that existing callers continue to work unchanged.
"""

# ── Re-exported dependencies (patched by tests) ──────────────────────────────
from education_system.systems.university.infrastructure.paths import DEFAULT_DB_PATH, DATA_DIR
from education_system.systems.university.infrastructure.database.db import get_connection

# ── Config / globals ──────────────────────────────────────────────────────────
from education_system.systems.university.infrastructure.database.data_backup.config import (
    DEFAULT_CONFIG,
    backup_history,
    backup_thread,
    config,
    encryption_key,
    ensure_backup_directory,
    last_full_backup,
    load_config,
    save_config,
    stop_flag,
)

# ── Metadata ──────────────────────────────────────────────────────────────────
from education_system.systems.university.infrastructure.database.data_backup.metadata import (
    BackupMetadata,
    metadata_manager,
)

# ── Security ──────────────────────────────────────────────────────────────────
from education_system.systems.university.infrastructure.database.data_backup.security import (
    calculate_file_hash,
    decrypt_file,
    encrypt_file,
    generate_encryption_key,
    secure_delete_file,
    verify_backup_integrity,
)

# ── Compression ───────────────────────────────────────────────────────────────
from education_system.systems.university.infrastructure.database.data_backup.compression import (
    compress_file,
    decompress_file,
)

# ── Storage ───────────────────────────────────────────────────────────────────
from education_system.systems.university.infrastructure.database.data_backup.storage import (
    download_from_aws_s3,
    upload_to_aws_s3,
    upload_to_ftp,
    upload_to_sftp,
)

# ── Notifications ─────────────────────────────────────────────────────────────
from education_system.systems.university.infrastructure.database.data_backup.notifications import (
    notify_backup_result,
    send_discord_notification,
    send_email_notification,
    send_slack_notification,
)

# ── Core operations ───────────────────────────────────────────────────────────
from education_system.systems.university.infrastructure.database.data_backup.operations import (
    ProgressTracker,
    create_enhanced_backup,
    create_incremental_backup,
    create_schema_only_backup,
    create_selective_backup,
    get_database_tables,
    has_database_changed,
    restore_from_backup,
    restore_partial_tables,
    validate_table_name,
)

# ── Exports ───────────────────────────────────────────────────────────────────
from education_system.systems.university.infrastructure.database.data_backup.exports import (
    export_to_csv,
    export_to_json,
    export_to_xml,
)

# ── Analysis ──────────────────────────────────────────────────────────────────
from education_system.systems.university.infrastructure.database.data_backup.analysis import (
    compare_backups,
    compare_table_data,
    generate_backup_statistics,
    get_database_tables_from_connection,
    validate_backup,
)

# ── Retention ─────────────────────────────────────────────────────────────────
from education_system.systems.university.infrastructure.database.data_backup.retention import (
    cleanup_old_backups,
    delete_backup,
    list_available_backups,
)

# ── Templates ─────────────────────────────────────────────────────────────────
from education_system.systems.university.infrastructure.database.data_backup.templates import (
    load_backup_template,
    save_backup_template,
)

# ── Scheduling ────────────────────────────────────────────────────────────────
from education_system.systems.university.infrastructure.database.data_backup.scheduling import (
    parse_cron_schedule,
    scheduled_backup_job,
    start_scheduler,
    stop_scheduler,
)

# ── CLI menus ─────────────────────────────────────────────────────────────────
from education_system.systems.university.infrastructure.database.data_backup.cli_menu import (
    configure_backups,
    configure_cloud_storage,
    configure_email_notifications,
    configure_remote_storage,
    configure_retention_policy,
    configure_webhooks,
    display_enhanced_backup_menu,
    manage_templates,
)


# ── Legacy aliases ────────────────────────────────────────────────────────────

def create_backup(manual=False, operation_name=None):
    """Legacy function for backward compatibility"""
    return create_enhanced_backup(manual=manual, operation_name=operation_name)


def display_backup_menu():
    """Legacy function name — forward to enhanced menu"""
    return display_enhanced_backup_menu()


def backup_before_operation(operation_name):
    """Create a backup before a major operation"""
    return create_enhanced_backup(manual=False, operation_name=operation_name)


def open_data_backup(*args, **kwargs):
    """Legacy name — forward to the enhanced menu function."""
    return display_enhanced_backup_menu(*args, **kwargs)
