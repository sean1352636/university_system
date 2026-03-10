"""Interactive CLI menus for backup configuration and operations."""

import datetime
import os

from education_system.university_system.core.i18n import get_text as _t, init_i18n
from education_system.university_system.utils.logging.log_config import configure_logging, get_log_file
from education_system.university_system.infrastructure.database.data_backup.config import (
    config,
    ensure_backup_directory,
    load_config,
    save_config,
)
from education_system.university_system.infrastructure.database.data_backup.operations import (
    create_enhanced_backup,
    get_database_tables,
)
from education_system.university_system.infrastructure.database.data_backup.retention import (
    delete_backup,
    list_available_backups,
)
from education_system.university_system.infrastructure.database.data_backup.analysis import (
    compare_backups,
    generate_backup_statistics,
    validate_backup,
)
from education_system.university_system.infrastructure.database.data_backup.exports import (
    export_to_csv,
    export_to_json,
    export_to_xml,
)
from education_system.university_system.infrastructure.database.data_backup.templates import (
    load_backup_template,
    save_backup_template,
)
from education_system.university_system.infrastructure.database.data_backup.scheduling import (
    start_scheduler,
    stop_scheduler,
)
from education_system.university_system.infrastructure.database.data_backup.operations import restore_from_backup

init_i18n()

logger = configure_logging(name=__name__)


# ── Sub-configuration menus ───────────────────────────────────────────────────

def configure_cloud_storage():
    """Configure cloud storage settings"""
    config["cloud_enabled"] = not config["cloud_enabled"]

    if config["cloud_enabled"]:
        print(_t("data_backup.cloud_providers") + ":")
        print("1. " + _t("data_backup.aws_s3"))
        print("2. " + _t("data_backup.google_cloud"))
        print("3. " + _t("data_backup.azure"))

        provider_choice = input(_t("data_backup.choose_provider") + " (1-3): ")

        if provider_choice == '1':
            config["cloud_provider"] = "aws"
            config["aws_bucket"] = input(_t("data_backup.enter_bucket_name") + ": ")
            config["aws_access_key"] = input(_t("data_backup.enter_access_key") + ": ")
            config["aws_secret_key"] = input(_t("data_backup.enter_secret_key") + ": ")
            config["aws_region"] = input(_t("data_backup.enter_region") + ": ") or "us-east-1"


def configure_remote_storage():
    """Configure remote storage settings"""
    config["remote_enabled"] = not config["remote_enabled"]

    if config["remote_enabled"]:
        print(_t("data_backup.remote_types") + ":")
        print("1. " + _t("data_backup.ftp"))
        print("2. " + _t("data_backup.sftp"))

        type_choice = input(_t("data_backup.choose_remote_type") + " (1-2): ")

        if type_choice == '1':
            config["remote_type"] = "ftp"
        elif type_choice == '2':
            config["remote_type"] = "sftp"

        config["remote_host"] = input(_t("data_backup.enter_hostname") + ": ")
        config["remote_username"] = input(_t("data_backup.enter_username") + ": ")
        config["remote_password"] = input(_t("data_backup.enter_password") + ": ")
        config["remote_path"] = input(_t("data_backup.enter_remote_path") + ": ") or "/backups"


def configure_email_notifications():
    """Configure email notification settings"""
    config["email_notifications"] = not config["email_notifications"]

    if config["email_notifications"]:
        config["smtp_server"] = input(_t("data_backup.enter_smtp_server") + ": ") or "smtp.gmail.com"
        try:
            config["smtp_port"] = int(input(_t("data_backup.enter_smtp_port") + ": ") or "587")
        except ValueError:
            config["smtp_port"] = 587

        config["email_username"] = input(_t("data_backup.enter_email_username") + ": ")
        config["email_password"] = input(_t("data_backup.enter_email_password") + ": ")

        recipients = input(_t("data_backup.enter_recipients") + ": ")
        config["notification_recipients"] = [r.strip() for r in recipients.split(",") if r.strip()]


