"""
Library settings management module.

This module provides functions for managing library system settings,
user preferences, authentication, and fine payment processing.
"""

from education_system.university_system.infrastructure.database.db import (
    sqlite3,
    get_connection as get_db_conn,
)
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
from education_system.university_system.modules.shared.utils.i18n import get_text
from education_system.university_system.infrastructure.logging.log_config import configure_logging
from datetime import datetime
from typing import Any, Dict, List, Optional

# Configure logging
logger = configure_logging(name=__name__)

DATABASE_FILE = str(DEFAULT_DB_PATH)

# Global auth object for backwards compatibility
auth = None


def get_db_connection() -> Optional[sqlite3.Connection]:
    """Get database connection wrapper."""
    try:
        return get_db_conn()
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None


def set_auth(auth_object) -> None:
    """Set global auth object for backwards compatibility.

    Parameters
    ----------
    auth_object : object
        The authentication object to use globally.
    """
    global auth
    auth = auth_object
    # Also set it in the global auth instance if available
    try:
        from education_system.university_system.infrastructure.auth import set_auth_instance
        set_auth_instance(auth_object)
    except ImportError:
        pass


def get_current_user_id() -> str:
    """Get current user ID from auth system.

    Returns
    -------
    str
        The current user's ID or 'cli_user' if not authenticated.
    """
    global auth
    if auth and hasattr(auth, 'current_user') and auth.current_user:
        return auth.current_user.get('user_id', 'cli_user')

    # Try to get from shared context
    try:
        from education_system.university_system.infrastructure.shared_context import get_auth
        shared_auth = get_auth()
        if shared_auth and shared_auth.current_user:
            return shared_auth.current_user.get('user_id', 'cli_user')
    except ImportError:
        pass

    return 'cli_user'


def get_library_settings(setting_name: str) -> Optional[str]:
    """Get library setting value by name.

    Parameters
    ----------
    setting_name : str
        The name of the setting to retrieve.

    Returns
    -------
    Optional[str]
        The setting value if found, None otherwise.
    """
    try:
        conn = get_db_connection()
        if not conn:
            return None

        cursor = conn.cursor()
        cursor.execute(
            'SELECT setting_value FROM library_settings WHERE setting_name = ?',
            (setting_name,)
        )
        result = cursor.fetchone()
        conn.close()

        return result[0] if result else None
    except sqlite3.Error as e:
        logger.error(f"Error getting setting {setting_name}: {e}")
        return None


