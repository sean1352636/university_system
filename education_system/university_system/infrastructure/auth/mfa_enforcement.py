"""
MFA Enforcement Module

Enforces Multi-Factor Authentication for specific user roles to enhance security.
Admin, staff, and instructor accounts require 2FA to be enabled before full access is granted.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Set, List

logger = logging.getLogger(__name__)

# Import database connection
try:
    from education_system.university_system.infrastructure.database.db import get_connection
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

# Import security alerts for compliance notifications
try:
    from education_system.university_system.infrastructure.security.security_alerts import send_security_alert
    SECURITY_ALERTS_AVAILABLE = True
except ImportError:
    SECURITY_ALERTS_AVAILABLE = False


class MFAEnforcement:
    """
    Enforce MFA for specific user roles.

    Configurable via environment variables:
    - MFA_REQUIRED_ROLES: Comma-separated roles requiring MFA (default: admin,staff,instructor)
    - MFA_GRACE_PERIOD_DAYS: Days before MFA becomes mandatory (default: 7)
    - MFA_ENFORCEMENT_ENABLED: Enable/disable enforcement (default: true)
    """

    # Default roles requiring MFA
    DEFAULT_REQUIRED_ROLES = {'admin', 'staff', 'instructor'}

    # Grace period for new users to set up MFA
    DEFAULT_GRACE_PERIOD_DAYS = 7

    def __init__(self):
        """Initialize MFA enforcement with configuration from environment."""
        self._load_config()

    def _load_config(self):
        """Load configuration from environment variables."""
        # Load required roles
        roles_env = os.getenv('MFA_REQUIRED_ROLES', '')
        if roles_env:
            self.required_roles = set(r.strip().lower() for r in roles_env.split(',') if r.strip())
        else:
            self.required_roles = self.DEFAULT_REQUIRED_ROLES.copy()

        # Load grace period
        try:
            self.grace_period_days = int(os.getenv('MFA_GRACE_PERIOD_DAYS', str(self.DEFAULT_GRACE_PERIOD_DAYS)))
        except ValueError:
            self.grace_period_days = self.DEFAULT_GRACE_PERIOD_DAYS

        # Check if enforcement is enabled
        self.enforcement_enabled = os.getenv('MFA_ENFORCEMENT_ENABLED', 'true').lower() == 'true'

    def require_mfa_for_role(self, role: str) -> bool:
        """
        Check if a specific role requires MFA.

        Args:
            role: User role to check

        Returns:
            bool: True if role requires MFA
        """
        if not self.enforcement_enabled:
            return False
        return role.lower() in self.required_roles

    def check_mfa_compliance(self, user: Dict) -> Dict:
        """
        Check if user is MFA compliant.

        Args:
            user: User dictionary with 'role', 'mfa_enabled', 'created_at' keys

        Returns:
            dict: {
                'compliant': bool,
                'required': bool,
                'in_grace_period': bool,
                'grace_period_expires': datetime or None,
                'message': str
            }
        """
        role = user.get('role', 'student').lower()
        mfa_enabled = user.get('mfa_enabled', False)
        user_id = user.get('id') or user.get('user_id')
        username = user.get('username', 'unknown')

        result = {
            'compliant': True,
            'required': False,
            'in_grace_period': False,
            'grace_period_expires': None,
            'message': ''
        }

        # Check if MFA is required for this role
        if not self.require_mfa_for_role(role):
            return result

        result['required'] = True

        # MFA is enabled - user is compliant
        if mfa_enabled:
            return result

        # MFA not enabled - check grace period
        created_at = user.get('created_at')
        if created_at:
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                except ValueError:
                    try:
                        created_at = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        created_at = None

            if created_at:
                grace_period_end = created_at + timedelta(days=self.grace_period_days)
                if datetime.now() < grace_period_end:
                    result['in_grace_period'] = True
                    result['grace_period_expires'] = grace_period_end
                    days_remaining = (grace_period_end - datetime.now()).days
                    result['message'] = (
                        f'{role.title()} users must enable 2FA. '
                        f'You have {days_remaining} day(s) remaining to set it up.'
                    )
                    return result

        # Grace period expired or no created_at - not compliant
        result['compliant'] = False
        result['message'] = (
            f'{role.title()} users must enable Two-Factor Authentication. '
            f'Please set up 2FA to continue using the system.'
        )

        # Log non-compliance
        logger.warning(f"MFA non-compliance: user={username}, role={role}")

        return result

    def get_mfa_status(self, user_id: int) -> Optional[Dict]:
        """
        Get detailed MFA status for a user from database.

        Args:
            user_id: User ID to check

        Returns:
            dict or None: MFA status details
        """
        if not DB_AVAILABLE:
            return None

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT u.id, u.username, u.role, u.created_at,
                           COALESCE(m.is_enabled, 0) as mfa_enabled,
                           m.method as mfa_method,
                           m.setup_date as mfa_setup_date
                    FROM users u
                    LEFT JOIN user_mfa m ON u.id = m.user_id
                    WHERE u.id = ?
                ''', (user_id,))
                row = cursor.fetchone()

                if not row:
                    return None

                return {
                    'user_id': row[0],
                    'username': row[1],
                    'role': row[2],
                    'created_at': row[3],
                    'mfa_enabled': bool(row[4]),
                    'mfa_method': row[5],
                    'mfa_setup_date': row[6]
                }
        except Exception as e:
            logger.error(f"Failed to get MFA status for user {user_id}: {e}")
            return None

    def get_non_compliant_users(self) -> List[Dict]:
        """
        Get list of users who should have MFA but don't.

        Returns:
            list: List of non-compliant user dictionaries
        """
        if not DB_AVAILABLE:
            return []

        non_compliant = []
        roles_tuple = tuple(self.required_roles)

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                # Build query with proper number of placeholders
                placeholders = ','.join('?' * len(roles_tuple))
                cursor.execute(f'''
                    SELECT u.id, u.username, u.email, u.role, u.created_at
                    FROM users u
                    LEFT JOIN user_mfa m ON u.id = m.user_id
                    WHERE u.role IN ({placeholders})
                      AND u.is_active = 1
                      AND (m.is_enabled IS NULL OR m.is_enabled = 0)
                ''', roles_tuple)

                for row in cursor.fetchall():
                    user = {
                        'user_id': row[0],
                        'username': row[1],
                        'email': row[2],
                        'role': row[3],
                        'created_at': row[4]
                    }
                    compliance = self.check_mfa_compliance({
                        'role': user['role'],
                        'mfa_enabled': False,
                        'created_at': user['created_at']
                    })
                    if not compliance['compliant'] and not compliance['in_grace_period']:
                        non_compliant.append({
                            **user,
                            'grace_period_expired': True
                        })

                return non_compliant
        except Exception as e:
            logger.error(f"Failed to get non-compliant users: {e}")
            return []

    def send_mfa_reminder(self, user: Dict) -> bool:
        """
        Send MFA setup reminder to user.

        Args:
            user: User dictionary

        Returns:
            bool: True if reminder sent successfully
        """
        try:
            from education_system.university_system.infrastructure.email.email_service import send_template_email

            template_vars = {
                'username': user.get('username'),
                'role': user.get('role', '').title(),
                'days_remaining': user.get('days_remaining', 0),
                'setup_url': '/settings/security/mfa'
            }

            return send_template_email(
                'mfa_setup_reminder',
                user.get('email'),
                template_vars
            )
        except ImportError:
            logger.warning("Email service not available for MFA reminder")
            return False
        except Exception as e:
            logger.error(f"Failed to send MFA reminder: {e}")
            return False

    def enforce_on_login(self, user: Dict) -> Dict:
        """
        Check MFA enforcement during login flow.

        Args:
            user: Authenticated user dictionary

        Returns:
            dict: {
                'allow_login': bool,
                'require_mfa_setup': bool,
                'show_warning': bool,
                'message': str,
                'redirect_to': str or None
            }
        """
        compliance = self.check_mfa_compliance(user)

        result = {
            'allow_login': True,
            'require_mfa_setup': False,
            'show_warning': False,
            'message': '',
            'redirect_to': None
        }

        if not compliance['required']:
            return result

        if compliance['compliant']:
            return result

        if compliance['in_grace_period']:
            # Allow login but show warning
            result['show_warning'] = True
            result['message'] = compliance['message']
            return result

        # Grace period expired - require MFA setup
        result['allow_login'] = False
        result['require_mfa_setup'] = True
        result['message'] = compliance['message']
        result['redirect_to'] = '/settings/security/mfa/setup'

        # Send security alert for enforcement action
        if SECURITY_ALERTS_AVAILABLE:
            send_security_alert(
                level='LOW',
                title='MFA Enforcement Activated',
                details={
                    'user_id': user.get('id') or user.get('user_id'),
                    'username': user.get('username'),
                    'role': user.get('role'),
                    'action': 'login_blocked_mfa_required'
                },
                source_module='mfa_enforcement'
            )

        return result


# Global instance (lazy initialization)
_mfa_enforcement: Optional[MFAEnforcement] = None


def get_mfa_enforcement() -> MFAEnforcement:
    """Get or create the global MFAEnforcement instance."""
    global _mfa_enforcement
    if _mfa_enforcement is None:
        _mfa_enforcement = MFAEnforcement()
    return _mfa_enforcement


# Convenience functions

def require_mfa_for_role(role: str) -> bool:
    """Check if role requires MFA."""
    return get_mfa_enforcement().require_mfa_for_role(role)


def check_mfa_compliance(user: Dict) -> Dict:
    """Check if user is MFA compliant."""
    return get_mfa_enforcement().check_mfa_compliance(user)


def enforce_mfa_on_login(user: Dict) -> Dict:
    """Enforce MFA during login flow."""
    return get_mfa_enforcement().enforce_on_login(user)


def get_non_compliant_users() -> List[Dict]:
    """Get list of non-compliant users."""
    return get_mfa_enforcement().get_non_compliant_users()


# Decorator for enforcing MFA on protected operations
def mfa_required(func):
    """
    Decorator to require MFA for sensitive operations.

    Usage:
        @mfa_required
        def delete_user(user_id):
            ...
    """
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        # Get current user from shared context
        try:
            from education_system.university_system.infrastructure.shared_context import get_auth
            auth = get_auth()
            if auth and auth.current_user:
                compliance = check_mfa_compliance(auth.current_user)
                if compliance['required'] and not compliance['compliant']:
                    raise PermissionError(
                        f"MFA required: {compliance['message']}"
                    )
        except ImportError:
            pass  # No auth context available

        return func(*args, **kwargs)

    return wrapper
