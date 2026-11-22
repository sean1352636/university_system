"""
Onboarding Manager

Handles onboarding/offboarding templates, task assignments,
and progress tracking for new and departing staff.
"""

from __future__ import annotations

import logging
import re
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

#: Marks the buddy on an onboarding assignment's notes.
BUDDY_NOTE = 'Buddy: '

TEMPLATE_FIELDS = ('name', 'description', 'role', 'department', 'template_type',
                   'estimated_days', 'is_active')


def _task_owner(conn, assigned_to_role: Optional[str], staff: str) -> Optional[str]:
    """Who does a task: the new starter / leaver ('employee'), their line
    manager ('manager'); anything else (HR, IT, facilities) is left to HR's
    queue (None)."""
    role = (assigned_to_role or 'employee').strip().lower()
    if role in ('employee', 'staff', 'self'):
        return staff
    if role in ('manager', 'line_manager'):
        return access.manager_of(staff, conn)
    return None


def _contract_on_file(staff: str) -> bool:
    """Is a signed contract linked in Document Manager? (Unknown: yes.)"""
    try:
        from education_system.systems.university.services.bus.document_bus import has_document
        return bool(has_document("contract", staff, document_type="contract"))
    except Exception:
        logger.debug("Contract check unavailable", exc_info=True)
        return True


