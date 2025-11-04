"""
Backwards-compatible facade for the legacy email_manager interface.

DEPRECATED: This module exists only for backwards compatibility.
New code should import directly from university_system.infrastructure.email.*

Canonical email infrastructure locations:
- Email sending: university_system.infrastructure.email.email_service
- Configuration: university_system.infrastructure.email.config
- Templates: university_system.infrastructure.email.templates
- Admin/Dashboard: university_system.infrastructure.email.admin
- Reports: university_system.infrastructure.email.reports
- Announcements: university_system.infrastructure.email.announcements
- Chat: university_system.infrastructure.email.chat_rooms
- SMTP: university_system.infrastructure.email.smtp

This facade will be removed in a future version.
"""

from __future__ import annotations

from importlib import import_module

_MODULE_EXPORTS = {
    'config': [
        'CONFIG_SCHEMA',
        'DEFAULT_CONFIG',
        'config',
        'validate_email_config',
        'load_config',
        'save_config',
        'validate_config',
        'configure_email_settings',
        'test_email_configuration',
        'ensure_email_config_for_database_mode'
    ],
    'logs': [
        'configure_logging',
        'get_log_file',
        'log_event',
        'handle_exception',
        'display_communication_logs_menu',
        'display_activity_logs',
        'export_communication_logs',
        'display_communication_analytics_menu',
        'LOG_MANAGEMENT_AVAILABLE',
        'log_manager',
        'logger'
    ],
    'database': [
        '_DB_READY',
        'USE_AUTH_DB',
        'MAIN_DIR',
        'PROJECT_ROOT',
        'DB_PATH',
        '_db_manager',
        '_db_manager_lock',
        '_ensure_db_ready',
        'ensure_db_directory',
        'ensure_parent_dir',
        'get_unified_connection',
        'SimpleDBManager',
        'get_db_manager',
        'execute_db_operation',
        'safe_db_operation',
        'initialize_email_db',
        'migrate_email_log_table',
        'schedule_database_maintenance',
        'optimize_database'
    ],
    'templates': [
        'DEFAULT_TEMPLATES',
        'initialize_analytics_templates',
        'ensure_templates_directory',
        'save_default_templates',
        'list_templates',
        'load_template',
        'create_template',
        'update_template',
        'delete_template',
        'render_template',
        'template_management_menu'
    ],
    'smtp': [
        'send_email_via_smtp'
    ],
    'reports': [
        'log_email_metrics',
        'generate_report',
        'generate_report_form',
        'get_user_communication_stats',
        'get_recent_communication_activity',
        'get_system_health_info'
    ],
    'announcements': [
        'send_batch_announcement',
        'display_announcements_menu',
        'create_announcement_safe',
        '_send_announcement_notifications',
        'mark_announcement_viewed',
        'get_announcement_by_id',
        'deactivate_announcement'
    ],
    'chat_rooms': [
        'initialize_chat_tables',
        'display_my_chat_rooms',
        'display_public_rooms',
        'create_chat_room_form',
        'enter_chat_room',
        'display_room_invitations',
        'manage_chat_room',
        'display_all_rooms_admin',
        'display_chat_rooms_menu'
    ],
    'email_service': [
        'email_queue',
        'worker_threads',
        'scheduled_jobs',
        'safe_log_email',
        'send_email',
        'send_email_db_only',
        'fix_inbox_display_issue',
        'generate_system_username',
        'send_email_as_user',
        'send_email_as_system',
        'get_appropriate_sender_id',
        'send_template_email',
        'get_stored_emails',
        'delete_stored_email',
        'clear_stored_emails',
        'email_worker',
        'start_email_workers',
        'stop_email_workers',
        'queue_email',
        'queue_template_email',
        'wait_for_email_queue',
        'send_bulk',
        'schedule_send',
        'process_scheduled_emails',
        'ensure_scheduler_running',
        'run_scheduler',
        'update_scheduled_email_status',
        'send_registration_confirmation',
        'send_update_confirmation',
        'send_grade_notification',
        'send_password_reset',
        'send_assignment_notification',
        'send_extension_notification',
        'send_confirmation_email',
        'send_batch_email_form',
        'schedule_email_form',
        'send_ticket_notification',
        'send_reply_notification',
        'send_appointment_confirmation',
        'send_health_notification',
        'send_internship_notification',
        'send_application_confirmation',
        'send_alumni_welcome_email',
        'send_mentorship_notification',
        'send_event_invitation',
        'send_donation_receipt',
        'send_permit_confirmation',
        'send_permit_update_confirmation',
        'send_book_checkout_confirmation',
        'send_book_return_reminder',
        'send_overdue_notification',
        'display_stored_emails_menu',
        'send_sla_alert',
        'send_satisfaction_survey',
        'send_bulk_satisfaction_surveys',
        'fix_existing_email_senders',
        'test_sender_attribution'
    ],
    'admin': [
        'search_users',
        'list_all_users',
        'integrate_communication_dashboard_with_main',
        'display_preferences_menu',
        'display_admin_message_management_menu',
        'display_communication_dashboard',
        'set_auth',
        'set_communication_auth',
        'initialize_integrated_system',
        'cleanup_integrated_system',
        'initialize_communication_system',
        'cleanup_communication_system',
        'test_email_system',
        'test_communication_dashboard_methods',
        'CommunicationDashboard',
        'send_system_notification',
        'display_messages_menu'
    ],
    'misc': [
        'debug_function_definition',
        'find_function_in_file',
        'check_syntax_errors'
    ],
}

__all__ = []
_globals = globals()

# Map module names to their actual import paths
_MODULE_PATHS = {
    'config': '.config',
    'logs': '.logs',
    'database': '.database',
    'templates': 'university_system.infrastructure.email.templates',
    'smtp': 'university_system.infrastructure.email.smtp',
    'reports': 'university_system.infrastructure.email.reports',
    'announcements': 'university_system.infrastructure.email.announcements',
    'chat_rooms': 'university_system.infrastructure.email.chat_rooms',
    'email_service': 'university_system.infrastructure.email.email_service',
    'admin': 'university_system.infrastructure.email.admin',
    'misc': 'university_system.infrastructure.email.misc',
}

for module_name, names in _MODULE_EXPORTS.items():
    import_path = _MODULE_PATHS.get(module_name, f".{module_name}")

    # Handle relative vs absolute imports
    if import_path.startswith('.'):
        module = import_module(import_path, __package__)
    else:
        module = import_module(import_path)

    for name in names:
        try:
            obj = getattr(module, name)
        except AttributeError as exc:
            raise AttributeError(f"{module_name}.{name} is not available") from exc
        _globals[name] = obj
        __all__.append(name)
