from typing import Any
# Import logging helpers from the refactored utils module
from education_system.university_system.modules.shared.utils.simple_activity_logger import (
    log_activity,
    log_create,
    log_read,
    log_update,
    log_delete,
    log_search,
    log_export,
    log_menu_navigation,
    log_dynamic_activity,
)

# Global variables
# Import auth instance management from user_authentication
try:
    from education_system.university_system.infrastructure.auth import get_current_user, set_auth_instance
    from education_system.university_system.infrastructure.shared_context import get_auth
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None
    get_auth = lambda: None

auth = None

def set_auth(auth_instance: Any) -> None:
    global auth
    auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)


def format_currency(amount):
    """Format amount as currency"""
    try:
        return f"£{float(amount):.2f}"
    except (ValueError, TypeError):
        return "£0.00"

def calculate_tax(amount, tax_rate=0.2):
    """Calculate tax amount"""
    try:
        return float(amount) * float(tax_rate)
    except (ValueError, TypeError):
        return 0.0

def get_system_settings():
    """Get system-wide shop settings"""
    default_settings = {
        'currency_symbol': '£',
        'default_tax_rate': 0.2,
        'low_stock_threshold': 10,
        'max_cart_items': 50,
        'receipt_footer': 'Thank you for shopping with us!',
        'shop_name': 'University Shop',
        'shop_address': 'University Campus',
        'shop_phone': '555-SHOP',
        'shop_email': 'shop@university.edu'
    }

    # In a real system, these might be stored in a settings table
    return default_settings
