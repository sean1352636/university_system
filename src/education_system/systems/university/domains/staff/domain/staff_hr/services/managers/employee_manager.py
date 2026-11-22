"""
Employee Manager

Handles staff profile management, documents, qualifications,
emergency contacts, workload allocation, and directory search.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608
from education_system.systems.university.domains.staff.domain.staff_hr import access
from education_system.systems.university.domains.staff.domain.staff_hr.services.managers import (
    _people as people,
)

try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
except ImportError:
    def log_activity(*args, **kwargs):
        pass

logger = logging.getLogger(__name__)

#: What anyone may see of a colleague (the staff directory).
DIRECTORY_FIELDS = ('user_id', 'department', 'job_title', 'office_location', 'phone_extension',
                    'bio', 'expertise_areas', 'qualifications', 'manager_id')
#: Set by HR only (the person sees them but cannot change them).
HR_FIELDS = ('employee_id', 'job_title', 'department', 'employment_type', 'hire_date',
             'contract_end_date', 'manager_id')
#: The person keeps these up to date themselves (HR may too).
SELF_FIELDS = ('office_location', 'phone_extension', 'emergency_contact_name',
               'emergency_contact_phone', 'emergency_contact_relationship', 'bio',
               'expertise_areas', 'qualifications')
#: Roles listed in the staff directory even without a profile.
STAFF_ROLES = ('admin', 'administrator', 'staff', 'instructor', 'lecturer', 'faculty')


def _blank(value: Any) -> str:
    return '' if value is None else str(value).strip()


def _check_manager(conn, staff: str, manager: Any) -> Optional[str]:
    """``manager`` as a username fit to be ``staff``'s line manager (None
    clears it): a known person, not themselves, not someone who reports to
    them (that would make a loop)."""
    if manager is None or _blank(manager) == '':
        return None
    boss = access.staff_key(manager, conn)
    if not boss:
        raise ValueError(f"No staff member '{manager}'")
    if boss == staff:
        raise ValueError("Someone cannot be their own line manager")
    if staff in access.management_chain(boss, conn):
        raise ValueError(f"{boss} already reports to {staff}; that would make a loop")
    return boss


def _owner_of_document(conn, document_id: int) -> Optional[str]:
    row = conn.execute("SELECT owner_id FROM documents WHERE document_id = ? "
                       "AND source_type = 'staff'", (document_id,)).fetchone()
    return people.key(row[0], conn) if row else None


def _schedule_shape(conn) -> set:
    return {r[1] for r in conn.execute("PRAGMA table_info(staff_schedules)").fetchall()}


def _schedule_key(conn) -> str:
    """The expression naming a schedule entry's id."""
    return 'COALESCE(schedule_id, id)' if 'id' in _schedule_shape(conn) else 'schedule_id'


def _schedule_row(row) -> Dict[str, Any]:
    data = dict(row)
    if data.get('schedule_id') is None and data.get('id') is not None:
        data['schedule_id'] = data['id']
    return data


def _owner_of_schedule(conn, schedule_id: int) -> Optional[str]:
    row = conn.execute("SELECT user_id FROM staff_schedules WHERE " + _schedule_key(conn) +
                       " = ?", (schedule_id,)).fetchone()
    return people.key(row[0], conn) if row else None


def _person_name(row: Dict[str, Any]) -> str:
    """A directory row's name, or the username when no name is held."""
    name = ' '.join(p for p in (_blank(row.get('first_name')), _blank(row.get('last_name'))) if p)
    return name or _blank(row.get('username'))


def _departures(conn, on_or_after: str, through: str) -> set:
    """Usernames who left between the two dates: the last working day on an
    exit interview, or a staff profile's contract end date."""
    rows = conn.execute('''
        SELECT user_id FROM exit_interviews
        WHERE last_working_day BETWEEN ? AND ? AND COALESCE(status, '') <> 'cancelled'
        UNION
        SELECT user_id FROM staff_profiles WHERE contract_end_date BETWEEN ? AND ?
    ''', (on_or_after, through, on_or_after, through)).fetchall()
    return {str(r[0]) for r in rows}