def configure_webhooks():
    """Configure webhook settings"""
    print(_t("data_backup.webhook_config") + ":")
    print("1. " + _t("data_backup.slack_webhook"))
    print("2. " + _t("data_backup.discord_webhook"))
    print("3. " + _t("data_backup.clear_webhooks"))

    choice = input(_t("data_backup.choose_option") + " (1-3): ")

    if choice == '1':
        config["slack_webhook"] = input(_t("data_backup.enter_slack_url") + ": ")
    elif choice == '2':
        config["discord_webhook"] = input(_t("data_backup.enter_discord_url") + ": ")
    elif choice == '3':
        config["slack_webhook"] = ""
        config["discord_webhook"] = ""


def configure_retention_policy():
    """Configure backup retention policy"""
    print(_t("data_backup.retention_policy") + ":")
    policy = config["retention_policy"]
    print(f"{_t('data_backup.daily_keep')}: {policy['daily_keep']}")
    print(f"{_t('data_backup.weekly_keep')}: {policy['weekly_keep']}")
    print(f"{_t('data_backup.monthly_keep')}: {policy['monthly_keep']}")
    print(f"{_t('data_backup.yearly_keep')}: {policy['yearly_keep']}")

    try:
        policy["daily_keep"] = int(input(_t("data_backup.enter_daily_keep") + ": ") or policy["daily_keep"])
        policy["weekly_keep"] = int(input(_t("data_backup.enter_weekly_keep") + ": ") or policy["weekly_keep"])
        policy["monthly_keep"] = int(input(_t("data_backup.enter_monthly_keep") + ": ") or policy["monthly_keep"])
        policy["yearly_keep"] = int(input(_t("data_backup.enter_yearly_keep") + ": ") or policy["yearly_keep"])
    except ValueError:
        print(_t("data_backup.invalid_keeping_current"))


def manage_templates():
    """Manage backup templates"""
    templates = config.get("backup_templates", {})

    while True:
        print("\n" + _t("data_backup.template_management") + ":")
        if templates:
            for i, name in enumerate(templates.keys(), 1):
                print(f"{i}. {name}")
            print(f"{len(templates) + 1}. " + _t("data_backup.delete_template"))
            print(f"{len(templates) + 2}. " + _t("data_backup.return"))
        else:
            print(_t("data_backup.no_templates"))
            print("1. " + _t("data_backup.return"))

        choice = input(_t("data_backup.enter_choice") + ": ")

        if not templates and choice == '1':
            break
        elif templates:
            if choice == str(len(templates) + 1):
                # Delete template
                template_name = input(_t("data_backup.enter_template_delete") + ": ")
                if template_name in templates:
                    del config["backup_templates"][template_name]
                    templates = config["backup_templates"]
                    print(_t("data_backup.template_deleted", name=template_name))
                else:
                    print(_t("data_backup.template_not_found"))
            elif choice == str(len(templates) + 2):
                break
            else:
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(templates):
                        template_name = list(templates.keys())[idx]
                        template = templates[template_name]

                        print("\n" + _t("data_backup.template_settings", name=template_name))
                        for key, value in template.items():
                            print(f"  {key}: {value}")

                        action = input("\n" + _t("data_backup.load_this_template") + " (y/n): ")
                        if action.lower() == 'y':
                            load_backup_template(template_name)
                            break
                except (ValueError, IndexError):
                    print(_t("chat_rooms.invalid_selection"))


# ── Main configuration menu ──────────────────────────────────────────────────

