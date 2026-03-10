"""
Session Management Module

This module handles user session management, including session validation,
timeout tracking, chatbot sessions, and CLI remember-me token functionality.

Classes:
    SessionManager: Manages user sessions and authentication tokens
"""

from typing import Optional, Dict, Any
import secrets
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

__all__ = ['SessionManager']


class SessionManager:
    """
    Manager for user session operations.

    This class handles session validation, timeout management, chatbot sessions,
    and CLI remember-me token functionality for persistent authentication.

    Attributes:
        db_manager: Database manager instance for data operations
        activity_logger: Activity logger for audit trails
        session_timeout: Session timeout in minutes (default 30)
        current_user: Current logged-in user information
        last_activity: Timestamp of last user activity
    """

    def __init__(self, db_manager, activity_logger, session_timeout=30):
        """
        Initialize the SessionManager.

        Parameters:
            db_manager: Database manager instance
            activity_logger: Activity logger instance
            session_timeout: Session timeout in minutes (default 30)
        """
        self.db_manager = db_manager
        self.activity_logger = activity_logger
        self.session_timeout = session_timeout
        self.current_user = None
        self.last_activity = None

    def check_session(self):
        """
        Check if the current session is valid and not timed out.

        Validates the current user session by checking if a user is logged in
        and if the session has not exceeded the timeout period. Automatically
        logs out the user if the session has timed out.

        Returns:
            bool: True if session is valid, False if expired or no user logged in

        Side Effects:
            - Updates last_activity timestamp if session is valid
            - Calls logout() if session has timed out
            - Prints timeout message to console when session expires
        """
        if not self.current_user:
            return False

        if not self.last_activity:
            return False

        # Check if session has timed out
        elapsed = (datetime.now() - self.last_activity).total_seconds() / 60
        if elapsed > self.session_timeout:
            print("Your session has timed out due to inactivity. Please log in again.")
            # Note: logout() should be called from the parent auth instance
            self.current_user = None
            self.last_activity = None
            return False

        # Update last activity time
        self.last_activity = datetime.now()
        return True

    def create_chatbot_session(self, username: str, current_user: dict, permission_checker) -> Optional[str]:
        """
        Create a chatbot session for an authenticated user.

        Generates a secure session token for chatbot access if the user is
        authenticated and has the required permissions.

        Parameters:
            username: Username requesting chatbot session
            current_user: Current user dictionary with authentication info
            permission_checker: Function/method to check if user has 'access_chatbot' permission

        Returns:
            str or None: Session token if successful, None if unauthorized

        Notes:
            - Requires user to be logged in
            - Requires 'access_chatbot' permission
            - Generates a 32-byte hex token
            - Logs session creation activity
        """
        if not current_user or current_user.get('username') != username:
            return None

        if not permission_checker('access_chatbot'):
            return None

        # Generate session token
        session_token = secrets.token_hex(32)

        # Log chatbot session creation
        self.activity_logger(
            username,
            'Chatbot session created',
            f'Token: {session_token[:8]}...',
            current_user.get('id')
        )

        return session_token

    def create_chatbot_session(self, username: str, current_user: dict, permission_checker) -> Optional[str]:
        """
        Create a chatbot session token and store it for later validation.

        Parameters:
            username: Username to create session for
            current_user: Current user dictionary
            permission_checker: Function/method to check permissions

        Returns:
            str: Session token if created, None if unauthorized
        """
        if not current_user or current_user.get('username') != username:
            return None
        if not permission_checker('access_chatbot'):
            return None

        token = secrets.token_hex(32)
        if not hasattr(self, '_chatbot_sessions'):
            self._chatbot_sessions = {}
        self._chatbot_sessions[token] = {
            'username': username,
            'created_at': datetime.now()
        }
        return token

    def validate_chatbot_session(self, session_token: str, username: str, current_user: dict, permission_checker) -> bool:
        """
        Validate a chatbot session token.

        Verifies that the session token is valid for the specified user.

        Parameters:
            session_token: Session token to validate
            username: Username associated with the token
            current_user: Current user dictionary
            permission_checker: Function/method to check permissions

        Returns:
            bool: True if session is valid, False otherwise
        """
        if not current_user or current_user.get('username') != username:
            return False

        if not permission_checker('access_chatbot'):
            return False

        # Validate against stored tokens
        if not hasattr(self, '_chatbot_sessions'):
            self._chatbot_sessions = {}

        session_data = self._chatbot_sessions.get(session_token)
        if not session_data:
            return False

        if session_data['username'] != username:
            return False

        # Check token expiry (1 hour)
        if datetime.now() - session_data['created_at'] > timedelta(hours=1):
            del self._chatbot_sessions[session_token]
            return False

        return True

    def update_last_activity(self):
        """Update the last activity timestamp to current time."""
        self.last_activity = datetime.now()

    def set_current_user(self, user_dict: dict):
        """
        Set the current user and initialize activity tracking.

        The user_dict may contain these optional fields for extended auth:
            - auth_method: 'password' | 'sso' | 'webauthn' | 'biometric'
            - active_linked_account_id: int or None
            - original_role: str or None (set during account role switching)
            - acting_as_delegate_for: int or None (target user_id when using delegated access)
            - sso_provider_id: str or None

        Parameters:
            user_dict: Dictionary containing user information
        """
        # Ensure extended auth fields have defaults
        user_dict.setdefault('auth_method', 'password')
        user_dict.setdefault('active_linked_account_id', None)
        user_dict.setdefault('original_role', None)
        user_dict.setdefault('acting_as_delegate_for', None)
        user_dict.setdefault('sso_provider_id', None)
        self.current_user = user_dict
        self.last_activity = datetime.now()

    def clear_session(self):
        """Clear the current session."""
        self.current_user = None
        self.last_activity = None


