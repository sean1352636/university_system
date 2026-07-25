"""Administration and dashboard integration helpers."""

from __future__ import annotations

from education_system.systems.university.infrastructure.email.admin._imports import (
    config,
    ensure_parent_dir,
    handle_exception,
    initialize_chat_tables,
    initialize_email_db,
    load_config,
    log_event,
    save_default_templates,
    start_email_workers,
)

# --- Mixin classes ---
from education_system.systems.university.infrastructure.email.admin.db import _DbMixin
from education_system.systems.university.infrastructure.email.admin.comm_logging import _LoggingMixin
from education_system.systems.university.infrastructure.email.admin.messaging import _MessagingMixin
from education_system.systems.university.infrastructure.email.admin.mailbox import _MailboxMixin
from education_system.systems.university.infrastructure.email.admin.compose import _ComposeMixin
from education_system.systems.university.infrastructure.email.admin.announcements import _AnnouncementsMixin
from education_system.systems.university.infrastructure.email.admin.chat import _ChatMixin
from education_system.systems.university.infrastructure.email.admin.preferences import _PreferencesMixin

# --- Standalone functions ---
from education_system.systems.university.infrastructure.email.admin.users import (
    search_users,
    list_all_users,
)
from education_system.systems.university.infrastructure.email.admin.menus import (
    display_messages_menu,
    display_preferences_menu,
    display_admin_message_management_menu,
    display_communication_dashboard,
)
from education_system.systems.university.infrastructure.email.admin.initialization import (
    integrate_communication_dashboard_with_main,
    set_auth,
    set_communication_auth,
    initialize_integrated_system,
    cleanup_integrated_system,
    initialize_communication_system,
    cleanup_communication_system,
    test_email_system,
    test_communication_dashboard_methods,
    send_system_notification,
)


class CommunicationDashboard(
    _DbMixin,
    _LoggingMixin,
    _MessagingMixin,
    _MailboxMixin,
    _ComposeMixin,
    _AnnouncementsMixin,
    _ChatMixin,
    _PreferencesMixin,
):
    """Main class for managing the university communication system with enhanced logging"""

    def __init__(self, db_path=None, auth=None):
        """Initialize using the same database path as auth system with logging integration"""
        try:
            # Use auth database path if available, with proper fallback
            from education_system.systems.university.infrastructure.paths import DEFAULT_DB_PATH
            if auth and hasattr(auth, 'db_path') and auth.db_path:
                self.db_path = auth.db_path
            else:
                self.db_path = db_path or str(DEFAULT_DB_PATH)

            self.auth = auth

            # Ensure the directory exists
            ensure_parent_dir(self.db_path)

            # Initialize email system
            load_config()
            save_default_templates()

            # Initialize databases using the unified connection
            email_success = initialize_email_db()
            chat_success = initialize_chat_tables()
            main_success = self._init_db()

            success = email_success and chat_success and main_success

            # Start email workers if configuration is complete and not in database-only mode
            if not config.get('database_only_mode', True):
                if config['sender_email'] and config['smtp_server']:
                    start_email_workers()

            if not success:
                log_event('warning', "Some database tables could not be initialized.")
            else:
                log_event('info', "Communication dashboard with enhanced logging initialized successfully")

        except Exception as e:
            log_event('error', f"Error initializing Communication Dashboard: {e}")
            raise


__all__ = [
    # Main class
    'CommunicationDashboard',
    # User functions
    'search_users',
    'list_all_users',
    # Menu functions
    'display_messages_menu',
    'display_preferences_menu',
    'display_admin_message_management_menu',
    'display_communication_dashboard',
    # Initialization functions
    'integrate_communication_dashboard_with_main',
    'set_auth',
    'set_communication_auth',
    'initialize_integrated_system',
    'cleanup_integrated_system',
    'initialize_communication_system',
    'cleanup_communication_system',
    'test_email_system',
    'test_communication_dashboard_methods',
    'send_system_notification',
]