def configure_backups():
    """Enhanced backup configuration with all new options"""
    while True:
        print("\n" + _t("data_backup.config_title") + ":")
        print("=" * 50)

        # Basic settings
        print("\n" + _t("data_backup.basic_settings") + ":")
        print(f"1.  {_t('data_backup.backup_directory')}: {config['backup_directory']}")
        print(f"2.  {_t('data_backup.scheduled_time')}: {config['scheduled_backup_time']}")
        print(f"3.  {_t('data_backup.frequency')}: {config['backup_frequency']}")
        print(f"4.  {_t('data_backup.max_backups')}: {config['max_backups']}")
        print(f"5.  {_t('data_backup.auto_backup')}: {_t('data_backup.enabled') if config['auto_backup_enabled'] else _t('data_backup.disabled')}")

        # Security settings
        print(f"\n{_t('data_backup.security_settings')}:")
        print(f"6.  {_t('data_backup.encryption')}: {_t('data_backup.enabled') if config['encryption_enabled'] else _t('data_backup.disabled')}")
        print(f"7.  {_t('data_backup.secure_deletion')}: {_t('data_backup.enabled') if config['secure_deletion'] else _t('data_backup.disabled')}")
        print(f"8.  {_t('data_backup.integrity_verification')}: {_t('data_backup.enabled') if config['verify_integrity'] else _t('data_backup.disabled')}")

        # Compression settings
        print(f"\n{_t('data_backup.compression_settings')}:")
        print(f"9.  {_t('data_backup.compression')}: {_t('data_backup.enabled') if config['compression_enabled'] else _t('data_backup.disabled')}")
        print(f"10. {_t('data_backup.compression_format')}: {config['compression_format']}")
        print(f"11. {_t('data_backup.compression_level')}: {config['compression_level']}")

        # Cloud/Remote settings
        print(f"\n{_t('data_backup.cloud_remote_storage')}:")
        print(f"12. {_t('data_backup.cloud_storage')}: {_t('data_backup.enabled') if config['cloud_enabled'] else _t('data_backup.disabled')}")
        print(f"13. {_t('data_backup.remote_storage')}: {_t('data_backup.enabled') if config['remote_enabled'] else _t('data_backup.disabled')}")

        # Backup types
        print(f"\n{_t('data_backup.backup_types')}:")
        print(f"14. {_t('data_backup.enable_incremental')}: {_t('common.yes') if config['enable_incremental'] else _t('common.no')}")
        print(f"15. {_t('data_backup.enable_selective')}: {_t('common.yes') if config['enable_selective'] else _t('common.no')}")

        # Notifications
        print(f"\n{_t('data_backup.notifications')}:")
        print(f"16. {_t('data_backup.email_notifications')}: {_t('data_backup.enabled') if config['email_notifications'] else _t('data_backup.disabled')}")
        print(f"17. {_t('data_backup.configure_webhooks')}")

        # Advanced features
        print(f"\n{_t('data_backup.advanced_features')}:")
        print(f"18. {_t('data_backup.change_detection')}: {_t('data_backup.enabled') if config['enable_change_detection'] else _t('data_backup.disabled')}")
        print(f"19. {_t('data_backup.parallel_backup')}: {_t('data_backup.enabled') if config['parallel_backup'] else _t('data_backup.disabled')}")
        print(f"20. {_t('data_backup.auto_validation')}: {_t('data_backup.enabled') if config['auto_validate'] else _t('data_backup.disabled')}")
        print(f"21. {_t('data_backup.configure_retention')}")
        print(f"22. {_t('data_backup.configure_cron')}")

        # Templates
        print(f"\n{_t('data_backup.templates')}:")
        print(f"23. {_t('data_backup.save_template')}")
        print(f"24. {_t('data_backup.load_template')}")
        print(f"25. {_t('data_backup.manage_templates')}")

        print(f"\n26. {_t('data_backup.save_return')}")

        choice = input("\n" + _t("data_backup.enter_choice") + " (1-26): ")

        # Basic settings
        if choice == '1':
            new_dir = input(_t("data_backup.enter_new_directory") + ": ")
            if new_dir:
                config["backup_directory"] = new_dir
                ensure_backup_directory()

        elif choice == '2':
            while True:
                new_time = input(_t("data_backup.enter_backup_time") + ": ")
                try:
                    datetime.datetime.strptime(new_time, "%H:%M")
                    config["scheduled_backup_time"] = new_time
                    break
                except ValueError:
                    print(_t("data_backup.invalid_time_format"))

        elif choice == '3':
            print(_t("data_backup.frequency_options") + ":")
            print("1. " + _t("data_backup.daily"))
            print("2. " + _t("data_backup.weekly"))
            print("3. " + _t("data_backup.monthly"))
            freq_choice = input(_t("data_backup.choose_option") + " (1-3): ")

            freq_map = {'1': 'daily', '2': 'weekly', '3': 'monthly'}
            if freq_choice in freq_map:
                config["backup_frequency"] = freq_map[freq_choice]

        elif choice == '4':
            try:
                max_backups = int(input(_t("data_backup.enter_max_backups") + ": "))
                if max_backups > 0:
                    config["max_backups"] = max_backups
            except ValueError:
                print(_t("data_backup.enter_valid_number"))

        elif choice == '5':
            config["auto_backup_enabled"] = not config["auto_backup_enabled"]

        # Security settings
        elif choice == '6':
            config["encryption_enabled"] = not config["encryption_enabled"]
            if config["encryption_enabled"] and not config["encryption_password"]:
                password = input(_t("data_backup.enter_encryption_password") + ": ")
                config["encryption_password"] = password

        elif choice == '7':
            config["secure_deletion"] = not config["secure_deletion"]

        elif choice == '8':
            config["verify_integrity"] = not config["verify_integrity"]

        # Compression settings
        elif choice == '9':
            config["compression_enabled"] = not config["compression_enabled"]

        elif choice == '10':
            print(_t("data_backup.compression_formats") + ":")
            print("1. " + _t("data_backup.gzip"))
            print("2. " + _t("data_backup.zip"))
            format_choice = input(_t("data_backup.choose_option") + " (1-2): ")

            if format_choice == '1':
                config["compression_format"] = "gzip"
            elif format_choice == '2':
                config["compression_format"] = "zip"

        elif choice == '11':
            try:
                level = int(input(_t("data_backup.enter_compression_level") + ": "))
                if 1 <= level <= 9:
                    config["compression_level"] = level
            except ValueError:
                print(_t("data_backup.invalid_level"))

        # Cloud/Remote settings
        elif choice == '12':
            configure_cloud_storage()

        elif choice == '13':
            configure_remote_storage()

        # Backup types
        elif choice == '14':
            config["enable_incremental"] = not config["enable_incremental"]

        elif choice == '15':
            config["enable_selective"] = not config["enable_selective"]
            if config["enable_selective"]:
                tables = get_database_tables()
                print(_t("data_backup.available_tables") + ": " + ", ".join(tables))
                selected = input(_t("data_backup.enter_table_names") + ": ").split(",")
                config["selective_tables"] = [t.strip() for t in selected if t.strip()]

        # Notifications
        elif choice == '16':
            configure_email_notifications()

        elif choice == '17':
            configure_webhooks()

        # Advanced features
        elif choice == '18':
            config["enable_change_detection"] = not config["enable_change_detection"]

        elif choice == '19':
            config["parallel_backup"] = not config["parallel_backup"]
            if config["parallel_backup"]:
                try:
                    threads = int(input(_t("data_backup.enter_max_threads") + ": "))
                    if 1 <= threads <= 8:
                        config["max_threads"] = threads
                except ValueError:
                    print(_t("data_backup.enter_valid_number"))

        elif choice == '20':
            config["auto_validate"] = not config["auto_validate"]

        elif choice == '21':
            configure_retention_policy()

        elif choice == '22':
            cron_expr = input(_t("data_backup.enter_cron") + ": ")
            config["cron_schedule"] = cron_expr

        # Templates
        elif choice == '23':
            name = input(_t("data_backup.enter_template_name") + ": ")
            if name:
                template_config = {k: v for k, v in config.items() if k != "backup_templates"}
                save_backup_template(name, template_config)

        elif choice == '24':
            templates = config.get("backup_templates", {})
            if templates:
                print(_t("data_backup.available_templates") + ":")
                for i, name in enumerate(templates.keys(), 1):
                    print(f"{i}. {name}")

                choice_template = input(_t("data_backup.enter_template_number") + ": ")
                try:
                    idx = int(choice_template) - 1
                    template_name = list(templates.keys())[idx]
                    load_backup_template(template_name)
                except (ValueError, IndexError):
                    print(_t("chat_rooms.invalid_selection"))
            else:
                print(_t("data_backup.no_templates"))

        elif choice == '25':
            manage_templates()

        elif choice == '26':
            save_config()

            # Restart scheduler with new settings
            stop_scheduler()
            if config["auto_backup_enabled"]:
                start_scheduler()

            break

        else:
            print(_t("data_backup.invalid_choice"))