def update_library_setting(setting_name: str, setting_value: str) -> bool:
    """Update or insert a library setting.

    Parameters
    ----------
    setting_name : str
        The name of the setting to update.
    setting_value : str
        The new value for the setting.

    Returns
    -------
    bool
        True if successful, False otherwise.
    """
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO library_settings (setting_name, setting_value)
            VALUES (?, ?)
        ''', (setting_name, setting_value))

        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error updating setting {setting_name}: {e}")
        return False


def validate_setting_value(setting_name: str, value: Any) -> Dict:
    """Validate a setting value before saving.

    Parameters
    ----------
    setting_name : str
        The name of the setting being validated.
    value : Any
        The value to validate.

    Returns
    -------
    Dict
        A dictionary with 'valid' (bool) and 'message' (str) keys.
    """
    # Define validation rules for known settings
    validation_rules = {
        'max_loan_days': lambda v: isinstance(v, int) and 1 <= v <= 365,
        'max_renewals': lambda v: isinstance(v, int) and 0 <= v <= 10,
        'fine_per_day': lambda v: isinstance(v, (int, float)) and v >= 0,
        'max_books_per_user': lambda v: isinstance(v, int) and 1 <= v <= 100,
        'reservation_expiry_days': lambda v: isinstance(v, int) and 1 <= v <= 30,
    }

    if setting_name in validation_rules:
        try:
            if validation_rules[setting_name](value):
                return {'valid': True, 'message': 'Setting value is valid'}
            else:
                return {'valid': False, 'message': f'Invalid value for {setting_name}'}
        except (TypeError, ValueError) as e:
            return {'valid': False, 'message': str(e)}

    # For unknown settings, accept any string value
    return {'valid': True, 'message': 'Setting value accepted'}


def validate_library_configuration() -> Dict:
    """Validate the entire library configuration.

    Returns
    -------
    Dict
        A dictionary with validation results and any issues found.
    """
    issues = []

    try:
        conn = get_db_connection()
        if not conn:
            return {'valid': False, 'issues': ['Cannot connect to database']}

        cursor = conn.cursor()

        # Check required settings exist
        required_settings = ['max_loan_days', 'fine_per_day', 'max_books_per_user']
        for setting in required_settings:
            cursor.execute(
                'SELECT setting_value FROM library_settings WHERE setting_name = ?',
                (setting,)
            )
            if not cursor.fetchone():
                issues.append(f"Missing required setting: {setting}")

        conn.close()

        return {
            'valid': len(issues) == 0,
            'issues': issues
        }
    except sqlite3.Error as e:
        return {'valid': False, 'issues': [str(e)]}


def enhanced_manage_settings() -> None:
    """Enhanced settings management with CLI interface."""
    print("\n" + "=" * 60)
    print(get_text("library.settings.title"))
    print("=" * 60)

    while True:
        print(f"\n1. {get_text('library.settings.view_all')}")
        print(f"2. {get_text('library.settings.update_setting')}")
        print(f"3. {get_text('library.settings.validate_config')}")
        print(f"4. {get_text('library.settings.reset_defaults')}")
        print(f"0. {get_text('common.back')}")

        choice = input(f"\n{get_text('library.settings.select_option')}: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _display_all_settings()
        elif choice == '2':
            _update_setting_interactive()
        elif choice == '3':
            result = validate_library_configuration()
            if result['valid']:
                print(f"\n✓ {get_text('library.settings.config_valid')}")
            else:
                print(f"\n✗ {get_text('library.settings.config_issues')}:")
                for issue in result['issues']:
                    print(f"  - {issue}")
        elif choice == '4':
            _reset_to_defaults()
        else:
            print(get_text("common.invalid_choice"))


def manage_settings() -> None:
    """Basic settings management interface."""
    enhanced_manage_settings()


def _display_all_settings() -> None:
    """Display all library settings."""
    try:
        conn = get_db_connection()
        if not conn:
            print(get_text("library.settings.db_connect_error"))
            return

        cursor = conn.cursor()
        cursor.execute('SELECT setting_name, setting_value FROM library_settings ORDER BY setting_name')
        settings = cursor.fetchall()
        conn.close()

        if not settings:
            print(f"\n{get_text('library.settings.no_settings')}")
            return

        print(f"\n{get_text('library.settings.current_settings')}:")
        print("-" * 40)
        for name, value in settings:
            print(f"  {name}: {value}")
        print("-" * 40)
    except sqlite3.Error as e:
        print(get_text("library.settings.load_error").format(error=e))


def _update_setting_interactive() -> None:
    """Interactively update a setting."""
    setting_name = input(f"{get_text('library.settings.enter_name')}: ").strip()
    if not setting_name:
        print(get_text("library.settings.name_required"))
        return

    current_value = get_library_settings(setting_name)
    if current_value:
        print(f"{get_text('library.settings.current_value')}: {current_value}")

    new_value = input(f"{get_text('library.settings.enter_value')}: ").strip()
    if not new_value:
        print(get_text("library.settings.value_required"))
        return

    if update_library_setting(setting_name, new_value):
        print(get_text("library.settings.update_success").format(name=setting_name))
    else:
        print(get_text("library.settings.update_failed").format(name=setting_name))


def _reset_to_defaults() -> None:
    """Reset settings to default values."""
    confirm = input(f"{get_text('library.settings.reset_confirm')} ({get_text('common.yes')}/{get_text('common.no')}): ").strip().lower()
    if confirm != get_text('common.yes'):
        print(get_text("library.settings.reset_cancelled"))
        return

    defaults = {
        'max_loan_days': '14',
        'max_renewals': '3',
        'fine_per_day': '0.50',
        'max_books_per_user': '10',
        'reservation_expiry_days': '7',
        'allow_self_checkout': 'true',
        'send_overdue_notifications': 'true',
    }

    for name, value in defaults.items():
        update_library_setting(name, value)

    print(f"✓ {get_text('library.settings.reset_success')}")


def manage_user_achievements(user_id: str = None) -> Dict:
    """Manage user reading achievements and badges.

    Parameters
    ----------
    user_id : str, optional
        The user ID to check achievements for. Uses current user if not specified.

    Returns
    -------
    Dict
        Dictionary containing user achievements and badges.
    """
    if not user_id:
        user_id = get_current_user_id()

    achievements = {
        'user_id': user_id,
        'badges': [],
        'reading_streak': 0,
        'books_read': 0,
        'reviews_written': 0,
    }

    try:
        conn = get_db_connection()
        if not conn:
            return achievements

        cursor = conn.cursor()

        # Count books read (returned loans)
        cursor.execute('''
            SELECT COUNT(*) FROM book_loans
            WHERE user_id = ? AND return_date IS NOT NULL
        ''', (user_id,))
        result = cursor.fetchone()
        achievements['books_read'] = result[0] if result else 0

        # Count reviews written
        cursor.execute('''
            SELECT COUNT(*) FROM book_reviews WHERE user_id = ?
        ''', (user_id,))
        result = cursor.fetchone()
        achievements['reviews_written'] = result[0] if result else 0

        # Assign badges based on achievements
        if achievements['books_read'] >= 100:
            achievements['badges'].append(get_text('library.badges.century_reader'))
        elif achievements['books_read'] >= 50:
            achievements['badges'].append(get_text('library.badges.avid_reader'))
        elif achievements['books_read'] >= 10:
            achievements['badges'].append(get_text('library.badges.book_worm'))
        elif achievements['books_read'] >= 1:
            achievements['badges'].append(get_text('library.badges.first_read'))

        if achievements['reviews_written'] >= 20:
            achievements['badges'].append(get_text('library.badges.top_reviewer'))
        elif achievements['reviews_written'] >= 5:
            achievements['badges'].append(get_text('library.badges.active_reviewer'))

        conn.close()
    except sqlite3.Error as e:
        logger.error(f"Error loading achievements: {e}")

    return achievements


def sync_user_data(user_id: str = None) -> bool:
    """Sync user data across library modules.

    Parameters
    ----------
    user_id : str, optional
        The user ID to sync. Uses current user if not specified.

    Returns
    -------
    bool
        True if sync was successful, False otherwise.
    """
    if not user_id:
        user_id = get_current_user_id()

    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        # Update last sync timestamp
        cursor.execute('''
            UPDATE library_users
            SET last_sync = ?
            WHERE user_id = ?
        ''', (datetime.now().isoformat(), user_id))

        conn.commit()
        conn.close()

        logger.info(f"User data synced for {user_id}")
        return True
    except sqlite3.Error as e:
        logger.error(f"Error syncing user data: {e}")
        return False


def validate_user_permissions(user_id: str, permission: str) -> bool:
    """Validate if user has a specific library permission.

    Parameters
    ----------
    user_id : str
        The user ID to check.
    permission : str
        The permission to validate (e.g., 'borrow_books', 'manage_inventory').

    Returns
    -------
    bool
        True if user has the permission, False otherwise.
    """
    # Define default permissions by role
    role_permissions = {
        'admin': ['borrow_books', 'manage_inventory', 'manage_users', 'view_reports',
                  'process_fines', 'configure_settings'],
        'librarian': ['borrow_books', 'manage_inventory', 'view_reports', 'process_fines'],
        'instructor': ['borrow_books', 'view_reports', 'create_reading_lists'],
        'student': ['borrow_books', 'view_own_history', 'create_reading_lists'],
    }

    try:
        # Get user role
        global auth
        user_role = 'student'  # Default

        if auth and hasattr(auth, 'current_user') and auth.current_user:
            user_role = auth.current_user.get('role', 'student').lower()

        # Check if permission is granted for this role
        if user_role in role_permissions:
            return permission in role_permissions[user_role]

        return False
    except Exception as e:
        logger.error(f"Error validating permissions: {e}")
        return False


def update_reading_goals(user_id: str = None, goals: Dict = None) -> bool:
    """Update user's reading goals.

    Parameters
    ----------
    user_id : str, optional
        The user ID. Uses current user if not specified.
    goals : Dict, optional
        Dictionary containing goal settings (e.g., {'books_per_year': 24}).

    Returns
    -------
    bool
        True if goals were updated, False otherwise.
    """
    if not user_id:
        user_id = get_current_user_id()

    if not goals:
        goals = {'books_per_year': 12, 'pages_per_day': 30}

    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        # Store goals as JSON in user preferences
        import json
        goals_json = json.dumps(goals)

        cursor.execute('''
            INSERT OR REPLACE INTO user_preferences (user_id, preference_key, preference_value)
            VALUES (?, 'reading_goals', ?)
        ''', (user_id, goals_json))

        conn.commit()
        conn.close()

        logger.info(f"Reading goals updated for {user_id}")
        return True
    except sqlite3.Error as e:
        logger.error(f"Error updating reading goals: {e}")
        return False


def record_usage_analytics(action: str, details: Dict = None) -> None:
    """Record usage analytics for the library system.

    Parameters
    ----------
    action : str
        The action being recorded (e.g., 'book_view', 'search', 'checkout').
    details : Dict, optional
        Additional details about the action.
    """
    user_id = get_current_user_id()

    try:
        conn = get_db_connection()
        if not conn:
            return

        cursor = conn.cursor()

        # Ensure analytics table exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS library_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                action TEXT NOT NULL,
                details TEXT,
                timestamp TEXT NOT NULL
            )
        ''')

        import json
        details_json = json.dumps(details) if details else None

        cursor.execute('''
            INSERT INTO library_analytics (user_id, action, details, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (user_id, action, details_json, datetime.now().isoformat()))

        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        logger.error(f"Error recording analytics: {e}")


def process_fine_payment(fine_id: int = None, user_id: str = None,
                         amount: float = None, payment_method: str = 'cash') -> Dict:
    """Process a fine payment.

    Parameters
    ----------
    fine_id : int, optional
        The specific fine ID to pay.
    user_id : str, optional
        The user ID paying fines.
    amount : float, optional
        The amount to pay. If not specified, pays all outstanding fines.
    payment_method : str, optional
        Payment method (cash, card, account). Default is 'cash'.

    Returns
    -------
    Dict
        Result dictionary with success status and payment details.
    """
    if not user_id:
        user_id = get_current_user_id()

    result = {
        'success': False,
        'message': '',
        'amount_paid': 0.0,
        'receipt_id': None,
    }

    try:
        conn = get_db_connection()
        if not conn:
            result['message'] = 'Cannot connect to database'
            return result

        cursor = conn.cursor()

        # Get outstanding fines
        if fine_id:
            cursor.execute('''
                SELECT loan_id, fine_amount, paid FROM book_loans
                WHERE loan_id = ? AND user_id = ? AND fine_amount > 0 AND (paid IS NULL OR paid = 0)
            ''', (fine_id, user_id))
        else:
            cursor.execute('''
                SELECT loan_id, fine_amount, paid FROM book_loans
                WHERE user_id = ? AND fine_amount > 0 AND (paid IS NULL OR paid = 0)
            ''', (user_id,))

        fines = cursor.fetchall()

        if not fines:
            result['message'] = 'No outstanding fines found'
            return result

        total_fines = sum(f[1] for f in fines)
        payment_amount = amount if amount else total_fines

        if payment_amount < total_fines and not fine_id:
            result['message'] = f'Partial payment not allowed. Total fines: £{total_fines:.2f}'
            return result

        # Process payment
        import uuid
        receipt_id = str(uuid.uuid4())[:8].upper()

        for loan_id, fine_amount, _ in fines:
            cursor.execute('''
                UPDATE book_loans SET paid = 1, payment_date = ?, payment_method = ?
                WHERE loan_id = ?
            ''', (datetime.now().isoformat(), payment_method, loan_id))

        # Record payment in payment_history
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS library_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                receipt_id TEXT UNIQUE,
                user_id TEXT,
                amount REAL,
                payment_method TEXT,
                payment_date TEXT
            )
        ''')

        # 8.117.103: also write to the unified ``payments`` table so
        # finance reports / cross-domain views see this payment. The
        # legacy ``library_payments`` row above is kept until all
        # readers migrate (only ``generate_fine_receipt`` reads it
        # today). Idempotent on (source_type, source_payment_id).
        conn.commit()
        conn.close()
        try:
            from education_system.university_system.modules.domain.finance.core.unified_payments import (
                record_payment,
            )
            record_payment(
                student_id=user_id,
                amount=payment_amount,
                payment_method=payment_method,
                source_type='library',
                source_payment_id=receipt_id,
                payment_type='fine',
                department='library',
                description='Library fine payment',
            )
        except Exception as exc:
            logger.warning(f"Unified payment mirror failed (library): {exc}")

        result['success'] = True
        result['message'] = f'Payment of £{payment_amount:.2f} processed successfully'
        result['amount_paid'] = payment_amount
        result['receipt_id'] = receipt_id

        # Record analytics
        record_usage_analytics('fine_payment', {
            'amount': payment_amount,
            'method': payment_method,
            'receipt_id': receipt_id
        })

    except sqlite3.Error as e:
        result['message'] = f'Payment error: {e}'
        logger.error(f"Fine payment error: {e}")

    return result


