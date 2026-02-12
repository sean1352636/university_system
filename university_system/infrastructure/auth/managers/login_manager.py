"""
Login Management Module

Handles login, logout, and authentication flow operations including 2FA completion
and login attempt logging.

Classes:
    LoginManager: Manages login/logout operations
"""

from typing import Dict, Union, Optional, Tuple
import logging
from datetime import datetime, timedelta

from university_system.infrastructure.database.db import sqlite3
from university_system.infrastructure.exceptions import (
    InvalidCredentialsError,
    AuthenticationError,
    DatabaseError,
)

logger = logging.getLogger(__name__)

# Import optional features
try:
    from university_system.core.activity_logger import (
        set_user, log_login, log_logout
    )
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False

try:
    from university_system.infrastructure.security.audit_helpers import safe_log_security_event
    from university_system.infrastructure.security.immutable_audit_log import AuditAction
    IMMUTABLE_AUDIT_AVAILABLE = True
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False

__all__ = ['LoginManager']


class LoginManager:
    """
    Manager for login and logout operations.

    This class handles the authentication flow, login attempts logging,
    2FA completion, and user session setup.

    Attributes:
        db_manager: Database manager instance
        activity_logger: Activity logger for audit trails
        password_hasher: Function to hash passwords
        account_security: AccountSecurityManager instance for lockout tracking
        mfa_manager: MFAManager instance for 2FA verification
        permission_getter: Function to get user permissions
        session_manager: SessionManager instance
    """

    def __init__(self, db_manager, activity_logger, password_hasher,
                 account_security, mfa_manager, permission_getter,
                 session_manager, role_inferrer, name_deriver):
        """
        Initialize the LoginManager.

        Parameters:
            db_manager: Database manager instance
            activity_logger: Activity logger instance
            password_hasher: Function to hash passwords (returns salt, hash tuple)
            account_security: AccountSecurityManager instance
            mfa_manager: MFAManager instance
            permission_getter: Function to get user permissions
            session_manager: SessionManager instance
            role_inferrer: Function to infer role from username
            name_deriver: Function to derive names from username
        """
        self.db_manager = db_manager
        self.activity_logger = activity_logger
        self.password_hasher = password_hasher
        self.account_security = account_security
        self.mfa_manager = mfa_manager
        self.get_user_permissions = permission_getter
        self.session_manager = session_manager
        self.infer_role = role_inferrer
        self.derive_name = name_deriver

    def _log_login_attempt(self, username: str, success: bool):
        """
        Log login attempts for security monitoring.

        Parameters:
            username: Username that attempted login
            success: Whether login was successful
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ip_address = "127.0.0.1"  # In a real system, get from request

                cursor.execute(
                    'INSERT INTO login_attempts (username, attempt_time, ip_address, success) VALUES (?, ?, ?, ?)',
                    (username, timestamp, ip_address, 1 if success else 0)
                )
                conn.commit()
        except sqlite3.Error as e:
            # Don't raise exceptions for logging failures
            print(f"Warning: Failed to log login attempt: {e}")

    def login(self, username: str, password: str) -> Union[Dict, bool, str]:
        """
        Authenticate a user and create a session.

        Parameters:
            username: The username
            password: The password

        Returns:
            Union[Dict, bool, str]:
                - dict: {'success': True, 'requires_2fa': True, 'user_id': int, 'username': str} if 2FA required
                - True: If login successful without 2FA
                - 'password_reset_required': If password reset needed
                - Raises exception on failure

        Raises:
            InvalidCredentialsError: If credentials are invalid or account is locked
            AuthenticationError: If account is deactivated or other auth errors
            DatabaseError: If database operation fails
        """
        # Check for account lockout
        if username in self.account_security.login_attempts:
            attempts, last_attempt_time = self.account_security.login_attempts[username]
            if attempts >= self.account_security.max_attempts:
                elapsed = (datetime.now() - last_attempt_time).total_seconds() / 60
                if elapsed < self.account_security.lockout_time:
                    wait_time = int(self.account_security.lockout_time - elapsed)
                    raise InvalidCredentialsError(
                        f"Account temporarily locked. Please try again in {wait_time} minutes.",
                        details={
                            'username': username,
                            'locked_until': (last_attempt_time + timedelta(minutes=self.account_security.lockout_time)).isoformat(),
                            'wait_minutes': wait_time
                        }
                    )
                else:
                    # Reset attempts if lockout period has passed
                    del self.account_security.login_attempts[username]

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Try with join (ideal case)
                cursor.execute(
                    '''SELECT ua.id, ua.password_hash, ua.salt, ua.user_id, ua.is_active,
                              ua.password_reset_required, ua.two_fa_enabled, u.role
                       FROM user_accounts ua
                       JOIN users u ON ua.user_id = u.id
                       WHERE ua.username = ?''',
                    (username,)
                )

                user_data = cursor.fetchone()

                # If join fails, try without join and create missing user profile
                if not user_data:
                    cursor.execute(
                        '''SELECT id, password_hash, salt, user_id, is_active,
                                  password_reset_required, two_fa_enabled
                           FROM user_accounts
                           WHERE username = ?''',
                        (username,)
                    )

                    account_data = cursor.fetchone()

                    if account_data:
                        logging.warning(f"User profile missing for account '{username}'. Creating profile...")
                        (account_id, password_hash, salt, user_id, is_active,
                         password_reset_required, two_fa_enabled) = account_data

                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        role_guess = self.infer_role(username)
                        first_name, last_name = self.derive_name(username)
                        email = f"{username}@university.local"

                        try:
                            cursor.execute(
                                '''INSERT INTO users (id, username, first_name, last_name, email, role, student_id, created_at, updated_at)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                (user_id, username, first_name, last_name, email, role_guess, None, timestamp, timestamp)
                            )
                            conn.commit()
                            logging.info(f"Created missing user profile for account '{username}'.")
                        except sqlite3.Error as exc:
                            logging.error(f"Failed to create user profile for '{username}': {exc}")

                        # Re-query with join
                        cursor.execute(
                            '''SELECT ua.id, ua.password_hash, ua.salt, ua.user_id, ua.is_active,
                                      ua.password_reset_required, ua.two_fa_enabled, u.role
                               FROM user_accounts ua
                               JOIN users u ON ua.user_id = u.id
                               WHERE ua.username = ?''',
                            (username,),
                        )
                        user_data = cursor.fetchone()

                        if not user_data:
                            return False

                if not user_data:
                    # User not found
                    self.account_security.increment_login_attempts(username)
                    self._log_login_attempt(username, False)

                    if ACTIVITY_LOGGER_AVAILABLE:
                        log_login(username, success=False)

                    if IMMUTABLE_AUDIT_AVAILABLE:
                        safe_log_security_event(
                            action=AuditAction.LOGIN_FAILURE,
                            user_id=username,
                            resource_type='authentication',
                            details={'username': username, 'reason': 'user_not_found'}
                        )

                    raise InvalidCredentialsError(
                        "Invalid username or password.",
                        details={'username': username}
                    )

                account_id, password_hash, salt, user_id, is_active, password_reset_required, two_fa_enabled, role = user_data

                # Check if account is active
                if not is_active:
                    raise AuthenticationError(
                        "This account has been deactivated. Please contact an administrator.",
                        code="ACCOUNT_DEACTIVATED",
                        details={'username': username}
                    )

                # Verify password
                _, hashed_attempt = self.password_hasher(password, salt)

                if hashed_attempt != password_hash:
                    # Incorrect password
                    self.account_security.increment_login_attempts(username)
                    self._log_login_attempt(username, False)

                    if ACTIVITY_LOGGER_AVAILABLE:
                        log_login(username, success=False)

                    if IMMUTABLE_AUDIT_AVAILABLE:
                        safe_log_security_event(
                            action=AuditAction.LOGIN_FAILURE,
                            user_id=str(user_id),
                            resource_type='authentication',
                            details={'username': username, 'reason': 'invalid_password'}
                        )

                    raise InvalidCredentialsError(
                        "Invalid username or password.",
                        details={'username': username}
                    )

                # Password correct, check if 2FA required
                if two_fa_enabled:
                    return {'success': True, 'requires_2fa': True, 'user_id': user_id, 'username': username}

                # Complete login without 2FA
                return self._complete_login(user_id, account_id, username, role, password_reset_required)

        except InvalidCredentialsError:
            raise
        except AuthenticationError:
            raise
        except sqlite3.Error as e:
            logging.error(f"Database error during login for {username}: {e}")
            raise DatabaseError(
                f"Database error during login: {str(e)}",
                code="DB_LOGIN_ERROR",
                details={'username': username}
            ) from e
        except Exception as e:
            logging.error(f"Unexpected error during login for {username}: {type(e).__name__}: {e}")
            raise AuthenticationError(
                "An unexpected error occurred during login. Please try again.",
                code="AUTH_UNEXPECTED_ERROR",
                details={'username': username, 'error_type': type(e).__name__}
            ) from e

    def _complete_login(self, user_id: int, account_id: int, username: str,
                        role: str, password_reset_required: bool) -> Union[bool, str]:
        """
        Complete the login process after authentication.

        Parameters:
            user_id: User's ID
            account_id: Account ID
            username: Username
            role: User role
            password_reset_required: Whether password reset is required

        Returns:
            Union[bool, str]: True if successful, 'password_reset_required' if reset needed
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Update last login
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    'UPDATE user_accounts SET last_login = ? WHERE id = ?',
                    (timestamp, account_id)
                )
                conn.commit()

                # Get user permissions
                permissions = self.get_user_permissions(user_id)

                # Get student_id and email
                cursor.execute('SELECT student_id, email FROM users WHERE id = ?', (user_id,))
                user_row = cursor.fetchone()
                student_id = user_row[0] if user_row else None
                email = user_row[1] if user_row and len(user_row) > 1 else ''

                # Set current user in session manager
                user_dict = {
                    'id': user_id,
                    'account_id': account_id,
                    'username': username,
                    'role': role,
                    'permissions': permissions,
                    'password_reset_required': password_reset_required,
                    'student_id': student_id,
                    'email': email
                }
                self.session_manager.set_current_user(user_dict)

                # Log successful login
                self._log_login_attempt(username, True)
                self.activity_logger(username, 'User login', None, user_id)

                if ACTIVITY_LOGGER_AVAILABLE:
                    set_user(username)
                    log_login(username, success=True)

                if IMMUTABLE_AUDIT_AVAILABLE:
                    safe_log_security_event(
                        action=AuditAction.LOGIN_SUCCESS,
                        user_id=str(user_id),
                        resource_type='session',
                        details={'username': username, 'role': role}
                    )

                # Reset login attempts
                self.account_security.reset_login_attempts(username)

                # Check if password reset required
                if password_reset_required:
                    print("You must change your password before continuing.")
                    return 'password_reset_required'

                return True

        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False

    def complete_two_fa_login(self, user_id: int, username: str, code: str) -> bool:
        """
        Complete login after 2FA verification.

        Parameters:
            user_id: User ID
            username: Username
            code: 2FA code (TOTP or recovery code)

        Returns:
            bool: True if successful, False otherwise
        """
        # Verify the 2FA code
        if not self.mfa_manager.verify_two_fa_code(user_id, code):
            # Check if it's a recovery code
            if not self.mfa_manager.verify_recovery_code(user_id, code):
                print("Invalid 2FA code.")
                return False

        # Get full user data
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    '''SELECT ua.id, ua.password_reset_required, u.role
                       FROM user_accounts ua
                       JOIN users u ON ua.user_id = u.id
                       WHERE u.id = ?''',
                    (user_id,)
                )

                user_data = cursor.fetchone()

                if not user_data:
                    print("User not found.")
                    return False

                account_id, password_reset_required, role = user_data

                # Complete login
                return self._complete_login(user_id, account_id, username, role, password_reset_required)

        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False

    def login_by_method(self, method: str, **kwargs) -> Union[Dict, bool, str]:
        """
        Unified login dispatcher for all authentication methods.

        Parameters:
            method: Authentication method ('password', 'sso', 'webauthn', 'biometric')
            **kwargs: Method-specific arguments

        Returns:
            Union[Dict, bool, str]: Login result
        """
        if method == 'password':
            return self.login(kwargs['username'], kwargs['password'])
        elif method == 'sso':
            return self.login_via_sso(kwargs['sso_identity'])
        elif method == 'webauthn':
            return self.login_via_webauthn(kwargs['assertion_data'])
        elif method == 'biometric':
            return self.login_via_biometric(kwargs['biometric_type'], kwargs['template_data'])
        else:
            raise AuthenticationError(
                f"Unsupported authentication method: {method}",
                code="UNSUPPORTED_AUTH_METHOD"
            )

    def login_via_sso(self, sso_identity: dict) -> Union[bool, str]:
        """
        Authenticate a user via SSO identity.

        Bypasses password verification but completes the standard login flow.

        Parameters:
            sso_identity: Dict with keys: user_id, username, role, provider_id

        Returns:
            Union[bool, str]: True if successful, 'password_reset_required' if reset needed
        """
        try:
            user_id = sso_identity.get('user_id')
            username = sso_identity.get('username')
            provider_id = sso_identity.get('provider_id')

            if not user_id or not username:
                raise AuthenticationError(
                    "Invalid SSO identity: missing user_id or username",
                    code="INVALID_SSO_IDENTITY"
                )

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''SELECT ua.id, ua.password_reset_required, u.role
                       FROM user_accounts ua
                       JOIN users u ON ua.user_id = u.id
                       WHERE u.id = ?''',
                    (user_id,)
                )
                user_data = cursor.fetchone()

                if not user_data:
                    raise AuthenticationError(
                        "SSO user not found in local database",
                        code="SSO_USER_NOT_FOUND"
                    )

                account_id, password_reset_required, role = user_data
                result = self._complete_login(
                    user_id, account_id, username, role, password_reset_required
                )

                # Tag the session with SSO metadata
                if result is True and self.session_manager.current_user:
                    self.session_manager.current_user['auth_method'] = 'sso'
                    self.session_manager.current_user['sso_provider_id'] = provider_id

                return result

        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"SSO login error: {e}")
            raise AuthenticationError(
                "SSO login failed unexpectedly",
                code="SSO_LOGIN_ERROR"
            ) from e

    def login_via_webauthn(self, assertion_data: dict) -> Union[bool, str]:
        """
        Authenticate a user via WebAuthn assertion.

        Parameters:
            assertion_data: Dict with keys: user_id, username, credential_id

        Returns:
            Union[bool, str]: True if successful, 'password_reset_required' if reset needed
        """
        try:
            user_id = assertion_data.get('user_id')
            username = assertion_data.get('username')

            if not user_id or not username:
                raise AuthenticationError(
                    "Invalid WebAuthn assertion: missing user_id or username",
                    code="INVALID_WEBAUTHN_ASSERTION"
                )

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''SELECT ua.id, ua.password_reset_required, u.role
                       FROM user_accounts ua
                       JOIN users u ON ua.user_id = u.id
                       WHERE u.id = ?''',
                    (user_id,)
                )
                user_data = cursor.fetchone()

                if not user_data:
                    raise AuthenticationError(
                        "WebAuthn user not found",
                        code="WEBAUTHN_USER_NOT_FOUND"
                    )

                account_id, password_reset_required, role = user_data
                result = self._complete_login(
                    user_id, account_id, username, role, password_reset_required
                )

                if result is True and self.session_manager.current_user:
                    self.session_manager.current_user['auth_method'] = 'webauthn'

                return result

        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"WebAuthn login error: {e}")
            raise AuthenticationError(
                "WebAuthn login failed unexpectedly",
                code="WEBAUTHN_LOGIN_ERROR"
            ) from e

    def login_via_biometric(self, biometric_type: str, template_data) -> Union[bool, str]:
        """
        Authenticate a user via biometric verification.

        Parameters:
            biometric_type: Type of biometric ('face' or 'fingerprint')
            template_data: Biometric template data for matching

        Returns:
            Union[bool, str]: True if successful, 'password_reset_required' if reset needed
        """
        try:
            # Import BiometricService to perform matching
            from university_system.infrastructure.auth.biometric_service import BiometricService
            bio_service = BiometricService(self.db_manager)

            # Try to match against all enrolled users
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''SELECT be.user_id, u.username
                       FROM biometric_enrollments be
                       JOIN users u ON be.user_id = u.id
                       WHERE be.biometric_type = ? AND be.is_active = 1''',
                    (biometric_type,)
                )
                enrolled_users = cursor.fetchall()

            matched_user_id = None
            matched_username = None

            for user_id, username in enrolled_users:
                if biometric_type == 'face':
                    result = bio_service.verify_face(user_id, template_data)
                else:
                    result = bio_service.verify_fingerprint(user_id, template_data)

                if result.get('success') and result.get('match'):
                    matched_user_id = user_id
                    matched_username = username
                    break

            if not matched_user_id:
                raise InvalidCredentialsError(
                    "Biometric authentication failed: no match found",
                    details={'biometric_type': biometric_type}
                )

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''SELECT ua.id, ua.password_reset_required, u.role
                       FROM user_accounts ua
                       JOIN users u ON ua.user_id = u.id
                       WHERE u.id = ?''',
                    (matched_user_id,)
                )
                user_data = cursor.fetchone()

                if not user_data:
                    raise AuthenticationError(
                        "Biometric user account not found",
                        code="BIOMETRIC_USER_NOT_FOUND"
                    )

                account_id, password_reset_required, role = user_data
                result = self._complete_login(
                    matched_user_id, account_id, matched_username, role, password_reset_required
                )

                if result is True and self.session_manager.current_user:
                    self.session_manager.current_user['auth_method'] = 'biometric'

                return result

        except (InvalidCredentialsError, AuthenticationError):
            raise
        except ImportError:
            raise AuthenticationError(
                "Biometric authentication is not available. Install face_recognition library.",
                code="BIOMETRIC_NOT_AVAILABLE"
            )
        except Exception as e:
            logger.error(f"Biometric login error: {e}")
            raise AuthenticationError(
                "Biometric login failed unexpectedly",
                code="BIOMETRIC_LOGIN_ERROR"
            ) from e

    def logout(self):
        """Log out the current user."""
        current_user = self.session_manager.current_user
        if not current_user:
            print("No user is currently logged in.")
            return

        username = current_user.get('username', 'Unknown')
        user_id = current_user.get('id', current_user.get('user_id'))

        # Log the logout activity
        if user_id:
            self.activity_logger(username, 'User logout', None, user_id)

        if ACTIVITY_LOGGER_AVAILABLE:
            log_logout(username)

        if IMMUTABLE_AUDIT_AVAILABLE:
            safe_log_security_event(
                action=AuditAction.LOGOUT,
                user_id=str(user_id) if user_id else username,
                resource_type='session',
                details={'username': username}
            )

        # Clear the session
        self.session_manager.clear_session()

        print(f"Goodbye, {username}! You have been logged out.")