# CLI Remember-Me Token Functions
def save_cli_remember_token(username: str, token: str, device_fingerprint: str):
    """
    Save remember me token to file for CLI.

    Stores authentication token locally to enable automatic login on next CLI session.

    Parameters:
        username: Username to remember
        token: Authentication token
        device_fingerprint: Device identifier for security

    Side Effects:
        - Creates ~/.university_system directory if not exists
        - Writes cli_remember_me.json file
        - Prints success message to console

    Notes:
        - Uses JSON format for token storage
        - Stores in user's home directory
        - Handles exceptions gracefully with warnings
    """
    try:
        import json
        import os
        import stat
        from pathlib import Path

        token_file = Path.home() / '.university_system' / 'cli_remember_me.json'
        token_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            'username': username,
            'token': token,
            'device_fingerprint': device_fingerprint
        }

        with open(token_file, 'w') as f:
            json.dump(data, f)

        # Set restrictive file permissions (owner read/write only)
        os.chmod(token_file, stat.S_IRUSR | stat.S_IWUSR)

        print(f"✅ Remember me token saved. You'll be automatically logged in next time.")

    except Exception as e:
        logging.warning(f"Failed to save remember me token: {e}")


def load_cli_remember_token() -> Optional[Dict[str, str]]:
    """
    Load remember me token from file for CLI.

    Retrieves stored authentication token for automatic login.

    Returns:
        dict or None: Dictionary with 'username', 'token', 'device_fingerprint' keys,
                     or None if no token exists or error occurs

    Notes:
        - Reads from ~/.university_system/cli_remember_me.json
        - Returns None if file doesn't exist
        - Handles exceptions gracefully with warnings
    """
    try:
        import json
        from pathlib import Path

        token_file = Path.home() / '.university_system' / 'cli_remember_me.json'

        if not token_file.exists():
            return None

        with open(token_file, 'r') as f:
            data = json.load(f)

        return data

    except Exception as e:
        logging.warning(f"Failed to load remember me token: {e}")
        return None


def clear_cli_remember_token():
    """
    Clear remember me token from file for CLI.

    Removes stored authentication token, requiring manual login on next session.

    Side Effects:
        - Deletes cli_remember_me.json if it exists
        - Prints confirmation message to console

    Notes:
        - Safe to call even if file doesn't exist
        - Handles exceptions gracefully with warnings
    """
    try:
        from pathlib import Path

        token_file = Path.home() / '.university_system' / 'cli_remember_me.json'

        if token_file.exists():
            token_file.unlink()
            print("Remember me token cleared.")

    except Exception as e:
        logging.warning(f"Failed to clear remember me token: {e}")


def check_cli_remember_me_token(auth):
    """
    Check for remember me token and auto-login if valid.

    Attempts to automatically log in using stored remember-me token.

    Parameters:
        auth: UserAuth or EnhancedAuth instance

    Returns:
        tuple: (auth_instance, success_bool)
               - auth_instance: Updated auth instance (may be EnhancedAuth)
               - success_bool: True if auto-login succeeded, False otherwise

    Side Effects:
        - May upgrade auth to EnhancedAuth if needed
        - Updates stored token if rotated
        - Prints auto-login status to console

    Notes:
        - Requires EnhancedAuth for token verification
        - Automatically rotates tokens on successful verification
        - Clears invalid tokens automatically
    """
    try:
        from education_system.university_system.infrastructure.auth.enhanced_auth import EnhancedAuth, create_enhanced_auth

        # Load saved token
        token_data = load_cli_remember_token()
        if not token_data:
            return auth, False

        username = token_data.get('username')
        token = token_data.get('token')
        device_fingerprint = token_data.get('device_fingerprint')

        if not all([username, token, device_fingerprint]):
            return auth, False

        # Create/use EnhancedAuth
        if not isinstance(auth, EnhancedAuth):
            auth = create_enhanced_auth()

        # Verify token
        result = auth.verify_remember_me_token(
            token=token,
            device_fingerprint=device_fingerprint,
            ip_address="127.0.0.1"
        )

        if result.get('success'):
            # Update saved token if rotated
            if result.get('new_token'):
                save_cli_remember_token(username, result['new_token'], device_fingerprint)

            print(f"\n🔓 Auto-login successful! Welcome back, {username}!")
            return auth, True
        else:
            # Clear invalid token
            clear_cli_remember_token()
            return auth, False

    except ImportError:
        # EnhancedAuth not available
        return auth, False
    except Exception as e:
        logging.warning(f"Error checking remember me token: {e}")
        return auth, False
