"""
Academic Staff Manager

Handles teaching portfolios, research profiles, student supervisions,
external examiners, and peer observations.
"""

from __future__ import annotations

import logging
from datetime import datetime
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

PORTFOLIO_FIELDS = ('teaching_philosophy', 'teaching_interests', 'courses_taught',
                    'teaching_innovations', 'awards_recognition', 'student_feedback_summary',
                    'professional_development')
RESEARCH_FIELDS = ('research_interests', 'h_index', 'total_citations', 'total_publications',
                   'orcid_id', 'google_scholar_id', 'researchgate_url', 'scopus_id')
RESEARCH_COUNTS = ('h_index', 'total_citations', 'total_publications')
SUPERVISION_FIELDS = ('student_id', 'student_name', 'program_type', 'thesis_title', 'start_date',
                      'expected_end_date', 'actual_end_date', 'status', 'supervision_role',
                      'progress_notes', 'milestones', 'degree', 'department',
                      'secondary_supervisor_id')
SUPERVISION_STATUSES = ('requested', 'active', 'completed', 'withdrawn', 'declined')
EXAMINER_FIELDS = ('name', 'institution', 'email', 'phone', 'expertise_area', 'department',
                   'appointment_start', 'appointment_end', 'status', 'contact_person_id', 'notes')
OBSERVATION_FIELDS = ('course_code', 'course_name', 'observation_date', 'observation_type',
                      'class_size', 'duration_minutes', 'strengths', 'areas_for_development',
                      'action_points', 'overall_rating', 'status')
#: Active research students per supervisor before they count as "at capacity".
SUPERVISION_CAPACITY = 6


def _date(value: Optional[str], label: str) -> Optional[str]:
    if value in (None, ''):
        return None
    try:
        datetime.strptime(str(value), '%Y-%m-%d')
    except ValueError:
        raise ValueError(f"{label} must be YYYY-MM-DD") from None
    return str(value)


def _has_table(conn, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (name,)).fetchone() is not None


def _upsert_own(conn, table: str, key_col: str, user_id: str, data: Dict[str, Any]) -> None:
    """Update or create the person's one row in ``table``."""
    table = validate_identifier(table, "table")
    existing = conn.execute('SELECT ' + validate_identifier(key_col, "column") + ' FROM ' + table +
                            ' WHERE user_id = ?', (user_id,)).fetchone()
    if existing:
        fields = ', '.join(validate_identifier(k, "column") + ' = ?' for k in data.keys())
        conn.execute('UPDATE ' + table + ' SET ' + fields + ', last_updated = ? WHERE user_id = ?',
                     list(data.values()) + [datetime.now().isoformat(), user_id])
    else:
        cols = ', '.join(['user_id'] + [validate_identifier(k, "column") for k in data.keys()])
        conn.execute('INSERT INTO ' + table + ' (' + cols + ') VALUES (' +
                     ', '.join(['?'] * (len(data) + 1)) + ')', [user_id] + list(data.values()))


def _supervises(row: Dict[str, Any], who: str) -> bool:
    return who in (row.get('supervisor_id'), row.get('secondary_supervisor_id'))


def _clean_supervision(conn, data: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: v for k, v in data.items() if k in SUPERVISION_FIELDS}
    for k in ('start_date', 'expected_end_date', 'actual_end_date'):
        if k in out:
            out[k] = _date(out[k], k.replace('_', ' ').capitalize())
    if out.get('status') and out['status'] not in SUPERVISION_STATUSES:
        raise ValueError(f"Status must be one of {', '.join(SUPERVISION_STATUSES)}")
    if out.get('secondary_supervisor_id'):
        found = access.staff_key(out['secondary_supervisor_id'], conn)
        if not found:
            raise ValueError(f"No staff member '{out['secondary_supervisor_id']}'")
        out['secondary_supervisor_id'] = found
    return out


def _whole(value: Any, label: str) -> Optional[int]:
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a whole number") from None


