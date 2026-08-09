"""Default-account bootstrap compatibility."""
from education_system.systems.university.infrastructure.exceptions import (
    AuthenticationError,
    PermissionDeniedError,
)

from ..facade import UserAuth, sqlite3

def setup_default_accounts():
    """Standalone helper to ensure baseline accounts exist."""
    print("=== ACCOUNT SETUP ===")
    try:
        auth = UserAuth()
        with auth.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            auth._create_default_accounts_if_needed(cursor, conn)

        auth.verify_default_accounts()
        print("Setup completed.")
        return True
    except sqlite3.Error as e:
        print(f"❌ Database error ensuring default accounts: {e}")
        return False
    except (AuthenticationError, PermissionDeniedError) as e:
        print(f"❌ Auth error ensuring default accounts: {e}")
        return False