def _task_row(conn, progress_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute('''
        SELECT p.*, t.title, t.description, t.category, t.assigned_to_role, t.is_required,
               a.user_id AS staff_user, a.status AS assignment_status, te.template_type
        FROM onboarding_task_progress p
        JOIN onboarding_template_tasks t ON p.task_id = t.task_id
        JOIN onboarding_assignments a ON p.assignment_id = a.assignment_id
        JOIN onboarding_templates te ON a.template_id = te.template_id
        WHERE p.progress_id = ?
    ''', (progress_id,)).fetchone()
    return dict(row) if row else None


def _may_do_task(actor: Any, task: Dict[str, Any], conn) -> bool:
    """HR, the task's owner, or — for an unowned employee task — the new
    starter themselves."""
    me = people.me(actor)
    if access.is_hr(actor, conn):
        return True
    if task.get('assigned_to'):
        return people.key(task['assigned_to'], conn) == me
    role = (task.get('assigned_to_role') or 'employee').lower()
    return role in ('employee', 'staff', 'self') and people.key(task['staff_user'], conn) == me


class OnboardingManager:
    """Manager for onboarding/offboarding processes."""

    @staticmethod
    def get_templates(template_type: Optional[str] = None,
                      active_only: bool = True) -> List[Dict[str, Any]]:
        """Get onboarding templates."""
        with get_connection() as conn:
            query = '''
                SELECT t.*, (SELECT COUNT(*) FROM onboarding_template_tasks k
                             WHERE k.template_id = t.template_id) AS task_count
                FROM onboarding_templates t WHERE 1=1
            '''
            params = []
            if active_only:
                query += ' AND t.is_active = 1'
            if template_type:
                query += ' AND t.template_type = ?'
                params.append(template_type)
            query += ' ORDER BY t.name'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_template(template_id: int) -> Optional[Dict[str, Any]]:
        """Get a template by ID."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM onboarding_templates WHERE template_id = ?
            ''', (template_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def create_template(name: str, created_by: Optional[str] = None, actor: Any = None,
                        **data) -> int:
        """Create a new onboarding template (with ``actor``: HR only)."""
        if not str(name or '').strip():
            raise ValueError("Template name is required")
        with transaction() as conn:
            if actor is not None:
                created_by = people.require_hr(actor, conn, "manage onboarding templates")
            cursor = conn.execute('''
                INSERT INTO onboarding_templates (
                    name, description, role, department,
                    template_type, estimated_days, is_active, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, data.get('description'), data.get('role'),
                  data.get('department'), data.get('template_type', 'onboarding'),
                  data.get('estimated_days', 30), data.get('is_active', 1), created_by))
            return cursor.lastrowid

    @staticmethod
    def update_template(template_id: int, actor: Any = None, **data) -> bool:
        """Change a template (with ``actor``: HR only)."""
        changes = {k: v for k, v in data.items() if k in TEMPLATE_FIELDS}
        if 'name' in changes and not str(changes['name'] or '').strip():
            raise ValueError("Template name is required")
        if not changes:
            return False
        with transaction() as conn:
            if actor is not None:
                people.require_hr(actor, conn, "manage onboarding templates")
            cur = conn.execute('UPDATE onboarding_templates SET ' +
                               ', '.join(validate_identifier(c, "column") + ' = ?' for c in changes) +
                               ', updated_at = ? WHERE template_id = ?',
                               list(changes.values()) + [datetime.now().isoformat(), template_id])
            return bool(cur.rowcount)

    @staticmethod
    def list_templates(actor: Any = None) -> List[Dict[str, Any]]:
        """Every template (active or not) with its task count (with
        ``actor``: HR only)."""
        with get_connection() as conn:
            if actor is not None:
                people.require_hr(actor, conn, "manage onboarding templates")
            rows = conn.execute('''
                SELECT t.*, (SELECT COUNT(*) FROM onboarding_template_tasks k
                             WHERE k.template_id = t.template_id) AS task_count
                FROM onboarding_templates t ORDER BY t.name
            ''').fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_template_tasks(template_id: int) -> List[Dict[str, Any]]:
        """Get tasks for a template."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM onboarding_template_tasks
                WHERE template_id = ? ORDER BY order_num, task_id
            ''', (template_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def add_template_task(template_id: int, title: str, actor: Any = None, **data) -> int:
        """Add a task to a template (``order_num`` defaults to last; with
        ``actor``: HR only)."""
        if not str(title or '').strip():
            raise ValueError("Task title is required")
        with transaction() as conn:
            if actor is not None:
                people.require_hr(actor, conn, "manage onboarding templates")
            if data.get('order_num') is None:
                data['order_num'] = (conn.execute(
                    'SELECT MAX(order_num) FROM onboarding_template_tasks WHERE template_id = ?',
                    (template_id,)).fetchone()[0] or 0) + 1
            cursor = conn.execute('''
                INSERT INTO onboarding_template_tasks (
                    template_id, title, description, category,
                    assigned_to_role, due_days, is_required, order_num
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (template_id, title, data.get('description'),
                  data.get('category', 'general'),
                  data.get('assigned_to_role', 'employee'),
                  data.get('due_days', 0), data.get('is_required', 1),
                  data.get('order_num', 0)))
            return cursor.lastrowid

    @staticmethod
    def delete_template_task(task_id: int, actor: Any = None) -> bool:
        """Remove a task from a template (with ``actor``: HR only). A task
        already given to someone stays (it would vanish from their list)."""
        with transaction() as conn:
            if actor is not None:
                people.require_hr(actor, conn, "manage onboarding templates")
            used = conn.execute('SELECT COUNT(*) FROM onboarding_task_progress WHERE task_id = ?',
                                (task_id,)).fetchone()[0]
            if used:
                raise ValueError(f"This task is part of {used} assignment(s) and cannot be deleted")
            return bool(conn.execute('DELETE FROM onboarding_template_tasks WHERE task_id = ?',
                                     (task_id,)).rowcount)

    @staticmethod
    def assign_template(user_id: str, template_id: int, assigned_by: str,
                        start_date: Optional[str] = None,
                        recipient_email: str = "",
                        staff_name: str = "",
                        department: str = "",
                        line_manager: str = "", actor: Any = None,
                        target_date: Optional[str] = None,
                        notes: Optional[str] = None) -> int:
        """Assign a template to a user. Each task goes to its owner
        (:func:`_task_owner`). With ``actor``: HR only, and the person must
        be known (username, users.id or employee number)."""
        start = start_date or datetime.now().strftime('%Y-%m-%d')
        with transaction() as conn:
            if actor is not None:
                assigned_by = people.require_hr(actor, conn, "assign onboarding")
                staff = access.staff_key(user_id, conn)
                if not staff:
                    raise ValueError(f"No staff member '{user_id}'")
                user_id = staff
                line_manager = line_manager or (access.manager_of(staff, conn) or "")
                recipient_email = recipient_email or (access.email_of(staff, conn) or "")
                staff_name = staff_name or access.display_name(staff, conn)
            template = conn.execute('''
                SELECT estimated_days FROM onboarding_templates WHERE template_id = ?
            ''', (template_id,)).fetchone()
            if actor is not None and not template:
                raise ValueError("No such template")
            estimated_days = template[0] if template else 30

            cursor = conn.execute('''
                INSERT INTO onboarding_assignments (
                    user_id, template_id, assigned_by, start_date,
                    target_completion_date, status, notes
                ) VALUES (?, ?, ?, ?, COALESCE(?, date(?, '+' || ? || ' days')), 'in_progress', ?)
            ''', (user_id, template_id, assigned_by, start, target_date, start, estimated_days,
                  notes))
            assignment_id = cursor.lastrowid

            # Create task progress records
            tasks = conn.execute('''
                SELECT task_id, due_days, assigned_to_role FROM onboarding_template_tasks
                WHERE template_id = ?
            ''', (template_id,)).fetchall()

            for task in tasks:
                conn.execute('''
                    INSERT INTO onboarding_task_progress (
                        assignment_id, task_id, status,
                        due_date, assigned_to
                    ) VALUES (?, ?, 'pending', date(?, '+' || ? || ' days'), ?)
                ''', (assignment_id, task[0], start, task[1] or 0,
                      _task_owner(conn, task[2], user_id)))
            if actor is not None:
                access.audit(conn, actor, 'assign_onboarding', user_id, 'onboarding_assignments',
                             assignment_id, {'template_id': template_id})

            log_activity('assign', 'onboarding', user_id=user_id,
                        details={'assignment_id': assignment_id})

            # Best-effort welcome email.
            try:
                from education_system.systems.university.domains.staff.domain.staff_hr.services.managers.leave_manager import (
                    _send_staff_hr_email,
                )
                tpl_meta = conn.execute(
                    "SELECT name FROM onboarding_templates WHERE template_id = ?",
                    (template_id,),
                ).fetchone()
                # Build a brief task summary so the email isn't empty even when
                # the caller didn't pre-compute one.
                task_rows = conn.execute(
                    """SELECT title FROM onboarding_template_tasks
                        WHERE template_id = ?
                        ORDER BY due_days, task_id
                        LIMIT 5""",
                    (template_id,),
                ).fetchall()
                if task_rows:
                    task_summary = "\n".join(f"  • {r[0]}" for r in task_rows)
                else:
                    task_summary = "  (your full task list is in the HR portal)"
                _send_staff_hr_email('onboarding_assigned', recipient_email, {
                    'staff_id':      user_id,
                    'staff_name':    staff_name or user_id,
                    'start_date':    start,
                    'department':    department or '(see HR portal)',
                    'line_manager':  line_manager or '(see HR portal)',
                    'template_name': (tpl_meta[0] if tpl_meta else f"Template #{template_id}"),
                    'assigned_by':   assigned_by,
                    'due_date':      f"{start} + {estimated_days} days",
                    'assignment_id': assignment_id,
                    'task_summary':  task_summary,
                })
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
            return assignment_id

    @staticmethod
    def start_onboarding(employee_id: str, template_id: int,
                         start_date: Optional[str] = None,
                         buddy_id: Optional[str] = None,
                         created_by: Optional[str] = None, actor: Any = None) -> int:
        """Start someone's onboarding from a template (:meth:`assign_template`).
        Both the new starter and the buddy must be known people; the buddy is
        recorded on the assignment's notes."""
        if start_date:
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
            except ValueError:
                raise ValueError("Start date must be in the form YYYY-MM-DD") from None
        notes = None
        with get_connection() as conn:
            staff = access.staff_key(employee_id, conn)
            if not staff:
                raise ValueError(f"No staff member '{employee_id}'")
            if buddy_id:
                buddy = access.staff_key(buddy_id, conn)
                if not buddy:
                    raise ValueError(f"No staff member '{buddy_id}'")
                if buddy == staff:
                    raise ValueError("Someone cannot be their own buddy")
                notes = f"{BUDDY_NOTE}{buddy}"
        return OnboardingManager.assign_template(
            staff, template_id, created_by, start_date=start_date, notes=notes, actor=actor)

    @staticmethod
    def get_active_onboardings(actor: Any = None) -> List[Dict[str, Any]]:
        """Onboardings in progress with ``progress`` (percent of tasks done),
        the person's name and department, and their buddy (with ``actor``: HR
        only)."""
        rows = OnboardingManager.list_assignments(actor, 'onboarding', 'in_progress')
        with get_connection() as conn:
            for row in rows:
                user = conn.execute('SELECT first_name, last_name FROM users WHERE username = ?',
                                    (row['user_id'],)).fetchone()
                profile = conn.execute('SELECT department FROM staff_profiles WHERE user_id = ?',
                                       (row['user_id'],)).fetchone()
                row['first_name'] = user[0] if user else row['user_id']
                row['last_name'] = user[1] if user else ''
                row['department'] = profile[0] if profile else None
                row['progress'] = (row['done_tasks'] * 100 // row['total_tasks']
                                   if row['total_tasks'] else 0)
                found = re.search(re.escape(BUDDY_NOTE) + r'(\S+)', row.get('notes') or '')
                if found:
                    row['buddy_name'] = access.display_name(found.group(1), conn)
        return rows

    @staticmethod
    def get_assignments(user_id: str,
                        status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get onboarding assignments for a user."""
        with get_connection() as conn:
            query = '''
                SELECT oa.*, ot.name as template_name, ot.template_type
                FROM onboarding_assignments oa
                JOIN onboarding_templates ot ON oa.template_id = ot.template_id
                WHERE oa.user_id = ?
            '''
            params = [user_id]
            if status:
                query += ' AND oa.status = ?'
                params.append(status)
            query += ' ORDER BY oa.start_date DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_task_progress(assignment_id: int) -> List[Dict[str, Any]]:
        """Get task progress for an assignment."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT tp.*, tt.title, tt.description, tt.category,
                       tt.assigned_to_role, tt.is_required
                FROM onboarding_task_progress tp
                JOIN onboarding_template_tasks tt ON tp.task_id = tt.task_id
                WHERE tp.assignment_id = ?
                ORDER BY tt.order_num, tt.task_id
            ''', (assignment_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_assignment(assignment_id: int, actor: Any = None) -> Optional[Dict[str, Any]]:
        """One assignment with its template and task counts (with ``actor``:
        HR or the person being on/offboarded)."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT a.*, t.name AS template_name, t.template_type,
                       (SELECT COUNT(*) FROM onboarding_task_progress p
                        WHERE p.assignment_id = a.assignment_id) AS total_tasks,
                       (SELECT COUNT(*) FROM onboarding_task_progress p
                        WHERE p.assignment_id = a.assignment_id AND p.status = 'completed') AS done_tasks
                FROM onboarding_assignments a
                JOIN onboarding_templates t ON a.template_id = t.template_id
                WHERE a.assignment_id = ?
            ''', (assignment_id,)).fetchone()
            if row and actor is not None and not access.is_hr(actor, conn) and \
                    people.key(row['user_id'], conn) != people.me(actor):
                raise PermissionError("You cannot see this onboarding")
            return dict(row) if row else None

    @staticmethod
    def get_assignment_tasks(assignment_id: int, actor: Any) -> List[Dict[str, Any]]:
        """An assignment's checklist (HR or the person it is for)."""
        if OnboardingManager.get_assignment(assignment_id, actor=actor) is None:
            raise ValueError("No such onboarding")
        return OnboardingManager.get_task_progress(assignment_id)

    @staticmethod
    def update_assignment(assignment_id: int, actor: Any, notes: Optional[str] = None,
                          target_date: Optional[str] = None) -> bool:
        """HR: add a progress note (appended, dated) or move the target date."""
        with transaction() as conn:
            me = people.require_hr(actor, conn, "update onboarding")
            row = conn.execute('SELECT user_id, notes FROM onboarding_assignments '
                               'WHERE assignment_id = ?', (assignment_id,)).fetchone()
            if not row:
                raise ValueError("No such onboarding")
            if target_date:
                datetime.strptime(target_date, '%Y-%m-%d')
            text = row['notes'] or ''
            if notes:
                stamp = f"[{datetime.now():%Y-%m-%d} {me}] {notes}"
                text = f"{text}\n{stamp}" if text else stamp
            conn.execute('''
                UPDATE onboarding_assignments
                SET notes = ?, target_completion_date = COALESCE(?, target_completion_date),
                    updated_at = ?
                WHERE assignment_id = ?
            ''', (text, target_date, datetime.now().isoformat(), assignment_id))
            access.audit(conn, actor, 'update_onboarding', row['user_id'], 'onboarding_assignments',
                         assignment_id, {'target_date': target_date, 'note': bool(notes)})
            return True

    @staticmethod
    def complete_assignment(assignment_id: int, actor: Any) -> bool:
        """HR: close an assignment. Every required task must be done and, for
        onboarding, the signed contract must be on file."""
        with transaction() as conn:
            people.require_hr(actor, conn, "complete onboarding")
            row = conn.execute('''
                SELECT a.status, COALESCE(a.staff_id, a.user_id) AS staff, a.user_id, t.template_type
                FROM onboarding_assignments a
                JOIN onboarding_templates t ON a.template_id = t.template_id
                WHERE a.assignment_id = ?
            ''', (assignment_id,)).fetchone()
            if not row:
                raise ValueError("No such onboarding")
            if row['status'] == 'completed':
                raise ValueError("Already completed")
            left = conn.execute('''
                SELECT COUNT(*) FROM onboarding_task_progress tp
                JOIN onboarding_template_tasks tt ON tp.task_id = tt.task_id
                WHERE tp.assignment_id = ? AND tt.is_required = 1 AND tp.status != 'completed'
            ''', (assignment_id,)).fetchone()[0]
            if left:
                raise ValueError(f"{left} required task(s) are still open")
            if (row['template_type'] or 'onboarding') == 'onboarding' and \
                    not _contract_on_file(row['staff']):
                raise ValueError("No signed contract is on file in Document Manager")
            conn.execute('''
                UPDATE onboarding_assignments
                SET status = 'completed', actual_completion_date = ?, updated_at = ?
                WHERE assignment_id = ?
            ''', (datetime.now().strftime('%Y-%m-%d'), datetime.now().isoformat(), assignment_id))
            access.audit(conn, actor, 'complete_onboarding', row['user_id'], 'onboarding_assignments',
                         assignment_id, None)
            return True

    @staticmethod
    def _finish(conn, progress_id: int, completed_by: str, notes: Optional[str]) -> Dict[str, Any]:
        conn.execute('''
            UPDATE onboarding_task_progress
            SET status = 'completed', completed_by = ?,
                completed_date = ?, notes = COALESCE(?, notes), updated_at = ?
            WHERE progress_id = ?
        ''', (completed_by, datetime.now().isoformat(), notes,
              datetime.now().isoformat(), progress_id))
        result = {'assignment_completed': False, 'contract_missing': False}
        progress = conn.execute('''
            SELECT tp.assignment_id, COALESCE(a.staff_id, a.user_id), t.template_type
            FROM onboarding_task_progress tp
            JOIN onboarding_assignments a ON tp.assignment_id = a.assignment_id
            JOIN onboarding_templates t ON a.template_id = t.template_id
            WHERE tp.progress_id = ?
        ''', (progress_id,)).fetchone()
        if not progress:
            return result
        # Check if all required tasks are complete
        incomplete = conn.execute('''
            SELECT COUNT(*) FROM onboarding_task_progress tp
            JOIN onboarding_template_tasks tt ON tp.task_id = tt.task_id
            WHERE tp.assignment_id = ?
              AND tt.is_required = 1 AND tp.status != 'completed'
        ''', (progress[0],)).fetchone()[0]
        if incomplete:
            return result
        # A new starter is not finished until their signed contract is on
        # file in Document Manager.
        if (progress[2] or 'onboarding') == 'onboarding' and not _contract_on_file(progress[1]):
            result['contract_missing'] = True
            return result
        conn.execute('''
            UPDATE onboarding_assignments
            SET status = 'completed', actual_completion_date = ?,
                updated_at = ?
            WHERE assignment_id = ? AND status != 'completed'
        ''', (datetime.now().isoformat()[:10], datetime.now().isoformat(), progress[0]))
        result['assignment_completed'] = True
        return result

    @staticmethod
    def complete_task(progress_id: int, completed_by: str,
                      notes: Optional[str] = None, actor: Any = None) -> bool:
        """Mark a task as complete (with ``actor``: its owner, the new starter
        for their own unowned tasks, or HR). The assignment completes when
        every required task is done (and, for onboarding, the contract is on
        file)."""
        return bool(OnboardingManager.complete_task_for(actor, progress_id, notes,
                                                        completed_by=completed_by)
                    is not None)

    @staticmethod
    def complete_task_for(actor: Any, progress_id: int, notes: Optional[str] = None,
                          completed_by: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """:meth:`complete_task`, returning ``{'assignment_completed',
        'contract_missing'}`` (None when there is no such task)."""
        with transaction() as conn:
            task = _task_row(conn, progress_id)
            if not task:
                return None
            if actor is not None:
                if not _may_do_task(actor, task, conn):
                    raise PermissionError("Only the task's owner or HR can complete it")
                if task['status'] == 'completed':
                    raise ValueError("Task is already completed")
                completed_by = people.me(actor)
            result = OnboardingManager._finish(conn, progress_id, completed_by, notes)
        log_activity('update', 'onboarding_task', details={'progress_id': progress_id,
                                                           'action': 'completed'})
        return result

    @staticmethod
    def get_my_tasks(actor: Any, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """The signed-in person's onboarding tasks: every task of their own
        onboarding/offboarding, and tasks they own for someone else."""
        with get_connection() as conn:
            me = people.me(actor)
            query = '''
                SELECT p.*, t.title, t.description, t.category, t.assigned_to_role,
                       te.name AS template_name, a.user_id AS staff_user
                FROM onboarding_task_progress p
                JOIN onboarding_template_tasks t ON p.task_id = t.task_id
                JOIN onboarding_assignments a ON p.assignment_id = a.assignment_id
                JOIN onboarding_templates te ON a.template_id = te.template_id
                WHERE (a.user_id = ? OR p.assigned_to = ?)
            '''
            params: list = [me, me]
            if status:
                query += ' AND p.status = ?'
                params.append(status)
            rows = conn.execute(query + ' ORDER BY p.due_date', params).fetchall()
            out = []
            for row in rows:
                data = dict(row)
                data['can_complete'] = data['status'] != 'completed' and _may_do_task(actor, data, conn)
                out.append(data)
            return out

    @staticmethod
    def get_task(progress_id: int, actor: Any = None) -> Optional[Dict[str, Any]]:
        """One task with its template details (with ``actor``: the new
        starter, the task's owner or HR)."""
        with get_connection() as conn:
            task = _task_row(conn, progress_id)
            if task and actor is not None and not _may_do_task(actor, task, conn) and \
                    people.key(task['staff_user'], conn) != people.me(actor):
                raise PermissionError("You cannot see this task")
            return task

    @staticmethod
    def list_assignments(actor: Any = None, template_type: Optional[str] = None,
                         status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Every assignment with task progress (with ``actor``: HR only)."""
        with get_connection() as conn:
            if actor is not None:
                people.require_hr(actor, conn, "see onboarding assignments")
            query = '''
                SELECT a.*, t.name AS template_name, t.template_type,
                       (SELECT COUNT(*) FROM onboarding_task_progress p
                        WHERE p.assignment_id = a.assignment_id) AS total_tasks,
                       (SELECT COUNT(*) FROM onboarding_task_progress p
                        WHERE p.assignment_id = a.assignment_id AND p.status = 'completed') AS done_tasks
                FROM onboarding_assignments a
                JOIN onboarding_templates t ON a.template_id = t.template_id
                WHERE 1=1
            '''
            params: list = []
            if template_type:
                query += ' AND t.template_type = ?'
                params.append(template_type)
            if status:
                query += ' AND a.status = ?'
                params.append(status)
            rows = conn.execute(query + ' ORDER BY a.start_date DESC', params).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def progress_overview(actor: Any = None) -> Dict[str, Any]:
        """Counts for the HR dashboard and the ten latest completions."""
        month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')
        with get_connection() as conn:
            if actor is not None:
                people.require_hr(actor, conn, "see onboarding progress")

            def active(kind):
                return conn.execute('''
                    SELECT COUNT(*) FROM onboarding_assignments a
                    JOIN onboarding_templates t ON a.template_id = t.template_id
                    WHERE a.status = 'in_progress' AND t.template_type = ?
                ''', (kind,)).fetchone()[0]

            recent = conn.execute('''
                SELECT a.user_id, t.name AS template_name, t.template_type,
                       a.actual_completion_date,
                       julianday(a.actual_completion_date) - julianday(a.start_date) AS days
                FROM onboarding_assignments a
                JOIN onboarding_templates t ON a.template_id = t.template_id
                WHERE a.status = 'completed'
                ORDER BY a.actual_completion_date DESC LIMIT 10
            ''').fetchall()
            return {
                'active_onboarding': active('onboarding'),
                'active_offboarding': active('offboarding'),
                'completed_this_month': conn.execute(
                    "SELECT COUNT(*) FROM onboarding_assignments WHERE status = 'completed' "
                    "AND actual_completion_date >= ?", (month_start,)).fetchone()[0],
                'average_days': conn.execute(
                    "SELECT AVG(julianday(actual_completion_date) - julianday(start_date)) "
                    "FROM onboarding_assignments WHERE status = 'completed' "
                    "AND actual_completion_date IS NOT NULL").fetchone()[0] or 0,
                'recent': [dict(r) for r in recent],
            }

    @staticmethod
    def get_pending_tasks(user_id: Optional[str] = None,
                          assigned_to: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get pending onboarding tasks."""
        with get_connection() as conn:
            query = '''
                SELECT tp.*, tt.title, tt.description, tt.category,
                       oa.user_id, u.first_name, u.last_name
                FROM onboarding_task_progress tp
                JOIN onboarding_template_tasks tt ON tp.task_id = tt.task_id
                JOIN onboarding_assignments oa ON tp.assignment_id = oa.assignment_id
                LEFT JOIN users u ON u.username = oa.user_id
                WHERE tp.status = 'pending' AND oa.status = 'in_progress'
            '''
            params = []
            if user_id:
                query += ' AND oa.user_id = ?'
                params.append(user_id)
            if assigned_to:
                query += ' AND tp.assigned_to = ?'
                params.append(assigned_to)
            query += ' ORDER BY tp.due_date'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_overdue_tasks() -> List[Dict[str, Any]]:
        """Get overdue onboarding tasks."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT tp.*, tt.title, oa.user_id, u.first_name, u.last_name
                FROM onboarding_task_progress tp
                JOIN onboarding_template_tasks tt ON tp.task_id = tt.task_id
                JOIN onboarding_assignments oa ON tp.assignment_id = oa.assignment_id
                LEFT JOIN users u ON u.username = oa.user_id
                WHERE tp.status = 'pending'
                  AND tp.due_date < date('now')
                  AND oa.status = 'in_progress'
                ORDER BY tp.due_date
            ''').fetchall()
            return [dict(row) for row in rows]
