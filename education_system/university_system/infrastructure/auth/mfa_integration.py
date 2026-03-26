#!/usr/bin/env python3
"""
MFA Integration Module
Integrates MFA into existing authentication flow
"""

import logging
import os
import sys
from typing import Dict, Tuple, Optional, Callable

logger = logging.getLogger(__name__)

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from education_system.university_system.infrastructure.auth.mfa_service import MFAService
from education_system.university_system.core.i18n import get_text, _


class MFAIntegration:
    """
    Integration layer for MFA in existing authentication system
    """

    def __init__(self):
        self.mfa_service = MFAService()

    def check_mfa_requirement(self, user_id: int, role: str) -> Dict:
        """
        Check if MFA is required for this user
        Call this after successful password authentication

        Returns:
            Dict with:
                - required: bool - Whether MFA is required
                - enabled: bool - Whether user has MFA enabled
                - needs_setup: bool - Whether user needs to set up MFA
                - grace_period: bool - Whether user is in grace period
                - must_verify: bool - Whether MFA verification is needed now
        """
        # Get enforcement policy
        policy_result = self.mfa_service.check_mfa_required(user_id, role)

        if not policy_result['success']:
            # Error checking policy - allow login but log
            logger.warning("Failed to check MFA policy: %s", policy_result.get('error'))
            return {
                'required': False,
                'enabled': False,
                'needs_setup': False,
                'must_verify': False,
                'error': policy_result.get('error')
            }

        # Check if bypassed
        if policy_result.get('bypassed'):
            return {
                'required': False,
                'enabled': False,
                'needs_setup': False,
                'must_verify': False,
                'bypassed': True
            }

        # Check if already enabled
        if policy_result.get('already_enabled'):
            return {
                'required': policy_result.get('required', False),
                'enabled': True,
                'needs_setup': False,
                'must_verify': True  # User must verify
            }

        # Check grace period
        if policy_result.get('grace_period'):
            return {
                'required': policy_result.get('required', False),
                'enabled': False,
                'needs_setup': True,
                'must_verify': False,
                'grace_period': True,
                'grace_deadline': policy_result.get('deadline')
            }

        # MFA required and no grace period
        if policy_result.get('required'):
            return {
                'required': True,
                'enabled': False,
                'needs_setup': True,
                'must_verify': False,
                'setup_required': True  # Must set up before continuing
            }

        # MFA not required
        return {
            'required': False,
            'enabled': False,
            'needs_setup': False,
            'must_verify': False
        }

    def check_device_trust(self, user_id: int, device_id: str, trust_token: str) -> bool:
        """
        Check if device is trusted (can skip MFA)

        Args:
            user_id: User ID
            device_id: Device identifier
            trust_token: Trust token from previous MFA verification

        Returns:
            bool: True if device is trusted and valid
        """
        if not all([user_id, device_id, trust_token]):
            return False

        result = self.mfa_service.verify_trusted_device(user_id, device_id, trust_token)
        return result.get('success') and result.get('trusted')

    def is_mfa_locked(self, user_id: int) -> Tuple[bool, Optional[str]]:
        """
        Check if user is locked due to failed MFA attempts

        Returns:
            Tuple of (is_locked: bool, reason: str)
        """
        is_locked = self.mfa_service.is_mfa_locked(user_id)

        if is_locked:
            return True, "Account temporarily locked due to multiple failed MFA verification attempts. Please try again in 15 minutes."

        return False, None

    def get_user_mfa_methods(self, user_id: int) -> Dict:
        """
        Get available MFA methods for user

        Returns:
            Dict with success and methods list
        """
        return self.mfa_service.get_user_mfa_methods(user_id)


# Integration helper functions for existing authentication code

