"""
Enhanced Authentication with Remember Me Support

This module extends the base authentication with:
- Remember me functionality
- Enhanced rate limiting
- Session management integration
"""

import logging
from typing import Optional, Dict, Tuple
from datetime import datetime

# Lazy import UserAuth to prevent circular dependencies
from university_system.infrastructure.security.remember_me import remember_me_manager
from university_system.infrastructure.security.rate_limiter import login_limiter
from university_system.infrastructure.security.session_management import SessionManager

logger = logging.getLogger(__name__)

# Import UserAuth only when the class is instantiated
_UserAuth = None

def _get_user_auth_class():
    """Lazy load UserAuth to prevent circular imports."""
    global _UserAuth
    if _UserAuth is None:
        from university_system.infrastructure.auth import UserAuth
        _UserAuth = UserAuth
    return _UserAuth


class EnhancedAuth:
    """
    Extended authentication with remember me and enhanced security.

    Usage:
        auth = EnhancedAuth()

        # Login with remember me
        result = auth.login_with_remember_me(
            username, password,
            remember_me=True,
            device_fingerprint="device_123",
            ip_address="192.168.1.1"
        )

        # Verify remember me token
        user_id = auth.verify_remember_me_token(
            token, device_fingerprint, ip_address
        )
    """

    def __init__(self, *args, **kwargs):
        # Lazy load and initialize UserAuth parent
        UserAuth = _get_user_auth_class()
        self.__class__.__bases__ = (UserAuth,)
        super().__init__(*args, **kwargs)

        self.remember_me_manager = remember_me_manager
        self.session_manager = SessionManager()

        # Initialize remember me database
        try:
            self.remember_me_manager.initialize_database()
        except Exception as e:
            logger.warning(f"Could not initialize remember me database: {e}")

    def login_with_remember_me(
        self,
        username: str,
        password: str,
        remember_me: bool = False,
        device_fingerprint: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict:
        """
        Login with optional remember me functionality.

        Args:
            username: Username
            password: Password
            remember_me: Whether to create remember me token
            device_fingerprint: Device identifier
            ip_address: Client IP address
            user_agent: User agent string

        Returns:
            Dictionary with login result:
            {
                'success': bool,
                'user': dict,
                'remember_token': str (if remember_me=True),
                'session_warnings': list
            }
        """
        # Check rate limit
        identifier = ip_address or username
        if not login_limiter.is_allowed(identifier):
            remaining = login_limiter.get_block_time_remaining(identifier)
            logger.warning(f"Rate limit exceeded for {identifier}")
            return {
                'success': False,
                'error': f'Too many login attempts. Please try again in {remaining} seconds.',
                'rate_limited': True
            }

        # Perform standard login
        try:
            login_result = self.login(username, password)

            if not login_result or (isinstance(login_result, dict) and not login_result.get('success')):
                # Login failed - rate limiter already recorded the attempt
                return {
                    'success': False,
                    'error': 'Invalid credentials',
                    'user': None
                }

            # Handle MFA if required
            if isinstance(login_result, dict) and login_result.get('requires_2fa'):
                return login_result

            # Login successful
            user = self.current_user
            if not user:
                return {'success': False, 'error': 'User information not available'}

            result = {
                'success': True,
                'user': user,
                'session_warnings': []
            }

            # Create remember me token if requested
            if remember_me and device_fingerprint:
                try:
                    token = self.remember_me_manager.create_token(
                        user_id=user['id'],
                        device_fingerprint=device_fingerprint,
                        ip_address=ip_address
                    )
                    result['remember_token'] = token
                    logger.info(f"Created remember me token for user {user['id']}")
                except Exception as e:
                    logger.error(f"Failed to create remember me token: {e}")
                    result['session_warnings'].append("Could not create remember me token")

            # Create session with enhanced features
            if user_agent and ip_address:
                try:
                    session_info = self.session_manager.create_session(
                        user_id=user['id'],
                        role=user.get('role', 'student'),
                        ip_address=ip_address,
                        user_agent=user_agent,
                        device_fingerprint=device_fingerprint
                    )

                    if session_info.get('warnings'):
                        result['session_warnings'].extend(session_info['warnings'])

                except Exception as e:
                    logger.error(f"Failed to create enhanced session: {e}")

            return result

        except Exception as e:
            logger.error(f"Login error: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def verify_remember_me_token(
        self,
        token: str,
        device_fingerprint: str,
        ip_address: Optional[str] = None
    ) -> Optional[int]:
        """
        Verify remember me token and auto-login user.

        Args:
            token: Remember me token
            device_fingerprint: Device identifier
            ip_address: Client IP address

        Returns:
            User ID if valid, None otherwise
        """
        try:
            user_id = self.remember_me_manager.verify_and_rotate_token(
                token, device_fingerprint, ip_address
            )

            if user_id:
                # Auto-login the user
                self._restore_session_from_user_id(user_id)
                logger.info(f"User {user_id} auto-logged in via remember me token")

            return user_id

        except Exception as e:
            logger.error(f"Error verifying remember me token: {e}")
            return None

    def _restore_session_from_user_id(self, user_id: int):
        """Restore user session from user ID"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get user information
                cursor.execute("""
                    SELECT u.id, u.username, u.first_name, u.last_name,
                           u.email, u.role, u.student_id
                    FROM users u
                    WHERE u.id = ?
                """, (user_id,))

                user_data = cursor.fetchone()

                if user_data:
                    self.current_user = {
                        'id': user_data[0],
                        'username': user_data[1],
                        'first_name': user_data[2],
                        'last_name': user_data[3],
                        'email': user_data[4],
                        'role': user_data[5],
                        'student_id': user_data[6]
                    }
                    logger.info(f"Session restored for user {self.current_user['username']}")

        except Exception as e:
            logger.error(f"Error restoring session: {e}")

    def logout_and_revoke_remember_me(self, user_id: Optional[int] = None):
        """
        Logout and revoke all remember me tokens.

        Args:
            user_id: User ID (uses current user if not provided)
        """
        if user_id is None and self.current_user:
            user_id = self.current_user['id']

        # Standard logout
        self.logout()

        # Revoke all remember me tokens
        if user_id:
            try:
                count = self.remember_me_manager.revoke_all_user_tokens(user_id)
                logger.info(f"Revoked {count} remember me tokens for user {user_id}")
            except Exception as e:
                logger.error(f"Error revoking remember me tokens: {e}")

    def get_active_sessions(self, user_id: Optional[int] = None) -> list:
        """
        Get all active sessions and remember me tokens.

        Args:
            user_id: User ID (uses current user if not provided)

        Returns:
            List of active sessions and tokens
        """
        if user_id is None and self.current_user:
            user_id = self.current_user['id']

        if not user_id:
            return []

        try:
            # Get remember me tokens
            tokens = self.remember_me_manager.get_user_tokens(user_id)

            # Get active sessions if session manager is available
            sessions = []
            try:
                active_sessions = self.session_manager._get_active_sessions(user_id)
                sessions = [
                    {
                        'type': 'session',
                        'device': s.get('user_agent', 'Unknown')[:50],
                        'ip': s.get('ip_address', 'Unknown'),
                        'created_at': s.get('created_at'),
                        'last_activity': s.get('last_activity')
                    }
                    for s in active_sessions
                ]
            except Exception:
                pass

            # Combine sessions and tokens
            all_sessions = sessions + [
                {
                    'type': 'remember_me',
                    **token
                }
                for token in tokens
            ]

            return all_sessions

        except Exception as e:
            logger.error(f"Error getting active sessions: {e}")
            return []


# Convenience function to create enhanced auth instance
def create_enhanced_auth(*args, **kwargs) -> EnhancedAuth:
    """Create an EnhancedAuth instance"""
    return EnhancedAuth(*args, **kwargs)


__all__ = ['EnhancedAuth', 'create_enhanced_auth']
