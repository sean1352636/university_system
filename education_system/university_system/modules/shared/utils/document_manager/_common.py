# Common imports shared across all document_manager submodules
import os
import csv
import json
import time
import shutil
import hashlib
import zipfile
import threading
from datetime import datetime, timedelta

# Internationalization
from education_system.university_system.core.i18n import get_text as _t

# Local imports - Database
from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager, get_connection

# Local imports - Paths
from education_system.university_system.core import paths

# SQL safety
from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608

# Local imports - Authentication
from education_system.university_system.infrastructure.auth import UserAuth, get_current_user, set_auth_instance
from education_system.university_system.infrastructure.shared_context import get_auth

# Import activity logger for audit trail
try:
    from education_system.university_system.core.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

# Optional imports - Email system
try:
    from education_system.university_system.infrastructure.email import (
        send_email,
        send_template_email,
        queue_email,
        initialize_communication_system,
        set_auth
    )
    from education_system.university_system.core.logs import log_event
    from education_system.university_system.infrastructure.email.template_utils import render_template
    EMAIL_SYSTEM_AVAILABLE = True
except ImportError:
    EMAIL_SYSTEM_AVAILABLE = False
    print(_t("shared.utils.document_manager.warning_email_unavailable", default="Warning: Email system not available"))
    # Provide a fallback log_event function
    def log_event(level, message):
        print(f"[{level.upper()}] {message}")


_base_get_connection = get_connection


def get_connection(*args, **kwargs):
    import sys

    package = sys.modules.get("education_system.university_system.modules.shared.utils.document_manager")
    package_get_connection = getattr(package, "get_connection", None)
    if callable(package_get_connection) and package_get_connection is not get_connection:
        return package_get_connection(*args, **kwargs)
    return _base_get_connection(*args, **kwargs)
