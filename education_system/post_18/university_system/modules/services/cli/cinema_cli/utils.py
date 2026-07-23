"""Cinema CLI utility and formatting functions."""

import logging

from education_system.post_18.university_system.infrastructure.shared_context import get_auth

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
        auth = get_auth()
        if auth and hasattr(auth, 'current_user') and auth.current_user:
            return auth.current_user
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
    return None


def is_staff_or_admin(user) -> bool:
    """Check if user has staff or admin privileges"""
    if not user:
        return False
    role = user.get('role', '').lower()
    return role in ['admin', 'staff', 'instructor']
