"""Cinema CLI constants, pricing, and optional dependency imports."""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
import random
import string

from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.infrastructure.shared_context import get_auth

# Ticket pricing
TICKET_TYPES = {
    "Adult": 12.00,
    "Child": 7.00,
    "Senior": 9.00,
    "Student": 8.00,
}

# Snacks menu with full selection
SNACKS_MENU = {
    "Popcorn (Small)": 4.99,
    "Popcorn (Medium)": 6.49,
    "Popcorn (Large)": 7.99,
    "Soda (Small)": 2.99,
    "Soda (Medium)": 3.99,
    "Soda (Large)": 4.99,
    "Candy (M&Ms)": 3.49,
    "Candy (Skittles)": 3.49,
    "Candy (Maltesers)": 3.49,
    "Nachos": 5.99,
    "Hot Dog": 4.99,
    "Pretzel": 3.99,
    "Ice Cream": 3.49,
}

# Combo deals
COMBO_DEALS = {
    "Small Combo": {"items": ["Popcorn (Small)", "Soda (Small)"], "price": 9.99, "original": 7.98},
    "Medium Combo": {"items": ["Popcorn (Medium)", "Soda (Medium)"], "price": 12.99, "original": 10.48},
    "Large Combo": {"items": ["Popcorn (Large)", "Soda (Large)"], "price": 14.99, "original": 12.98},
    "Family Combo": {"items": ["Popcorn (Large)", "Popcorn (Large)", "Soda (Large)", "Soda (Large)"], "price": 24.99, "original": 25.96},
    "Snack Pack": {"items": ["Nachos", "Soda (Medium)", "Candy (M&Ms)"], "price": 11.99, "original": 12.47},
}

# Membership pricing
MEMBERSHIP_PRICE = 5.99
POINTS_PER_POUND = 1  # Earn 1 point per £1 spent
MEMBER_DISCOUNT = 0.10  # 10% discount on tickets

# Import email service
try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

# Import finance integration
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        record_payment_to_finance,
        process_student_finance_account_payment
    )
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False

# Import activity logger
try:
    from education_system.university_system.modules.shared.utils.activity_logger import log_activity
    ACTIVITY_LOGGING = True
except ImportError:
    ACTIVITY_LOGGING = False

logger = logging.getLogger(__name__)