def generate_fine_receipt(receipt_id: str = None, payment_info: Dict = None) -> str:
    """Generate a fine payment receipt.

    Parameters
    ----------
    receipt_id : str, optional
        The receipt ID to generate.
    payment_info : Dict, optional
        Payment information dictionary.

    Returns
    -------
    str
        The formatted receipt text.
    """
    receipt_lines = [
        "=" * 50,
        "        UNIVERSITY LIBRARY",
        "        FINE PAYMENT RECEIPT",
        "=" * 50,
    ]

    try:
        if receipt_id:
            # 8.117.103: read from the unified payments table first
            # (the new write path). Fall back to library_payments for
            # rows recorded before the migration.
            payment = None
            try:
                from education_system.university_system.modules.domain.finance.core.unified_payments import (
                    read_payments,
                )
                rows = read_payments(source_type='library',
                                     source_payment_id=receipt_id, limit=1)
                if rows:
                    r = rows[0]
                    payment = (r.get('student_id'), r.get('amount'),
                               r.get('payment_method'), r.get('payment_date'))
            except Exception:
                payment = None

            if not payment:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT user_id, amount, payment_method, payment_date
                        FROM library_payments WHERE receipt_id = ?
                    ''', (receipt_id,))
                    payment = cursor.fetchone()
                    conn.close()

            if payment:
                user_id, amount, method, date = payment
                receipt_lines.extend([
                    f"Receipt #: {receipt_id}",
                    f"Date: {date}",
                    f"User ID: {user_id}",
                    "-" * 50,
                    f"Amount Paid: £{amount:.2f}",
                    f"Payment Method: {method.title()}",
                    "-" * 50,
                    "",
                    "Thank you for your payment!",
                    "=" * 50,
                ])
        elif payment_info:
            receipt_lines.extend([
                f"Receipt #: {payment_info.get('receipt_id', 'N/A')}",
                f"Date: {payment_info.get('date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}",
                f"User ID: {payment_info.get('user_id', 'N/A')}",
                "-" * 50,
                f"Amount Paid: £{payment_info.get('amount', 0):.2f}",
                f"Payment Method: {payment_info.get('method', 'N/A').title()}",
                "-" * 50,
                "",
                "Thank you for your payment!",
                "=" * 50,
            ])
        else:
            receipt_lines.append("No payment information available.")
    except Exception as e:
        receipt_lines.append(f"Error generating receipt: {e}")

    return "\n".join(receipt_lines)