def current_staff(conn) -> List[Dict[str, Any]]:
    """Staff profiles of the people employed today: already hired, and not
    past a contract end date or the last working day on an exit interview."""
    today = date.today().isoformat()
    left = _departures(conn, '0000-00-00', today)
    # Someone leaving today is still here today.
    left -= {str(r[0]) for r in conn.execute(
        "SELECT user_id FROM staff_profiles WHERE contract_end_date = ?", (today,)).fetchall()}
    left -= {str(r[0]) for r in conn.execute(
        "SELECT user_id FROM exit_interviews WHERE last_working_day = ?", (today,)).fetchall()}
    rows = conn.execute('''
        SELECT * FROM staff_profiles
        WHERE hire_date IS NULL OR hire_date = '' OR hire_date <= ?
    ''', (today,)).fetchall()
    return [dict(r) for r in rows if str(r['user_id']) not in left]


class EmployeeManager:
    """Manager for staff profiles and employee data."""

    # ==================== PROFILE OPERATIONS ====================

    @staticmethod
    def get_profile(user_id: str, actor: Any = None) -> Optional[Dict[str, Any]]:
        """Get staff profile by username (or users.id / employee number).

        With ``actor``: the person and HR see the whole record (HR reading
        someone else's is audited); anyone else sees the directory fields."""
        with get_connection() as conn:
            staff = people.key(user_id, conn)
            row = conn.execute('''
                SELECT * FROM staff_profiles WHERE user_id = ?
            ''', (staff,)).fetchone()
            if not row:
                return None
            profile = dict(row)
            if actor is None:
                return profile
            name = people.me(actor)
            if name == staff:
                return profile
            if access.is_hr(actor, conn):
                access.audit(conn, actor, 'view_personal_file', staff, 'staff_profiles',
                             profile.get('profile_id'))
                return profile
            return {k: profile.get(k) for k in DIRECTORY_FIELDS}

    @staticmethod
    def create_profile(user_id: str, **data) -> int:
        """Create a new staff profile."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO staff_profiles (
                    user_id, employee_id, department, job_title,
                    employment_type, hire_date, contract_end_date,
                    manager_id, office_location, phone_extension,
                    emergency_contact_name, emergency_contact_phone,
                    emergency_contact_relationship, bio,
                    expertise_areas, qualifications
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                data.get('employee_id'),
                data.get('department'),
                data.get('job_title'),
                data.get('employment_type', 'full-time'),
                data.get('hire_date'),
                data.get('contract_end_date'),
                data.get('manager_id'),
                data.get('office_location'),
                data.get('phone_extension'),
                data.get('emergency_contact_name'),
                data.get('emergency_contact_phone'),
                data.get('emergency_contact_relationship'),
                data.get('bio'),
                data.get('expertise_areas'),
                data.get('qualifications'),
            ))
            profile_id = cursor.lastrowid
            log_activity('create', 'staff_profile', user_id=user_id,
                        details={'profile_id': profile_id})
            return profile_id

    @staticmethod
    def update_profile(user_id: str, actor: Any = None, **data) -> bool:
        """Update staff profile fields.

        With ``actor``: the person may change :data:`SELF_FIELDS`, HR any
        field; ``manager_id`` is checked as in :meth:`set_line_manager`."""
        if not data:
            return False
        if actor is not None:
            with get_connection() as conn:
                user_id = people.key(user_id, conn)
                if access.is_hr(actor, conn):
                    people.me(actor)
                else:
                    people.require_self_or_hr(actor, user_id, conn, "change this profile")
                    locked = sorted(k for k in data if k not in SELF_FIELDS)
                    if locked:
                        raise PermissionError("Only HR can change " + ", ".join(locked))
                if 'manager_id' in data:
                    data['manager_id'] = _check_manager(conn, user_id, data['manager_id'])

        # Build dynamic update query
        fields = []
        values = []
        for key, value in data.items():
            if key not in ('user_id', 'profile_id', 'created_at'):
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return False

        fields.append('updated_at = ?')
        values.append(datetime.now().isoformat())
        values.append(user_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE staff_profiles SET ' + ', '.join(fields) + ' WHERE user_id = ?',
                values)
            if actor is not None:
                access.audit(conn, actor, 'update_profile', user_id, 'staff_profiles', user_id,
                             {'fields': sorted(data)})
            log_activity('update', 'staff_profile', user_id=user_id,
                        details={'updated_fields': list(data.keys())})
            return True

    @staticmethod
    def save_profile(actor: Any, username: Optional[str] = None, **fields) -> str:
        """Create or update a profile from a form (the profile screen).

        ``username`` defaults to the signed-in person. Fields that are not the
        person's to change (:data:`HR_FIELDS`) must come back unchanged unless
        ``actor`` is HR. Returns the username saved."""
        with transaction() as conn:
            name = people.me(actor)
            staff = people.key(username, conn) if username else name
            hr = access.is_hr(actor, conn)
            if not hr:
                people.require_self_or_hr(actor, staff, conn, "change this profile")
            row = conn.execute('SELECT * FROM staff_profiles WHERE user_id = ?',
                               (staff,)).fetchone()
            current = dict(row) if row else {}
            allowed = set(SELF_FIELDS) | (set(HR_FIELDS) if hr else set())
            changes = {}
            for column, value in fields.items():
                if column not in SELF_FIELDS and column not in HR_FIELDS:
                    raise ValueError(f"Unknown profile field '{column}'")
                if _blank(value) == _blank(current.get(column)):
                    continue
                if column not in allowed:
                    raise PermissionError(f"Only HR can change {column.replace('_', ' ')}")
                changes[column] = value if _blank(value) else None
            if 'manager_id' in changes:
                changes['manager_id'] = _check_manager(conn, staff, changes['manager_id'])
            if not changes and row:
                return staff
            now = datetime.now().isoformat()
            if row:
                sets = ', '.join(validate_identifier(c, "column") + ' = ?' for c in changes)
                conn.execute('UPDATE staff_profiles SET ' + sets + ', updated_at = ? '
                             'WHERE user_id = ?', list(changes.values()) + [now, staff])
            else:
                cols = ['user_id'] + [validate_identifier(c, "column") for c in changes]
                conn.execute('INSERT INTO staff_profiles (' + ', '.join(cols) + ') VALUES (' +
                             ', '.join('?' * len(cols)) + ')', [staff] + list(changes.values()))
            access.audit(conn, actor, 'update_profile' if row else 'create_profile', staff,
                         'staff_profiles', staff, {'fields': sorted(changes)})
        log_activity('update' if row else 'create', 'staff_profile', user_id=staff,
                     details={'updated_fields': sorted(changes)})
        return staff

    @staticmethod
    def set_line_manager(actor: Any, username: str, manager: Optional[str]) -> Optional[str]:
        """HR sets (or with ``manager`` empty, clears) ``username``'s line
        manager. The manager must be a known person, not themselves and not
        one of their own reports. Returns the manager's username."""
        with transaction() as conn:
            people.require_hr(actor, conn, "change a line manager")
            staff = access.staff_key(username, conn)
            if not staff:
                raise ValueError(f"No staff member '{username}'")
            boss = _check_manager(conn, staff, manager)
            before = access.manager_of(staff, conn)
            if conn.execute('SELECT 1 FROM staff_profiles WHERE user_id = ?',
                            (staff,)).fetchone():
                conn.execute('UPDATE staff_profiles SET manager_id = ?, updated_at = ? '
                             'WHERE user_id = ?', (boss, datetime.now().isoformat(), staff))
            else:
                conn.execute('INSERT INTO staff_profiles (user_id, manager_id) VALUES (?, ?)',
                             (staff, boss))
            access.audit(conn, actor, 'set_line_manager', staff, 'staff_profiles', staff,
                         {'from': before, 'to': boss})
        log_activity('update', 'line_manager', user_id=staff,
                     details={'from': before, 'to': boss})
        return boss

    @staticmethod
    def update_emergency_contact(user_id: str, name: str, phone: str,
                                  relationship: str, actor: Any = None) -> bool:
        """Update emergency contact information (with ``actor``: the person
        or HR)."""
        with transaction() as conn:
            if actor is not None:
                user_id = people.key(user_id, conn)
                people.require_self_or_hr(actor, user_id, conn, "change an emergency contact")
                access.audit(conn, actor, 'update_emergency_contact', user_id,
                             'staff_profiles', user_id)
            conn.execute('''
                UPDATE staff_profiles
                SET emergency_contact_name = ?,
                    emergency_contact_phone = ?,
                    emergency_contact_relationship = ?,
                    updated_at = ?
                WHERE user_id = ?
            ''', (name, phone, relationship, datetime.now().isoformat(), user_id))
            log_activity('update', 'emergency_contact', user_id=user_id)
            return True

    # ==================== DOCUMENT OPERATIONS ====================

    @staticmethod
    def get_documents(user_id: str, doc_type: Optional[str] = None,
                      actor: Any = None) -> List[Dict[str, Any]]:
        """Get all documents for a user, optionally filtered by type (with
        ``actor``: the person or HR; HR looking is audited)."""
        with get_connection() as conn:
            if actor is not None:
                user_id = people.key(user_id, conn)
                if people.require_self_or_hr(actor, user_id, conn,
                                             "see personal documents") != user_id:
                    access.audit(conn, actor, 'list_documents', user_id, 'documents')
            if doc_type:
                rows = conn.execute('''
                    SELECT * FROM documents
                    WHERE source_type = 'staff' AND owner_id = ? AND owner_type = 'staff'
                      AND document_type = ?
                    ORDER BY upload_date DESC
                ''', (user_id, doc_type)).fetchall()
            else:
                rows = conn.execute('''
                    SELECT * FROM documents
                    WHERE source_type = 'staff' AND owner_id = ? AND owner_type = 'staff'
                    ORDER BY upload_date DESC
                ''', (user_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_document(document_id: int, actor: Any = None) -> Optional[Dict[str, Any]]:
        """One staff document (with ``actor``: its owner or HR; audited)."""
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM documents WHERE document_id = ? "
                               "AND source_type = 'staff'", (document_id,)).fetchone()
            if not row:
                return None
            if actor is not None:
                owner = people.key(row['owner_id'], conn)
                people.require_self_or_hr(actor, owner, conn, "open personal documents")
                access.audit(conn, actor, 'open_document', owner, 'documents', document_id)
            return dict(row)

    @staticmethod
    def add_document(user_id: str, doc_type: str, doc_name: str,
                     file_path: Optional[str] = None, actor: Any = None, **data) -> int:
        """Add a new document to a staff profile (with ``actor``: the person
        or HR; audited)."""
        with transaction() as conn:
            if actor is not None:
                user_id = people.key(user_id, conn)
                data.setdefault('uploaded_by', people.require_self_or_hr(
                    actor, user_id, conn, "add personal documents"))
            cursor = conn.execute('''
                INSERT INTO documents (
                    source_type, owner_id, owner_type, document_type,
                    document_name, file_path, issue_date, expiry_date,
                    status, uploaded_by, notes
                ) VALUES ('staff', ?, 'staff', ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                doc_type,
                doc_name,
                file_path,
                data.get('issue_date'),
                data.get('expiry_date'),
                data.get('status', 'active'),
                data.get('uploaded_by'),
                data.get('notes'),
            ))
            doc_id = cursor.lastrowid
            if actor is not None:
                access.audit(conn, actor, 'add_document', user_id, 'documents', doc_id,
                             {'type': doc_type})
            log_activity('create', 'staff_document', user_id=user_id,
                        details={'document_id': doc_id, 'type': doc_type})
            return doc_id

    @staticmethod
    def update_document(document_id: int, actor: Any = None, **data) -> bool:
        """Update a document record (with ``actor``: its owner or HR)."""
        if not data:
            return False

        fields = []
        values = []
        for key, value in data.items():
            if key not in ('document_id', 'user_id', 'created_at'):
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return False

        values.append(document_id)

        with transaction() as conn:
            if actor is not None:
                owner = _owner_of_document(conn, document_id)
                if owner is None:
                    return False
                people.require_self_or_hr(actor, owner, conn, "change personal documents")
                access.audit(conn, actor, 'update_document', owner, 'documents', document_id,
                             {'fields': sorted(data)})
            conn.execute(
                'UPDATE documents SET ' + ', '.join(fields) +
                " WHERE document_id = ? AND source_type = 'staff'",
                values)
            log_activity('update', 'staff_document',
                        details={'document_id': document_id})
            return True

    @staticmethod
    def delete_document(document_id: int, actor: Any = None) -> bool:
        """Delete a document record (with ``actor``: its owner or HR;
        audited)."""
        with transaction() as conn:
            if actor is not None:
                owner = _owner_of_document(conn, document_id)
                if owner is None:
                    return False
                people.require_self_or_hr(actor, owner, conn, "delete personal documents")
                access.audit(conn, actor, 'delete_document', owner, 'documents', document_id)
            conn.execute(
                "DELETE FROM documents WHERE document_id = ? AND source_type = 'staff'",
                (document_id,))
            log_activity('delete', 'staff_document',
                        details={'document_id': document_id})
            return True

    @staticmethod
    def get_expiring_documents(days: int = 30) -> List[Dict[str, Any]]:
        """Get documents expiring within the specified number of days."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT d.*, p.department, p.job_title
                FROM documents d
                LEFT JOIN staff_profiles p ON d.owner_id = p.user_id
                WHERE d.source_type = 'staff' AND d.owner_type = 'staff'
                  AND d.expiry_date IS NOT NULL
                  AND d.expiry_date <= date('now', '+' || ? || ' days')
                  AND d.expiry_date >= date('now')
                  AND d.status = 'active'
                ORDER BY d.expiry_date
            ''', (days,)).fetchall()
            return [dict(row) for row in rows]

    # ==================== WORKLOAD OPERATIONS ====================

    @staticmethod
    def get_workload(user_id: str, academic_year: Optional[str] = None,
                     semester: Optional[str] = None, actor: Any = None) -> List[Dict[str, Any]]:
        """Get workload allocation for a user (with ``actor``: the person,
        their line managers or HR)."""
        with get_connection() as conn:
            if actor is not None:
                user_id = people.key(user_id, conn)
                people.require_view(actor, user_id, conn, "this workload")
            query = 'SELECT * FROM staff_workload WHERE user_id = ?'
            params = [user_id]

            if academic_year:
                query += ' AND academic_year = ?'
                params.append(academic_year)
            if semester:
                query += ' AND semester = ?'
                params.append(semester)

            query += ' ORDER BY academic_year DESC, semester DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def set_workload(user_id: str, academic_year: str, semester: Optional[str],
                     actor: Any = None, **hours) -> int:
        """Set or update workload allocation for a user (``semester`` None:
        the whole year; with ``actor``: the person, their line managers or
        HR)."""
        with transaction() as conn:
            if actor is not None:
                user_id = people.key(user_id, conn)
                people.require_self_or_manager(actor, user_id, conn, "set this workload")
            # Check if record exists
            existing = conn.execute('''
                SELECT workload_id FROM staff_workload
                WHERE user_id = ? AND academic_year = ? AND semester IS ?
            ''', (user_id, academic_year, semester)).fetchone()

            if existing:
                # Update existing record
                conn.execute('''
                    UPDATE staff_workload
                    SET teaching_hours = ?,
                        research_hours = ?,
                        admin_hours = ?,
                        service_hours = ?,
                        total_fte = ?,
                        notes = ?,
                        updated_at = ?
                    WHERE workload_id = ?
                ''', (
                    hours.get('teaching_hours', 0),
                    hours.get('research_hours', 0),
                    hours.get('admin_hours', 0),
                    hours.get('service_hours', 0),
                    hours.get('total_fte', 1.0),
                    hours.get('notes'),
                    datetime.now().isoformat(),
                    existing[0],
                ))
                log_activity('update', 'staff_workload', user_id=user_id,
                            details={'workload_id': existing[0]})
                return existing[0]
            else:
                # Create new record
                cursor = conn.execute('''
                    INSERT INTO staff_workload (
                        user_id, academic_year, semester,
                        teaching_hours, research_hours, admin_hours,
                        service_hours, total_fte, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_id,
                    academic_year,
                    semester,
                    hours.get('teaching_hours', 0),
                    hours.get('research_hours', 0),
                    hours.get('admin_hours', 0),
                    hours.get('service_hours', 0),
                    hours.get('total_fte', 1.0),
                    hours.get('notes'),
                ))
                workload_id = cursor.lastrowid
                log_activity('create', 'staff_workload', user_id=user_id,
                            details={'workload_id': workload_id})
                return workload_id

    # ==================== SCHEDULE OPERATIONS ====================
    # ``staff_schedules`` may be the Staff HR table (``schedule_id`` primary
    # key) or the older shift-rota table it was added onto (``id`` key,
    # NOT NULL ``staff_id``/``shift_date``/``position``, ``schedule_id`` a plain
    # column); :func:`_schedule_shape` handles both.

    @staticmethod
    def get_schedules(user_id: str, actor: Any = None) -> List[Dict[str, Any]]:
        """Get all schedules for a user (with ``actor``: the person, their
        line managers or HR)."""
        with get_connection() as conn:
            if actor is not None:
                user_id = people.key(user_id, conn)
                people.require_view(actor, user_id, conn, "this schedule")
            rows = conn.execute('''
                SELECT * FROM staff_schedules
                WHERE user_id = ?
                ORDER BY day_of_week, start_time
            ''', (user_id,)).fetchall()
            return [_schedule_row(row) for row in rows]

    @staticmethod
    def get_schedule(schedule_id: int, actor: Any = None) -> Optional[Dict[str, Any]]:
        """One schedule entry."""
        with get_connection() as conn:
            row = conn.execute('SELECT * FROM staff_schedules WHERE ' +
                               _schedule_key(conn) + ' = ?', (schedule_id,)).fetchone()
            if row and actor is not None:
                people.require_view(actor, _owner_of_schedule(conn, schedule_id), conn,
                                    "this schedule")
            return _schedule_row(row) if row else None

    @staticmethod
    def add_schedule(user_id: str, day_of_week: int, start_time: str,
                     end_time: str, actor: Any = None, **data) -> int:
        """Add a schedule entry for a user (with ``actor``: the person, their
        line managers or HR)."""
        with transaction() as conn:
            if actor is not None:
                user_id = people.key(user_id, conn)
                people.require_self_or_manager(actor, user_id, conn, "change this schedule")
            values = {
                'user_id': user_id,
                'day_of_week': day_of_week,
                'start_time': start_time,
                'end_time': end_time,
                'location': data.get('location'),
                'schedule_type': data.get('schedule_type') or 'office_hours',
                'is_recurring': data.get('is_recurring', 1),
                'effective_from': data.get('effective_from'),
                'effective_to': data.get('effective_to'),
                'notes': data.get('notes'),
            }
            cols = _schedule_shape(conn)
            if 'staff_id' in cols:      # the shift-rota shape
                values.update(staff_id=user_id, position=values['schedule_type'],
                              shift_date=values['effective_from'] or
                              datetime.now().strftime('%Y-%m-%d'))
            cursor = conn.execute(
                'INSERT INTO staff_schedules (' + ', '.join(values) + ') VALUES (' +
                ', '.join('?' * len(values)) + ')', list(values.values()))
            schedule_id = cursor.lastrowid
            if 'id' in cols:
                conn.execute('UPDATE staff_schedules SET schedule_id = id WHERE id = ?',
                             (schedule_id,))
            log_activity('create', 'staff_schedule', user_id=user_id,
                        details={'schedule_id': schedule_id})
            return schedule_id

    @staticmethod
    def update_schedule(schedule_id: int, actor: Any = None, **data) -> bool:
        """Change a schedule entry (with ``actor``: its owner, their line
        managers or HR)."""
        columns = ('day_of_week', 'start_time', 'end_time', 'location', 'schedule_type',
                   'is_recurring', 'effective_from', 'effective_to', 'notes')
        changes = {k: v for k, v in data.items() if k in columns}
        if not changes:
            return False
        with transaction() as conn:
            owner = _owner_of_schedule(conn, schedule_id)
            if owner is None:
                return False
            if actor is not None:
                people.require_self_or_manager(actor, owner, conn, "change this schedule")
            if 'schedule_type' in changes and 'position' in _schedule_shape(conn):
                changes['position'] = changes['schedule_type'] or 'office_hours'
            conn.execute('UPDATE staff_schedules SET ' +
                         ', '.join(validate_identifier(c, "column") + ' = ?' for c in changes) +
                         ' WHERE ' + _schedule_key(conn) + ' = ?',
                         list(changes.values()) + [schedule_id])
        log_activity('update', 'staff_schedule', user_id=owner,
                     details={'schedule_id': schedule_id})
        return True

    @staticmethod
    def delete_schedule(schedule_id: int, actor: Any = None) -> bool:
        """Delete a schedule entry (with ``actor``: its owner, their line
        managers or HR)."""
        with transaction() as conn:
            if actor is not None:
                owner = _owner_of_schedule(conn, schedule_id)
                if owner is None:
                    return False
                people.require_self_or_manager(actor, owner, conn, "change this schedule")
            conn.execute('DELETE FROM staff_schedules WHERE ' + _schedule_key(conn) + ' = ?',
                         (schedule_id,))
            log_activity('delete', 'staff_schedule',
                        details={'schedule_id': schedule_id})
            return True

    # ==================== DIRECTORY OPERATIONS ====================

    @staticmethod
    def search_directory(search: Optional[str] = None,
                         department: Optional[str] = None,
                         expertise: Optional[str] = None,
                         limit: int = 50,
                         offset: int = 0) -> List[Dict[str, Any]]:
        """Search staff directory with optional filters."""
        with get_connection() as conn:
            query = '''
                SELECT p.*, u.username, u.email, u.first_name, u.last_name
                FROM staff_profiles p
                LEFT JOIN users u ON u.username = p.user_id OR u.id = p.user_id
                WHERE 1=1
            '''
            params = []

            if search:
                query += '''
                    AND (p.user_id LIKE ?
                         OR p.employee_id LIKE ?
                         OR p.job_title LIKE ?
                         OR p.expertise_areas LIKE ?
                         OR u.first_name LIKE ?
                         OR u.last_name LIKE ?
                         OR u.email LIKE ?)
                '''
                search_term = f'%{search}%'
                params.extend([search_term] * 7)

            if department:
                query += ' AND p.department = ?'
                params.append(department)

            if expertise:
                query += ' AND p.expertise_areas LIKE ?'
                params.append(f'%{expertise}%')

            query += ' ORDER BY p.department, p.job_title LIMIT ? OFFSET ?'
            params.extend([limit, offset])

            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_directory_count(search: Optional[str] = None,
                            department: Optional[str] = None,
                            expertise: Optional[str] = None) -> int:
        """Get total count for directory search."""
        with get_connection() as conn:
            query = '''
                SELECT COUNT(*) FROM staff_profiles p
                LEFT JOIN users u ON u.username = p.user_id OR u.id = p.user_id
                WHERE 1=1
            '''
            params = []

            if search:
                query += '''
                    AND (p.user_id LIKE ?
                         OR p.employee_id LIKE ?
                         OR p.job_title LIKE ?
                         OR p.expertise_areas LIKE ?
                         OR u.first_name LIKE ?
                         OR u.last_name LIKE ?
                         OR u.email LIKE ?)
                '''
                search_term = f'%{search}%'
                params.extend([search_term] * 7)

            if department:
                query += ' AND p.department = ?'
                params.append(department)

            if expertise:
                query += ' AND p.expertise_areas LIKE ?'
                params.append(f'%{expertise}%')

            result = conn.execute(query, params).fetchone()
            return result[0] if result else 0

    @staticmethod
    def get_departments() -> List[str]:
        """Get list of all departments from profiles."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT DISTINCT department FROM staff_profiles
                WHERE department IS NOT NULL AND department != ''
                ORDER BY department
            ''').fetchall()
            return [row[0] for row in rows]

    @staticmethod
    def get_staff_by_manager(manager_id: str) -> List[Dict[str, Any]]:
        """Get all staff reporting directly to a manager."""
        with get_connection() as conn:
            boss = people.key(manager_id, conn)
            reports = access.reports_of(boss, conn) if boss else []
            if not reports:
                return []
            rows = conn.execute(
                'SELECT p.*, u.email, u.first_name, u.last_name FROM staff_profiles p '
                'LEFT JOIN users u ON u.username = p.user_id WHERE p.user_id IN (' +
                ', '.join('?' * len(reports)) + ') ORDER BY p.job_title', reports).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def directory(search: Optional[str] = None, department: Optional[str] = None,
                  usernames: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """The staff directory: every staff login (with or without a profile)
        and every profile, directory fields only. ``usernames`` limits it to
        those people."""
        with get_connection() as conn:
            roles = ', '.join('?' * len(STAFF_ROLES))
            query = (
                'SELECT COALESCE(u.username, p.user_id) AS username, u.first_name, '
                'u.last_name, u.email, p.job_title, p.department, p.office_location, '
                'p.phone_extension, p.expertise_areas, p.manager_id '
                'FROM users u LEFT JOIN staff_profiles p ON p.user_id = u.username '
                'WHERE LOWER(u.role) IN (' + roles + ') '
                'UNION '
                'SELECT p.user_id, NULL, NULL, NULL, p.job_title, p.department, '
                'p.office_location, p.phone_extension, p.expertise_areas, p.manager_id '
                'FROM staff_profiles p WHERE p.user_id NOT IN '
                '(SELECT username FROM users WHERE username IS NOT NULL)')
            rows = [dict(r) for r in conn.execute(query, STAFF_ROLES).fetchall()]
        needle = _blank(search).lower()
        out = []
        for row in rows:
            if usernames is not None and row['username'] not in usernames:
                continue
            if department and row.get('department') != department:
                continue
            if needle and not any(needle in _blank(row.get(k)).lower() for k in (
                    'username', 'first_name', 'last_name', 'email', 'job_title',
                    'expertise_areas')):
                continue
            out.append(row)
        return sorted(out, key=lambda r: _blank(r['username']).lower())

    @staticmethod
    def directory_entry(username: str) -> Optional[Dict[str, Any]]:
        """One colleague's directory card (directory fields, names, e-mail and
        line manager)."""
        with get_connection() as conn:
            staff = people.key(username, conn)
            row = conn.execute('SELECT * FROM staff_profiles WHERE user_id = ?',
                               (staff,)).fetchone()
            user = conn.execute('SELECT first_name, last_name, email FROM users '
                                'WHERE username = ?', (staff,)).fetchone()
            if not row and not user:
                return None
            card = {k: (row[k] if row else None) for k in DIRECTORY_FIELDS}
            card['user_id'] = staff
            card.update(dict(user) if user else {'first_name': None, 'last_name': None,
                                                  'email': None})
            card['manager_id'] = access.manager_of(staff, conn)
            return card

    @staticmethod
    def team_of(actor: Any, deep: bool = False) -> List[Dict[str, Any]]:
        """The signed-in manager's reports (``deep``: the whole tree below
        them) — directory fields only."""
        with get_connection() as conn:
            reports = access.reports_of(people.me(actor), conn, deep=deep)
        if not reports:
            return []
        return EmployeeManager.directory(usernames=reports)

    # ==================== DIRECTORY SEARCH ====================

    @staticmethod
    def search_employees(name: Optional[str] = None, department: Optional[str] = None,
                         job_title: Optional[str] = None,
                         limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Colleagues matching every filter given (each a case-insensitive
        part of the value): the staff directory with each row's ``name``."""
        wanted_name = _blank(name).lower()
        wanted_department = _blank(department).lower()
        wanted_title = _blank(job_title).lower()
        out = []
        for row in EmployeeManager.directory():
            row['name'] = _person_name(row)
            if wanted_name and wanted_name not in row['name'].lower() \
                    and wanted_name not in _blank(row['username']).lower():
                continue
            if wanted_department and wanted_department not in _blank(row.get('department')).lower():
                continue
            if wanted_title and wanted_title not in _blank(row.get('job_title')).lower():
                continue
            out.append(row)
        return out[:limit] if limit else out

    @staticmethod
    def get_all_employees() -> List[Dict[str, Any]]:
        """Everyone in the staff directory."""
        return EmployeeManager.search_employees()

    @staticmethod
    def get_organization_structure() -> Dict[str, List[Dict[str, Any]]]:
        """The directory by department: ``{department: [person, ...]}``, each
        department in name order (no department: ``Unassigned``)."""
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for row in EmployeeManager.search_employees():
            groups.setdefault(_blank(row.get('department')) or 'Unassigned', []).append(row)
        return {dept: sorted(groups[dept], key=lambda r: r['name'].lower())
                for dept in sorted(groups)}

    # ==================== REPORTS ====================

    @staticmethod
    def get_statistics() -> Dict[str, int]:
        """Today's headcount by employment type and availability."""
        today = date.today().isoformat()
        with get_connection() as conn:
            staff = current_staff(conn)
            away = {str(r[0]) for r in conn.execute('''
                SELECT user_id FROM leave_requests
                WHERE status = 'approved' AND start_date <= ? AND end_date >= ?
            ''', (today, today)).fetchall()}
        kinds = [_blank(s.get('employment_type')).lower().replace('_', '-').replace(' ', '-')
                 for s in staff]
        on_leave = sum(1 for s in staff if str(s['user_id']) in away)
        return {
            'total_employees': len(staff),
            'full_time': kinds.count('full-time'),
            'part_time': kinds.count('part-time'),
            'contract': sum(1 for k in kinds if k in ('contract', 'fixed-term', 'temporary')),
            'active': len(staff) - on_leave,
            'on_leave': on_leave,
        }

    @staticmethod
    def get_department_breakdown() -> Dict[str, int]:
        """Today's headcount per department (no department: ``Unassigned``)."""
        with get_connection() as conn:
            staff = current_staff(conn)
        counts: Dict[str, int] = {}
        for person in staff:
            dept = _blank(person.get('department')) or 'Unassigned'
            counts[dept] = counts.get(dept, 0) + 1
        return dict(sorted(counts.items()))

    @staticmethod
    def get_headcount_report() -> Dict[str, Any]:
        """Headcount, starters and leavers this month and calendar year, and
        turnover: leavers this year over the year's average headcount."""
        today = date.today()
        now = today.isoformat()
        month_start = today.replace(day=1).isoformat()
        year_start = today.replace(month=1, day=1).isoformat()
        with get_connection() as conn:
            current = len(current_staff(conn))
            month_leavers = _departures(conn, month_start, now)
            year_leavers = _departures(conn, year_start, now)

            def hires(since: str) -> int:
                return conn.execute('''
                    SELECT COUNT(*) FROM staff_profiles WHERE hire_date BETWEEN ? AND ?
                ''', (since, now)).fetchone()[0]

            hires_month, hires_year = hires(month_start), hires(year_start)
        at_start = current - hires_year + len(year_leavers)
        average = (at_start + current) / 2
        return {
            'current': current,
            'new_hires_month': hires_month,
            'new_hires_year': hires_year,
            'departures_month': len(month_leavers),
            'departures_year': len(year_leavers),
            'turnover_rate': len(year_leavers) * 100.0 / average if average > 0 else 0.0,
        }
