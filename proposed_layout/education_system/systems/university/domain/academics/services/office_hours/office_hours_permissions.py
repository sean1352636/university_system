"""Office Hours permission setup."""

import logging
from datetime import datetime
from education_system.systems.university.infrastructure.database.db import get_connection, transaction

logger = logging.getLogger(__name__)


def setup_office_hours_permissions(auth=None):
    """Setup permissions for office hours management."""
    try:
        with transaction() as conn:
            cursor = conn.cursor()

            permissions = [
                ('manage_office_hours', 'Create, edit, and delete office hours'),
                ('book_office_hours', 'Book office hour appointments'),
                ('view_office_hours', 'View office hours schedules'),
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
                'admin': ['manage_office_hours', 'book_office_hours', 'view_office_hours'],
                'instructor': ['manage_office_hours', 'view_office_hours'],
                'student': ['book_office_hours', 'view_office_hours'],
                'staff': ['view_office_hours'],
            }

            for role_name, perms in role_perms.items():
                role_row = cursor.execute(
                    'SELECT id FROM roles WHERE role_name = ?', (role_name,)
                ).fetchone()
                if not role_row:
                    continue
                role_id = role_row[0]
                for perm_name in perms:
                    perm_row = cursor.execute(
                        'SELECT id FROM permissions WHERE permission_name = ?', (perm_name,)
                    ).fetchone()
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

            logger.info("Office hours permissions setup completed")
    except Exception as e:
        logger.warning(f"Error setting up office hours permissions: {e}")
