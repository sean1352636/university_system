"""TA Management permission setup."""

import logging
from datetime import datetime
from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction

logger = logging.getLogger(__name__)


def setup_ta_permissions(auth=None):
    """Setup permissions for TA management."""
    try:
        with transaction() as conn:
            cursor = conn.cursor()

            permissions = [
                ('manage_tas', 'Assign, remove, and manage teaching assistants'),
                ('view_ta_assignments', 'View TA assignments and workload'),
                ('assign_tas', 'Assign TAs to courses'),
            ]

            for perm_name, description in permissions:
                existing = cursor.execute(
                    'SELECT id FROM permissions WHERE permission_name = ?', (perm_name,)
                ).fetchone()
                if not existing:
                    cursor.execute(
                        'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                        (perm_name, description, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                    )

            role_perms = {
                'admin': ['manage_tas', 'view_ta_assignments', 'assign_tas'],
                'instructor': ['manage_tas', 'view_ta_assignments', 'assign_tas'],
                'staff': ['view_ta_assignments'],
                'student': ['view_ta_assignments'],
            }

            for role_name, perms in role_perms.items():
                role_row = cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role_name,)).fetchone()
                if not role_row:
                    continue
                role_id = role_row[0]
                for perm_name in perms:
                    perm_row = cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,)).fetchone()
                    if not perm_row:
                        continue
                    perm_id = perm_row[0]
                    existing = cursor.execute(
                        'SELECT 1 FROM role_permissions WHERE role_id = ? AND permission_id = ?',
                        (role_id, perm_id)
                    ).fetchone()
                    if not existing:
                        cursor.execute(
                            'INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                            (role_id, perm_id)
                        )

            logger.info("TA management permissions setup completed")
    except Exception as e:
        logger.warning(f"Error setting up TA permissions: {e}")