# ── Main backup menu ─────────────────────────────────────────────────────────

def display_enhanced_backup_menu():
    """Display the enhanced backup menu"""
    # Load configuration
    load_config()

    # Start scheduler if auto backup is enabled
    if config["auto_backup_enabled"]:
        start_scheduler()

    while True:
        print("\n" + "="*60)
        print("           " + _t("data_backup.title"))
        print("="*60)
        print(_t("data_backup.basic_operations") + ":")
        print("1.  " + _t("data_backup.create_manual"))
        print("2.  " + _t("data_backup.view_available"))
        print("3.  " + _t("data_backup.delete_backup"))
        print("4.  " + _t("data_backup.restore_from"))
        print("5.  " + _t("data_backup.configure_settings"))

        print("\n" + _t("data_backup.advanced_types") + ":")
        print("6.  " + _t("data_backup.create_incremental"))
        print("7.  " + _t("data_backup.create_selective"))
        print("8.  " + _t("data_backup.create_schema"))

        print("\n" + _t("data_backup.analysis_comparison") + ":")
        print("9.  " + _t("data_backup.compare_backups"))
        print("10. " + _t("data_backup.validate_backup"))
        print("11. " + _t("data_backup.generate_stats"))

        print("\n" + _t("data_backup.export_import") + ":")
        print("12. " + _t("data_backup.export_backup"))
        print("13. " + _t("data_backup.partial_restore"))

        print("\n" + _t("data_backup.cloud_remote") + ":")
        print("14. " + _t("data_backup.upload_cloud"))
        print("15. " + _t("data_backup.download_cloud"))
        print("16. " + _t("data_backup.sync_remote"))

        print("\n" + _t("data_backup.templates_automation") + ":")
        print("17. " + _t("data_backup.quick_backup"))
        print("18. " + _t("data_backup.schedule_custom"))

        print("\n19. " + _t("data_backup.view_log"))
        print("20. " + _t("data_backup.return_main"))

        choice = input("\n" + _t("data_backup.enter_choice") + " (1-20): ")

        if choice == '1':
            # Create manual backup with options
            print("\n" + _t("data_backup.backup_type") + ":")
            print("1. " + _t("data_backup.full_backup"))
            print("2. " + _t("data_backup.incremental_backup"))
            print("3. " + _t("data_backup.schema_only"))
            print("4. " + _t("data_backup.selective_tables"))

            backup_type_choice = input(_t("data_backup.choose_backup_type") + " (1-4): ")

            backup_type = "full"
            tables = None

            if backup_type_choice == '2':
                backup_type = "incremental"
            elif backup_type_choice == '3':
                backup_type = "schema"
            elif backup_type_choice == '4':
                backup_type = "selective"
                available_tables = get_database_tables()
                print(_t("data_backup.available_tables") + ": " + ", ".join(available_tables))
                selected = input(_t("data_backup.enter_table_names") + ": ").split(",")
                tables = [t.strip() for t in selected if t.strip() in available_tables]

            backup_path = create_enhanced_backup(
                manual=True,
                backup_type=backup_type,
                tables=tables
            )

            if backup_path:
                print(_t("data_backup.backup_created", path=backup_path))

            input(_t("common.press_enter"))

        elif choice == '2':
            # Enhanced backup listing with filtering
            print("\n" + _t("data_backup.filter_options") + ":")
            print("1. " + _t("data_backup.show_all"))
            print("2. " + _t("data_backup.filter_by_type"))
            print("3. " + _t("data_backup.search_by_name"))

            filter_choice = input(_t("data_backup.choose_option") + " (1-3): ")

            filter_type = None
            search_term = None

            if filter_choice == '2':
                filter_type = input(_t("data_backup.enter_backup_type") + ": ")
            elif filter_choice == '3':
                search_term = input(_t("data_backup.enter_search_term") + ": ")

            backups = list_available_backups(filter_type=filter_type, search_term=search_term)

            if not backups:
                print(_t("data_backup.no_backups_found"))
            else:
                print("\n" + _t("data_backup.available_backups") + ":")
                print("-" * 120)
                print(f"{_t('common.id'):<4} {_t('common.type'):<12} {_t('common.date'):<20} {_t('common.size'):<12} {_t('data_backup.encrypted'):<10} {_t('data_backup.cloud'):<6} {_t('data_backup.filename')}")
                print("-" * 120)

                for backup in backups:
                    print(f"{backup['id']:<4} "
                          f"{backup.get('backup_type', 'full'):<12} "
                          f"{backup['date_formatted']:<20} "
                          f"{backup['size_formatted']:<12} "
                          f"{_t('common.yes') if backup.get('encrypted', False) else _t('common.no'):<10} "
                          f"{_t('common.yes') if backup.get('cloud_uploaded', False) else _t('common.no'):<6} "
                          f"{backup['filename']}")

            input("\n" + _t("common.press_enter"))

        elif choice == '3':
            # Delete backup
            backups = list_available_backups()

            if not backups:
                print(_t("data_backup.no_backups_found"))
            else:
                print("\n" + _t("data_backup.available_backups") + ":")
                print("-" * 120)
                print(f"{_t('common.id'):<4} {_t('common.type'):<12} {_t('common.date'):<20} {_t('common.size'):<12} {_t('data_backup.filename')}")
                print("-" * 120)

                for backup in backups:
                    print(f"{backup['id']:<4} "
                          f"{backup.get('backup_type', 'full'):<12} "
                          f"{backup['date_formatted']:<20} "
                          f"{backup['size_formatted']:<12} "
                          f"{backup['filename']}")

                try:
                    backup_id = int(input("\n" + _t("data_backup.enter_backup_id_delete") + ": "))
                    if backup_id == 0:
                        print(_t("data_backup.deletion_cancelled"))
                    elif 1 <= backup_id <= len(backups):
                        backup = backups[backup_id - 1]

                        confirm = input(_t("data_backup.confirm_delete", filename=backup['filename']) + " (yes/no): ")
                        if confirm.lower() in ['yes', 'y']:
                            success = delete_backup(backup['path'])
                            if success:
                                print(_t("data_backup.deleted_success", filename=backup['filename']))
                            else:
                                print(_t("data_backup.failed_delete", filename=backup['filename']))
                        else:
                            print(_t("data_backup.deletion_cancelled"))
                    else:
                        print(_t("data_backup.invalid_backup_id"))
                except ValueError:
                    print(_t("data_backup.enter_valid_number"))

            input("\n" + _t("common.press_enter"))

        elif choice == '4':
            # Enhanced restore with options
            backups = list_available_backups()

            if not backups:
                print(_t("data_backup.no_backups_found"))
            else:
                print("\n" + _t("data_backup.available_backups") + ":")
                for i, backup in enumerate(backups, 1):
                    print(f"{i}. {backup['filename']} ({backup['date_formatted']})")

                try:
                    backup_id = int(input("\n" + _t("data_backup.enter_backup_id_restore") + ": "))
                    if backup_id == 0:
                        continue
                    elif 1 <= backup_id <= len(backups):
                        backup = backups[backup_id - 1]

                        print("\n" + _t("data_backup.restore_options") + ":")
                        print("1. " + _t("data_backup.full_restore"))
                        print("2. " + _t("data_backup.partial_restore_option"))

                        restore_choice = input(_t("data_backup.choose_option") + " (1-2): ")

                        target_tables = None
                        if restore_choice == '2':
                            available_tables = get_database_tables()
                            print(_t("data_backup.available_tables") + ": " + ", ".join(available_tables))
                            selected = input(_t("data_backup.enter_table_names") + ": ").split(",")
                            target_tables = [t.strip() for t in selected if t.strip()]

                        confirm = input(_t("data_backup.confirm_restore", filename=backup['filename']) + " (y/n): ")
                        if confirm.lower() == 'y':
                            success = restore_from_backup(
                                backup['path'],
                                target_tables=target_tables
                            )
                            print(_t("data_backup.restore_successful") if success else _t("data_backup.restore_failed"))
                    else:
                        print(_t("data_backup.invalid_backup_id"))
                except ValueError:
                    print(_t("data_backup.enter_valid_number"))

            input("\n" + _t("common.press_enter"))

        elif choice == '5':
            configure_backups()

        elif choice == '6':
            # Create incremental backup
            backup_path = create_enhanced_backup(manual=True, backup_type="incremental")
            if backup_path:
                print(_t("data_backup.backup_created", path=backup_path))
            input(_t("common.press_enter"))

        elif choice == '7':
            # Create selective backup
            tables = get_database_tables()
            print(_t("data_backup.available_tables") + ": " + ", ".join(tables))
            selected = input(_t("data_backup.enter_table_names") + ": ").split(",")
            selected_tables = [t.strip() for t in selected if t.strip() in tables]

            if selected_tables:
                backup_path = create_enhanced_backup(
                    manual=True,
                    backup_type="selective",
                    tables=selected_tables
                )
                if backup_path:
                    print(_t("data_backup.backup_created", path=backup_path))
            input(_t("common.press_enter"))

        elif choice == '8':
            # Create schema-only backup
            backup_path = create_enhanced_backup(manual=True, backup_type="schema")
            if backup_path:
                print(_t("data_backup.backup_created", path=backup_path))
            input(_t("common.press_enter"))

        elif choice == '9':
            # Compare backups
            backups = list_available_backups()
            if len(backups) < 2:
                print(_t("data_backup.need_two_backups"))
            else:
                print(_t("data_backup.select_first_backup") + ":")
                for i, backup in enumerate(backups, 1):
                    print(f"{i}. {backup['filename']}")

                try:
                    id1 = int(input(_t("data_backup.enter_first_id") + ": ")) - 1
                    id2 = int(input(_t("data_backup.enter_second_id") + ": ")) - 1

                    if 0 <= id1 < len(backups) and 0 <= id2 < len(backups) and id1 != id2:
                        differences = compare_backups(backups[id1]['path'], backups[id2]['path'])
                        if differences:
                            print("\n" + _t("data_backup.comparison_results") + ":")
                            print(f"{_t('data_backup.tables_added')}: {len(differences['tables_added'])}")
                            print(f"{_t('data_backup.tables_removed')}: {len(differences['tables_removed'])}")
                            print(f"{_t('data_backup.tables_modified')}: {len(differences['tables_modified'])}")
                    else:
                        print(_t("data_backup.invalid_backup_ids"))
                except ValueError:
                    print(_t("data_backup.enter_valid_numbers"))

            input("\n" + _t("common.press_enter"))

        elif choice == '10':
            # Validate backup
            backups = list_available_backups()
            if not backups:
                print(_t("data_backup.no_backups_found"))
            else:
                print(_t("data_backup.select_backup_validate") + ":")
                for i, backup in enumerate(backups, 1):
                    print(f"{i}. {backup['filename']}")

                try:
                    backup_id = int(input(_t("data_backup.enter_choice") + ": ")) - 1
                    if 0 <= backup_id < len(backups):
                        print(_t("data_backup.validating"))
                        results = validate_backup(backups[backup_id]['path'])

                        print("\n" + _t("data_backup.validation_results") + ":")
                        print(f"{_t('data_backup.file_exists')}: {'✓' if results['file_exists'] else '✗'}")
                        print(f"{_t('data_backup.file_readable')}: {'✓' if results['file_readable'] else '✗'}")
                        print(f"{_t('data_backup.database_valid')}: {'✓' if results['database_valid'] else '✗'}")
                        print(f"{_t('data_backup.tables_accessible')}: {'✓' if results['tables_accessible'] else '✗'}")
                        print(f"{_t('data_backup.hash_verified')}: {'✓' if results['hash_verified'] else '✗'}")

                        if results['errors']:
                            print("\n" + _t("data_backup.errors_found") + ":")
                            for error in results['errors']:
                                print(f"  • {error}")
                    else:
                        print(_t("data_backup.invalid_backup_id"))
                except ValueError:
                    print(_t("data_backup.enter_valid_number"))

            input("\n" + _t("common.press_enter"))

        elif choice == '11':
            # Generate statistics
            print(_t("data_backup.generating_stats"))
            stats = generate_backup_statistics()

            print("\n" + _t("data_backup.stats_report") + ":")
            print("=" * 40)
            print(f"{_t('data_backup.total_backups')}: {stats['total_backups']}")
            print(f"{_t('data_backup.total_size')}: {stats['total_size'] / (1024*1024*1024):.2f} GB")
            print(f"{_t('data_backup.average_size')}: {stats['average_size'] / (1024*1024):.2f} MB")
            print(f"{_t('data_backup.recent_activity')}: {stats['recent_activity']} backups")

            if stats['backup_types']:
                print("\n" + _t("data_backup.backup_types_label") + ":")
                for backup_type, count in stats['backup_types'].items():
                    print(f"  {backup_type}: {count}")

            input("\n" + _t("common.press_enter"))

        elif choice == '12':
            # Export backup
            backups = list_available_backups()
            if not backups:
                print(_t("data_backup.no_backups_found"))
            else:
                print(_t("data_backup.select_backup_export") + ":")
                for i, backup in enumerate(backups, 1):
                    print(f"{i}. {backup['filename']}")

                try:
                    backup_id = int(input(_t("data_backup.enter_choice") + ": ")) - 1
                    if 0 <= backup_id < len(backups):
                        backup = backups[backup_id]

                        print(_t("data_backup.export_formats") + ":")
                        print("1. " + _t("data_backup.csv"))
                        print("2. " + _t("data_backup.json"))
                        print("3. " + _t("data_backup.xml"))

                        format_choice = input(_t("data_backup.choose_format") + " (1-3): ")

                        if format_choice == '1':
                            output_dir = input(_t("data_backup.enter_output_dir") + ": ") or "csv_export"
                            export_to_csv(backup['path'], output_dir)
                        elif format_choice == '2':
                            output_file = input(_t("data_backup.enter_output_file") + ": ") or "backup_export.json"
                            export_to_json(backup['path'], output_file)
                        elif format_choice == '3':
                            output_file = input(_t("data_backup.enter_output_file") + ": ") or "backup_export.xml"
                            export_to_xml(backup['path'], output_file)
                    else:
                        print(_t("data_backup.invalid_backup_id"))
                except ValueError:
                    print(_t("data_backup.enter_valid_number"))

            input("\n" + _t("common.press_enter"))

        elif choice == '13':
            # This is handled in choice 4 (restore) with partial restore option
            print(_t("data_backup.partial_restore_hint"))
            input(_t("common.press_enter"))

        elif choice == '14':
            # Upload to cloud (if configured)
            if not config["cloud_enabled"]:
                print(_t("data_backup.cloud_not_configured"))
            else:
                print(_t("data_backup.cloud_upload_hint"))
            input(_t("common.press_enter"))

        elif choice == '15':
            # Download from cloud
            if not config["cloud_enabled"]:
                print(_t("data_backup.cloud_not_configured"))
            else:
                print(_t("data_backup.cloud_download_hint"))
            input(_t("common.press_enter"))

        elif choice == '16':
            # Sync with remote
            if not config["remote_enabled"]:
                print(_t("data_backup.remote_not_configured"))
            else:
                print(_t("data_backup.remote_sync_hint"))
            input(_t("common.press_enter"))

        elif choice == '17':
            # Quick backup using template
            templates = config.get("backup_templates", {})
            if not templates:
                print(_t("data_backup.no_templates"))
            else:
                print(_t("data_backup.available_templates") + ":")
                for i, name in enumerate(templates.keys(), 1):
                    print(f"{i}. {name}")

                try:
                    template_choice = int(input(_t("data_backup.choose_template") + ": ")) - 1
                    template_names = list(templates.keys())
                    if 0 <= template_choice < len(template_names):
                        template_name = template_names[template_choice]

                        # Save current config
                        old_config = config.copy()

                        # Load template
                        load_backup_template(template_name)

                        # Create backup
                        backup_path = create_enhanced_backup(manual=True)
                        if backup_path:
                            print(_t("data_backup.template_backup_created", path=backup_path))

                        # Restore original config
                        config.update(old_config)
                    else:
                        print(_t("data_backup.invalid_template"))
                except ValueError:
                    print(_t("data_backup.enter_valid_number"))

            input(_t("common.press_enter"))

        elif choice == '18':
            # Schedule custom backup
            print(_t("data_backup.custom_schedule_hint"))
            input(_t("common.press_enter"))

        elif choice == '19':
            # View backup log
            try:
                # Read from app.log and filter for backup-related entries
                app_log_path = get_log_file('app.log')
                if not os.path.exists(app_log_path):
                    print(_t("data_backup.no_log_found"))
                else:
                    with open(app_log_path, 'r') as f:
                        lines = f.readlines()

                    # Filter for backup-related entries
                    backup_lines = [
                        line for line in lines
                        if 'data_backup' in line.lower() or 'backup' in line.lower()
                    ]

                    if not backup_lines:
                        print("\n" + _t("data_backup.no_log_entries"))
                    else:
                        # Show last 50 backup-related lines
                        print("\n" + _t("data_backup.backup_log", count=min(50, len(backup_lines))) + ":")
                        print("-" * 80)
                        for line in backup_lines[-50:]:
                            print(line.strip())
            except (OSError, IOError) as e:
                print(_t("data_backup.error_reading_log", error=str(e)))
            except UnicodeDecodeError as e:
                print(_t("data_backup.error_reading_log", error=str(e)))

            input("\n" + _t("common.press_enter"))

        elif choice == '20':
            # Stop scheduler and return
            stop_scheduler()
            print(_t("data_backup.returning_main"))
            break

        else:
            print(_t("data_backup.invalid_choice"))
