"""Formatting, identifier generation and auth helpers."""

import logging
import random
import string
from datetime import datetime

import education_system.systems.university.plugins.campus_commerce.interfaces.cli.services.nailbar_cli as _pkg

logger = logging.getLogger(__name__)


def print_header(text: str):
    """Print a formatted header"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_subheader(text: str):
    """Print a formatted subheader"""
    print("\n" + "-" * 70)
    print(f"  {text}")
    print("-" * 70)


def get_current_user():
    """Get the currently logged-in user"""
    try:
        auth = _pkg.get_auth()
        if auth and hasattr(auth, 'current_user') and auth.current_user:
            return auth.current_user
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
    return None


def is_staff():
    """Check if current user is staff/admin"""
    try:
        user = get_current_user()
        if user:
            role = user.get('role', '').lower()
            return role in ['admin', 'staff', 'instructor']
    except Exception as e:
        logger.error(f"Error checking staff status: {e}")
    return False


def generate_booking_ref():
    """Generate unique booking reference"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    random_suffix = ''.join(random.choices(string.digits, k=4))
    return f"NAIL-{timestamp}-{random_suffix}"


def generate_receipt_number():
    """Generate unique receipt number"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"REC-{timestamp}-{random_suffix}"


def format_currency(amount: float) -> str:
    """Format amount as currency"""
    try:
        return f"£{float(amount):.2f}"
    except (ValueError, TypeError):
        return "£0.00"


def format_date(date_str: str) -> str:
    """Format date string for display"""
    try:
        if isinstance(date_str, str):
            dt = datetime.strptime(date_str, '%Y-%m-%d')
        else:
            dt = date_str
        return dt.strftime('%d %B %Y')
    except Exception:
        return str(date_str)


__all__ = [
    'print_header', 'print_subheader', 'get_current_user', 'is_staff',
    'generate_booking_ref', 'generate_receipt_number', 'format_currency',
    'format_date',
]
