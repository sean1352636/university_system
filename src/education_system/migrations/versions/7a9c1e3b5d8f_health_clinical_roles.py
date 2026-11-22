"""university: clinical roles for the Health Portal; generic staff lose health access

Health records are UK GDPR special-category data, seen on a need-to-know
basis (``domains/health/application/health/access``). Until now the only
way to give someone clinical access was the generic ``staff`` role, which
also granted ``view_any_health_record``, ``manage_vaccinations``,
``manage_health_appointments``, ``view_health_reports`` and
``health_email_manager`` to every member of staff.

This migration:

1. adds the clinical roles ``nurse``, ``doctor``, ``clinician``,
   ``first_aider``, ``dentist`` and ``health_admin`` to ``roles``, each with
   the health permissions its work needs (``ROLE_GRANTS`` below);
2. revokes those five health permissions from ``staff`` (and from any other
   non-clinical role holding them except ``admin``). Staff outside the
   health team reach a record only through break-glass access, which is
   logged and reported to the health administrators.

``view_accommodations`` stays with staff (teaching staff need to know an
accommodation exists); approving and managing accommodations stays with
admin and moves to ``health_admin``. Idempotent: rows are inserted only when
missing and the revocations are plain deletes.

Revision ID: 7a9c1e3b5d8f
Revises: 6f8b0d2e4a7c
Create Date: 2026-10-18 12:00:00.000000
"""
import logging
from datetime import datetime
from typing import Sequence, Union

from alembic import op


revision: str = '7a9c1e3b5d8f'
down_revision: Union[str, Sequence[str], None] = '6f8b0d2e4a7c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger(__name__)

ROLE_DESCRIPTIONS = {
    'nurse': 'Nurse in the university health service: clinical access to student health records',
    'doctor': 'Doctor in the university health service: clinical access to student health records',
    'clinician': 'Other clinician in the university health service: clinical access to student '
                 'health records',
    'first_aider': 'Trained first aider: emergency health information and first-aid records',
    'dentist': 'Dentist in the university dental clinic: clinical access to student health '
               'records',
    'health_admin': 'Health service administrator: health records, reports, accommodation '
                    'approval and break-glass review',
}

_COMMON = ['view_health_advisories', 'view_health_resources']
_CLINICAL = _COMMON + [
    'view_any_health_record', 'manage_health_records', 'manage_vaccinations',
    'manage_health_appointments', 'schedule_health_appointment', 'view_health_reports',
    'issue_health_advisories', 'health_email_manager', 'view_accommodations',
]
ROLE_GRANTS = {
    'nurse': _CLINICAL,
    'doctor': _CLINICAL,
    'clinician': _CLINICAL,
    'dentist': _COMMON + ['view_any_health_record', 'manage_health_records',
                          'manage_health_appointments', 'schedule_health_appointment'],
    'first_aider': _COMMON + ['view_any_health_record'],
    'health_admin': _CLINICAL + ['approve_accommodations', 'manage_accommodations',
                                 'health_data_management', 'health_security_audit'],
}

#: Health permissions only the health team (and admin) may hold.
REVOKED = ('view_any_health_record', 'manage_vaccinations', 'manage_health_appointments',
           'view_health_reports', 'health_email_manager')
#: Roles that keep them.
KEEP = ('admin',) + tuple(ROLE_GRANTS)

PERMISSION_DESCRIPTIONS = {
    'view_any_health_record': 'View any student health record',
    'manage_health_records': 'Create and update student health records',
    'manage_vaccinations': 'Record and verify vaccinations',
    'manage_health_appointments': 'Manage health appointments for any student',
    'schedule_health_appointment': 'Schedule a health appointment',
    'view_health_reports': 'View population health reports',
    'issue_health_advisories': 'Issue health advisories',
    'health_email_manager': 'Send health e-mails',
    'view_accommodations': 'View medical accommodations',
    'approve_accommodations': 'Approve or reject medical accommodations',
    'manage_accommodations': 'Manage medical accommodations',
    'health_data_management': 'Health data retention and management',
    'health_security_audit': 'Health security audit',
    'view_health_advisories': 'View health advisories',
    'view_health_resources': 'View health resources',
}


def _tables(execute) -> set:
    return {r[0] for r in execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def _id(execute, table, column, value):
    row = execute(f'SELECT id FROM "{table}" WHERE "{column}" = ?',  # nosec B608
                  (value,)).fetchone()
    return row[0] if row else None


def upgrade() -> None:
    execute = op.get_bind().exec_driver_sql
    if not {'roles', 'permissions', 'role_permissions'} <= _tables(execute):
        return          # fresh install: the auth seeding creates these with the new roles
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 1. The clinical roles and their grants.
    for role, description in ROLE_DESCRIPTIONS.items():
        if _id(execute, 'roles', 'role_name', role) is None:
            execute("INSERT INTO roles (role_name, description, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?)", (role, description, now, now))
    for role, grants in ROLE_GRANTS.items():
        role_id = _id(execute, 'roles', 'role_name', role)
        for permission in grants:
            permission_id = _id(execute, 'permissions', 'permission_name', permission)
            if permission_id is None:
                execute("INSERT INTO permissions (permission_name, description, created_at) "
                        "VALUES (?, ?, ?)",
                        (permission, PERMISSION_DESCRIPTIONS.get(permission, permission), now))
                permission_id = _id(execute, 'permissions', 'permission_name', permission)
            execute("INSERT OR IGNORE INTO role_permissions (role_id, permission_id) "
                    "VALUES (?, ?)", (role_id, permission_id))

    # 2. Generic staff (and any other non-clinical role) lose clinical access.
    marks_p = ','.join('?' * len(REVOKED))
    marks_k = ','.join('?' * len(KEEP))
    removed = execute(
        f"DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions "  # nosec B608
        f"WHERE permission_name IN ({marks_p})) AND role_id NOT IN (SELECT id FROM roles "
        f"WHERE role_name IN ({marks_k}))", REVOKED + KEEP).rowcount
    logger.info("Revoked %s clinical health grants from non-clinical roles", removed)


def downgrade() -> None:
    execute = op.get_bind().exec_driver_sql
    if not {'roles', 'permissions', 'role_permissions'} <= _tables(execute):
        return
    # Give staff back exactly what it had before this revision.
    staff_id = _id(execute, 'roles', 'role_name', 'staff')
    if staff_id is not None:
        for permission in REVOKED:
            permission_id = _id(execute, 'permissions', 'permission_name', permission)
            if permission_id is not None:
                execute("INSERT OR IGNORE INTO role_permissions (role_id, permission_id) "
                        "VALUES (?, ?)", (staff_id, permission_id))
    # Drop the clinical roles' grants; a role row stays while anyone holds it.
    for role in ROLE_DESCRIPTIONS:
        role_id = _id(execute, 'roles', 'role_name', role)
        if role_id is None:
            continue
        execute("DELETE FROM role_permissions WHERE role_id = ?", (role_id,))
        in_use = 'users' in _tables(execute) and execute(
            "SELECT 1 FROM users WHERE LOWER(role) = ? LIMIT 1", (role,)).fetchone()
        if not in_use:
            execute("DELETE FROM roles WHERE id = ?", (role_id,))
