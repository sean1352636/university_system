"""
Account Security Module

This module handles account security features including lockout management,
emergency unlock functionality, and failed login attempt tracking.

Classes:
    AccountSecurityManager: Manages account lockout and security features
"""

from typing import Dict, List, Optional
import os
import hmac
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Import optional security features
try:
    from university_system.infrastructure.security.security_alerts import (
        alert_account_lockout,
    )
    SECURITY_ALERTS_AVAILABLE = True
except ImportError:
    SECURITY_ALERTS_AVAILABLE = False

# Import centralized activity logger
try:
    from university_system.modules.shared.utils.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False

__all__ = ['AccountSecurityManager']


class AccountSecurityManager:
    """
    Manager for account security and lockout operations.

    This class handles failed login attempts, account lockouts, and emergency
    unlock functionality to prevent brute force attacks.

    Attributes:
        db_manager: Database manager instance for data operations
        activity_logger: Activity logger for audit trails
        max_attempts: Maximum failed login attempts before lockout (default 5)
        lockout_time: Lockout duration in minutes (default 15)
        login_attempts: Dictionary tracking failed attempts {username: (attempts, timestamp)}
    """

    def __init__(self, db_manager, activity_logger, max_attempts=5, lockout_time=15):
        """
        Initialize the AccountSecurityManager.

        Parameters:
            db_manager: Database manager instance
            activity_logger: Activity logger instance
            max_attempts: Maximum failed login attempts before lockout (default 5)
            lockout_time: Lockout duration in minutes (default 15)
        """
        self.db_manager = db_manager
        self.activity_logger = activity_logger
        self.max_attempts = max_attempts
        self.lockout_time = lockout_time
        self.login_attempts = {}  # {username: (attempts, last_attempt_time)}

    def increment_login_attempts(self, username: str, ip_address: Optional[str] = None):
        """
        Track failed login attempts and send alerts on lockout.

        Increments the failed login counter for a username and triggers security
        alerts when the account becomes locked out.

        Parameters:
            username: Username that failed login
            ip_address: IP address of login attempt (optional)

        Side Effects:
            - Updates login_attempts dictionary
            - Sends security alert if account gets locked (when SECURITY_ALERTS_AVAILABLE)

        Notes:
            - Creates new entry if username not tracked
            - Sends alert when attempts reach max_attempts threshold
        """
        if username in self.login_attempts:
            attempts, _ = self.login_attempts[username]
            new_attempts = attempts + 1
            self.login_attempts[username] = (new_attempts, datetime.now())
        else:
            new_attempts = 1
            self.login_attempts[username] = (1, datetime.now())

        # Send security alert when account gets locked out
        if new_attempts >= self.max_attempts and SECURITY_ALERTS_AVAILABLE:
            alert_account_lockout(
                user_id=username,
                ip_address=ip_address or 'unknown',
                failed_attempts=new_attempts,
                lockout_duration_minutes=self.lockout_time
            )

    def get_remaining_login_attempts(self, username: str) -> int:
        """
        Get the number of remaining login attempts before lockout.

        Calculates how many failed login attempts remain before the account
        is locked, accounting for expired lockout periods.

        Parameters:
            username: The username to check

        Returns:
            int: Number of remaining attempts (max_attempts if no failed attempts yet)

        Notes:
            - Returns max_attempts if user has no failed attempts
            - Resets and returns max_attempts if lockout period has expired
            - Returns 0 if account is currently locked out
        """
        if username not in self.login_attempts:
            return self.max_attempts

        attempts, last_attempt_time = self.login_attempts[username]

        # Check if lockout period has expired
        elapsed = (datetime.now() - last_attempt_time).total_seconds() / 60
        if elapsed >= self.lockout_time:
            # Lockout expired, reset attempts
            return self.max_attempts

        remaining = self.max_attempts - attempts
        return max(0, remaining)

    def get_lockout_time_remaining(self, username: str) -> Optional[int]:
        """
        Get the remaining lockout time in minutes.

        Calculates how much time remains before a locked account can attempt
        login again.

        Parameters:
            username: The username to check

        Returns:
            int or None: Minutes remaining on lockout, or None if not locked out

        Notes:
            - Returns None if user has no failed attempts
            - Returns None if attempts below max_attempts
            - Returns None if lockout period has expired
            - Returns integer minutes remaining if account is locked
        """
        if username not in self.login_attempts:
            return None

        attempts, last_attempt_time = self.login_attempts[username]

        if attempts < self.max_attempts:
            return None

        elapsed = (datetime.now() - last_attempt_time).total_seconds() / 60
        if elapsed >= self.lockout_time:
            return None

        return int(self.lockout_time - elapsed)

    def reset_login_attempts(self, username: str):
        """
        Reset failed login attempts for a user.

        Clears the failed login counter for a username, typically called
        after successful login.

        Parameters:
            username: Username to reset
        """
        if username in self.login_attempts:
            del self.login_attempts[username]

    def emergency_unlock(self, username: str, emergency_password: str) -> Dict[str, any]:
        """
        Emergency unlock function to reset a locked account.

        This function allows administrators to unlock an account that has been
        locked due to too many failed login attempts, using a secure emergency
        password.

        Parameters:
            username: The username of the locked account
            emergency_password: The emergency unlock password

        Returns:
            dict: Result with 'success' boolean and 'message' string
                  - success: True if unlock succeeded, False otherwise
                  - message: Description of result

        Security:
            - Uses constant-time comparison to prevent timing attacks
            - Logs all unlock attempts (successful and failed)
            - Checks if account is actually locked before unlocking
            - Uses EMERGENCY_UNLOCK_PASSWORD environment variable
            - Default password: 'UnlockMe2024!SecureAdmin' (documented in README)

        Notes:
            - Only unlocks if account is actually locked out
            - Logs security events for audit trail
        """
        # Verify emergency password using constant-time comparison
        # Password is documented in README.md
        expected_password = os.environ.get('EMERGENCY_UNLOCK_PASSWORD', 'UnlockMe2024!SecureAdmin')

        if not hmac.compare_digest(emergency_password, expected_password):
            # Log failed emergency unlock attempt
            logger.warning(f"Failed emergency unlock attempt for user: {username}")
            if ACTIVITY_LOGGER_AVAILABLE:
                log_activity('security', 'emergency_unlock_failed',
                           details={'username': username, 'reason': 'invalid_password'})
            return {
                'success': False,
                'message': 'Invalid emergency unlock password.'
            }

        # Check if user is actually locked
        if username not in self.login_attempts:
            return {
                'success': False,
                'message': f'User "{username}" is not currently locked out.'
            }

        attempts, _ = self.login_attempts[username]
        if attempts < self.max_attempts:
            return {
                'success': False,
                'message': f'User "{username}" is not currently locked out.'
            }

        # Perform the unlock
        del self.login_attempts[username]

        # Log successful emergency unlock
        logger.info(f"Emergency unlock performed for user: {username}")
        if ACTIVITY_LOGGER_AVAILABLE:
            log_activity('security', 'emergency_unlock_success',
                       details={'username': username})

        return {
            'success': True,
            'message': f'Account "{username}" has been unlocked successfully.'
        }

    def list_locked_accounts(self) -> List[Dict[str, any]]:
        """
        List all currently locked accounts.

        Retrieves information about all accounts that are currently locked out
        due to failed login attempts.

        Returns:
            list: List of dictionaries with locked account info, each containing:
                  - username: str - Account username
                  - failed_attempts: int - Number of failed attempts
                  - locked_at: str - ISO format timestamp of lockout
                  - minutes_remaining: int - Minutes until unlock

        Notes:
            - Only includes accounts that are currently locked
            - Excludes accounts where lockout period has expired
        """
        locked_accounts = []
        now = datetime.now()

        for username, (attempts, last_attempt_time) in self.login_attempts.items():
            if attempts >= self.max_attempts:
                elapsed = (now - last_attempt_time).total_seconds() / 60
                if elapsed < self.lockout_time:
                    locked_accounts.append({
                        'username': username,
                        'failed_attempts': attempts,
                        'locked_at': last_attempt_time.isoformat(),
                        'minutes_remaining': int(self.lockout_time - elapsed)
                    })

        return locked_accounts

    def emergency_unlock_all(self, emergency_password: str) -> Dict[str, any]:
        """
        Emergency unlock ALL locked accounts in the system.

        This function allows administrators to unlock all locked accounts
        at once using the emergency password.

        Parameters:
            emergency_password: The emergency unlock password

        Returns:
            dict: Result with 'success' boolean, 'message' string, and 'unlocked' list
                  - success: True if unlock succeeded, False otherwise
                  - message: Description of result
                  - unlocked: List of unlocked usernames

        Security:
            - Uses constant-time comparison to prevent timing attacks
            - Logs all bulk unlock attempts
            - Records number of accounts unlocked

        Notes:
            - Returns empty list if no accounts are locked
            - Clears all locked accounts from tracking
            - Comprehensive audit logging for compliance
        """
        expected_password = os.environ.get('EMERGENCY_UNLOCK_PASSWORD', 'UnlockMe2024!SecureAdmin')

        if not hmac.compare_digest(emergency_password, expected_password):
            logger.warning("Failed emergency unlock ALL attempt")
            if ACTIVITY_LOGGER_AVAILABLE:
                log_activity('security', 'emergency_unlock_all_failed',
                           details={'reason': 'invalid_password'})
            return {
                'success': False,
                'message': 'Invalid emergency unlock password.',
                'unlocked': []
            }

        # Get list of locked accounts before unlocking
        locked_accounts = self.list_locked_accounts()
        unlocked_usernames = [acc['username'] for acc in locked_accounts]

        if not unlocked_usernames:
            return {
                'success': True,
                'message': 'No accounts are currently locked.',
                'unlocked': []
            }

        # Unlock all accounts
        for username in unlocked_usernames:
            if username in self.login_attempts:
                del self.login_attempts[username]

        # Log the bulk unlock
        logger.info(f"Emergency unlock ALL performed: {len(unlocked_usernames)} accounts unlocked")
        if ACTIVITY_LOGGER_AVAILABLE:
            log_activity('security', 'emergency_unlock_all_success',
                       details={'unlocked_count': len(unlocked_usernames),
                               'usernames': unlocked_usernames})

        return {
            'success': True,
            'message': f'Successfully unlocked {len(unlocked_usernames)} account(s).',
            'unlocked': unlocked_usernames
        }
