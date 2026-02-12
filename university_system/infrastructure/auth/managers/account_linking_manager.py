"""
Account Linking Management Module

Handles account linking operations including link requests, approvals, rejections,
role switching between linked accounts, and account unlinking.

Classes:
    AccountLinkingManager: Manages account linking and role switching operations
"""

from typing import Optional, List, Dict
import logging
from datetime import datetime

from university_system.infrastructure.database.db import sqlite3

logger = logging.getLogger(__name__)

__all__ = ['AccountLinkingManager']


class AccountLinkingManager:
    """
    Manager for account linking and role switching operations.

    Handles the full lifecycle of account linking: creating link requests,
    approving or rejecting them, managing linked account records, switching
    active roles between linked accounts, and unlinking accounts.

    Attributes:
        db_manager: Database manager instance for data operations
        activity_logger: Activity logger for audit trails
        get_current_user: Function to get the current logged-in user dict
        permission_manager: PermissionManager instance for permission checks
    """

    def __init__(self, db_manager, activity_logger, current_user_getter, permission_manager):
        """
        Initialize the AccountLinkingManager.

        Parameters:
            db_manager: Database manager instance
            activity_logger: Activity logger callable (username, action, details, user_id)
            current_user_getter: Function that returns the current user dict
            permission_manager: PermissionManager instance for permission checks
        """
        self.db_manager = db_manager
        self.activity_logger = activity_logger
        self.get_current_user = current_user_getter
        self.permission_manager = permission_manager

    def create_link_request(self, target_user_id: int, reason: Optional[str] = None) -> Dict:
        """Create a pending request to link current user's account with a target user."""
        current_user = self.get_current_user()
        if not current_user:
            logger.warning("Account link request attempted without authentication")
            return {'success': False, 'error': 'You must be logged in to create a link request.'}

        requesting_user_id = current_user.get('id')
        username = current_user.get('username', 'Unknown')

        if requesting_user_id == target_user_id:
            return {'success': False, 'error': 'Cannot link an account to itself.'}

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Verify target user exists
                cursor.execute('SELECT id, username FROM users WHERE id = ?', (target_user_id,))
                target_user = cursor.fetchone()
                if not target_user:
                    return {'success': False, 'error': 'Target user not found.'}

                target_username = target_user[1]

                # Check for existing pending request
                cursor.execute(
                    '''SELECT id FROM account_link_requests
                       WHERE requesting_user_id = ? AND target_user_id = ?
                       AND status = 'pending' ''',
                    (requesting_user_id, target_user_id)
                )
                if cursor.fetchone():
                    return {'success': False, 'error': 'A pending link request already exists for this user pair.'}

                # Check for existing active link
                cursor.execute(
                    '''SELECT id FROM linked_accounts
                       WHERE ((primary_user_id = ? AND secondary_user_id = ?)
                              OR (primary_user_id = ? AND secondary_user_id = ?))
                       AND is_active = 1''',
                    (requesting_user_id, target_user_id, target_user_id, requesting_user_id)
                )
                if cursor.fetchone():
                    return {'success': False, 'error': 'These accounts are already linked.'}

                # Create the link request
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    '''INSERT INTO account_link_requests
                       (requesting_user_id, target_user_id, status, reason, created_at)
                       VALUES (?, ?, 'pending', ?, ?)''',
                    (requesting_user_id, target_user_id, reason, timestamp)
                )
                request_id = cursor.lastrowid
                conn.commit()

                self.activity_logger(
                    username, 'Account link request created',
                    f'Request #{request_id}: linking with user #{target_user_id} ({target_username})',
                    requesting_user_id
                )
                logger.info(f"Link request #{request_id} created by {username} for user #{target_user_id}")

                return {
                    'success': True,
                    'request_id': request_id,
                    'message': f'Link request #{request_id} created. Awaiting administrator approval.'
                }

        except sqlite3.Error as e:
            logger.error(f"Database error creating link request: {e}")
            return {'success': False, 'error': f'Database error: {str(e)}'}

    def approve_link_request(self, request_id: int) -> Dict:
        """Approve a pending link request and create the linked_accounts record."""
        current_user = self.get_current_user()
        if not current_user:
            return {'success': False, 'error': 'You must be logged in to approve link requests.'}

        if not self.permission_manager.has_permission('manage_account_links'):
            logger.warning(
                f"User {current_user.get('username')} attempted to approve link request "
                f"without manage_account_links permission"
            )
            return {'success': False, 'error': 'You do not have permission to approve link requests.'}

        approver_id = current_user.get('id')
        approver_username = current_user.get('username', 'Unknown')

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    '''SELECT id, requesting_user_id, target_user_id, status
                       FROM account_link_requests WHERE id = ?''',
                    (request_id,)
                )
                request = cursor.fetchone()
                if not request:
                    return {'success': False, 'error': 'Link request not found.'}

                req_id, requesting_user_id, target_user_id, status = request
                if status != 'pending':
                    return {'success': False, 'error': f'Link request is already {status}.'}

                # Verify both users still exist
                cursor.execute('SELECT id FROM users WHERE id = ?', (requesting_user_id,))
                if not cursor.fetchone():
                    return {'success': False, 'error': 'Requesting user no longer exists.'}
                cursor.execute('SELECT id FROM users WHERE id = ?', (target_user_id,))
                if not cursor.fetchone():
                    return {'success': False, 'error': 'Target user no longer exists.'}

                # Check for existing active link
                cursor.execute(
                    '''SELECT id FROM linked_accounts
                       WHERE ((primary_user_id = ? AND secondary_user_id = ?)
                              OR (primary_user_id = ? AND secondary_user_id = ?))
                       AND is_active = 1''',
                    (requesting_user_id, target_user_id, target_user_id, requesting_user_id)
                )
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                if cursor.fetchone():
                    cursor.execute(
                        '''UPDATE account_link_requests
                           SET status = 'approved', resolved_at = ?, resolved_by = ?
                           WHERE id = ?''',
                        (timestamp, approver_id, request_id)
                    )
                    conn.commit()
                    return {'success': False, 'error': 'These accounts are already linked. Request marked as approved.'}

                # Create linked accounts record
                cursor.execute(
                    '''INSERT INTO linked_accounts
                       (primary_user_id, secondary_user_id, linked_at, linked_by, is_active)
                       VALUES (?, ?, ?, ?, 1)''',
                    (requesting_user_id, target_user_id, timestamp, approver_id)
                )
                link_id = cursor.lastrowid

                # Update request status
                cursor.execute(
                    '''UPDATE account_link_requests
                       SET status = 'approved', resolved_at = ?, resolved_by = ?
                       WHERE id = ?''',
                    (timestamp, approver_id, request_id)
                )
                conn.commit()

                self.activity_logger(
                    approver_username, 'Account link request approved',
                    f'Request #{request_id}: users #{requesting_user_id} and #{target_user_id} linked (link #{link_id})',
                    approver_id
                )
                logger.info(f"Link request #{request_id} approved by {approver_username}, link #{link_id} created")

                return {
                    'success': True,
                    'link_id': link_id,
                    'message': f'Link request #{request_id} approved. Accounts are now linked.'
                }

        except sqlite3.Error as e:
            logger.error(f"Database error approving link request #{request_id}: {e}")
            return {'success': False, 'error': f'Database error: {str(e)}'}

    def reject_link_request(self, request_id: int, reason: Optional[str] = None) -> Dict:
        """Reject a pending link request with an optional reason."""
        current_user = self.get_current_user()
        if not current_user:
            return {'success': False, 'error': 'You must be logged in to reject link requests.'}

        if not self.permission_manager.has_permission('manage_account_links'):
            logger.warning(
                f"User {current_user.get('username')} attempted to reject link request "
                f"without manage_account_links permission"
            )
            return {'success': False, 'error': 'You do not have permission to reject link requests.'}

        rejector_id = current_user.get('id')
        rejector_username = current_user.get('username', 'Unknown')

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    'SELECT id, status FROM account_link_requests WHERE id = ?',
                    (request_id,)
                )
                request = cursor.fetchone()
                if not request:
                    return {'success': False, 'error': 'Link request not found.'}

                req_id, status = request
                if status != 'pending':
                    return {'success': False, 'error': f'Link request is already {status}.'}

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    '''UPDATE account_link_requests
                       SET status = 'rejected', resolved_at = ?, resolved_by = ?,
                           reason = COALESCE(?, reason)
                       WHERE id = ?''',
                    (timestamp, rejector_id, reason, request_id)
                )
                conn.commit()

                rejection_detail = f'Request #{request_id} rejected'
                if reason:
                    rejection_detail += f': {reason}'

                self.activity_logger(
                    rejector_username, 'Account link request rejected',
                    rejection_detail, rejector_id
                )
                logger.info(f"Link request #{request_id} rejected by {rejector_username}")

                return {'success': True, 'message': f'Link request #{request_id} has been rejected.'}

        except sqlite3.Error as e:
            logger.error(f"Database error rejecting link request #{request_id}: {e}")
            return {'success': False, 'error': f'Database error: {str(e)}'}

    def get_linked_accounts(self, user_id: Optional[int] = None) -> List[Dict]:
        """Get all active linked accounts for a user (defaults to current user)."""
        current_user = self.get_current_user()
        if not current_user:
            logger.warning("Get linked accounts attempted without authentication")
            return []

        if user_id is None:
            user_id = current_user.get('id')

        # Non-admin users can only view their own linked accounts
        if user_id != current_user.get('id'):
            if not self.permission_manager.has_permission('manage_account_links'):
                logger.warning(
                    f"User {current_user.get('username')} attempted to view linked accounts "
                    f"for user #{user_id} without permission"
                )
                return []

        try:
            with self.db_manager.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute(
                    '''SELECT la.id, la.primary_user_id, la.secondary_user_id,
                              la.linked_at, la.linked_by, la.is_active,
                              u1.username AS primary_username, u1.role AS primary_role,
                              u2.username AS secondary_username, u2.role AS secondary_role
                       FROM linked_accounts la
                       JOIN users u1 ON la.primary_user_id = u1.id
                       JOIN users u2 ON la.secondary_user_id = u2.id
                       WHERE (la.primary_user_id = ? OR la.secondary_user_id = ?)
                       AND la.is_active = 1
                       ORDER BY la.linked_at DESC''',
                    (user_id, user_id)
                )

                links = []
                for row in cursor.fetchall():
                    link_dict = dict(row)
                    # Determine which is the "other" user
                    if link_dict['primary_user_id'] == user_id:
                        link_dict['linked_user_id'] = link_dict['secondary_user_id']
                        link_dict['linked_username'] = link_dict['secondary_username']
                        link_dict['linked_role'] = link_dict['secondary_role']
                    else:
                        link_dict['linked_user_id'] = link_dict['primary_user_id']
                        link_dict['linked_username'] = link_dict['primary_username']
                        link_dict['linked_role'] = link_dict['primary_role']
                    links.append(link_dict)

                return links

        except sqlite3.Error as e:
            logger.error(f"Database error getting linked accounts for user #{user_id}: {e}")
            return []

    def switch_active_role(self, linked_account_id: int) -> Dict:
        """Switch current user's active role to the linked account's role."""
        current_user = self.get_current_user()
        if not current_user:
            return {'success': False, 'error': 'You must be logged in to switch roles.'}

        user_id = current_user.get('id')
        username = current_user.get('username', 'Unknown')
        current_role = current_user.get('role', '')

        if current_user.get('active_linked_account_id'):
            return {'success': False, 'error': 'You already have an active role switch. Please revert first.'}

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    '''SELECT id, primary_user_id, secondary_user_id, is_active
                       FROM linked_accounts
                       WHERE id = ? AND is_active = 1''',
                    (linked_account_id,)
                )
                link = cursor.fetchone()
                if not link:
                    return {'success': False, 'error': 'Linked account not found or is inactive.'}

                link_id, primary_user_id, secondary_user_id, is_active = link

                # Determine the target user (the "other" user in the link)
                if primary_user_id == user_id:
                    target_user_id = secondary_user_id
                elif secondary_user_id == user_id:
                    target_user_id = primary_user_id
                else:
                    return {'success': False, 'error': 'You are not part of this linked account relationship.'}

                # Get target user's role
                cursor.execute('SELECT role FROM users WHERE id = ?', (target_user_id,))
                target_data = cursor.fetchone()
                if not target_data:
                    return {'success': False, 'error': 'Target linked user not found.'}

                target_role = target_data[0]

                # Get permissions for the target role
                cursor.execute(
                    '''SELECT p.permission_name
                       FROM permissions p
                       JOIN role_permissions rp ON p.id = rp.permission_id
                       JOIN roles r ON rp.role_id = r.id
                       WHERE r.role_name = ?''',
                    (target_role,)
                )
                target_permissions = [row[0] for row in cursor.fetchall()]

                # Record the role switch
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    '''INSERT INTO active_role_switches
                       (user_id, original_role, switched_to_role, linked_account_id, switched_at)
                       VALUES (?, ?, ?, ?, ?)''',
                    (user_id, current_role, target_role, linked_account_id, timestamp)
                )
                switch_id = cursor.lastrowid
                conn.commit()

                # Update the session with the new role
                current_user['original_role'] = current_role
                current_user['role'] = target_role
                current_user['permissions'] = target_permissions
                current_user['active_linked_account_id'] = linked_account_id
                current_user['_role_switch_id'] = switch_id

                self.activity_logger(
                    username, 'Role switched via account link',
                    f'From {current_role} to {target_role} (link #{linked_account_id})',
                    user_id
                )
                logger.info(f"User {username} switched from {current_role} to {target_role}")

                return {
                    'success': True,
                    'switch_id': switch_id,
                    'original_role': current_role,
                    'new_role': target_role,
                    'permissions': target_permissions,
                    'message': f'Successfully switched to {target_role} role.'
                }

        except sqlite3.Error as e:
            logger.error(f"Database error switching role for user #{user_id}: {e}")
            return {'success': False, 'error': f'Database error: {str(e)}'}

    def revert_role(self) -> Dict:
        """Revert to original role after a role switch."""
        current_user = self.get_current_user()
        if not current_user:
            return {'success': False, 'error': 'You must be logged in to revert roles.'}

        user_id = current_user.get('id')
        username = current_user.get('username', 'Unknown')
        original_role = current_user.get('original_role')
        switch_id = current_user.get('_role_switch_id')

        if not original_role:
            return {'success': False, 'error': 'No active role switch to revert.'}

        current_switched_role = current_user.get('role', '')

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get permissions for the original role
                cursor.execute(
                    '''SELECT p.permission_name
                       FROM permissions p
                       JOIN role_permissions rp ON p.id = rp.permission_id
                       JOIN roles r ON rp.role_id = r.id
                       WHERE r.role_name = ?''',
                    (original_role,)
                )
                original_permissions = [row[0] for row in cursor.fetchall()]

                # Update the role switch record
                if switch_id:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute(
                        '''UPDATE active_role_switches SET reverted_at = ?
                           WHERE id = ? AND user_id = ? AND reverted_at IS NULL''',
                        (timestamp, switch_id, user_id)
                    )
                    conn.commit()

                # Restore original role in session
                current_user['role'] = original_role
                current_user['permissions'] = original_permissions
                current_user.pop('original_role', None)
                current_user.pop('active_linked_account_id', None)
                current_user.pop('_role_switch_id', None)

                self.activity_logger(
                    username, 'Role reverted from account link switch',
                    f'Reverted from {current_switched_role} back to {original_role}',
                    user_id
                )
                logger.info(f"User {username} reverted from {current_switched_role} to {original_role}")

                return {
                    'success': True,
                    'reverted_from': current_switched_role,
                    'restored_role': original_role,
                    'permissions': original_permissions,
                    'message': f'Successfully reverted to {original_role} role.'
                }

        except sqlite3.Error as e:
            logger.error(f"Database error reverting role for user #{user_id}: {e}")
            return {'success': False, 'error': f'Database error: {str(e)}'}

    def unlink_account(self, link_id: int) -> Dict:
        """Deactivate a linked account relationship."""
        current_user = self.get_current_user()
        if not current_user:
            return {'success': False, 'error': 'You must be logged in to unlink accounts.'}

        user_id = current_user.get('id')
        username = current_user.get('username', 'Unknown')

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    '''SELECT id, primary_user_id, secondary_user_id, is_active
                       FROM linked_accounts WHERE id = ?''',
                    (link_id,)
                )
                link = cursor.fetchone()
                if not link:
                    return {'success': False, 'error': 'Linked account record not found.'}

                link_record_id, primary_user_id, secondary_user_id, is_active = link
                if not is_active:
                    return {'success': False, 'error': 'This account link is already inactive.'}

                # Verify user is a participant or has admin permission
                is_participant = user_id in (primary_user_id, secondary_user_id)
                has_admin_perm = self.permission_manager.has_permission('manage_account_links')
                if not is_participant and not has_admin_perm:
                    logger.warning(f"User {username} attempted to unlink #{link_id} without permission")
                    return {'success': False, 'error': 'You do not have permission to unlink these accounts.'}

                # Revert role switch if active on this link
                if current_user.get('active_linked_account_id') == link_id:
                    revert_result = self.revert_role()
                    if not revert_result.get('success'):
                        logger.warning(f"Failed to revert role before unlinking: {revert_result.get('error')}")

                # Deactivate the link
                cursor.execute('UPDATE linked_accounts SET is_active = 0 WHERE id = ?', (link_id,))
                conn.commit()

                # Get other user's name for logging
                other_user_id = secondary_user_id if primary_user_id == user_id else primary_user_id
                cursor.execute('SELECT username FROM users WHERE id = ?', (other_user_id,))
                other_row = cursor.fetchone()
                other_username = other_row[0] if other_row else f'user #{other_user_id}'

                self.activity_logger(
                    username, 'Account unlinked',
                    f'Link #{link_id}: unlinked from {other_username}', user_id
                )
                logger.info(f"Link #{link_id} deactivated by {username}")

                return {'success': True, 'message': f'Account link #{link_id} has been deactivated.'}

        except sqlite3.Error as e:
            logger.error(f"Database error unlinking account #{link_id}: {e}")
            return {'success': False, 'error': f'Database error: {str(e)}'}

    def get_link_requests(self, status: str = 'pending',
                          user_id: Optional[int] = None) -> List[Dict]:
        """Get link requests filtered by status. Admins see all; others see own only."""
        current_user = self.get_current_user()
        if not current_user:
            logger.warning("Get link requests attempted without authentication")
            return []

        current_user_id = current_user.get('id')
        has_admin_perm = self.permission_manager.has_permission('manage_account_links')

        valid_statuses = ('pending', 'approved', 'rejected')
        if status not in valid_statuses:
            logger.warning(f"Invalid link request status filter: {status}")
            return []

        try:
            with self.db_manager.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                base_query = '''SELECT alr.id, alr.requesting_user_id, alr.target_user_id,
                                       alr.status, alr.reason, alr.created_at,
                                       alr.resolved_at, alr.resolved_by,
                                       u1.username AS requesting_username, u1.role AS requesting_role,
                                       u2.username AS target_username, u2.role AS target_role
                                FROM account_link_requests alr
                                JOIN users u1 ON alr.requesting_user_id = u1.id
                                JOIN users u2 ON alr.target_user_id = u2.id'''

                if has_admin_perm and user_id is None:
                    cursor.execute(
                        base_query + ' WHERE alr.status = ? ORDER BY alr.created_at DESC',
                        (status,)
                    )
                else:
                    filter_user_id = user_id if user_id is not None else current_user_id
                    if not has_admin_perm and filter_user_id != current_user_id:
                        logger.warning(
                            f"User {current_user.get('username')} attempted to view link requests "
                            f"for user #{filter_user_id} without permission"
                        )
                        return []

                    cursor.execute(
                        base_query + ''' WHERE alr.status = ?
                            AND (alr.requesting_user_id = ? OR alr.target_user_id = ?)
                            ORDER BY alr.created_at DESC''',
                        (status, filter_user_id, filter_user_id)
                    )

                requests = [dict(row) for row in cursor.fetchall()]

                # Add resolver username if available
                for req in requests:
                    if req.get('resolved_by'):
                        cursor.execute(
                            'SELECT username FROM users WHERE id = ?',
                            (req['resolved_by'],)
                        )
                        resolver = cursor.fetchone()
                        req['resolved_by_username'] = resolver['username'] if resolver else None

                return requests

        except sqlite3.Error as e:
            logger.error(f"Database error getting link requests (status={status}): {e}")
            return []
