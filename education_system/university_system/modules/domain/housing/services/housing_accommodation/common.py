from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager
import datetime
import os
import random
import string
# Use logging helpers from the refactored utils module
from education_system.university_system.modules.shared.utils.i18n import (
    get_text,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)
from education_system.university_system.modules.shared.utils.simple_activity_logger import (
    log_activity,
    log_create,
    log_read,
    log_update,
    log_delete,
    log_search,
    log_export,
    log_menu_navigation,
)
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.utils.finance_integration import record_payment_to_finance

# Global variable to store the auth instance
# Import auth instance management from user_authentication
try:
    from education_system.university_system.infrastructure.auth import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

auth = None

def set_auth(auth_instance):
    global auth
    auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)

def generate_id(prefix):
    """Generate a unique ID with a given prefix"""
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{prefix}-{timestamp}-{random_chars}"