def integrate_mfa_check(user_id: int, role: str, device_id: str = None, trust_token: str = None) -> Dict:
    """
    Complete MFA check for login flow
    Call this after successful password authentication

    Args:
        user_id: User ID
        role: User role
        device_id: Optional device identifier
        trust_token: Optional device trust token

    Returns:
        Dict with:
            - action: 'allow' | 'require_mfa' | 'require_setup' | 'locked' | 'grace'
            - message: str - Message to display to user
            - data: dict - Additional data for the action
    """
    integration = MFAIntegration()

    # Check if locked
    is_locked, lock_reason = integration.is_mfa_locked(user_id)
    if is_locked:
        return {
            'action': 'locked',
            'message': lock_reason,
            'data': {}
        }

    # Check device trust if provided
    if device_id and trust_token:
        if integration.check_device_trust(user_id, device_id, trust_token):
            return {
                'action': 'allow',
                'message': 'Login successful (trusted device)',
                'data': {'trusted_device': True}
            }

    # Check MFA requirement
    mfa_check = integration.check_mfa_requirement(user_id, role)

    if mfa_check.get('error'):
        # Error checking MFA - allow login but log warning
        return {
            'action': 'allow',
            'message': 'Login successful',
            'data': {'mfa_check_failed': True, 'error': mfa_check['error']}
        }

    # User must verify with MFA
    if mfa_check.get('must_verify'):
        methods_result = integration.get_user_mfa_methods(user_id)
        methods_list = methods_result.get('methods', []) if methods_result.get('success') else []
        return {
            'action': 'require_mfa',
            'message': 'Please complete MFA verification',
            'data': {
                'user_id': user_id,
                'methods': methods_list
            }
        }

    # User must set up MFA (required, no grace period)
    if mfa_check.get('setup_required'):
        return {
            'action': 'require_setup',
            'message': 'MFA setup is required to continue',
            'data': {
                'user_id': user_id,
                'required': True
            }
        }

    # User should set up MFA (in grace period)
    if mfa_check.get('grace_period'):
        return {
            'action': 'grace',
            'message': f"MFA setup recommended. Deadline: {mfa_check.get('grace_deadline', 'soon')}",
            'data': {
                'user_id': user_id,
                'deadline': mfa_check.get('grace_deadline'),
                'required': mfa_check.get('required')
            }
        }

    # MFA not required, allow login
    return {
        'action': 'allow',
        'message': 'Login successful',
        'data': {}
    }


# Patch function for existing UserAuth class
def create_mfa_patch_for_user_auth():
    """
    Creates a patch that can be applied to existing UserAuth.login() method

    Usage in user_authentication.py:

    from infrastructure.auth.mfa_integration import create_mfa_patch_for_user_auth

    class UserAuth:
        def login(self, username, password):
            # ... existing password verification ...

            if password_valid:
                # Apply MFA check
                mfa_patch = create_mfa_patch_for_user_auth()
                mfa_result = mfa_patch(user_id, role)

                if mfa_result['action'] == 'require_mfa':
                    # Show MFA verification dialog
                    return {'success': False, 'mfa_required': True, 'data': mfa_result['data']}
                elif mfa_result['action'] == 'require_setup':
                    # Show MFA setup wizard
                    return {'success': False, 'mfa_setup_required': True, 'data': mfa_result['data']}
                elif mfa_result['action'] == 'locked':
                    # Show locked message
                    return {'success': False, 'locked': True, 'message': mfa_result['message']}
                # ... continue with normal login ...
    """

    def mfa_check_patch(user_id: int, role: str, device_id: str = None, trust_token: str = None):
        return integrate_mfa_check(user_id, role, device_id, trust_token)

    return mfa_check_patch


# GUI Integration helpers
def show_mfa_for_login(parent, user_id: int, username: str) -> Tuple[bool, Optional[str]]:
    """
    Show appropriate MFA dialog for login flow

    Args:
        parent: Tkinter parent window
        user_id: User ID
        username: Username

    Returns:
        Tuple of (success: bool, trust_token: Optional[str])
    """
    integration = MFAIntegration()

    # Check if user has MFA enabled
    methods = integration.get_user_mfa_methods(user_id)

    if not methods.get('success') or not methods.get('methods'):
        # No MFA methods configured - should not happen if enforcement is working
        return False, None

    # Show verification dialog
    try:
        from education_system.university_system.infrastructure.auth.mfa_gui import show_mfa_verification

        trust_token = None

        def on_success(result):
            nonlocal trust_token
            trust_token = result.get('trust_token')

        verified = show_mfa_verification(parent, user_id, username, on_success)

        return verified, trust_token

    except Exception as e:
        logger.error("Error showing MFA verification")
        return False, None


def show_mfa_setup_for_login(parent, user_id: int, username: str, required: bool = False) -> bool:
    """
    Show MFA setup wizard for login flow

    Args:
        parent: Tkinter parent window
        user_id: User ID
        username: Username
        required: Whether MFA is required (vs optional)

    Returns:
        bool: True if setup was completed
    """
    try:
        from education_system.university_system.infrastructure.auth.mfa_gui import show_mfa_setup

        setup_completed = False

        def on_complete():
            nonlocal setup_completed
            setup_completed = True

        show_mfa_setup(parent, user_id, username, on_complete)

        return setup_completed

    except Exception as e:
        logger.error("Error showing MFA setup")
        return False


