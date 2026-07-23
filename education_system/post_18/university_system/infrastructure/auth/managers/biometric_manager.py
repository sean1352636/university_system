"""
Biometric Authentication Manager Module

This module bridges BiometricService with the authentication system, providing
biometric enrollment, authentication, listing, and revocation capabilities.

Classes:
    BiometricManager: Manages biometric authentication operations
"""

from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

from education_system.post_18.university_system.infrastructure.database.db import sqlite3

# Conditionally import BiometricService
try:
    from education_system.post_18.university_system.infrastructure.auth.biometric_service import BiometricService
    BIOMETRIC_SERVICE_AVAILABLE = True
except ImportError:
    BIOMETRIC_SERVICE_AVAILABLE = False

logger = logging.getLogger(__name__)

__all__ = ['BiometricManager']

# Supported biometric types
SUPPORTED_BIOMETRIC_TYPES = ['face', 'fingerprint']


class BiometricManager:
    """
    Manager for biometric authentication operations.

    This class bridges BiometricService with the authentication system,
    handling biometric enrollment, authentication, listing, and revocation
    for enhanced account security.

    Attributes:
        db_manager: Database manager instance for data operations
        activity_logger: Activity logger for audit trails
        get_current_user: Function to get current user info
        biometric_service: BiometricService instance (if available)
    """

    def __init__(self, db_manager, activity_logger, current_user_getter):
        """
        Initialize the BiometricManager.

        Parameters:
            db_manager: Database manager instance
            activity_logger: Activity logger callable (username, action, details, user_id)
            current_user_getter: Function to get current user info
        """
        self.db_manager = db_manager
        self.activity_logger = activity_logger
        self.get_current_user = current_user_getter
        self.biometric_service = None

        if BIOMETRIC_SERVICE_AVAILABLE:
            try:
                self.biometric_service = BiometricService(db_manager=db_manager)
            except Exception as e:
                logger.warning(f"Failed to initialize BiometricService: {e}")

    def _ensure_tables(self, conn) -> None:
        """
        Ensure biometric enrollment tables exist.

        Uses the same canonical schema as BiometricService to avoid
        conflicts when both modules access the same table.

        Parameters:
            conn: Active database connection
        """
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS biometric_enrollments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                enrollment_id TEXT UNIQUE,
                user_id TEXT NOT NULL,
                biometric_type TEXT NOT NULL,
                template_data BLOB,
                template_hash TEXT,
                device_name TEXT DEFAULT 'Unknown Device',
                quality_score REAL,
                created_at TEXT NOT NULL,
                last_verified_at TEXT,
                is_active INTEGER DEFAULT 1,
                verification_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                metadata TEXT DEFAULT '{}',
                revoked_at TEXT
            )
        ''')
        conn.commit()

    def _get_user_info(self, conn, user_id: int) -> Optional[Dict]:
        """
        Get basic user information for logging.

        Parameters:
            conn: Active database connection
            user_id: User ID to look up

        Returns:
            dict or None: User info dict with 'id' and 'username', or None if not found
        """
        cursor = conn.cursor()
        cursor.execute('''
            SELECT u.id, ua.username
            FROM users u
            JOIN user_accounts ua ON u.id = ua.user_id
            WHERE u.id = ?
        ''', (user_id,))
        row = cursor.fetchone()
        if row:
            return {'id': row[0], 'username': row[1]}
        return None

    def enroll_biometric(self, biometric_type: str, data: str,
                         user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Enroll a biometric credential for a user.

        Routes to face or fingerprint enrollment based on biometric_type.
        If user_id is not specified, uses the current logged-in user.

        Parameters:
            biometric_type: Type of biometric ('face' or 'fingerprint')
            data: Biometric data payload (template or encoding)
            user_id: Optional user ID to enroll for (defaults to current user)

        Returns:
            dict: Result dictionary containing:
                  - success: bool - Whether enrollment succeeded
                  - enrollment_id: int - ID of the enrollment record (if successful)
                  - message: str - Result message
        """
        if not BIOMETRIC_SERVICE_AVAILABLE:
            return {
                'success': False,
                'message': 'BiometricService is not available. Install required dependencies.'
            }

        if biometric_type not in SUPPORTED_BIOMETRIC_TYPES:
            return {
                'success': False,
                'message': (
                    f"Unsupported biometric type '{biometric_type}'. "
                    f"Supported types: {', '.join(SUPPORTED_BIOMETRIC_TYPES)}"
                )
            }

        # Resolve user
        current_user = self.get_current_user()
        if user_id is None:
            if not current_user:
                return {'success': False, 'message': 'No user logged in and no user_id provided.'}
            user_id = current_user['id']

        if not data:
            return {'success': False, 'message': 'Biometric data must not be empty.'}

        try:
            with self.db_manager.get_connection() as conn:
                self._ensure_tables(conn)
                cursor = conn.cursor()

                # Verify user exists
                user_info = self._get_user_info(conn, user_id)
                if not user_info:
                    return {'success': False, 'message': f'User with ID {user_id} not found.'}

                # Check for existing active enrollment of same type
                cursor.execute('''
                    SELECT id FROM biometric_enrollments
                    WHERE user_id = ? AND biometric_type = ? AND is_active = 1
                ''', (user_id, biometric_type))
                existing = cursor.fetchone()
                if existing:
                    return {
                        'success': False,
                        'message': (
                            f"User already has an active {biometric_type} enrollment. "
                            f"Revoke it before enrolling a new one."
                        )
                    }

                # Route to the appropriate enrollment method on BiometricService
                # The service handles the INSERT into biometric_enrollments
                if biometric_type == 'face':
                    service_result = self.biometric_service.enroll_face(user_id, data)
                else:
                    service_result = self.biometric_service.enroll_fingerprint(user_id, data)

                if not service_result.get('success', False):
                    return {
                        'success': False,
                        'message': service_result.get(
                            'message',
                            service_result.get('error', 'Biometric enrollment failed.')
                        )
                    }

                enrollment_id = service_result.get('enrollment_id')

                # Log activity
                actor_username = current_user['username'] if current_user else 'system'
                actor_id = current_user.get('id') if current_user else None
                self.activity_logger(
                    actor_username,
                    f'Biometric enrolled: {biometric_type}',
                    f'Enrollment ID: {enrollment_id}, Target user: {user_info["username"]}',
                    actor_id
                )

                logger.info(
                    f"Biometric enrollment created: type={biometric_type}, "
                    f"user={user_info['username']}, enrollment_id={enrollment_id}"
                )

                return {
                    'success': True,
                    'enrollment_id': enrollment_id,
                    'message': f'{biometric_type.capitalize()} biometric enrolled successfully.'
                }

        except sqlite3.Error as e:
            logger.error(f"Database error during biometric enrollment: {e}")
            return {'success': False, 'message': 'Database error during biometric enrollment.'}
        except Exception as e:
            logger.error(f"Unexpected error during biometric enrollment: {e}")
            return {'success': False, 'message': 'An unexpected error occurred during enrollment.'}

    def authenticate_biometric(self, biometric_type: str, data: str) -> Dict[str, Any]:
        """
        Authenticate a user using biometric data.

        Attempts to match the provided biometric data against enrolled records.

        Parameters:
            biometric_type: Type of biometric ('face' or 'fingerprint')
            data: Biometric data to authenticate with

        Returns:
            dict: Result dictionary containing:
                  - success: bool - Whether authentication succeeded
                  - user_id: int - Authenticated user ID (if successful)
                  - username: str - Authenticated username (if successful)
                  - message: str - Result message
        """
        if not BIOMETRIC_SERVICE_AVAILABLE:
            return {
                'success': False,
                'message': 'BiometricService is not available. Install required dependencies.'
            }

        if biometric_type not in SUPPORTED_BIOMETRIC_TYPES:
            return {
                'success': False,
                'message': (
                    f"Unsupported biometric type '{biometric_type}'. "
                    f"Supported types: {', '.join(SUPPORTED_BIOMETRIC_TYPES)}"
                )
            }

        if not data:
            return {'success': False, 'message': 'Biometric data must not be empty.'}

        try:
            # Delegate to BiometricService for matching
            if biometric_type == 'face':
                service_result = self.biometric_service.authenticate_face(data)
            else:
                service_result = self.biometric_service.authenticate_fingerprint(data)

            if not service_result.get('success', False):
                logger.info(f"Biometric authentication failed: type={biometric_type}")
                return {
                    'success': False,
                    'message': service_result.get('message', 'Biometric authentication failed.')
                }

            matched_user_id = service_result.get('user_id')
            if not matched_user_id:
                return {'success': False, 'message': 'No matching user found.'}

            # Look up the user info
            with self.db_manager.get_connection() as conn:
                user_info = self._get_user_info(conn, matched_user_id)
                if not user_info:
                    return {
                        'success': False,
                        'message': 'Matched user no longer exists in the system.'
                    }

            # Log successful authentication
            self.activity_logger(
                user_info['username'],
                f'Biometric authentication: {biometric_type}',
                'Authentication successful',
                user_info['id']
            )

            logger.info(
                f"Biometric authentication successful: type={biometric_type}, "
                f"user={user_info['username']}"
            )

            return {
                'success': True,
                'user_id': user_info['id'],
                'username': user_info['username'],
                'message': 'Biometric authentication successful.'
            }

        except sqlite3.Error:
            logger.error("Database error during biometric authentication")
            return {'success': False, 'message': 'Database error during biometric authentication.'}
        except Exception:
            logger.error("Unexpected error during biometric authentication")
            return {'success': False, 'message': 'An unexpected error occurred during authentication.'}

    def list_enrollments(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        List biometric enrollments for a user.

        If user_id is not specified, lists enrollments for the current user.

        Parameters:
            user_id: Optional user ID (defaults to current user)

        Returns:
            list: List of enrollment dictionaries, each containing:
                  - id: int - Enrollment ID
                  - user_id: int - User ID
                  - biometric_type: str - Type of biometric
                  - is_active: bool - Whether enrollment is active
                  - created_at: str - Enrollment timestamp
                  - revoked_at: str or None - Revocation timestamp
        """
        current_user = self.get_current_user()
        if user_id is None:
            if not current_user:
                logger.warning("Cannot list enrollments: no user logged in and no user_id provided.")
                return []
            user_id = current_user['id']

        try:
            with self.db_manager.get_connection() as conn:
                self._ensure_tables(conn)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT id, user_id, biometric_type, is_active, created_at, revoked_at
                    FROM biometric_enrollments
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                ''', (user_id,))

                enrollments = []
                for row in cursor.fetchall():
                    enrollments.append({
                        'id': row['id'],
                        'user_id': row['user_id'],
                        'biometric_type': row['biometric_type'],
                        'is_active': bool(row['is_active']),
                        'created_at': row['created_at'],
                        'revoked_at': row['revoked_at'],
                    })

                return enrollments

        except sqlite3.Error as e:
            logger.error(f"Database error listing biometric enrollments: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing biometric enrollments: {e}")
            return []

    def revoke_enrollment(self, enrollment_id: int) -> Dict[str, Any]:
        """
        Revoke a biometric enrollment.

        Marks the specified enrollment as inactive and records the revocation
        timestamp. Also notifies the BiometricService to remove the credential.

        Parameters:
            enrollment_id: ID of the enrollment to revoke

        Returns:
            dict: Result dictionary containing:
                  - success: bool - Whether revocation succeeded
                  - message: str - Result message
        """
        current_user = self.get_current_user()
        if not current_user:
            return {'success': False, 'message': 'You must be logged in to revoke enrollments.'}

        try:
            with self.db_manager.get_connection() as conn:
                self._ensure_tables(conn)
                cursor = conn.cursor()

                # Fetch the enrollment
                cursor.execute('''
                    SELECT id, user_id, biometric_type, is_active
                    FROM biometric_enrollments
                    WHERE id = ?
                ''', (enrollment_id,))
                enrollment = cursor.fetchone()

                if not enrollment:
                    return {'success': False, 'message': f'Enrollment {enrollment_id} not found.'}

                enroll_id, enroll_user_id, biometric_type, is_active = enrollment

                if not is_active:
                    return {
                        'success': False,
                        'message': f'Enrollment {enrollment_id} is already revoked.'
                    }

                # Permission check: user can revoke own, or admin can revoke any
                is_own = current_user['id'] == enroll_user_id
                is_admin = current_user.get('role', '').lower() == 'admin'
                has_perm = 'manage_users' in current_user.get('permissions', [])

                if not is_own and not is_admin and not has_perm:
                    return {
                        'success': False,
                        'message': 'You do not have permission to revoke this enrollment.'
                    }

                # Revoke the enrollment
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                    UPDATE biometric_enrollments
                    SET is_active = 0, revoked_at = ?
                    WHERE id = ?
                ''', (timestamp, enrollment_id))
                conn.commit()

                # Get target user info for logging
                user_info = self._get_user_info(conn, enroll_user_id)
                target_username = user_info['username'] if user_info else str(enroll_user_id)

                # Log activity
                self.activity_logger(
                    current_user['username'],
                    f'Biometric revoked: {biometric_type}',
                    f'Enrollment ID: {enrollment_id}, Target user: {target_username}',
                    current_user['id']
                )

                logger.info(
                    f"Biometric enrollment revoked: enrollment_id={enrollment_id}, "
                    f"type={biometric_type}, user={target_username}"
                )

                return {
                    'success': True,
                    'message': (
                        f'{biometric_type.capitalize()} enrollment {enrollment_id} '
                        f'revoked successfully.'
                    )
                }

        except sqlite3.Error as e:
            logger.error(f"Database error revoking biometric enrollment: {e}")
            return {'success': False, 'message': 'Database error during enrollment revocation.'}
        except Exception as e:
            logger.error(f"Unexpected error revoking biometric enrollment: {e}")
            return {'success': False, 'message': 'An unexpected error occurred during revocation.'}