def _clean_observation(data: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: v for k, v in data.items() if k in OBSERVATION_FIELDS}
    if 'observation_date' in out:
        out['observation_date'] = _date(out['observation_date'], "Observation date")
    for k in ('class_size', 'duration_minutes', 'overall_rating'):
        if k in out:
            out[k] = _whole(out[k], k.replace('_', ' ').capitalize())
    if out.get('overall_rating') is not None and not 1 <= out['overall_rating'] <= 5:
        raise ValueError("Overall rating must be 1-5")
    if out.get('status') and out['status'] not in ('draft', 'submitted'):
        raise ValueError("An observation is saved as draft or submitted; "
                         "only the person observed can acknowledge it")
    return out


def _observation_parties(row: Dict[str, Any]) -> tuple:
    return row.get('observer_id'), row.get('observee_id')


class AcademicStaffManager:
    """Manager for academic staff features."""

    # ==================== TEACHING PORTFOLIOS ====================

    @staticmethod
    def get_teaching_portfolio(user_id: str, actor: Any = None) -> Optional[Dict[str, Any]]:
        """Get teaching portfolio for a user (with ``actor``: themselves,
        their line or HR)."""
        with get_connection() as conn:
            if actor is not None:
                user_id = people.key(user_id, conn)
                people.require_view(actor, user_id, conn, "this teaching portfolio")
            row = conn.execute('''
                SELECT * FROM teaching_portfolios WHERE user_id = ?
            ''', (user_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def update_teaching_portfolio(user_id: str, actor: Any = None, **data) -> bool:
        """Update or create teaching portfolio (with ``actor``: the person
        themselves or HR, and only portfolio fields)."""
        with transaction() as conn:
            if actor is not None:
                user_id = people.key(user_id, conn)
                people.require_self_or_hr(actor, user_id, conn, "edit a teaching portfolio")
                unknown = set(data) - set(PORTFOLIO_FIELDS)
                if unknown:
                    raise ValueError(f"Not a portfolio field: {', '.join(sorted(unknown))}")
            if not data:
                return False
            _upsert_own(conn, 'teaching_portfolios', 'portfolio_id', user_id, data)
            return True

    # ==================== RESEARCH PROFILES ====================

    @staticmethod
    def get_research_profile(user_id: str, actor: Any = None) -> Optional[Dict[str, Any]]:
        """Get research profile for a user (with ``actor``: themselves, their
        line or HR)."""
        with get_connection() as conn:
            if actor is not None:
                user_id = people.key(user_id, conn)
                people.require_view(actor, user_id, conn, "this research profile")
            row = conn.execute('''
                SELECT * FROM research_profiles WHERE user_id = ?
            ''', (user_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def update_research_profile(user_id: str, actor: Any = None, **data) -> bool:
        """Update or create research profile (with ``actor``: the person
        themselves or HR; counts must be whole numbers of 0 or more)."""
        with transaction() as conn:
            if actor is not None:
                user_id = people.key(user_id, conn)
                people.require_self_or_hr(actor, user_id, conn, "edit a research profile")
                unknown = set(data) - set(RESEARCH_FIELDS)
                if unknown:
                    raise ValueError(f"Not a research profile field: {', '.join(sorted(unknown))}")
                for k in RESEARCH_COUNTS:
                    if k in data:
                        data[k] = _whole(data[k], k.replace('_', ' ')) or 0
                        if data[k] < 0:
                            raise ValueError(f"{k.replace('_', ' ')} cannot be negative")
            if not data:
                return False
            _upsert_own(conn, 'research_profiles', 'profile_id', user_id, data)
            return True

    # ==================== STUDENT SUPERVISIONS ====================

    @staticmethod
    def get_supervisions(supervisor_id: str,
                         status: Optional[str] = None, actor: Any = None) -> List[Dict[str, Any]]:
        """Get student supervisions for a supervisor (as first or second
        supervisor; with ``actor``: themselves, their line or HR)."""
        with get_connection() as conn:
            if actor is not None:
                supervisor_id = people.key(supervisor_id, conn)
                people.require_view(actor, supervisor_id, conn, "these supervisions")
            query = ('SELECT * FROM student_supervisions '
                     'WHERE (supervisor_id = ? OR secondary_supervisor_id = ?)')
            params = [supervisor_id, supervisor_id]
            if status:
                query += ' AND status = ?'
                params.append(status)
            query += ' ORDER BY start_date DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_supervision(supervision_id: int, actor: Any = None) -> Optional[Dict[str, Any]]:
        """One supervision (with ``actor``: a supervisor on it, their line or HR)."""
        with get_connection() as conn:
            row = conn.execute('SELECT * FROM student_supervisions WHERE supervision_id = ?',
                               (supervision_id,)).fetchone()
            row = dict(row) if row else None
            if row and actor is not None and not _supervises(row, people.me(actor)) and \
                    not access.can_view_person(actor, row['supervisor_id'], conn):
                raise PermissionError("You cannot see this supervision")
            return row

    @staticmethod
    def add_supervision(supervisor_id: str, student_id: str,
                        program_type: str, actor: Any = None, **data) -> int:
        """Add a new student supervision (with ``actor``: for yourself, or
        HR for anyone; a student name is required)."""
        with transaction() as conn:
            if actor is not None:
                supervisor_id = people.key(supervisor_id, conn)
                people.require_self_or_hr(actor, supervisor_id, conn, "add a supervision")
                if not str(data.get('student_name') or '').strip():
                    raise ValueError("Student name is required")
                data = _clean_supervision(conn, data)
            cursor = conn.execute('''
                INSERT INTO student_supervisions (
                    supervisor_id, student_id, student_name, program_type,
                    thesis_title, start_date, expected_end_date,
                    supervision_role, progress_notes, status, degree, department,
                    secondary_supervisor_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (supervisor_id, student_id or '', data.get('student_name'),  # column is NOT NULL
                  program_type, data.get('thesis_title'), data.get('start_date'),
                  data.get('expected_end_date'),
                  data.get('supervision_role', 'primary'),
                  data.get('progress_notes'), data.get('status') or 'active',
                  data.get('degree'), data.get('department'),
                  data.get('secondary_supervisor_id')))
            return cursor.lastrowid

    @staticmethod
    def update_supervision(supervision_id: int, actor: Any = None, **data) -> bool:
        """Update a supervision record (with ``actor``: a supervisor on it or
        HR, and only supervision fields)."""
        if not data:
            return False
        with transaction() as conn:
            if actor is not None:
                row = conn.execute('SELECT * FROM student_supervisions WHERE supervision_id = ?',
                                   (supervision_id,)).fetchone()
                if not row:
                    raise ValueError("No such supervision")
                if not _supervises(dict(row), people.me(actor)) and not access.is_hr(actor, conn):
                    raise PermissionError("Only a supervisor on this student or HR can change it")
                data = _clean_supervision(conn, data)
                if not data:
                    return False
            fields = ', '.join(validate_identifier(k, "column") + ' = ?' for k in data.keys())
            values = list(data.values()) + [datetime.now().isoformat(), supervision_id]
            conn.execute(
                'UPDATE student_supervisions SET ' + fields + ', updated_at = ? WHERE supervision_id = ?',
                values)
            return True

    @staticmethod
    def get_supervision_requests(actor: Any) -> List[Dict[str, Any]]:
        """Supervisions proposed to the signed-in person (status 'requested')."""
        with get_connection() as conn:
            me = people.me(actor)
            rows = conn.execute(
                "SELECT * FROM student_supervisions WHERE supervisor_id = ? AND status = 'requested' "
                "ORDER BY created_at", (me,)).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def _answer_request(supervision_id: int, actor: Any, status: str,
                        note: Optional[str]) -> bool:
        with transaction() as conn:
            row = conn.execute('SELECT * FROM student_supervisions WHERE supervision_id = ?',
                               (supervision_id,)).fetchone()
            if not row:
                raise ValueError("No such supervision request")
            if row['supervisor_id'] != people.me(actor):
                raise PermissionError("Only the proposed supervisor can answer this request")
            if row['status'] != 'requested':
                raise ValueError("This request has already been answered")
            notes = row['progress_notes'] or ''
            if note:
                notes = (notes + '\n' if notes else '') + f"[{datetime.now():%Y-%m-%d}] {note}"
            conn.execute('''
                UPDATE student_supervisions
                SET status = ?, start_date = COALESCE(start_date, ?), progress_notes = ?,
                    updated_at = ?
                WHERE supervision_id = ?
            ''', (status, datetime.now().strftime('%Y-%m-%d') if status == 'active' else None,
                  notes or None, datetime.now().isoformat(), supervision_id))
            return True

    @staticmethod
    def accept_supervision(supervision_id: int, actor: Any) -> bool:
        """Accept a supervision request: it becomes active from today
        (unless a start date was proposed)."""
        return AcademicStaffManager._answer_request(supervision_id, actor, 'active', None)

    @staticmethod
    def decline_supervision(supervision_id: int, reason: str, actor: Any) -> bool:
        """Decline a supervision request, giving a reason."""
        if not str(reason or '').strip():
            raise ValueError("Give a reason for declining")
        return AcademicStaffManager._answer_request(supervision_id, actor, 'declined',
                                                    f"Declined: {reason.strip()}")

    @staticmethod
    def supervision_summary(actor: Any) -> Dict[str, Any]:
        """HR: active research students by programme and department, and
        supervisors at or under :data:`SUPERVISION_CAPACITY`."""
        with get_connection() as conn:
            people.require_hr(actor, conn, "see the supervision overview")
            rows = conn.execute(
                "SELECT supervisor_id, LOWER(COALESCE(program_type, '')) AS program, "
                "COALESCE(NULLIF(department, ''), 'Unassigned') AS department "
                "FROM student_supervisions WHERE status = 'active'").fetchall()
            load: Dict[str, int] = {}
            by_department: Dict[str, int] = {}
            for r in rows:
                load[r['supervisor_id']] = load.get(r['supervisor_id'], 0) + 1
                by_department[r['department']] = by_department.get(r['department'], 0) + 1
            return {
                'phd_count': sum(1 for r in rows if r['program'] == 'phd'),
                'masters_count': sum(1 for r in rows if r['program'] == 'masters'),
                'other_count': sum(1 for r in rows if r['program'] not in ('phd', 'masters')),
                'at_capacity': sum(1 for n in load.values() if n >= SUPERVISION_CAPACITY),
                'available': sum(1 for n in load.values() if n < SUPERVISION_CAPACITY),
                'capacity': SUPERVISION_CAPACITY,
                'by_supervisor': dict(sorted(load.items())),
                'by_department': dict(sorted(by_department.items())),
            }

    # ==================== TEACHING ====================

    @staticmethod
    def get_teaching_assignments(user_id: str, actor: Any = None) -> List[Dict[str, Any]]:
        """Modules taught (the module teaching team) and courses on the
        Staff HR teaching load, newest year first."""
        with get_connection() as conn:
            user_id = people.key(user_id, conn)
            if actor is not None:
                people.require_view(actor, user_id, conn, "these teaching assignments")
            out: List[Dict[str, Any]] = []
            if _has_table(conn, 'module_staff'):
                for r in conn.execute(
                        "SELECT ms.module_code AS course_code, "
                        "COALESCE(m.module_name, '') AS course_name, ms.role, ms.hours, "
                        "ms.academic_year FROM module_staff ms LEFT JOIN modules m "
                        "ON m.module_code = ms.module_code WHERE ms.username = ? COLLATE NOCASE",
                        (user_id,)).fetchall():
                    out.append(dict(r, source='module team', term=None, hours_per_week=None))
            for r in conn.execute(
                    "SELECT course_code, course_name, section, academic_year, semester AS term, "
                    "contact_hours_pw AS hours_per_week, enrolled_students FROM "
                    "teaching_load_courses WHERE user_id = ?", (user_id,)).fetchall():
                out.append(dict(r, source='teaching load', role='Instructor'))
            out.sort(key=lambda r: (str(r.get('academic_year') or ''), r.get('course_code') or ''),
                     reverse=True)
            return out

    @staticmethod
    def get_publications(user_id: str, actor: Any = None, limit: Optional[int] = None
                         ) -> List[Dict[str, Any]]:
        """Research outputs the person is an author on (Research Office
        record: listed author, lead author, or PI of the output's project)."""
        with get_connection() as conn:
            user_id = people.key(user_id, conn)
            if actor is not None:
                people.require_view(actor, user_id, conn, "these publications")
            clauses = ['p.lead_author_id = ?']
            params: list = [user_id]
            if _has_table(conn, 'research_output_authors'):
                clauses.append('p.publication_id IN (SELECT publication_id FROM '
                               'research_output_authors WHERE username = ?)')
                params.append(user_id)
            if _has_table(conn, 'research_projects'):
                clauses.append('p.project_id IN (SELECT project_id FROM research_projects '
                               'WHERE principal_investigator_id = ?)')
                params.append(user_id)
            sql = ('SELECT p.* FROM research_publications p WHERE ' + ' OR '.join(clauses) +
                   ' ORDER BY COALESCE(p.publication_date, p.acceptance_date, p.created_at) DESC')
            if limit:
                sql += ' LIMIT ?'
                params.append(int(limit))
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    @staticmethod
    def teaching_load_summary(actor: Any) -> List[Dict[str, Any]]:
        """HR: per person, courses and weekly contact hours on the teaching
        load, module-team hours, and whether credits exceed the department
        standard's maximum."""
        with get_connection() as conn:
            people.require_hr(actor, conn, "see teaching loads")
            default_max = conn.execute(
                "SELECT max_credits FROM teaching_load_standards WHERE is_default = 1 "
                "LIMIT 1").fetchone()
            default_max = default_max[0] if default_max else None
            rows: Dict[str, Dict[str, Any]] = {}
            for r in conn.execute(
                    "SELECT user_id, COUNT(*) AS course_count, "
                    "COALESCE(SUM(contact_hours_pw), 0) AS contact_hours, "
                    "COALESCE(SUM(credit_hours), 0) AS credits, MAX(department) AS department "
                    "FROM teaching_load_courses GROUP BY user_id").fetchall():
                rows[r['user_id']] = dict(r, module_hours=0)
            if _has_table(conn, 'module_staff'):
                for who, n, hours in conn.execute(
                        "SELECT LOWER(username), COUNT(*), COALESCE(SUM(hours), 0) "
                        "FROM module_staff GROUP BY LOWER(username)").fetchall():
                    key = people.key(who, conn)
                    row = rows.setdefault(key, {'user_id': key, 'course_count': 0,
                                                'contact_hours': 0, 'credits': 0,
                                                'department': None, 'module_hours': 0})
                    row['course_count'] += n
                    row['module_hours'] += hours
            for row in rows.values():
                limit = None
                if row.get('department'):
                    found = conn.execute(
                        "SELECT max_credits FROM teaching_load_standards WHERE department = ? "
                        "LIMIT 1", (row['department'],)).fetchone()
                    limit = found[0] if found else None
                limit = limit if limit is not None else default_max
                row['name'] = access.display_name(row['user_id'], conn)
                row['max_credits'] = limit
                row['load_status'] = ('Overloaded' if limit is not None and row['credits'] > limit
                                      else 'Within standard' if limit is not None else 'No standard')
            return sorted(rows.values(), key=lambda r: r['name'].lower())

    # ==================== EXTERNAL EXAMINERS ====================

    @staticmethod
    def get_external_examiners(active_only: bool = True) -> List[Dict[str, Any]]:
        """Get external examiners."""
        with get_connection() as conn:
            if active_only:
                rows = conn.execute('''
                    SELECT * FROM external_examiners WHERE status = 'active'
                    ORDER BY name
                ''').fetchall()
            else:
                rows = conn.execute('''
                    SELECT * FROM external_examiners ORDER BY name
                ''').fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_external_examiner(examiner_id: int) -> Optional[Dict[str, Any]]:
        """One external examiner."""
        with get_connection() as conn:
            row = conn.execute('SELECT * FROM external_examiners WHERE examiner_id = ?',
                               (examiner_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def _clean_examiner(conn, data: Dict[str, Any],
                        current: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        out = {k: v for k, v in data.items() if k in EXAMINER_FIELDS}
        if 'name' in out and not str(out['name'] or '').strip():
            raise ValueError("Examiner name is required")
        for k in ('appointment_start', 'appointment_end'):
            if k in out:
                out[k] = _date(out[k], k.replace('_', ' ').capitalize())
        start = out.get('appointment_start', (current or {}).get('appointment_start'))
        end = out.get('appointment_end', (current or {}).get('appointment_end'))
        if start and end and end < start:
            raise ValueError("The appointment cannot end before it starts")
        if out.get('contact_person_id'):
            found = access.staff_key(out['contact_person_id'], conn)
            if not found:
                raise ValueError(f"No staff member '{out['contact_person_id']}'")
            out['contact_person_id'] = found
        return out

    @staticmethod
    def add_external_examiner(name: str, actor: Any = None, **data) -> int:
        """Add a new external examiner (with ``actor``: HR only)."""
        with transaction() as conn:
            if actor is not None:
                people.require_hr(actor, conn, "manage external examiners")
                data = AcademicStaffManager._clean_examiner(conn, dict(data, name=name))
                name = data.pop('name')
            cursor = conn.execute('''
                INSERT INTO external_examiners (
                    name, institution, email, phone, expertise_area,
                    department, appointment_start, appointment_end,
                    contact_person_id, notes, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, data.get('institution'), data.get('email'),
                  data.get('phone'), data.get('expertise_area'),
                  data.get('department'), data.get('appointment_start'),
                  data.get('appointment_end'), data.get('contact_person_id'),
                  data.get('notes'), data.get('status') or 'active'))
            if actor is not None:
                access.audit(conn, actor, 'add_external_examiner', None, 'external_examiners',
                             cursor.lastrowid, {'name': name})
            return cursor.lastrowid

    @staticmethod
    def update_external_examiner(examiner_id: int, actor: Any, **data) -> bool:
        """HR: change an external examiner's record."""
        with transaction() as conn:
            people.require_hr(actor, conn, "manage external examiners")
            current = conn.execute('SELECT * FROM external_examiners WHERE examiner_id = ?',
                                   (examiner_id,)).fetchone()
            if not current:
                raise ValueError("No such examiner")
            data = AcademicStaffManager._clean_examiner(conn, data, dict(current))
            if not data:
                return False
            cur = conn.execute('UPDATE external_examiners SET ' +
                               ', '.join(validate_identifier(k, "column") + ' = ?' for k in data) +
                               ' WHERE examiner_id = ?', list(data.values()) + [examiner_id])
            if not cur.rowcount:
                raise ValueError("No such examiner")
            access.audit(conn, actor, 'update_external_examiner', None, 'external_examiners',
                         examiner_id, sorted(data))
            return True

    @staticmethod
    def get_examiner_assignments(examiner_id: int) -> List[Dict[str, Any]]:
        """Get assignments for an external examiner."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM examiner_assignments
                WHERE examiner_id = ? ORDER BY academic_year DESC
            ''', (examiner_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_examining_duties(user_id: str, actor: Any = None) -> List[Dict[str, Any]]:
        """A member of staff's examining work: research degrees they examine
        internally, and external examiners they are the contact for."""
        with get_connection() as conn:
            user_id = people.key(user_id, conn)
            if actor is not None:
                people.require_view(actor, user_id, conn, "these examining duties")
            out: List[Dict[str, Any]] = []
            if _has_table(conn, 'research_theses'):
                for r in conn.execute(
                        "SELECT student_id, title, degree, viva_date, status, outcome "
                        "FROM research_theses WHERE internal_examiner_id = ?",
                        (user_id,)).fetchall():
                    out.append({'kind': 'Internal examiner', 'title': r['title'],
                                'detail': f"{r['degree'] or 'Research degree'} - {r['student_id']}",
                                'date': r['viva_date'], 'status': r['outcome'] or r['status']})
            columns = {c[1] for c in conn.execute('PRAGMA table_info(student_supervisions)')}
            if 'internal_examiner_id' in columns:
                for r in conn.execute(
                        "SELECT student_name, thesis_title, program_type, viva_date, status, "
                        "outcome FROM student_supervisions WHERE internal_examiner_id = ?",
                        (user_id,)).fetchall():
                    out.append({'kind': 'Internal examiner', 'title': r['thesis_title'],
                                'detail': f"{r['program_type'] or ''} - {r['student_name']}",
                                'date': r['viva_date'], 'status': r['outcome'] or r['status']})
            for r in conn.execute(
                    "SELECT name, institution, appointment_start, appointment_end, status "
                    "FROM external_examiners WHERE contact_person_id = ?", (user_id,)).fetchall():
                out.append({'kind': 'Contact for external examiner', 'title': r['name'],
                            'detail': r['institution'] or '',
                            'date': f"{r['appointment_start'] or '?'} to {r['appointment_end'] or '?'}",
                            'status': r['status']})
            return out

    # ==================== PEER OBSERVATIONS ====================

    @staticmethod
    def get_peer_observations(user_id: str, role: str = 'both',
                              actor: Any = None) -> List[Dict[str, Any]]:
        """Get peer observations where user is observer or observee (with
        ``actor``: themselves, their line or HR)."""
        with get_connection() as conn:
            if actor is not None:
                user_id = people.key(user_id, conn)
                people.require_view(actor, user_id, conn, "these observations")
            if role == 'observer':
                rows = conn.execute('''
                    SELECT * FROM peer_observations WHERE observer_id = ?
                    ORDER BY observation_date DESC
                ''', (user_id,)).fetchall()
            elif role == 'observee':
                rows = conn.execute('''
                    SELECT * FROM peer_observations WHERE observee_id = ?
                    ORDER BY observation_date DESC
                ''', (user_id,)).fetchall()
            else:
                rows = conn.execute('''
                    SELECT * FROM peer_observations
                    WHERE observer_id = ? OR observee_id = ?
                    ORDER BY observation_date DESC
                ''', (user_id, user_id)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def list_observations(actor: Any) -> List[Dict[str, Any]]:
        """Every observation the signed-in person may see: HR all; others
        their own and those of the people they line-manage."""
        with get_connection() as conn:
            me = people.me(actor)
            allowed = access.visible_people(actor, conn)
            rows = [dict(r) for r in conn.execute(
                'SELECT * FROM peer_observations ORDER BY observation_date DESC').fetchall()]
            if allowed is None:
                return rows
            allowed = set(allowed) | {me}
            return [r for r in rows if r.get('observee_id') in allowed or r.get('observer_id') == me]

    @staticmethod
    def get_observation(observation_id: int, actor: Any = None) -> Optional[Dict[str, Any]]:
        """One observation (with ``actor``: the observer, the person observed,
        their line or HR). Adds ``can_edit`` / ``can_acknowledge``."""
        with get_connection() as conn:
            row = conn.execute('SELECT * FROM peer_observations WHERE observation_id = ?',
                               (observation_id,)).fetchone()
            if not row:
                return None
            row = dict(row)
            if actor is not None:
                me = people.me(actor)
                observer, observee = _observation_parties(row)
                if me != observer and not (observee and access.can_view_person(actor, observee, conn)):
                    raise PermissionError("You cannot see this observation")
                row['can_edit'] = me == observer and row.get('status') != 'acknowledged'
                row['can_acknowledge'] = me == observee and row.get('status') == 'submitted'
            return row

    @staticmethod
    def create_observation(observer_id: str, observee_id: str,
                           observation_date: str, actor: Any = None, **data) -> int:
        """Create a new peer observation record (with ``actor``: you are the
        observer, and the person observed must be a known colleague)."""
        with transaction() as conn:
            if actor is not None:
                observer_id = people.me(actor)
                found = access.staff_key(observee_id, conn)
                if not found:
                    raise ValueError(f"No staff member '{observee_id}'")
                if found == observer_id:
                    raise ValueError("You cannot observe yourself")
                observee_id = found
                data = _clean_observation(dict(data, observation_date=observation_date))
                observation_date = data.pop('observation_date', None)
                if not observation_date:
                    raise ValueError("Observation date is required")
                data['observer_name'] = access.display_name(observer_id, conn)
                data['observee_name'] = access.display_name(observee_id, conn)
            cursor = conn.execute('''
                INSERT INTO peer_observations (
                    observer_id, observer_name, observee_id, observee_name,
                    course_code, course_name, observation_date,
                    observation_type, class_size, duration_minutes,
                    strengths, areas_for_development, action_points,
                    overall_rating, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (observer_id, data.get('observer_name'), observee_id,
                  data.get('observee_name'), data.get('course_code'),
                  data.get('course_name'), observation_date,
                  data.get('observation_type', 'peer'),
                  data.get('class_size'), data.get('duration_minutes'),
                  data.get('strengths'), data.get('areas_for_development'),
                  data.get('action_points'), data.get('overall_rating'),
                  data.get('status', 'draft')))
            return cursor.lastrowid

    @staticmethod
    def update_observation(observation_id: int, actor: Any, **data) -> bool:
        """The observer edits their observation until it is acknowledged."""
        with transaction() as conn:
            row = conn.execute('SELECT * FROM peer_observations WHERE observation_id = ?',
                               (observation_id,)).fetchone()
            if not row:
                raise ValueError("No such observation")
            if row['observer_id'] != people.me(actor):
                raise PermissionError("Only the observer can change an observation")
            if row['status'] == 'acknowledged':
                raise ValueError("This observation has been acknowledged and is closed")
            data = _clean_observation(data)
            if not data:
                return False
            conn.execute('UPDATE peer_observations SET ' +
                         ', '.join(validate_identifier(k, "column") + ' = ?' for k in data) +
                         ' WHERE observation_id = ?', list(data.values()) + [observation_id])
            return True

    @staticmethod
    def submit_observation(observation_id: int, actor: Any = None) -> bool:
        """Submit a peer observation for acknowledgement (with ``actor``:
        the observer)."""
        with transaction() as conn:
            if actor is not None:
                row = conn.execute('SELECT observer_id, status FROM peer_observations '
                                   'WHERE observation_id = ?', (observation_id,)).fetchone()
                if not row:
                    raise ValueError("No such observation")
                if row['observer_id'] != people.me(actor):
                    raise PermissionError("Only the observer can submit an observation")
                if row['status'] != 'draft':
                    raise ValueError("Only a draft can be submitted")
            conn.execute('''
                UPDATE peer_observations
                SET status = 'submitted' WHERE observation_id = ?
            ''', (observation_id,))
            return True

    @staticmethod
    def acknowledge_observation(observation_id: int, actor: Any = None) -> bool:
        """Acknowledge a peer observation (with ``actor``: the person
        observed, once it is submitted)."""
        with transaction() as conn:
            if actor is not None:
                row = conn.execute('SELECT observee_id, status FROM peer_observations '
                                   'WHERE observation_id = ?', (observation_id,)).fetchone()
                if not row:
                    raise ValueError("No such observation")
                if row['observee_id'] != people.me(actor):
                    raise PermissionError("Only the person observed can acknowledge it")
                if row['status'] != 'submitted':
                    raise ValueError("Only a submitted observation can be acknowledged")
            conn.execute('''
                UPDATE peer_observations
                SET status = 'acknowledged', acknowledged_date = ?
                WHERE observation_id = ?
            ''', (datetime.now().isoformat(), observation_id))
            return True