# Example integration code for existing login method
INTEGRATION_EXAMPLE = """
# Example: Integrating MFA into existing UserAuth.login() method

from infrastructure.auth.mfa_integration import integrate_mfa_check, show_mfa_for_login, show_mfa_setup_for_login

class UserAuth:
    def login(self, username, password, device_id=None, trust_token=None):
        '''Login with MFA support'''

        # Step 1: Existing password authentication
        # ... your existing password verification code ...

        if not password_valid:
            return {'success': False, 'error': 'Invalid credentials'}

        # Step 2: MFA check (new)
        mfa_result = integrate_mfa_check(user_id, role, device_id, trust_token)

        # Step 3: Handle MFA actions
        if mfa_result['action'] == 'locked':
            return {
                'success': False,
                'locked': True,
                'message': mfa_result['message']
            }

        elif mfa_result['action'] == 'require_mfa':
            # User must verify MFA before login
            # In CLI: prompt for MFA code
            # In GUI: show MFA verification dialog
            return {
                'success': False,
                'mfa_required': True,
                'user_id': user_id,
                'username': username,
                'methods': mfa_result['data']['methods']
            }

        elif mfa_result['action'] == 'require_setup':
            # User must set up MFA before login
            return {
                'success': False,
                'mfa_setup_required': True,
                'user_id': user_id,
                'username': username,
                'required': True
            }

        elif mfa_result['action'] == 'grace':
            # User should set up MFA soon (optional for now)
            # Show warning but allow login
            return {
                'success': True,
                'user_id': user_id,
                'session_id': session_id,
                'warning': mfa_result['message'],
                'mfa_setup_recommended': True
            }

        elif mfa_result['action'] == 'allow':
            # MFA passed or not required - proceed with login
            return {
                'success': True,
                'user_id': user_id,
                'session_id': session_id,
                'trusted_device': mfa_result['data'].get('trusted_device', False)
            }

        # Default: allow login
        return {
            'success': True,
            'user_id': user_id,
            'session_id': session_id
        }


# Example: GUI integration in login dialog
class LoginDialog:
    def perform_login(self):
        username = self.username_entry.get()
        password = self.password_entry.get()

        # Get device info
        device_id = self.get_device_id()  # Your device fingerprinting
        trust_token = self.get_stored_trust_token()  # From local storage

        # Attempt login
        result = self.auth.login(username, password, device_id, trust_token)

        if result['success']:
            # Login successful
            self.on_login_success(result)

        elif result.get('mfa_required'):
            # Show MFA verification dialog
            verified, new_trust_token = show_mfa_for_login(
                self,
                result['user_id'],
                result['username']
            )

            if verified:
                # MFA verified - complete login
                if new_trust_token:
                    self.store_trust_token(new_trust_token)

                # Create session
                session_id = self.auth.create_session(result['user_id'])
                self.on_login_success({'user_id': result['user_id'], 'session_id': session_id})
            else:
                messagebox.showerror("Error", "MFA verification failed")

        elif result.get('mfa_setup_required'):
            # Show MFA setup wizard
            completed = show_mfa_setup_for_login(
                self,
                result['user_id'],
                result['username'],
                required=result.get('required', False)
            )

            if completed:
                messagebox.showinfo("Success", "MFA setup complete! Please log in again.")
            else:
                if result.get('required'):
                    messagebox.showerror("Error", "MFA setup is required to continue")
                else:
                    # Optional - allow login
                    messagebox.showwarning("Warning", "MFA setup recommended for security")

        elif result.get('locked'):
            messagebox.showerror("Account Locked", result['message'])

        else:
            messagebox.showerror("Error", result.get('error', 'Login failed'))
"""


if __name__ == '__main__':
    # Test integration
    print("MFA Integration Module")
    print("=" * 60)
    print("\nExample Integration Code:")
    print(INTEGRATION_EXAMPLE)

    # Test MFA check
    print("\n" + "=" * 60)
    print("Testing MFA check for user_id=1, role='admin'")

    result = integrate_mfa_check(user_id=1, role='admin')
    print(f"\nResult: {result}")
