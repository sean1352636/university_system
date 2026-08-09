
from education_system.systems.university.infrastructure.database.db import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

# University system imports
from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH

# Import auth instance management
try:
    from education_system.systems.university.infrastructure.auth import get_current_user, set_auth_instance
    from education_system.systems.university.infrastructure.shared_context import get_auth, set_auth as set_shared_auth
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None
    get_auth = lambda: None
    set_shared_auth = lambda x: None

# Import finance integration for student payments
try:
    from education_system.systems.university.infrastructure.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False

# Import activity logger for audit trail
try:
    from education_system.systems.university.infrastructure.utils.activity_logger import (
        log_activity,
        log_create,
        log_read,
        log_update,
        log_delete,
        log_menu_navigation,
    )
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None
    log_create = lambda *args, **kwargs: None
    log_read = lambda *args, **kwargs: None
    log_update = lambda *args, **kwargs: None
    log_delete = lambda *args, **kwargs: None
    log_menu_navigation = lambda *args, **kwargs: None

# Import i18n for internationalization
from education_system.systems.university.infrastructure.i18n import (
    get_text,
    get_current_language,
)
from education_system.systems.university.infrastructure.utils.language_selector import (
    display_language_menu_option,
)

logger = logging.getLogger(__name__)

# Global auth instance
auth = None

# Categories for cafe menu items
CATEGORIES = ["Hot Drinks", "Cold Drinks", "Pastries", "Food"]


__all__ = [name for name in globals() if not name.startswith("__")]
