"""Shared imports for the admin package."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta

from education_system.systems.university.infrastructure.email import state
from education_system.systems.university.infrastructure.sql_safety import (
    validate_column_definition,
    safe_alter_table_add_column,
    SQLIdentifierError,
)

logger = logging.getLogger("university_system.infrastructure.email.admin")


# This package's menus are interactive CLI UI: prompts, message lists, message
# bodies, health reports. The root logger carries only a RotatingFileHandler
# (the console is owned by the application entry point, which the CLI never
# configures), so writing menu text with logger.info() sent every menu straight
# to app.log and left the operator staring at bare "Enter choice:" prompts.
# UI goes to stdout; the log keeps a copy. Genuine diagnostics still use
# `logger` directly.
def _out(message):
    """Print a line of menu UI to the console and record it in the log."""
    print(message)
    logger.info(message)


def _err(message):
    """Print a user-facing failure to the console and record it as an error."""
    print(message)
    logger.error(message)

from education_system.systems.university.infrastructure.email.announcements import (
    _send_announcement_notifications,
    create_announcement_safe,
    deactivate_announcement,
    display_announcements_menu,
    get_announcement_by_id,
    mark_announcement_viewed,
)
from education_system.systems.university.infrastructure.email.chat_rooms import (
    create_chat_room_form,
    display_all_rooms_admin,
    display_chat_rooms_menu,
    display_my_chat_rooms,
    display_public_rooms,
    display_room_invitations,
    enter_chat_room,
    initialize_chat_tables,
    manage_chat_room,
)
from education_system.systems.university.infrastructure.email.config import (
    config,
    configure_email_settings,
    ensure_email_config_for_database_mode,
    load_config,
    save_config,
)
from education_system.systems.university.infrastructure.email.email_db_utilities import (
    execute_db_operation,
    initialize_email_db,
    ensure_parent_dir,
    ensure_db_directory,
)
from education_system.systems.university.infrastructure.email.email_service import (
    display_stored_emails_menu,
    ensure_scheduler_running,
    get_stored_emails,
    queue_email,
    schedule_send,
    send_bulk,
    send_email,
    send_email_as_user,
    send_template_email,
    start_email_workers,
    wait_for_email_queue,
)
from education_system.systems.university.infrastructure.logs import (
    LOG_MANAGEMENT_AVAILABLE,
    display_communication_analytics_menu,
    display_communication_logs_menu,
    handle_exception,
    log_event,
    log_manager,
)
from education_system.systems.university.infrastructure.email.reports import (
    generate_report_form,
    get_recent_communication_activity,
    get_system_health_info,
    get_user_communication_stats,
)
from education_system.systems.university.infrastructure.email.state import auth_proxy as auth
from education_system.systems.university.infrastructure.email.templates import (
    template_management_menu,
    save_default_templates,
    render_template,
)
