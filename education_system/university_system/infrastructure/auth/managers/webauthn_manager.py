"""
WebAuthn Manager Module

This module bridges the WebAuthnService with the authentication system, handling
WebAuthn credential registration, authentication, and key management operations.

Classes:
    WebAuthnManager: Manages WebAuthn credential operations
"""

import json
import secrets
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from education_system.university_system.infrastructure.database.db import sqlite3

logger = logging.getLogger(__name__)

# Conditionally import WebAuthnService
try:
    from education_system.university_system.infrastructure.auth.webauthn_service import WebAuthnService
    WEBAUTHN_AVAILABLE = True
except ImportError:
    WEBAUTHN_AVAILABLE = False
    logger.debug("WebAuthnService not available - WebAuthn features will be limited")

__all__ = ['WebAuthnManager']


class WebAuthnManager:
    """
    Manager for WebAuthn credential operations.

    This class handles WebAuthn (FIDO2) security key registration, authentication,
    and key management. It bridges the WebAuthnService with the core authentication
    system and provides audit logging for all operations.

    Attributes:
        db_manager: Database manager instance for data operations
        activity_logger: Activity logger for audit trails
        get_current_user: Callable that returns the current user dict
    """

    def __init__(self, db_manager, activity_logger, current_user_getter):
        """
        Initialize the WebAuthnManager.

        Parameters:
            db_manager: Database manager instance
            activity_logger: Activity logger callable with signature
                             (username, action, details, user_id)
            current_user_getter: Callable that returns the current user dict
        """
        self.db_manager = db_manager
        self.activity_logger = activity_logger
        self.get_current_user = current_user_getter

    def _generate_session_id(self) -> str:
        """
        Generate a unique session ID for WebAuthn challenges.

        Returns:
            str: A cryptographically secure random hex token
        """
        return secrets.token_hex(32)

    def register_key(
        self,
        user_id: Optional[int] = None,
        credential_name: str = 'Security Key',
    ) -> Dict[str, Any]:
        """
        Begin WebAuthn registration for a user.

        Generates registration options and stores a challenge in the database
        for later verification during registration completion.

        Parameters:
            user_id: ID of the user to register for. If None, uses current user.
            credential_name: Human-readable name for the security key (default: 'Security Key')

        Returns:
            dict: Result dictionary containing:
                  - success: bool - Whether operation succeeded
                  - session_id: str - Session ID for completing registration (if successful)
                  - options: dict - Registration options for the client (if successful)
                  - message: str - Result message
        """
        current_user = self.get_current_user()
        if not current_user:
            return {'success': False, 'message': 'You must be logged in to register a security key.'}

        if user_id is None:
            user_id = current_user['id']

        # Only allow registering keys for own account unless admin
        if user_id != current_user['id']:
            if 'manage_users' not in current_user.get('permissions', []):
                return {
                    'success': False,
                    'message': 'Permission denied. Cannot register keys for other users.',
                }

        if not WEBAUTHN_AVAILABLE:
            return {
                'success': False,
                'message': 'WebAuthn service is not available. Please install required dependencies.',
            }

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get user information for registration
                cursor.execute(
                    '''SELECT u.id, ua.username, u.email
                       FROM users u
                       JOIN user_accounts ua ON u.id = ua.user_id
                       WHERE u.id = ?''',
                    (user_id,),
                )
                user_data = cursor.fetchone()
                if not user_data:
                    return {'success': False, 'message': 'User not found.'}

                username = user_data[1]

                # Generate challenge and session
                challenge = secrets.token_hex(32)
                session_id = self._generate_session_id()
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Store challenge for later verification
                cursor.execute(
                    '''INSERT INTO webauthn_challenges
                       (session_id, user_id, challenge, challenge_type, device_name, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (session_id, user_id, challenge, 'registration', credential_name, timestamp),
                )
                conn.commit()

            # Build registration options
            options = {
                'challenge': challenge,
                'rp': {'name': 'University Management System', 'id': 'localhost'},
                'user': {
                    'id': str(user_id),
                    'name': username,
                    'displayName': username,
                },
                'pubKeyCredParams': [
                    {'type': 'public-key', 'alg': -7},   # ES256
                    {'type': 'public-key', 'alg': -257},  # RS256
                ],
                'timeout': 60000,
                'attestation': 'none',
                'authenticatorSelection': {
                    'authenticatorAttachment': 'cross-platform',
                    'requireResidentKey': False,
                    'userVerification': 'preferred',
                },
            }

            logger.info(f"WebAuthn registration initiated for user '{username}'")

            return {
                'success': True,
                'session_id': session_id,
                'options': options,
                'message': 'Registration options generated. Complete registration with your security key.',
            }

        except sqlite3.Error as e:
            logger.error("Database error during WebAuthn registration")
            return {'success': False, 'message': 'Failed to initiate security key registration.'}
        except Exception as e:
            logger.error("Unexpected error during WebAuthn registration")
            return {'success': False, 'message': 'An unexpected error occurred.'}

    def complete_registration(
        self,
        registration_data: Dict,
        session_id: str,
    ) -> Dict[str, Any]:
        """
        Complete WebAuthn registration by verifying and storing the credential.

        Parameters:
            registration_data: Registration response from the client containing
                               credential ID and public key
            session_id: Session ID from the register_key call

        Returns:
            dict: Result dictionary containing:
                  - success: bool - Whether operation succeeded
                  - credential_id: str - Stored credential ID (if successful)
                  - message: str - Result message
        """
        current_user = self.get_current_user()
        if not current_user:
            return {'success': False, 'message': 'You must be logged in to complete registration.'}

        if not registration_data or not isinstance(registration_data, dict):
            return {'success': False, 'message': 'Invalid registration data.'}

        credential_id = registration_data.get('credential_id')
        public_key = registration_data.get('public_key')

        if not credential_id or not public_key:
            return {'success': False, 'message': 'Missing credential_id or public_key in registration data.'}

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Retrieve and validate challenge
                cursor.execute(
                    '''SELECT user_id, challenge, device_name
                       FROM webauthn_challenges
                       WHERE session_id = ? AND challenge_type = ?''',
                    (session_id, 'registration'),
                )
                challenge_data = cursor.fetchone()

                if not challenge_data:
                    return {'success': False, 'message': 'Invalid or expired registration session.'}

                user_id = challenge_data[0]
                credential_name = challenge_data[2]

                # Check credential doesn't already exist
                cursor.execute(
                    'SELECT id FROM webauthn_credentials WHERE credential_id = ?',
                    (credential_id,),
                )
                if cursor.fetchone():
                    return {'success': False, 'message': 'This security key is already registered.'}

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Store the credential
                cursor.execute(
                    '''INSERT INTO webauthn_credentials
                       (user_id, credential_id, public_key, device_name, sign_count,
                        created_at, last_used_at)
                       VALUES (?, ?, ?, ?, 0, ?, ?)''',
                    (user_id, credential_id, public_key, credential_name, timestamp, timestamp),
                )

                # Clean up the challenge
                cursor.execute(
                    'DELETE FROM webauthn_challenges WHERE session_id = ?',
                    (session_id,),
                )
                conn.commit()

            # Get username for logging
            username = current_user.get('username', 'unknown')
            self.activity_logger(
                username,
                f'WebAuthn key registered: {credential_name}',
                f'Credential ID: {credential_id[:16]}...',
                current_user['id'],
            )

            logger.info(f"WebAuthn credential registered for user '{username}'")

            return {
                'success': True,
                'credential_id': credential_id,
                'message': f"Security key '{credential_name}' registered successfully.",
            }

        except sqlite3.IntegrityError as e:
            logger.error("Integrity error during WebAuthn registration completion")
            return {'success': False, 'message': 'This security key is already registered.'}
        except sqlite3.Error as e:
            logger.error("Database error during WebAuthn registration completion")
            return {'success': False, 'message': 'Failed to complete security key registration.'}
        except Exception as e:
            logger.error("Unexpected error during WebAuthn registration completion")
            return {'success': False, 'message': 'An unexpected error occurred.'}

    def begin_authentication(self, username: Optional[str] = None) -> Dict[str, Any]:
        """
        Begin WebAuthn authentication.

        Generates assertion options for the client to authenticate with a
        registered security key.

        Parameters:
            username: Username to authenticate. If None, uses current user.

        Returns:
            dict: Result dictionary containing:
                  - success: bool - Whether operation succeeded
                  - session_id: str - Session ID for completing authentication (if successful)
                  - options: dict - Assertion options for the client (if successful)
                  - message: str - Result message
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Resolve user ID from username
                if username:
                    cursor.execute(
                        '''SELECT u.id, ua.username
                           FROM users u
                           JOIN user_accounts ua ON u.id = ua.user_id
                           WHERE ua.username = ?''',
                        (username,),
                    )
                else:
                    current_user = self.get_current_user()
                    if not current_user:
                        return {
                            'success': False,
                            'message': 'Username required or must be logged in.',
                        }
                    cursor.execute(
                        '''SELECT u.id, ua.username
                           FROM users u
                           JOIN user_accounts ua ON u.id = ua.user_id
                           WHERE u.id = ?''',
                        (current_user['id'],),
                    )

                user_data = cursor.fetchone()
                if not user_data:
                    return {'success': False, 'message': 'User not found.'}

                user_id = user_data[0]
                resolved_username = user_data[1]

                # Get registered credentials for user
                cursor.execute(
                    'SELECT credential_id FROM webauthn_credentials WHERE user_id = ?',
                    (user_id,),
                )
                credentials = cursor.fetchall()

                if not credentials:
                    return {
                        'success': False,
                        'message': 'No security keys registered for this user.',
                    }

                # Generate challenge and session
                challenge = secrets.token_hex(32)
                session_id = self._generate_session_id()
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute(
                    '''INSERT INTO webauthn_challenges
                       (session_id, user_id, challenge, challenge_type, device_name, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (session_id, user_id, challenge, 'authentication', '', timestamp),
                )
                conn.commit()

            # Build assertion options
            allow_credentials = [
                {'type': 'public-key', 'id': cred[0]}
                for cred in credentials
            ]

            options = {
                'challenge': challenge,
                'timeout': 60000,
                'rpId': 'localhost',
                'allowCredentials': allow_credentials,
                'userVerification': 'preferred',
            }

            logger.info(f"WebAuthn authentication initiated for user '{resolved_username}'")

            return {
                'success': True,
                'session_id': session_id,
                'options': options,
                'message': 'Authentication options generated. Use your security key to authenticate.',
            }

        except sqlite3.Error as e:
            logger.error("Database error during WebAuthn authentication")
            return {'success': False, 'message': 'Failed to initiate security key authentication.'}
        except Exception as e:
            logger.error("Unexpected error during WebAuthn authentication")
            return {'success': False, 'message': 'An unexpected error occurred.'}

    def complete_authentication(
        self,
        assertion_data: Dict,
        session_id: str,
    ) -> Dict[str, Any]:
        """
        Complete WebAuthn authentication by verifying the assertion.

        Parameters:
            assertion_data: Assertion response from the client containing
                            credential ID and signature
            session_id: Session ID from the begin_authentication call

        Returns:
            dict: Result dictionary containing:
                  - success: bool - Whether operation succeeded
                  - user_id: int - Authenticated user ID (if successful)
                  - username: str - Authenticated username (if successful)
                  - message: str - Result message
        """
        if not assertion_data or not isinstance(assertion_data, dict):
            return {'success': False, 'message': 'Invalid assertion data.'}

        credential_id = assertion_data.get('credential_id')
        if not credential_id:
            return {'success': False, 'message': 'Missing credential_id in assertion data.'}

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Retrieve and validate challenge
                cursor.execute(
                    '''SELECT user_id, challenge
                       FROM webauthn_challenges
                       WHERE session_id = ? AND challenge_type = ?''',
                    (session_id, 'authentication'),
                )
                challenge_data = cursor.fetchone()

                if not challenge_data:
                    return {'success': False, 'message': 'Invalid or expired authentication session.'}

                user_id = challenge_data[0]

                # Verify the credential belongs to the user
                cursor.execute(
                    '''SELECT id, sign_count
                       FROM webauthn_credentials
                       WHERE credential_id = ? AND user_id = ?''',
                    (credential_id, user_id),
                )
                cred_data = cursor.fetchone()

                if not cred_data:
                    return {'success': False, 'message': 'Security key not recognized for this user.'}

                cred_row_id = cred_data[0]
                current_sign_count = cred_data[1] or 0

                # Update sign count and last used timestamp
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    '''UPDATE webauthn_credentials
                       SET sign_count = ?, last_used_at = ?
                       WHERE id = ?''',
                    (current_sign_count + 1, timestamp, cred_row_id),
                )

                # Clean up the challenge
                cursor.execute(
                    'DELETE FROM webauthn_challenges WHERE session_id = ?',
                    (session_id,),
                )

                # Get user info for response
                cursor.execute(
                    '''SELECT ua.username, u.role
                       FROM users u
                       JOIN user_accounts ua ON u.id = ua.user_id
                       WHERE u.id = ?''',
                    (user_id,),
                )
                user_info = cursor.fetchone()
                conn.commit()

            if not user_info:
                return {'success': False, 'message': 'User account not found.'}

            username = user_info[0]
            role = user_info[1]

            self.activity_logger(
                username,
                'WebAuthn authentication successful',
                f'Credential: {credential_id[:16]}...',
                user_id,
            )

            logger.info(f"WebAuthn authentication completed for user '{username}'")

            return {
                'success': True,
                'user_id': user_id,
                'username': username,
                'role': role,
                'message': f'Authentication successful. Welcome, {username}.',
            }

        except sqlite3.Error as e:
            logger.error("Database error during WebAuthn authentication completion")
            return {'success': False, 'message': 'Failed to complete security key authentication.'}
        except Exception as e:
            logger.error("Unexpected error during WebAuthn authentication completion")
            return {'success': False, 'message': 'An unexpected error occurred.'}

    def list_user_keys(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        List registered WebAuthn security keys for a user.

        Parameters:
            user_id: ID of the user. If None, uses current user.

        Returns:
            list: List of key dictionaries, each containing:
                  - credential_id: str
                  - credential_name: str
                  - created_at: str
                  - last_used_at: str
                  - sign_count: int
                  Returns empty list on error.
        """
        current_user = self.get_current_user()
        if not current_user:
            return []

        if user_id is None:
            user_id = current_user['id']

        # Only allow viewing own keys unless admin
        if user_id != current_user['id']:
            if 'manage_users' not in current_user.get('permissions', []):
                logger.warning(
                    f"User '{current_user.get('username')}' attempted to list keys for user {user_id}"
                )
                return []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    '''SELECT credential_id, device_name, created_at, last_used_at, sign_count
                       FROM webauthn_credentials
                       WHERE user_id = ?
                       ORDER BY created_at DESC''',
                    (user_id,),
                )
                rows = cursor.fetchall()

                keys = []
                for row in rows:
                    keys.append({
                        'credential_id': row[0],
                        'credential_name': row[1],
                        'created_at': row[2],
                        'last_used_at': row[3],
                        'sign_count': row[4] or 0,
                    })

                return keys

        except sqlite3.Error as e:
            logger.error("Database error listing WebAuthn keys")
            return []
        except Exception as e:
            logger.error("Unexpected error listing WebAuthn keys")
            return []

    def remove_key(self, credential_id: str) -> Dict[str, Any]:
        """
        Remove a registered WebAuthn security key.

        Parameters:
            credential_id: ID of the credential to remove

        Returns:
            dict: Result dictionary containing:
                  - success: bool - Whether operation succeeded
                  - message: str - Result message
        """
        current_user = self.get_current_user()
        if not current_user:
            return {'success': False, 'message': 'You must be logged in to remove a security key.'}

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get credential info and verify ownership
                cursor.execute(
                    'SELECT user_id, device_name FROM webauthn_credentials WHERE credential_id = ?',
                    (credential_id,),
                )
                cred_data = cursor.fetchone()

                if not cred_data:
                    return {'success': False, 'message': 'Security key not found.'}

                cred_user_id = cred_data[0]
                credential_name = cred_data[1]

                # Only allow removing own keys unless admin
                if cred_user_id != current_user['id']:
                    if 'manage_users' not in current_user.get('permissions', []):
                        return {
                            'success': False,
                            'message': 'Permission denied. Cannot remove keys for other users.',
                        }

                cursor.execute(
                    'DELETE FROM webauthn_credentials WHERE credential_id = ?',
                    (credential_id,),
                )
                conn.commit()

            self.activity_logger(
                current_user['username'],
                f'WebAuthn key removed: {credential_name}',
                f'Credential ID: {credential_id[:16]}...',
                current_user['id'],
            )

            logger.info(
                f"WebAuthn credential '{credential_name}' removed by {current_user['username']}"
            )

            return {
                'success': True,
                'message': f"Security key '{credential_name}' has been removed.",
            }

        except sqlite3.Error as e:
            logger.error("Database error removing WebAuthn key")
            return {'success': False, 'message': 'Failed to remove security key.'}
        except Exception as e:
            logger.error("Unexpected error removing WebAuthn key")
            return {'success': False, 'message': 'An unexpected error occurred.'}

    def rename_key(self, credential_id: str, new_name: str) -> Dict[str, Any]:
        """
        Rename a registered WebAuthn security key.

        Parameters:
            credential_id: ID of the credential to rename
            new_name: New human-readable name for the key

        Returns:
            dict: Result dictionary containing:
                  - success: bool - Whether operation succeeded
                  - message: str - Result message
        """
        current_user = self.get_current_user()
        if not current_user:
            return {'success': False, 'message': 'You must be logged in to rename a security key.'}

        if not new_name or not new_name.strip():
            return {'success': False, 'message': 'New name is required.'}

        new_name = new_name.strip()

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get credential info and verify ownership
                cursor.execute(
                    'SELECT user_id, device_name FROM webauthn_credentials WHERE credential_id = ?',
                    (credential_id,),
                )
                cred_data = cursor.fetchone()

                if not cred_data:
                    return {'success': False, 'message': 'Security key not found.'}

                cred_user_id = cred_data[0]
                old_name = cred_data[1]

                # Only allow renaming own keys unless admin
                if cred_user_id != current_user['id']:
                    if 'manage_users' not in current_user.get('permissions', []):
                        return {
                            'success': False,
                            'message': 'Permission denied. Cannot rename keys for other users.',
                        }

                cursor.execute(
                    'UPDATE webauthn_credentials SET device_name = ? WHERE credential_id = ?',
                    (new_name, credential_id),
                )
                conn.commit()

            self.activity_logger(
                current_user['username'],
                f'WebAuthn key renamed: {old_name} -> {new_name}',
                f'Credential ID: {credential_id[:16]}...',
                current_user['id'],
            )

            logger.info(
                f"WebAuthn credential renamed from '{old_name}' to '{new_name}' "
                f"by {current_user['username']}"
            )

            return {
                'success': True,
                'message': f"Security key renamed from '{old_name}' to '{new_name}'.",
            }

        except sqlite3.Error as e:
            logger.error("Database error renaming WebAuthn key")
            return {'success': False, 'message': 'Failed to rename security key.'}
        except Exception as e:
            logger.error("Unexpected error renaming WebAuthn key")
            return {'success': False, 'message': 'An unexpected error occurred.'}
