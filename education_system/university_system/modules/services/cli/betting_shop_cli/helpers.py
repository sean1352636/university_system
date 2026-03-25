"""
Betting Shop CLI - Helper/utility functions.
"""

from education_system.university_system.modules.services.cli.betting_shop_cli.constants import logger, get_auth


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


def is_admin():
    """Check if current user is admin/staff"""
    user = get_current_user()
    if not user:
        return False
    role = user.get('role', '').lower()
    return role in ['admin', 'staff', 'administrator']
