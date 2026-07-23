"""
Delegated Access Manager Module

This module manages delegated access (power of attorney) functionality,
allowing users to grant other users limited access to their account data
within defined scopes. It handles delegation creation, revocation, scope
management, request workflows, expiration, and audit logging.

Classes:
    DelegatedAccessManager: Manages delegated access operations
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.infrastructure.auth.delegated_access_scopes import (
    DELEGATION_SCOPES,
    get_scope_permissions,
)

logger = logging.getLogger(__name__)

__all__ = ['DelegatedAccessManager']


class DelegatedAccessManager:
    """
    Manager for delegated access and power of attorney operations.

    This class handles the full lifecycle of delegated access: creation,
    revocation, scope management, request workflows (create, approve, reject),
    automatic expiration, permission checking, and audit trail logging.

    Attributes:
        db_manager: Database manager instance for data operations
        activity_logger: Activity logger for audit trails
        get_current_user: Function to get current user info
        permission_manager: PermissionManager instance for permission checks
    """

    def __init__(self, db_manager, activity_logger, current_user_getter, permission_manager):
        """
        Initialize the DelegatedAccessManager.

        Parameters:
            db_manager: Database manager instance
            activity_logger: Activity logger callable (username, action, details, user_id)
            current_user_getter: Function to get current user info
            permission_manager: PermissionManager instance for permission checks
        """
        self.db_manager = db_manager
        self.activity_logger = activity_logger
        self.get_current_user = current_user_getter
        self.permission_manager = permission_manager

    def _ensure_tables(self, conn) -> None:
        """
        Ensure delegated access tables exist.

        Creates the delegated_access, delegated_access_requests, and
        delegated_access_audit tables if they do not already exist.

        Parameters:
            conn: Active database connection
        """
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS delegated_access (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                grantor_user_id INTEGER NOT NULL,
                delegate_user_id INTEGER NOT NULL,
                scope_json TEXT NOT NULL,
                relationship TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                expires_at TEXT,
                revoked_at TEXT,
                FOREIGN KEY (grantor_user_id) REFERENCES users(id),
                FOREIGN KEY (delegate_user_id) REFERENCES users(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS delegated_access_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                requester_user_id INTEGER NOT NULL,
                target_user_id INTEGER NOT NULL,
                relationship TEXT NOT NULL,
                scope_json TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                resolved_at TEXT,
                resolved_by INTEGER,
                FOREIGN KEY (requester_user_id) REFERENCES users(id),
                FOREIGN KEY (target_user_id) REFERENCES users(id),
                FOREIGN KEY (resolved_by) REFERENCES users(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS delegated_access_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                delegation_id INTEGER NOT NULL,
                delegate_user_id INTEGER NOT NULL,
                target_user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                resource_type TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (delegation_id) REFERENCES delegated_access(id),
                FOREIGN KEY (delegate_user_id) REFERENCES users(id),
                FOREIGN KEY (target_user_id) REFERENCES users(id)
            )
        ''')

        conn.commit()

    def _get_user_info(self, conn, user_id: int) -> Optional[Dict]:
        """
        Get basic user information.

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

    def _validate_scope_keys(self, scope_keys: List[str]) -> Optional[str]:
        """
        Validate that all scope keys are recognized.

        Parameters:
            scope_keys: List of scope key strings to validate

        Returns:
            str or None: Error message if invalid, None if all valid
        """
        if not scope_keys:
            return 'At least one scope key is required.'

        invalid_keys = [key for key in scope_keys if key not in DELEGATION_SCOPES]
        if invalid_keys:
            valid_keys = ', '.join(DELEGATION_SCOPES.keys())
            return (
                f"Invalid scope keys: {', '.join(invalid_keys)}. "
                f"Valid keys: {valid_keys}"
            )
        return None

    def create_delegation(self, delegate_user_id: int, scope_keys: List[str],
                          relationship: str,
                          expires_at: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a delegated access grant from the current user to a delegate.

        The current user becomes the grantor. The delegate receives access
        to the grantor's data within the specified scopes.

        Parameters:
            delegate_user_id: User ID of the delegate receiving access
            scope_keys: List of scope keys from DELEGATION_SCOPES
            relationship: Description of the relationship (e.g. 'parent', 'guardian')
            expires_at: Optional expiration datetime string (YYYY-MM-DD HH:MM:SS)

        Returns:
            dict: Result dictionary containing:
                  - success: bool - Whether creation succeeded
                  - delegation_id: int - ID of the new delegation (if successful)
                  - message: str - Result message
        """
        current_user = self.get_current_user()
        if not current_user:
            return {'success': False, 'message': 'You must be logged in to create a delegation.'}

        grantor_user_id = current_user['id']

        if grantor_user_id == delegate_user_id:
            return {'success': False, 'message': 'Cannot delegate access to yourself.'}

        if not relationship or not relationship.strip():
            return {'success': False, 'message': 'Relationship description is required.'}

        # Validate scope keys
        validation_error = self._validate_scope_keys(scope_keys)
        if validation_error:
            return {'success': False, 'message': validation_error}

        try:
            with self.db_manager.get_connection() as conn:
                self._ensure_tables(conn)
                cursor = conn.cursor()

                # Verify delegate user exists
                delegate_info = self._get_user_info(conn, delegate_user_id)
                if not delegate_info:
                    return {
                        'success': False,
                        'message': f'Delegate user with ID {delegate_user_id} not found.'
                    }

                # Check for existing active delegation between these users
                cursor.execute('''
                    SELECT id FROM delegated_access
                    WHERE grantor_user_id = ? AND delegate_user_id = ? AND status = 'active'
                ''', (grantor_user_id, delegate_user_id))
                existing = cursor.fetchone()
                if existing:
                    return {
                        'success': False,
                        'message': (
                            f'An active delegation to user {delegate_info["username"]} '
                            f'already exists (ID: {existing[0]}). '
                            f'Update its scope or revoke it first.'
                        )
                    }

                # Create the delegation
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                scope_json = json.dumps(scope_keys)

                cursor.execute('''
                    INSERT INTO delegated_access
                        (grantor_user_id, delegate_user_id, scope_json, relationship,
                         status, created_at, updated_at, expires_at)
                    VALUES (?, ?, ?, ?, 'active', ?, ?, ?)
                ''', (grantor_user_id, delegate_user_id, scope_json,
                      relationship.strip(), timestamp, timestamp, expires_at))
                delegation_id = cursor.lastrowid
                conn.commit()

                # Log activity
                self.activity_logger(
                    current_user['username'],
                    'Delegation created',
                    (
                        f'Delegation ID: {delegation_id}, '
                        f'Delegate: {delegate_info["username"]}, '
                        f'Scopes: {", ".join(scope_keys)}, '
                        f'Relationship: {relationship.strip()}'
                    ),
                    current_user['id']
                )

                logger.info(
                    f"Delegation created: id={delegation_id}, "
                    f"grantor={current_user['username']}, "
                    f"delegate={delegate_info['username']}, "
                    f"scopes={scope_keys}"
                )

                return {
                    'success': True,
                    'delegation_id': delegation_id,
                    'message': (
                        f'Delegation to {delegate_info["username"]} created successfully '
                        f'with scopes: {", ".join(scope_keys)}.'
                    )
                }

        except sqlite3.Error as e:
            logger.error(f"Database error creating delegation: {e}")
            return {'success': False, 'message': 'Database error while creating delegation.'}
        except Exception as e:
            logger.error(f"Unexpected error creating delegation: {e}")
            return {'success': False, 'message': 'An unexpected error occurred.'}

    def revoke_delegation(self, delegation_id: int) -> Dict[str, Any]:
        """
        Revoke an active delegation.

        Only the grantor or an admin can revoke a delegation.

        Parameters:
            delegation_id: ID of the delegation to revoke

        Returns:
            dict: Result dictionary containing:
                  - success: bool - Whether revocation succeeded
                  - message: str - Result message
        """
        current_user = self.get_current_user()
        if not current_user:
            return {'success': False, 'message': 'You must be logged in to revoke a delegation.'}

        try:
            with self.db_manager.get_connection() as conn:
                self._ensure_tables(conn)
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT id, grantor_user_id, delegate_user_id, status
                    FROM delegated_access
                    WHERE id = ?
                ''', (delegation_id,))
                delegation = cursor.fetchone()

                if not delegation:
                    return {
                        'success': False,
                        'message': f'Delegation {delegation_id} not found.'
                    }

                _, grantor_id, delegate_id, status = delegation

                if status != 'active':
                    return {
                        'success': False,
                        'message': f'Delegation {delegation_id} is not active (status: {status}).'
                    }

                # Permission check: grantor or admin
                is_grantor = current_user['id'] == grantor_id
                is_admin = current_user.get('role', '').lower() == 'admin'
                has_perm = 'manage_users' in current_user.get('permissions', [])

                if not is_grantor and not is_admin and not has_perm:
                    return {
                        'success': False,
                        'message': 'You do not have permission to revoke this delegation.'
                    }

                # Revoke
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                    UPDATE delegated_access
                    SET status = 'revoked', revoked_at = ?, updated_at = ?
                    WHERE id = ?
                ''', (timestamp, timestamp, delegation_id))
                conn.commit()

                # Get delegate info for logging
                delegate_info = self._get_user_info(conn, delegate_id)
                delegate_name = delegate_info['username'] if delegate_info else str(delegate_id)

                self.activity_logger(
                    current_user['username'],
                    'Delegation revoked',
                    f'Delegation ID: {delegation_id}, Delegate: {delegate_name}',
                    current_user['id']
                )

                logger.info(
                    f"Delegation revoked: id={delegation_id}, "
                    f"by={current_user['username']}"
                )

                return {
                    'success': True,
                    'message': f'Delegation {delegation_id} revoked successfully.'
                }

        except sqlite3.Error as e:
            logger.error(f"Database error revoking delegation: {e}")
            return {'success': False, 'message': 'Database error while revoking delegation.'}
        except Exception as e:
            logger.error(f"Unexpected error revoking delegation: {e}")
            return {'success': False, 'message': 'An unexpected error occurred.'}

    def get_delegations_for_user(self, user_id: Optional[int] = None,
                                 as_grantor: bool = True) -> List[Dict[str, Any]]:
        """
        Get delegations for a user.

        Parameters:
            user_id: User ID to query (defaults to current user)
            as_grantor: If True, returns delegations granted by the user.
                        If False, returns delegations received by the user.

        Returns:
            list: List of delegation dictionaries, each containing:
                  - id, grantor_user_id, delegate_user_id, scope_keys,
                    relationship, status, created_at, updated_at, expires_at,
                    revoked_at, grantor_username, delegate_username
        """
        current_user = self.get_current_user()
        if user_id is None:
            if not current_user:
                logger.warning("Cannot list delegations: no user logged in.")
                return []
            user_id = current_user['id']

        try:
            with self.db_manager.get_connection() as conn:
                self._ensure_tables(conn)
                cursor = conn.cursor()

                if as_grantor:
                    cursor.execute('''
                        SELECT da.id, da.grantor_user_id, da.delegate_user_id,
                               da.scope_json, da.relationship, da.status,
                               da.created_at, da.updated_at, da.expires_at, da.revoked_at,
                               g_ua.username AS grantor_username,
                               d_ua.username AS delegate_username
                        FROM delegated_access da
                        JOIN user_accounts g_ua ON da.grantor_user_id = g_ua.user_id
                        JOIN user_accounts d_ua ON da.delegate_user_id = d_ua.user_id
                        WHERE da.grantor_user_id = ?
                        ORDER BY da.created_at DESC
                    ''', (user_id,))
                else:
                    cursor.execute('''
                        SELECT da.id, da.grantor_user_id, da.delegate_user_id,
                               da.scope_json, da.relationship, da.status,
                               da.created_at, da.updated_at, da.expires_at, da.revoked_at,
                               g_ua.username AS grantor_username,
                               d_ua.username AS delegate_username
                        FROM delegated_access da
                        JOIN user_accounts g_ua ON da.grantor_user_id = g_ua.user_id
                        JOIN user_accounts d_ua ON da.delegate_user_id = d_ua.user_id
                        WHERE da.delegate_user_id = ?
                        ORDER BY da.created_at DESC
                    ''', (user_id,))

                delegations = []
                for row in cursor.fetchall():
                    try:
                        scope_keys = json.loads(row[3])
                    except (json.JSONDecodeError, TypeError):
                        scope_keys = []

                    delegations.append({
                        'id': row[0],
                        'grantor_user_id': row[1],
                        'delegate_user_id': row[2],
                        'scope_keys': scope_keys,
                        'relationship': row[4],
                        'status': row[5],
                        'created_at': row[6],
                        'updated_at': row[7],
                        'expires_at': row[8],
                        'revoked_at': row[9],
                        'grantor_username': row[10],
                        'delegate_username': row[11],
                    })

                return delegations

        except sqlite3.Error as e:
            logger.error(f"Database error listing delegations: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing delegations: {e}")
            return []

    def check_delegated_permission(self, delegate_user_id: int, target_user_id: int,
                                   permission: str) -> bool:
        """
        Check if a delegate has a specific delegated permission for a target user.

        Only considers active, non-expired delegations.

        Parameters:
            delegate_user_id: User ID of the delegate
            target_user_id: User ID of the grantor (target)
            permission: Permission string to check

        Returns:
            bool: True if the delegate has the permission via delegation
        """
        try:
            with self.db_manager.get_connection() as conn:
                self._ensure_tables(conn)
                cursor = conn.cursor()

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                    SELECT scope_json FROM delegated_access
                    WHERE grantor_user_id = ?
                      AND delegate_user_id = ?
                      AND status = 'active'
                      AND (expires_at IS NULL OR expires_at > ?)
                ''', (target_user_id, delegate_user_id, now))

                for row in cursor.fetchall():
                    try:
                        scope_keys = json.loads(row[0])
                    except (json.JSONDecodeError, TypeError):
                        continue

                    permissions = get_scope_permissions(scope_keys)
                    if permission in permissions:
                        return True

                return False

        except sqlite3.Error as e:
            logger.error(f"Database error checking delegated permission: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error checking delegated permission: {e}")
            return False

    def get_delegated_permissions(self, delegate_user_id: int,
                                  target_user_id: int) -> List[str]:
        """
        Get all delegated permissions a delegate has for a target user.

        Aggregates permissions across all active, non-expired delegations
        between the two users.

        Parameters:
            delegate_user_id: User ID of the delegate
            target_user_id: User ID of the grantor (target)

        Returns:
            list: List of unique permission strings
        """
        try:
            with self.db_manager.get_connection() as conn:
                self._ensure_tables(conn)
                cursor = conn.cursor()

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                    SELECT scope_json FROM delegated_access
                    WHERE grantor_user_id = ?
                      AND delegate_user_id = ?
                      AND status = 'active'
                      AND (expires_at IS NULL OR expires_at > ?)
                ''', (target_user_id, delegate_user_id, now))

                all_permissions = set()
                for row in cursor.fetchall():
                    try:
                        scope_keys = json.loads(row[0])
                    except (json.JSONDecodeError, TypeError):
                        continue

                    permissions = get_scope_permissions(scope_keys)
                    all_permissions.update(permissions)

                return list(all_permissions)

        except sqlite3.Error as e:
            logger.error(f"Database error getting delegated permissions: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting delegated permissions: {e}")
            return []

    def update_delegation_scope(self, delegation_id: int,
                                scope_keys: List[str]) -> Dict[str, Any]:
        """
        Update the scope of an existing delegation.

        Only the grantor or an admin can update the scope.

        Parameters:
            delegation_id: ID of the delegation to update
            scope_keys: New list of scope keys

        Returns:
            dict: Result dictionary containing:
                  - success: bool - Whether update succeeded
                  - message: str - Result message
        """
        current_user = self.get_current_user()
        if not current_user:
            return {'success': False, 'message': 'You must be logged in to update a delegation.'}

        # Validate scope keys
        validation_error = self._validate_scope_keys(scope_keys)
        if validation_error:
            return {'success': False, 'message': validation_error}

        try:
            with self.db_manager.get_connection() as conn:
                self._ensure_tables(conn)
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT id, grantor_user_id, delegate_user_id, scope_json, status
                    FROM delegated_access
                    WHERE id = ?
                ''', (delegation_id,))
                delegation = cursor.fetchone()

                if not delegation:
                    return {
                        'success': False,
                        'message': f'Delegation {delegation_id} not found.'
                    }

                _, grantor_id, delegate_id, old_scope_json, status = delegation

                if status != 'active':
                    return {
                        'success': False,
                        'message': f'Delegation {delegation_id} is not active (status: {status}).'
                    }

                # Permission check: grantor or admin
                is_grantor = current_user['id'] == grantor_id
                is_admin = current_user.get('role', '').lower() == 'admin'
                has_perm = 'manage_users' in current_user.get('permissions', [])

                if not is_grantor and not is_admin and not has_perm:
                    return {
                        'success': False,
                        'message': 'You do not have permission to update this delegation.'
                    }

                # Update scope
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                new_scope_json = json.dumps(scope_keys)

                cursor.execute('''
                    UPDATE delegated_access
                    SET scope_json = ?, updated_at = ?
                    WHERE id = ?
                ''', (new_scope_json, timestamp, delegation_id))
                conn.commit()

                # Parse old scopes for logging
                try:
                    old_scopes = json.loads(old_scope_json)
                except (json.JSONDecodeError, TypeError):
                    old_scopes = []

                delegate_info = self._get_user_info(conn, delegate_id)
                delegate_name = delegate_info['username'] if delegate_info else str(delegate_id)

                self.activity_logger(
                    current_user['username'],
                    'Delegation scope updated',
                    (
                        f'Delegation ID: {delegation_id}, '
                        f'Delegate: {delegate_name}, '
                        f'Old scopes: {", ".join(old_scopes)}, '
                        f'New scopes: {", ".join(scope_keys)}'
                    ),
                    current_user['id']
                )

                logger.info(
                    f"Delegation scope updated: id={delegation_id}, "
                    f"new_scopes={scope_keys}"
                )

                return {
                    'success': True,
                    'message': (
                        f'Delegation {delegation_id} scope updated to: '
                        f'{", ".join(scope_keys)}.'
                    )
                }

        except sqlite3.Error as e:
            logger.error(f"Database error updating delegation scope: {e}")
            return {'success': False, 'message': 'Database error while updating delegation scope.'}
        except Exception as e:
            logger.error(f"Unexpected error updating delegation scope: {e}")
            return {'success': False, 'message': 'An unexpected error occurred.'}

    def create_delegation_request(self, target_user_id: int, relationship: str,
                                  scope_keys: List[str]) -> Dict[str, Any]:
        """
        Create a request for delegated access.

        The current user requests access to the target user's data. The
        target user (or an admin) must approve the request before access
        is granted.

        Parameters:
            target_user_id: User ID of the account to request access to
            relationship: Description of the relationship
            scope_keys: List of scope keys being requested

        Returns:
            dict: Result dictionary containing:
                  - success: bool - Whether request creation succeeded
                  - request_id: int - ID of the request (if successful)
                  - message: str - Result message
        """
        current_user = self.get_current_user()
        if not current_user:
            return {'success': False, 'message': 'You must be logged in to create a request.'}

        requester_user_id = current_user['id']

        if requester_user_id == target_user_id:
            return {'success': False, 'message': 'Cannot request delegated access to yourself.'}

        if not relationship or not relationship.strip():
            return {'success': False, 'message': 'Relationship description is required.'}

        # Validate scope keys
        validation_error = self._validate_scope_keys(scope_keys)
        if validation_error:
            return {'success': False, 'message': validation_error}

        try:
            with self.db_manager.get_connection() as conn:
                self._ensure_tables(conn)
                cursor = conn.cursor()

                # Verify target user exists
                target_info = self._get_user_info(conn, target_user_id)
                if not target_info:
                    return {
                        'success': False,
                        'message': f'Target user with ID {target_user_id} not found.'
                    }

                # Check for existing pending request
                cursor.execute('''
                    SELECT id FROM delegated_access_requests
                    WHERE requester_user_id = ? AND target_user_id = ? AND status = 'pending'
                ''', (requester_user_id, target_user_id))
                existing = cursor.fetchone()
                if existing:
                    return {
                        'success': False,
                        'message': (
                            f'A pending request for access to {target_info["username"]} '
                            f'already exists (ID: {existing[0]}).'
                        )
                    }

                # Create the request
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                scope_json = json.dumps(scope_keys)

                cursor.execute('''
                    INSERT INTO delegated_access_requests
                        (requester_user_id, target_user_id, relationship, scope_json,
                         status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 'pending', ?, ?)
                ''', (requester_user_id, target_user_id, relationship.strip(),
                      scope_json, timestamp, timestamp))
                request_id = cursor.lastrowid
                conn.commit()

                self.activity_logger(
                    current_user['username'],
                    'Delegation request created',
                    (
                        f'Request ID: {request_id}, '
                        f'Target: {target_info["username"]}, '
                        f'Scopes: {", ".join(scope_keys)}'
                    ),
                    current_user['id']
                )

                logger.info(
                    f"Delegation request created: id={request_id}, "
                    f"requester={current_user['username']}, "
                    f"target={target_info['username']}"
                )

                return {
                    'success': True,
                    'request_id': request_id,
                    'message': (
                        f'Delegation request submitted to {target_info["username"]}. '
                        f'Awaiting approval.'
                    )
                }

        except sqlite3.Error as e:
            logger.error(f"Database error creating delegation request: {e}")
            return {'success': False, 'message': 'Database error while creating request.'}
        except Exception as e:
            logger.error(f"Unexpected error creating delegation request: {e}")
            return {'success': False, 'message': 'An unexpected error occurred.'}

    def approve_delegation_request(self, request_id: int) -> Dict[str, Any]:
        """
        Approve a delegation request and create the delegation.

        Only the target user (grantor) or an admin can approve the request.

        Parameters:
            request_id: ID of the request to approve

        Returns:
            dict: Result dictionary containing:
                  - success: bool - Whether approval succeeded
                  - delegation_id: int - ID of the created delegation (if successful)
                  - message: str - Result message
        """
        current_user = self.get_current_user()
        if not current_user:
            return {'success': False, 'message': 'You must be logged in to approve a request.'}

        try:
            with self.db_manager.get_connection() as conn:
                self._ensure_tables(conn)
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT id, requester_user_id, target_user_id, relationship,
                           scope_json, status
                    FROM delegated_access_requests
                    WHERE id = ?
                ''', (request_id,))
                request = cursor.fetchone()

                if not request:
                    return {
                        'success': False,
                        'message': f'Delegation request {request_id} not found.'
                    }

                _, requester_id, target_id, relationship, scope_json, status = request

                if status != 'pending':
                    return {
                        'success': False,
                        'message': (
                            f'Request {request_id} is not pending (status: {status}).'
                        )
                    }

                # Permission check: target user or admin
                is_target = current_user['id'] == target_id
                is_admin = current_user.get('role', '').lower() == 'admin'
                has_perm = 'manage_users' in current_user.get('permissions', [])

                if not is_target and not is_admin and not has_perm:
                    return {
                        'success': False,
                        'message': 'You do not have permission to approve this request.'
                    }

                # Parse scope
                try:
                    scope_keys = json.loads(scope_json)
                except (json.JSONDecodeError, TypeError):
                    scope_keys = []

                # Create the delegation
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                    INSERT INTO delegated_access
                        (grantor_user_id, delegate_user_id, scope_json, relationship,
                         status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 'active', ?, ?)
                ''', (target_id, requester_id, scope_json, relationship,
                      timestamp, timestamp))
                delegation_id = cursor.lastrowid

                # Update request status
                cursor.execute('''
                    UPDATE delegated_access_requests
                    SET status = 'approved', resolved_at = ?, resolved_by = ?, updated_at = ?
                    WHERE id = ?
                ''', (timestamp, current_user['id'], timestamp, request_id))
                conn.commit()

                requester_info = self._get_user_info(conn, requester_id)
                requester_name = requester_info['username'] if requester_info else str(requester_id)

                self.activity_logger(
                    current_user['username'],
                    'Delegation request approved',
                    (
                        f'Request ID: {request_id}, '
                        f'Delegation ID: {delegation_id}, '
                        f'Requester: {requester_name}'
                    ),
                    current_user['id']
                )

                logger.info(
                    f"Delegation request approved: request_id={request_id}, "
                    f"delegation_id={delegation_id}"
                )

                return {
                    'success': True,
                    'delegation_id': delegation_id,
                    'message': (
                        f'Request {request_id} approved. '
                        f'Delegation {delegation_id} created for {requester_name}.'
                    )
                }

        except sqlite3.Error as e:
            logger.error(f"Database error approving delegation request: {e}")
            return {'success': False, 'message': 'Database error while approving request.'}
        except Exception as e:
            logger.error(f"Unexpected error approving delegation request: {e}")
            return {'success': False, 'message': 'An unexpected error occurred.'}

    def reject_delegation_request(self, request_id: int,
                                  reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Reject a delegation request.

        Only the target user (grantor) or an admin can reject the request.

        Parameters:
            request_id: ID of the request to reject
            reason: Optional reason for rejection

        Returns:
            dict: Result dictionary containing:
                  - success: bool - Whether rejection succeeded
                  - message: str - Result message
        """
        current_user = self.get_current_user()
        if not current_user:
            return {'success': False, 'message': 'You must be logged in to reject a request.'}

        try:
            with self.db_manager.get_connection() as conn:
                self._ensure_tables(conn)
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT id, requester_user_id, target_user_id, status
                    FROM delegated_access_requests
                    WHERE id = ?
                ''', (request_id,))
                request = cursor.fetchone()

                if not request:
                    return {
                        'success': False,
                        'message': f'Delegation request {request_id} not found.'
                    }

                _, requester_id, target_id, status = request

                if status != 'pending':
                    return {
                        'success': False,
                        'message': (
                            f'Request {request_id} is not pending (status: {status}).'
                        )
                    }

                # Permission check: target user or admin
                is_target = current_user['id'] == target_id
                is_admin = current_user.get('role', '').lower() == 'admin'
                has_perm = 'manage_users' in current_user.get('permissions', [])

                if not is_target and not is_admin and not has_perm:
                    return {
                        'success': False,
                        'message': 'You do not have permission to reject this request.'
                    }

                # Reject the request
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                    UPDATE delegated_access_requests
                    SET status = 'rejected', reason = ?, resolved_at = ?,
                        resolved_by = ?, updated_at = ?
                    WHERE id = ?
                ''', (reason, timestamp, current_user['id'], timestamp, request_id))
                conn.commit()

                requester_info = self._get_user_info(conn, requester_id)
                requester_name = requester_info['username'] if requester_info else str(requester_id)

                self.activity_logger(
                    current_user['username'],
                    'Delegation request rejected',
                    (
                        f'Request ID: {request_id}, '
                        f'Requester: {requester_name}'
                        + (f', Reason: {reason}' if reason else '')
                    ),
                    current_user['id']
                )

                logger.info(
                    f"Delegation request rejected: request_id={request_id}, "
                    f"reason={reason or 'none given'}"
                )

                return {
                    'success': True,
                    'message': f'Request {request_id} rejected.'
                }

        except sqlite3.Error as e:
            logger.error(f"Database error rejecting delegation request: {e}")
            return {'success': False, 'message': 'Database error while rejecting request.'}
        except Exception as e:
            logger.error(f"Unexpected error rejecting delegation request: {e}")
            return {'success': False, 'message': 'An unexpected error occurred.'}

    def get_delegation_requests(self, status: str = 'pending',
                                user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get delegation requests filtered by status.

        Returns requests where the user is either the requester or the target,
        depending on the user_id provided (defaults to current user).

        Parameters:
            status: Filter by request status ('pending', 'approved', 'rejected')
            user_id: User ID to query (defaults to current user)

        Returns:
            list: List of request dictionaries, each containing:
                  - id, requester_user_id, target_user_id, relationship,
                    scope_keys, status, reason, created_at, updated_at,
                    resolved_at, requester_username, target_username
        """
        current_user = self.get_current_user()
        if user_id is None:
            if not current_user:
                logger.warning("Cannot list delegation requests: no user logged in.")
                return []
            user_id = current_user['id']

        try:
            with self.db_manager.get_connection() as conn:
                self._ensure_tables(conn)
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT dar.id, dar.requester_user_id, dar.target_user_id,
                           dar.relationship, dar.scope_json, dar.status, dar.reason,
                           dar.created_at, dar.updated_at, dar.resolved_at,
                           r_ua.username AS requester_username,
                           t_ua.username AS target_username
                    FROM delegated_access_requests dar
                    JOIN user_accounts r_ua ON dar.requester_user_id = r_ua.user_id
                    JOIN user_accounts t_ua ON dar.target_user_id = t_ua.user_id
                    WHERE dar.status = ?
                      AND (dar.requester_user_id = ? OR dar.target_user_id = ?)
                    ORDER BY dar.created_at DESC
                ''', (status, user_id, user_id))

                requests = []
                for row in cursor.fetchall():
                    try:
                        scope_keys = json.loads(row[4])
                    except (json.JSONDecodeError, TypeError):
                        scope_keys = []

                    requests.append({
                        'id': row[0],
                        'requester_user_id': row[1],
                        'target_user_id': row[2],
                        'relationship': row[3],
                        'scope_keys': scope_keys,
                        'status': row[5],
                        'reason': row[6],
                        'created_at': row[7],
                        'updated_at': row[8],
                        'resolved_at': row[9],
                        'requester_username': row[10],
                        'target_username': row[11],
                    })

                return requests

        except sqlite3.Error as e:
            logger.error(f"Database error listing delegation requests: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing delegation requests: {e}")
            return []

    def expire_delegations(self) -> Dict[str, Any]:
        """
        Expire delegations that have passed their expires_at timestamp.

        Scans all active delegations and transitions those past their
        expiration time to 'expired' status.

        Returns:
            dict: Result dictionary containing:
                  - success: bool - Whether the operation succeeded
                  - expired_count: int - Number of delegations expired
                  - message: str - Result message
        """
        try:
            with self.db_manager.get_connection() as conn:
                self._ensure_tables(conn)
                cursor = conn.cursor()

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Find active delegations past their expiry
                cursor.execute('''
                    SELECT id FROM delegated_access
                    WHERE status = 'active'
                      AND expires_at IS NOT NULL
                      AND expires_at <= ?
                ''', (now,))
                expired_ids = [row[0] for row in cursor.fetchall()]

                if not expired_ids:
                    return {
                        'success': True,
                        'expired_count': 0,
                        'message': 'No delegations to expire.'
                    }

                # Expire them
                placeholders = ', '.join('?' for _ in expired_ids)
                cursor.execute(f'''
                    UPDATE delegated_access
                    SET status = 'expired', updated_at = ?
                    WHERE id IN ({placeholders})
                ''', [now] + expired_ids)
                conn.commit()

                expired_count = len(expired_ids)

                logger.info(f"Expired {expired_count} delegation(s): IDs={expired_ids}")

                return {
                    'success': True,
                    'expired_count': expired_count,
                    'message': f'Expired {expired_count} delegation(s).'
                }

        except sqlite3.Error as e:
            logger.error(f"Database error expiring delegations: {e}")
            return {
                'success': False,
                'expired_count': 0,
                'message': 'Database error while expiring delegations.'
            }
        except Exception as e:
            logger.error(f"Unexpected error expiring delegations: {e}")
            return {
                'success': False,
                'expired_count': 0,
                'message': 'An unexpected error occurred.'
            }

    def log_delegated_action(self, delegation_id: int, delegate_user_id: int,
                             target_user_id: int, action: str,
                             resource_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Log a delegated action to the audit table.

        Records an action performed by a delegate on behalf of a grantor
        for compliance and auditing purposes.

        Parameters:
            delegation_id: ID of the delegation authorizing the action
            delegate_user_id: User ID of the delegate performing the action
            target_user_id: User ID of the grantor whose data was accessed
            action: Description of the action performed
            resource_type: Optional type of resource accessed

        Returns:
            dict: Result dictionary containing:
                  - success: bool - Whether logging succeeded
                  - audit_id: int - ID of the audit record (if successful)
                  - message: str - Result message
        """
        if not action or not action.strip():
            return {'success': False, 'message': 'Action description is required.'}

        try:
            with self.db_manager.get_connection() as conn:
                self._ensure_tables(conn)
                cursor = conn.cursor()

                # Verify delegation exists
                cursor.execute('''
                    SELECT id, status FROM delegated_access WHERE id = ?
                ''', (delegation_id,))
                delegation = cursor.fetchone()

                if not delegation:
                    return {
                        'success': False,
                        'message': f'Delegation {delegation_id} not found.'
                    }

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                    INSERT INTO delegated_access_audit
                        (delegation_id, delegate_user_id, target_user_id,
                         action, resource_type, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (delegation_id, delegate_user_id, target_user_id,
                      action.strip(), resource_type, timestamp))
                audit_id = cursor.lastrowid
                conn.commit()

                # Also log via activity logger for cross-system audit
                delegate_info = self._get_user_info(conn, delegate_user_id)
                delegate_name = delegate_info['username'] if delegate_info else str(delegate_user_id)

                self.activity_logger(
                    delegate_name,
                    f'Delegated action: {action.strip()}',
                    (
                        f'Delegation ID: {delegation_id}, '
                        f'Target user ID: {target_user_id}'
                        + (f', Resource: {resource_type}' if resource_type else '')
                    ),
                    delegate_user_id
                )

                logger.info(
                    f"Delegated action logged: audit_id={audit_id}, "
                    f"delegation_id={delegation_id}, "
                    f"action={action.strip()}"
                )

                return {
                    'success': True,
                    'audit_id': audit_id,
                    'message': 'Delegated action logged successfully.'
                }

        except sqlite3.Error as e:
            logger.error(f"Database error logging delegated action: {e}")
            return {'success': False, 'message': 'Database error while logging action.'}
        except Exception as e:
            logger.error(f"Unexpected error logging delegated action: {e}")
            return {'success': False, 'message': 'An unexpected error occurred.'}
