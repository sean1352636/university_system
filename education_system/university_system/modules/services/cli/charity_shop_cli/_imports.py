"""
Shared imports, constants, and utilities for the charity shop CLI package.
"""

from education_system.university_system.infrastructure.database.db import sqlite3
import logging
import csv
import json
import os
import random
import string
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from decimal import Decimal

# University system imports
from education_system.university_system.core.paths import DEFAULT_DB_PATH
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.core.sql_safety import safe_alter_table_add_column

# Import auth instance management
try:
    from education_system.university_system.infrastructure.auth import get_current_user, set_auth_instance
    from education_system.university_system.infrastructure.shared_context import get_auth, set_auth as set_shared_auth
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None
    get_auth = lambda: None
    set_shared_auth = lambda x: None

# Import activity logger for audit trail
try:
    from education_system.university_system.modules.shared.utils.simple_activity_logger import (
        log_activity,
        log_create,
        log_read,
        log_update,
        log_delete,
        log_search,
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
    log_search = lambda *args, **kwargs: None
    log_menu_navigation = lambda *args, **kwargs: None

# Import i18n for internationalization
from education_system.university_system.core.i18n import (
    get_text,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)

logger = logging.getLogger(__name__)

# Global auth instance
auth = None

# Table name for charity shop stock
TABLE_NAME = "charity_shop_stock"

# Additional table names
CUSTOMERS_TABLE = "charity_shop_customers"
DONATIONS_TABLE = "charity_shop_donations"
DONORS_TABLE = "charity_shop_donors"
STAFF_TABLE = "charity_shop_staff"
GIFT_CARDS_TABLE = "charity_shop_gift_cards"
PRICE_HISTORY_TABLE = "charity_shop_price_history"
SALES_TABLE = "charity_shop_sales"
BUNDLES_TABLE = "charity_shop_bundles"
PROMOTIONS_TABLE = "charity_shop_promotions"
LAYAWAY_TABLE = "charity_shop_layaway"
LOYALTY_TABLE = "charity_shop_loyalty"
ARCHIVED_TABLE = "charity_shop_archived"
LOCATIONS_TABLE = "charity_shop_locations"
SHIFTS_TABLE = "charity_shop_shifts"
TASKS_TABLE = "charity_shop_tasks"
WISHLISTS_TABLE = "charity_shop_wishlists"
FEEDBACK_TABLE = "charity_shop_feedback"
REFERRALS_TABLE = "charity_shop_referrals"

# Validate all table name constants at module load time
from education_system.university_system.core.sql_safety import validate_table_name
for _tbl in [TABLE_NAME, CUSTOMERS_TABLE, DONATIONS_TABLE, DONORS_TABLE, STAFF_TABLE,
             GIFT_CARDS_TABLE, PRICE_HISTORY_TABLE, SALES_TABLE, BUNDLES_TABLE,
             PROMOTIONS_TABLE, LAYAWAY_TABLE, LOYALTY_TABLE, ARCHIVED_TABLE,
             LOCATIONS_TABLE, SHIFTS_TABLE, TASKS_TABLE, WISHLISTS_TABLE,
             FEEDBACK_TABLE, REFERRALS_TABLE]:
    validate_table_name(_tbl)

# Categories for charity shop items
CATEGORIES = [
    "Books", "Clothing", "Electronics", "Furniture", "Homeware",
    "Toys", "Music/DVDs", "Accessories", "Sports", "Other"
]

# Condition options
CONDITIONS = ["New", "Excellent", "Good", "Fair", "Poor"]

# Low stock threshold default
DEFAULT_LOW_STOCK_THRESHOLD = 5

# Loyalty points per pound spent
LOYALTY_POINTS_PER_POUND = 10


def set_auth(auth_instance: Any) -> None:
    """Set the global auth instance for charity shop CLI."""
    global auth
    auth = auth_instance
    if HAS_AUTH:
        set_auth_instance(auth_instance)
        try:
            set_shared_auth(auth_instance)
        except Exception as e:
            logger.warning(f"Failed to set auth in shared_context: {e}")
