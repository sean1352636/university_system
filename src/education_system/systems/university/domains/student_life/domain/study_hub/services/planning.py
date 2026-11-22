"""
AI Study Companion Service

Study plans built from the student's real exams, deadlines, marks and module
topics; SM-2 flashcards that Claude (or the student's notes) can write;
concept explanations from Claude, grounded in the module's records when no
AI is configured; reminders; and a staff view.

The rules live in the sibling modules — ``plan_builder`` (plans),
``spaced_repetition`` (SM-2), ``companion_ai`` (Claude and its fallback),
``study_context`` (the student's records), ``companion_reminders`` and
``companion_staff``. This class is the one entry point the GUI, CLI and API
use, and owns the transactions.

Methods that change a student's rows take an optional ``student_id``: when
given, the row must belong to it (``PermissionError`` otherwise). The GUI,
CLI and API always pass it.
"""

from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple
import json

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.database.schemas import (
    study_companion_schema as schema,
)
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.domains.student_life.domain.study_hub.services import (
    companion_ai, companion_reminders, companion_staff, plan_builder, spaced_repetition,
    study_context,
)

MAX_QUESTION = 500
MAX_ANSWER = 2000


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _day(value, label="Date") -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        raise ValueError(f"{label} must be YYYY-MM-DD") from None


def _dicts(cur) -> List[Dict]:
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def _send_emails(emails) -> int:
    if not emails:
        return 0
    from education_system.systems.university.application.teaching.occurrences import send_emails
    return send_emails(emails)


class AIStudyService:
    """Service for AI-powered study assistance."""

    def __init__(self):
        """Initialize the AI Study Service."""
        self._ensure_tables_exist()
        from education_system.systems.university.domains.student_life.domain.study_hub.services import (
            ProfileService, SessionService,
        )
        self.profiles = ProfileService()
        self.sessions = SessionService()

    def _ensure_tables_exist(self):
        """Apply the companion schema (migration ``d8f0a2c4e6b9``) once per
        database file. Used to run four CREATE TABLEs and write an activity
        row on every construction."""
        with get_connection() as conn:
            schema.apply_to_connection(conn)

    # ========== ownership ==========

    @staticmethod
    def _owner_of(conn, table, key, value) -> Optional[str]:
        if table == "study_plan_tasks":
            row = conn.execute("SELECT p.student_id FROM study_plan_tasks t JOIN study_plans p "
                               "ON p.plan_id = t.plan_id WHERE t.task_id = ?", (value,)).fetchone()
        else:
            row = conn.execute(f"SELECT student_id FROM {table} WHERE {key} = ?",  # nosec B608
                               (value,)).fetchone()
        return str(row[0]) if row else None

    def _check(self, conn, table, key, value, student_id, what) -> str:
        owner = self._owner_of(conn, table, key, value)
        if owner is None:
            raise ValueError(f"No such {what}")
        if student_id is not None and owner != str(student_id):
            raise PermissionError(f"That {what} belongs to someone else")
        return owner

    def owner_of_plan(self, plan_id) -> Optional[str]:
        with get_connection() as conn:
            return self._owner_of(conn, "study_plans", "plan_id", plan_id)

    def owner_of_task(self, task_id) -> Optional[str]:
        with get_connection() as conn:
            return self._owner_of(conn, "study_plan_tasks", "task_id", task_id)

    def owner_of_flashcard(self, flashcard_id) -> Optional[str]:
        with get_connection() as conn:
            return self._owner_of(conn, "flashcards", "flashcard_id", flashcard_id)

    def owner_of_explanation(self, explanation_id) -> Optional[str]:
        with get_connection() as conn:
            return self._owner_of(conn, "concept_explanations", "explanation_id", explanation_id)

    # ========== the student's records ==========

    def available_modules(self, student_id: str, all_active: bool = False) -> List[Dict]:
        """Modules to plan for: the student's enrolments, or (``all_active``,
        for staff) every active module."""
        with get_connection() as conn:
            if all_active and study_context._has_table(conn, "modules"):
                active = ("COALESCE(is_active, 1) = 1 AND "
                          if "is_active" in study_context._columns(conn, "modules") else "")
                return _dicts(conn.execute(
                    "SELECT DISTINCT module_code, COALESCE(module_name, module_code) AS module_name "
                    "FROM modules WHERE " + active + "TRIM(COALESCE(module_code, '')) <> '' "
                    "ORDER BY module_code"))
            return study_context.enrolled_modules(conn, student_id)

    def exam_for_module(self, student_id: str, module_code: str) -> Optional[Dict]:
        """The student's next published sitting for a module."""
        with get_connection() as conn:
            return study_context.next_exam(conn, student_id, module_code)

    def upcoming(self, student_id: str, days: int = 28) -> Dict:
        """Exams and deadlines in the next ``days`` days."""
        today = date.today()
        end = today + timedelta(days=days)
        with get_connection() as conn:
            return {"exams": study_context.upcoming_exams(conn, student_id, today, end),
                    "deadlines": study_context.upcoming_deadlines(conn, student_id, today, end)}

    # ========== Study Plan Generation ==========

    def generate_study_plan(self, student_id: str, course_id: Optional[str],
                           exam_date: str, hours_per_day: float = 2,
                           plan_name: Optional[str] = None, today: Optional[date] = None) -> Dict:
        """
        Generate a personalized study plan based on upcoming exams.

        Args:
            student_id: Student's ID
            course_id: Module code (optional; ``None`` plans every module with an exam)
            exam_date: Exam date (YYYY-MM-DD format)
            hours_per_day: Hours available per day
            plan_name: Optional name (default "Exam Prep - <module> - <date>")

        Returns:
            ``{plan_id, total_hours, days_until_exam, tasks_generated, warnings, exam}``
        """
        today = today or date.today()
        exam_day = _day(exam_date, "Exam date")
        days_until_exam = (exam_day - today).days
        if days_until_exam < 0:
            raise ValueError("Exam date must be in the future")
        hours = float(hours_per_day)
        if not 0.25 <= hours <= 12:
            raise ValueError("Hours per day must be between 0.25 and 12")
        course_id = (course_id or "").strip() or None

        with transaction() as conn:
            built = plan_builder.build(conn, student_id, course_id, today, exam_day, hours)
            tasks = built["tasks"]
            minutes = sum(t["duration"] for t in tasks)
            name = (plan_name or "").strip() or (
                f"Exam Prep - {course_id + ' - ' if course_id else ''}{exam_day.isoformat()}")
            now = _now()
            cursor = conn.execute("""
                INSERT INTO study_plans
                (student_id, course_id, plan_name, start_date, end_date, total_hours,
                 exam_date, exam_id, hours_per_day, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active', ?, ?)
            """, (str(student_id), course_id, name, today.isoformat(), exam_day.isoformat(),
                  round(minutes / 60), exam_day.isoformat(),
                  (built["exam"] or {}).get("exam_id"), hours, now, now))
            plan_id = cursor.lastrowid
            for task in tasks:
                conn.execute("""
                    INSERT INTO study_plan_tasks
                    (plan_id, task_title, task_description, scheduled_date, duration_minutes,
                     priority, module_code, topic, task_kind, status, original_date, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                """, (plan_id, task['title'], task['description'], task['date'],
                      task['duration'], task['priority'], task.get('module_code'),
                      task.get('topic'), task.get('kind', 'custom'), task['date'], now))

        log_activity('create', 'study_plan',
                     details={'plan_id': plan_id, 'student_id': student_id, 'exam_date': exam_date})
        return {
            'plan_id': plan_id,
            'total_hours': round(minutes / 60),
            'days_until_exam': days_until_exam,
            'tasks_generated': len(tasks),
            'warnings': built["warnings"],
            'exam': built["exam"],
        }

    def create_plan(self, student_id: str, plan_name: str, end_date: str,
                    course_id: Optional[str] = None, start_date: Optional[str] = None,
                    notes: Optional[str] = None) -> int:
        """An empty plan the student fills with their own tasks."""
        name = (plan_name or "").strip()
        if not name:
            raise ValueError("Give the plan a name")
        start = _day(start_date or date.today(), "Start date")
        end = _day(end_date, "End date")
        if end < start:
            raise ValueError("The end date is before the start date")
        now = _now()
        with transaction() as conn:
            cur = conn.execute(
                "INSERT INTO study_plans (student_id, course_id, plan_name, start_date, end_date, "
                "total_hours, exam_date, status, notes, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 0, ?, 'Active', ?, ?, ?)",
                (str(student_id), (course_id or None), name, start.isoformat(), end.isoformat(),
                 end.isoformat(), notes, now, now))
            plan_id = cur.lastrowid
        log_activity('create', 'study_plan', details={'plan_id': plan_id, 'student_id': student_id})
        return plan_id

    def _refresh_status(self, conn, plan_id, today=None):
        """Complete a plan whose tasks are all done or whose exam has passed."""
        today = (today or date.today()).isoformat()
        row = conn.execute("SELECT status, end_date FROM study_plans WHERE plan_id = ?",
                           (plan_id,)).fetchone()
        if not row or (row[0] or "Active") != "Active":
            return
        left = conn.execute("SELECT COUNT(*), SUM(CASE WHEN COALESCE(status, 'pending') = "
                            "'pending' THEN 1 ELSE 0 END) FROM study_plan_tasks WHERE plan_id = ?",
                            (plan_id,)).fetchone()
        total, pending = int(left[0] or 0), int(left[1] or 0)
        if (total and pending == 0) or (row[1] and str(row[1])[:10] < today):
            conn.execute("UPDATE study_plans SET status = 'Completed', completed_at = ?, "
                         "updated_at = ? WHERE plan_id = ?", (_now(), _now(), plan_id))

    def _recount(self, conn, plan_id):
        minutes = conn.execute("SELECT COALESCE(SUM(duration_minutes), 0) FROM study_plan_tasks "
                               "WHERE plan_id = ? AND COALESCE(status, 'pending') <> 'skipped'",
                               (plan_id,)).fetchone()[0]
        conn.execute("UPDATE study_plans SET total_hours = ?, updated_at = ? WHERE plan_id = ?",
                     (round((minutes or 0) / 60), _now(), plan_id))

    def get_study_plan(self, plan_id: int) -> Optional[Dict]:
        """Retrieve a study plan by ID, with its tasks and progress."""
        with get_connection() as conn:
            plan_row = conn.execute("""
                SELECT * FROM study_plans WHERE plan_id = ?
            """, (plan_id,)).fetchone()

            if not plan_row:
                return None

            tasks = conn.execute("""
                SELECT * FROM study_plan_tasks
                WHERE plan_id = ?
                ORDER BY scheduled_date,
                         CASE priority WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END,
                         task_id
            """, (plan_id,)).fetchall()

            tasks = [dict(task) for task in tasks]
            done = sum(1 for t in tasks if (t.get('status') or 'pending') == 'done')
            today = date.today().isoformat()
            overdue = sum(1 for t in tasks if (t.get('status') or 'pending') == 'pending'
                          and str(t.get('scheduled_date'))[:10] < today)
            return {
                'plan': dict(plan_row),
                'tasks': tasks,
                'progress': {'total': len(tasks), 'done': done, 'overdue': overdue,
                             'percent': round(100.0 * done / len(tasks), 1) if tasks else 0.0},
            }

    def get_student_study_plans(self, student_id: str, include_archived: bool = True) -> List[Dict]:
        """Get all study plans for a student (statuses brought up to date)."""
        with transaction() as conn:
            for (pid,) in conn.execute("SELECT plan_id FROM study_plans WHERE student_id = ? "
                                       "AND COALESCE(status, 'Active') = 'Active'",
                                       (str(student_id),)).fetchall():
                self._refresh_status(conn, pid)
        with get_connection() as conn:
            sql = ("SELECT p.*, (SELECT COUNT(*) FROM study_plan_tasks t WHERE t.plan_id = p.plan_id) "
                   "AS task_count, (SELECT COUNT(*) FROM study_plan_tasks t WHERE t.plan_id = "
                   "p.plan_id AND COALESCE(t.status, 'pending') = 'done') AS done_count "
                   "FROM study_plans p WHERE p.student_id = ?")
            if not include_archived:
                sql += " AND COALESCE(p.status, 'Active') <> 'Archived'"
            plans = conn.execute(sql + " ORDER BY p.created_at DESC, p.plan_id DESC",
                                 (str(student_id),)).fetchall()

            return [dict(plan) for plan in plans]

    def update_plan(self, plan_id: int, student_id: Optional[str] = None, *,
                    plan_name: Optional[str] = None, exam_date: Optional[str] = None,
                    notes: Optional[str] = None, course_id: Optional[str] = None) -> Dict:
        """Rename a plan, move its exam date, or change its notes or module.

        Moving the exam earlier skips tasks that now fall on or after it;
        moving it later leaves the existing tasks (use Reschedule Missed or
        add tasks to fill the extra days).
        """
        with transaction() as conn:
            self._check(conn, "study_plans", "plan_id", plan_id, student_id, "study plan")
            sets, params = [], []
            if plan_name is not None:
                if not plan_name.strip():
                    raise ValueError("Give the plan a name")
                sets.append("plan_name = ?")
                params.append(plan_name.strip())
            if notes is not None:
                sets.append("notes = ?")
                params.append(notes.strip() or None)
            if course_id is not None:
                sets.append("course_id = ?")
                params.append(course_id.strip() or None)
            skipped = 0
            if exam_date is not None:
                new_end = _day(exam_date, "Exam date").isoformat()
                sets += ["end_date = ?", "exam_date = ?"]
                params += [new_end, new_end]
                skipped = conn.execute(
                    "UPDATE study_plan_tasks SET status = 'skipped', updated_at = ?, notes = "
                    "COALESCE(notes || ' ', '') || '(after the new exam date)' WHERE plan_id = ? "
                    "AND COALESCE(status, 'pending') = 'pending' AND scheduled_date >= ?",
                    (_now(), plan_id, new_end)).rowcount
            if sets:
                conn.execute("UPDATE study_plans SET " + ", ".join(sets) + ", updated_at = ? "
                             "WHERE plan_id = ?", (*params, _now(), plan_id))
            self._recount(conn, plan_id)
        log_activity('update', 'study_plan', details={'plan_id': plan_id})
        return {"plan_id": plan_id, "tasks_skipped": skipped}

    def set_plan_status(self, plan_id: int, status: str, student_id: Optional[str] = None) -> str:
        """Active / Paused / Completed / Archived."""
        status = (status or "").strip().title()
        if status not in schema.PLAN_STATUSES:
            raise ValueError("Status is one of: " + ", ".join(schema.PLAN_STATUSES))
        now = _now()
        with transaction() as conn:
            self._check(conn, "study_plans", "plan_id", plan_id, student_id, "study plan")
            conn.execute(
                "UPDATE study_plans SET status = ?, updated_at = ?, "
                "completed_at = CASE WHEN ? = 'Completed' THEN COALESCE(completed_at, ?) "
                "ELSE completed_at END, "
                "archived_at = CASE WHEN ? = 'Archived' THEN ? ELSE NULL END WHERE plan_id = ?",
                (status, now, status, now, status, now, plan_id))
        log_activity('update', 'study_plan', details={'plan_id': plan_id, 'status': status})
        return status

    def delete_plan(self, plan_id: int, student_id: Optional[str] = None) -> bool:
        """Delete a plan and its tasks. Time already logged from its tasks
        stays in the student's study history."""
        with transaction() as conn:
            self._check(conn, "study_plans", "plan_id", plan_id, student_id, "study plan")
            conn.execute("DELETE FROM study_plan_tasks WHERE plan_id = ?", (plan_id,))
            conn.execute("DELETE FROM study_plans WHERE plan_id = ?", (plan_id,))
        log_activity('delete', 'study_plan', details={'plan_id': plan_id})
        return True

    # ========== Tasks ==========

    def add_task(self, plan_id: int, title: str, scheduled_date: str,
                 duration_minutes: int = 60, priority: str = "Medium",
                 description: Optional[str] = None, module_code: Optional[str] = None,
                 student_id: Optional[str] = None) -> int:
        title = (title or "").strip()
        if not title:
            raise ValueError("Give the task a title")
        priority = (priority or "Medium").strip().title()
        if priority not in plan_builder.PRIORITIES:
            raise ValueError("Priority is Low, Medium or High")
        minutes = int(duration_minutes)
        if not 5 <= minutes <= 720:
            raise ValueError("A task is 5 to 720 minutes")
        when = _day(scheduled_date).isoformat()
        with transaction() as conn:
            self._check(conn, "study_plans", "plan_id", plan_id, student_id, "study plan")
            cur = conn.execute(
                "INSERT INTO study_plan_tasks (plan_id, task_title, task_description, "
                "scheduled_date, duration_minutes, priority, module_code, task_kind, status, "
                "original_date, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'custom', 'pending', ?, ?)",
                (plan_id, title, (description or "").strip() or None, when, minutes, priority,
                 module_code or None, when, _now()))
            task_id = cur.lastrowid
            conn.execute("UPDATE study_plans SET status = 'Active', completed_at = NULL "
                         "WHERE plan_id = ? AND status = 'Completed'", (plan_id,))
            self._recount(conn, plan_id)
        return task_id

    def update_task(self, task_id: int, student_id: Optional[str] = None, *,
                    title: Optional[str] = None, scheduled_date: Optional[str] = None,
                    duration_minutes: Optional[int] = None, priority: Optional[str] = None,
                    description: Optional[str] = None, notes: Optional[str] = None) -> bool:
        sets, params = [], []
        if title is not None:
            if not title.strip():
                raise ValueError("Give the task a title")
            sets.append("task_title = ?")
            params.append(title.strip())
        if scheduled_date is not None:
            sets.append("scheduled_date = ?")
            params.append(_day(scheduled_date).isoformat())
        if duration_minutes is not None:
            if not 5 <= int(duration_minutes) <= 720:
                raise ValueError("A task is 5 to 720 minutes")
            sets.append("duration_minutes = ?")
            params.append(int(duration_minutes))
        if priority is not None:
            p = priority.strip().title()
            if p not in plan_builder.PRIORITIES:
                raise ValueError("Priority is Low, Medium or High")
            sets.append("priority = ?")
            params.append(p)
        if description is not None:
            sets.append("task_description = ?")
            params.append(description.strip() or None)
        if notes is not None:
            sets.append("notes = ?")
            params.append(notes.strip() or None)
        if not sets:
            return False
        with transaction() as conn:
            self._check(conn, "study_plan_tasks", "task_id", task_id, student_id, "task")
            conn.execute("UPDATE study_plan_tasks SET " + ", ".join(sets) + ", updated_at = ? "
                         "WHERE task_id = ?", (*params, _now(), task_id))
            plan_id = conn.execute("SELECT plan_id FROM study_plan_tasks WHERE task_id = ?",
                                   (task_id,)).fetchone()[0]
            self._recount(conn, plan_id)
        return True

    def reschedule_task(self, task_id: int, new_date: str, student_id: Optional[str] = None) -> str:
        when = _day(new_date).isoformat()
        with transaction() as conn:
            self._check(conn, "study_plan_tasks", "task_id", task_id, student_id, "task")
            conn.execute("UPDATE study_plan_tasks SET scheduled_date = ?, "
                         "original_date = COALESCE(original_date, scheduled_date), "
                         "rescheduled_count = COALESCE(rescheduled_count, 0) + 1, "
                         "status = CASE WHEN status = 'skipped' THEN 'pending' ELSE "
                         "COALESCE(status, 'pending') END, updated_at = ? WHERE task_id = ?",
                         (when, _now(), task_id))
        return when

    def delete_task(self, task_id: int, student_id: Optional[str] = None) -> bool:
        with transaction() as conn:
            self._check(conn, "study_plan_tasks", "task_id", task_id, student_id, "task")
            plan_id = conn.execute("SELECT plan_id FROM study_plan_tasks WHERE task_id = ?",
                                   (task_id,)).fetchone()[0]
            conn.execute("DELETE FROM study_plan_tasks WHERE task_id = ?", (task_id,))
            self._recount(conn, plan_id)
            self._refresh_status(conn, plan_id)
        return True

    def skip_task(self, task_id: int, student_id: Optional[str] = None) -> bool:
        with transaction() as conn:
            self._check(conn, "study_plan_tasks", "task_id", task_id, student_id, "task")
            conn.execute("UPDATE study_plan_tasks SET status = 'skipped', completed = 0, "
                         "updated_at = ? WHERE task_id = ?", (_now(), task_id))
            plan_id = conn.execute("SELECT plan_id FROM study_plan_tasks WHERE task_id = ?",
                                   (task_id,)).fetchone()[0]
            self._recount(conn, plan_id)
            self._refresh_status(conn, plan_id)
        return True

    def complete_study_task(self, task_id: int, student_id: Optional[str] = None) -> bool:
        """Mark a study task as completed, and count the time studied.

        Ticking off a plan task used to record nothing outside the plan,
        so working through an entire study plan left the student's
        streak and study statistics at zero.
        """
        with transaction() as conn:
            if student_id is not None:
                self._check(conn, "study_plan_tasks", "task_id", task_id, student_id, "task")
            task = conn.execute(
                "SELECT t.task_id, t.duration_minutes, t.task_title, t.plan_id, "
                "       COALESCE(t.module_code, p.course_id) AS course_id, "
                "       COALESCE(t.status, 'pending') AS status, p.student_id "
                "FROM study_plan_tasks t "
                "LEFT JOIN study_plans p ON p.plan_id = t.plan_id "
                "WHERE t.task_id = ?", (task_id,)).fetchone()
            if task is None:
                raise ValueError("No such task")
            already = task["status"] == "done"

            conn.execute("""
                UPDATE study_plan_tasks
                SET completed = 1, status = 'done', completed_at = COALESCE(completed_at, ?),
                    updated_at = ?
                WHERE task_id = ?
            """, (datetime.now().isoformat(), _now(), task_id))
            self._refresh_status(conn, task["plan_id"])

            log_activity('update', 'study_task', task_id=task_id,
                        details={'status': 'completed'})

        # Outside the transaction: a logging failure must not undo the
        # completion the student just recorded. A task ticked twice is
        # counted once.
        if not already and task["student_id"]:
            self.sessions.log(
                task["student_id"], minutes=int(task["duration_minutes"] or 0),
                module_code=task["course_id"], topic=task["task_title"],
                source="plan_task", source_id=task_id)
        return True

    def uncomplete_task(self, task_id: int, student_id: Optional[str] = None) -> bool:
        """Undo a completion (and the study time it logged)."""
        with transaction() as conn:
            self._check(conn, "study_plan_tasks", "task_id", task_id, student_id, "task")
            conn.execute("UPDATE study_plan_tasks SET completed = 0, status = 'pending', "
                         "completed_at = NULL, updated_at = ? WHERE task_id = ?", (_now(), task_id))
            plan_id = conn.execute("SELECT plan_id FROM study_plan_tasks WHERE task_id = ?",
                                   (task_id,)).fetchone()[0]
            conn.execute("UPDATE study_plans SET status = 'Active', completed_at = NULL "
                         "WHERE plan_id = ? AND status = 'Completed' AND end_date >= ?",
                         (plan_id, date.today().isoformat()))
            if study_context._has_table(conn, "study_sessions"):
                conn.execute("DELETE FROM study_sessions WHERE source = 'plan_task' "
                             "AND source_id = ?", (task_id,))
        return True

    def reschedule_missed(self, plan_id: int, student_id: Optional[str] = None,
                          today: Optional[date] = None) -> Dict:
        """Move the plan's missed (overdue, pending) tasks onto the remaining
        days before the exam, lightest day first. Tasks that cannot fit — the
        exam is today or past — are skipped. ``{moved, skipped}``."""
        today = today or date.today()
        with transaction() as conn:
            owner = self._check(conn, "study_plans", "plan_id", plan_id, student_id, "study plan")
            plan = conn.execute("SELECT end_date, hours_per_day FROM study_plans WHERE plan_id = ?",
                                (plan_id,)).fetchone()
            end = _day(plan[0]) if plan[0] else today
            missed = _dicts(conn.execute(
                "SELECT task_id, duration_minutes FROM study_plan_tasks WHERE plan_id = ? "
                "AND COALESCE(status, 'pending') = 'pending' AND scheduled_date < ? "
                "ORDER BY scheduled_date, task_id", (plan_id, today.isoformat())))
            days = [today + timedelta(days=i) for i in range((end - today).days)]
            if not days:
                for t in missed:
                    conn.execute("UPDATE study_plan_tasks SET status = 'skipped', updated_at = ? "
                                 "WHERE task_id = ?", (_now(), t["task_id"]))
                self._refresh_status(conn, plan_id)
                return {"moved": 0, "skipped": len(missed)}
            load = {d.isoformat(): 0 for d in days}
            load.update({k: v for k, v in study_context.planned_minutes(
                conn, owner, days[0], days[-1]).items() if k in load})
            for t in missed:
                target = min(load, key=lambda k: (load[k], k))
                load[target] += int(t["duration_minutes"] or 0)
                conn.execute("UPDATE study_plan_tasks SET scheduled_date = ?, "
                             "original_date = COALESCE(original_date, scheduled_date), "
                             "rescheduled_count = COALESCE(rescheduled_count, 0) + 1, "
                             "updated_at = ? WHERE task_id = ?", (target, _now(), t["task_id"]))
        log_activity('update', 'study_plan_reschedule',
                     details={'plan_id': plan_id, 'moved': len(missed)})
        return {"moved": len(missed), "skipped": 0}

    # ========== Flashcard System ==========

    @staticmethod
    def _card_text(question, answer, deck_name):
        question, answer = (question or "").strip(), (answer or "").strip()
        deck_name = (deck_name or "").strip()
        if not (deck_name and question and answer):
            raise ValueError("A card needs a deck, a question and an answer")
        if len(question) > MAX_QUESTION or len(answer) > MAX_ANSWER:
            raise ValueError(f"Questions are up to {MAX_QUESTION} characters and answers up "
                             f"to {MAX_ANSWER}")
        if len(deck_name) > 100:
            raise ValueError("Deck names are up to 100 characters")
        return question, answer, deck_name

    def create_flashcard(self, student_id: str, course_id: Optional[str],
                        deck_name: str, question: str, answer: str,
                        source: str = "manual", source_ref: Optional[str] = None) -> int:
        """
        Create a new flashcard for spaced repetition learning.

        Args:
            student_id: Student's ID
            course_id: Course ID (optional)
            deck_name: Name of the flashcard deck
            question: Question text
            answer: Answer text

        Returns:
            Flashcard ID
        """
        ids = self.create_flashcards(student_id, course_id, deck_name,
                                     [{"question": question, "answer": answer}],
                                     source=source, source_ref=source_ref)
        return ids[0]

    def create_flashcards(self, student_id: str, course_id: Optional[str], deck_name: str,
                          cards, source: str = "manual", source_ref: Optional[str] = None) -> List[int]:
        """Add several cards to a deck. New cards are due tomorrow."""
        if source not in schema.CARD_SOURCES:
            raise ValueError("Unknown card source")
        rows = [self._card_text(c.get("question"), c.get("answer"), deck_name) for c in cards]
        next_review = (date.today() + timedelta(days=1)).isoformat()
        ids = []
        with transaction() as conn:
            for question, answer, deck in rows:
                cursor = conn.execute("""
                    INSERT INTO flashcards
                    (student_id, course_id, deck_name, question, answer, next_review,
                     ease_factor, interval_days, repetitions, lapses, source, source_ref,
                     updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?, ?, ?)
                """, (str(student_id), (course_id or None), deck, question, answer, next_review,
                      spaced_repetition.DEFAULT_EASE, source, source_ref, _now()))
                ids.append(cursor.lastrowid)

        log_activity('create', 'flashcard',
                    details={'flashcards': len(ids), 'deck': deck_name, 'source': source})
        return ids

    def generate_flashcards(self, student_id: str, course_id: Optional[str], deck_name: str,
                            notes: str, count: int = 10) -> Dict:
        """Write cards from the student's notes (Claude, else definitions found
        in the notes) and add them to ``deck_name``. ``{created, cards, source}``."""
        result = companion_ai.cards_from_text(notes, count, topic=course_id)
        if not result["cards"]:
            return {"created": [], "cards": [], "source": result["source"]}
        ids = self.create_flashcards(student_id, course_id, deck_name, result["cards"],
                                     source=result["source"])
        return {"created": ids, "cards": result["cards"], "source": result["source"]}

    def flashcards_from_explanation(self, explanation_id: int, deck_name: Optional[str] = None,
                                    count: int = 8, student_id: Optional[str] = None) -> Dict:
        with get_connection() as conn:
            owner = self._check(conn, "concept_explanations", "explanation_id", explanation_id,
                                student_id, "explanation")
            row = conn.execute("SELECT concept_name, explanation, course_id FROM "
                               "concept_explanations WHERE explanation_id = ?",
                               (explanation_id,)).fetchone()
        result = companion_ai.cards_from_text(row["explanation"], count, topic=row["concept_name"])
        if not result["cards"]:
            return {"created": [], "cards": [], "source": result["source"]}
        ids = self.create_flashcards(owner, row["course_id"], deck_name or row["concept_name"],
                                     result["cards"], source="explanation",
                                     source_ref=f"explanation:{explanation_id}")
        return {"created": ids, "cards": result["cards"], "source": result["source"]}

    def card_from_mistake(self, flashcard_id: int, given: Optional[str] = None,
                          student_id: Optional[str] = None) -> int:
        """A follow-up card for a card the student got wrong — aimed at the
        confusion in ``given`` (their answer), or the card reversed."""
        with get_connection() as conn:
            owner = self._check(conn, "flashcards", "flashcard_id", flashcard_id, student_id,
                                "flashcard")
            card = conn.execute("SELECT question, answer, deck_name, course_id FROM flashcards "
                                "WHERE flashcard_id = ?", (flashcard_id,)).fetchone()
        new = companion_ai.card_from_mistake(card["question"], card["answer"], given)
        return self.create_flashcards(owner, card["course_id"], card["deck_name"],
                                      [new], source="mistake",
                                      source_ref=f"flashcard:{flashcard_id}")[0]

    def get_due_flashcards(self, student_id: str, deck_name: Optional[str] = None) -> List[Dict]:
        """Get flashcards due for review, most overdue first, up to the
        student's daily limit. Suspended cards are left out."""
        with get_connection() as conn:
            limit = companion_reminders.settings(conn, student_id)["daily_card_limit"]
            query = """
                SELECT * FROM flashcards
                WHERE student_id = ? AND COALESCE(suspended, 0) = 0
                AND (next_review IS NULL OR next_review <= ?)
            """
            params = [str(student_id), date.today().isoformat()]

            if deck_name:
                query += " AND deck_name = ?"
                params.append(deck_name)

            query += " ORDER BY next_review IS NOT NULL, next_review, flashcard_id LIMIT ?"
            params.append(int(limit))

            flashcards = conn.execute(query, params).fetchall()
            return [dict(card) for card in flashcards]

    def review_flashcard(self, flashcard_id: int, correct: Optional[bool] = None,
                         quality=None, student_id: Optional[str] = None) -> Dict:
        """
        Review a flashcard and reschedule it with SM-2.

        Args:
            flashcard_id: Flashcard ID
            correct: Whether the answer was right (Good / Again)
            quality: Or a grade — again, hard, good, easy, or 0-5

        Returns:
            ``{next_review, days_until_next, review_count, ease_factor, correct}``
        """
        grade = spaced_repetition.quality_for(correct, quality)
        with transaction() as conn:
            owner = self._check(conn, "flashcards", "flashcard_id", flashcard_id, student_id,
                                "flashcard")
            card = conn.execute("""
                SELECT review_count, correct_count, ease_factor, interval_days, repetitions,
                       lapses
                FROM flashcards WHERE flashcard_id = ?
            """, (flashcard_id,)).fetchone()

            state = spaced_repetition.schedule(
                ease=card['ease_factor'], interval=card['interval_days'],
                repetitions=card['repetitions'], quality=grade)
            review_count = (card['review_count'] or 0) + 1
            correct_count = (card['correct_count'] or 0) + (1 if state['correct'] else 0)

            conn.execute("""
                UPDATE flashcards
                SET review_count = ?, correct_count = ?, last_reviewed = ?, next_review = ?,
                    ease_factor = ?, interval_days = ?, repetitions = ?, lapses = ?,
                    last_quality = ?, difficulty_rating = ?, updated_at = ?
                WHERE flashcard_id = ?
            """, (review_count, correct_count, datetime.now().isoformat(), state['next_review'],
                  state['ease_factor'], state['interval_days'], state['repetitions'],
                  (card['lapses'] or 0) + (1 if state['lapsed'] else 0), grade, 5 - grade,
                  _now(), flashcard_id))
            conn.execute("INSERT INTO flashcard_reviews (flashcard_id, student_id, quality, "
                         "interval_days, ease_factor) VALUES (?, ?, ?, ?, ?)",
                         (flashcard_id, owner, grade, state['interval_days'],
                          state['ease_factor']))

        log_activity('update', 'flashcard_review',
                     details={'flashcard_id': flashcard_id, 'quality': grade,
                              'next_review': state['next_review']})
        return {
            'next_review': state['next_review'],
            'days_until_next': state['interval_days'],
            'review_count': review_count,
            'ease_factor': state['ease_factor'],
            'correct': state['correct'],
        }

    def get_flashcard_decks(self, student_id: str) -> List[Dict]:
        """Get all flashcard decks for a student with statistics."""
        with get_connection() as conn:
            decks = conn.execute("""
                SELECT
                    deck_name,
                    course_id,
                    COUNT(*) as total_cards,
                    SUM(CASE WHEN COALESCE(suspended, 0) = 0
                             AND (next_review IS NULL OR next_review <= ?) THEN 1 ELSE 0 END)
                        as due_count,
                    SUM(CASE WHEN COALESCE(suspended, 0) = 1 THEN 1 ELSE 0 END) as suspended,
                    COALESCE(SUM(correct_count) * 100.0 / NULLIF(SUM(review_count), 0), 0)
                        as accuracy
                FROM flashcards
                WHERE student_id = ?
                GROUP BY deck_name, course_id
                ORDER BY deck_name
            """, (date.today().isoformat(), str(student_id))).fetchall()

            return [dict(deck) for deck in decks]

    def list_flashcards(self, student_id: str, deck_name: Optional[str] = None) -> List[Dict]:
        with get_connection() as conn:
            sql = "SELECT * FROM flashcards WHERE student_id = ?"
            params = [str(student_id)]
            if deck_name:
                sql += " AND deck_name = ?"
                params.append(deck_name)
            return [dict(r) for r in conn.execute(sql + " ORDER BY deck_name, flashcard_id",
                                                  params).fetchall()]

    def update_flashcard(self, flashcard_id: int, student_id: Optional[str] = None, *,
                         question: Optional[str] = None, answer: Optional[str] = None,
                         deck_name: Optional[str] = None,
                         course_id: Optional[str] = None) -> bool:
        with transaction() as conn:
            self._check(conn, "flashcards", "flashcard_id", flashcard_id, student_id, "flashcard")
            card = conn.execute("SELECT question, answer, deck_name FROM flashcards "
                                "WHERE flashcard_id = ?", (flashcard_id,)).fetchone()
            q, a, d = self._card_text(question if question is not None else card[0],
                                      answer if answer is not None else card[1],
                                      deck_name if deck_name is not None else card[2])
            conn.execute("UPDATE flashcards SET question = ?, answer = ?, deck_name = ?, "
                         "course_id = CASE WHEN ? IS NULL THEN course_id ELSE NULLIF(?, '') END, "
                         "updated_at = ? WHERE flashcard_id = ?",
                         (q, a, d, course_id, course_id, _now(), flashcard_id))
        return True

    def set_flashcard_suspended(self, flashcard_id: int, suspended: bool,
                                student_id: Optional[str] = None) -> bool:
        with transaction() as conn:
            self._check(conn, "flashcards", "flashcard_id", flashcard_id, student_id, "flashcard")
            conn.execute("UPDATE flashcards SET suspended = ?, updated_at = ? "
                         "WHERE flashcard_id = ?", (int(bool(suspended)), _now(), flashcard_id))
        return True

    def delete_flashcard(self, flashcard_id: int, student_id: Optional[str] = None) -> bool:
        with transaction() as conn:
            self._check(conn, "flashcards", "flashcard_id", flashcard_id, student_id, "flashcard")
            conn.execute("DELETE FROM flashcard_reviews WHERE flashcard_id = ?", (flashcard_id,))
            conn.execute("DELETE FROM flashcards WHERE flashcard_id = ?", (flashcard_id,))
        log_activity('delete', 'flashcard', details={'flashcard_id': flashcard_id})
        return True

    def rename_deck(self, student_id: str, deck_name: str, new_name: str) -> int:
        new_name = (new_name or "").strip()
        if not new_name or len(new_name) > 100:
            raise ValueError("Deck names are 1 to 100 characters")
        with transaction() as conn:
            return conn.execute("UPDATE flashcards SET deck_name = ?, updated_at = ? "
                                "WHERE student_id = ? AND deck_name = ?",
                                (new_name, _now(), str(student_id), deck_name)).rowcount

    def delete_deck(self, student_id: str, deck_name: str) -> int:
        with transaction() as conn:
            conn.execute("DELETE FROM flashcard_reviews WHERE flashcard_id IN (SELECT "
                         "flashcard_id FROM flashcards WHERE student_id = ? AND deck_name = ?)",
                         (str(student_id), deck_name))
            count = conn.execute("DELETE FROM flashcards WHERE student_id = ? AND deck_name = ?",
                                 (str(student_id), deck_name)).rowcount
        log_activity('delete', 'flashcard_deck', details={'deck': deck_name, 'cards': count})
        return count

    # ========== Concept Explainer ==========

    def explain_concept(self, student_id: str, course_id: Optional[str],
                       concept_name: str, difficulty_level: str = "Beginner") -> Dict:
        """
        Explain a concept — by Claude when configured, otherwise from the
        module's records and the student's own cards (``source`` says which).

        Args:
            student_id: Student's ID
            course_id: Module code (optional; grounds the explanation)
            concept_name: Name of the concept to explain
            difficulty_level: 'Beginner', 'Intermediate', or 'Advanced'

        Returns:
            ``{explanation_id, concept_name, explanation, difficulty_level, source, model}``
        """
        concept_name = (concept_name or "").strip()
        level = difficulty_level if difficulty_level in companion_ai.LEVELS else "Beginner"
        course_id = (course_id or "").strip() or None
        with get_connection() as conn:
            material = study_context.course_material(conn, course_id, concept_name) if course_id else None
            needle = f"%{concept_name.lower()}%"
            own = _dicts(conn.execute(
                "SELECT question, answer FROM flashcards WHERE student_id = ? AND "
                "(LOWER(question) LIKE ? OR LOWER(answer) LIKE ?) LIMIT 6",
                (str(student_id), needle, needle))) if concept_name else []
        result = companion_ai.explain(concept_name, level, material, own)

        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO concept_explanations
                (student_id, course_id, concept_name, explanation, difficulty_level, source,
                 model, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (str(student_id), course_id, concept_name, result["explanation"], level,
                  result["source"], result["model"], _now()))

            explanation_id = cursor.lastrowid

        log_activity('create', 'concept_explanation',
                     details={'explanation_id': explanation_id, 'concept': concept_name,
                              'level': level, 'source': result["source"]})

        return {
            'explanation_id': explanation_id,
            'concept_name': concept_name,
            'explanation': result["explanation"],
            'difficulty_level': level,
            'source': result["source"],
            'model': result["model"],
        }

    def save_explanation(self, student_id: str, concept_name: str, explanation: str,
                         course_id: Optional[str] = None,
                         difficulty_level: str = "Beginner") -> int:
        """Keep a student's own written explanation alongside the generated ones."""
        concept_name, explanation = (concept_name or "").strip(), (explanation or "").strip()
        if not concept_name or not explanation:
            raise ValueError("An explanation needs a concept and some text")
        with transaction() as conn:
            return conn.execute(
                "INSERT INTO concept_explanations (student_id, course_id, concept_name, "
                "explanation, difficulty_level, source, created_at) VALUES (?, ?, ?, ?, ?, "
                "'template', ?)", (str(student_id), course_id or None, concept_name, explanation,
                                   difficulty_level if difficulty_level in companion_ai.LEVELS
                                   else "Beginner", _now())).lastrowid

    def rate_explanation(self, explanation_id: int, rating: int,
                         student_id: Optional[str] = None) -> bool:
        """Rate the helpfulness of an explanation (1-5 stars)."""
        if not isinstance(rating, int) or not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5")

        with transaction() as conn:
            self._check(conn, "concept_explanations", "explanation_id", explanation_id,
                        student_id, "explanation")
            conn.execute("""
                UPDATE concept_explanations
                SET helpful_rating = ?, rated_at = ?
                WHERE explanation_id = ?
            """, (rating, _now(), explanation_id))

        log_activity('update', 'concept_explanation_rating',
                     explanation_id=explanation_id, details={'rating': rating})
        return True

    def delete_explanation(self, explanation_id: int, student_id: Optional[str] = None) -> bool:
        with transaction() as conn:
            self._check(conn, "concept_explanations", "explanation_id", explanation_id,
                        student_id, "explanation")
            conn.execute("DELETE FROM concept_explanations WHERE explanation_id = ?",
                         (explanation_id,))
        return True

    def get_explanation_history(self, student_id: str) -> List[Dict]:
        """Get all concept explanations for a student."""
        with get_connection() as conn:
            explanations = conn.execute("""
                SELECT * FROM concept_explanations
                WHERE student_id = ?
                ORDER BY created_at DESC, explanation_id DESC
                LIMIT 50
            """, (str(student_id),)).fetchall()

            return [dict(exp) for exp in explanations]

    # ========== Analytics ==========

    def get_study_analytics(self, student_id: str) -> Dict:
        """Get comprehensive study analytics for a student."""
        sid = str(student_id)
        since = (date.today() - timedelta(days=30)).isoformat()
        with get_connection() as conn:
            plan_stats = conn.execute("""
                SELECT
                    COUNT(*) as total_plans,
                    SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) as active_plans,
                    SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) as completed_plans,
                    SUM(total_hours) as planned_hours
                FROM study_plans
                WHERE student_id = ?
            """, (sid,)).fetchone()

            task_stats = conn.execute("""
                SELECT
                    COUNT(*) as total_tasks,
                    SUM(CASE WHEN COALESCE(spt.status, 'pending') = 'done' THEN 1 ELSE 0 END)
                        as completed_tasks,
                    SUM(CASE WHEN COALESCE(spt.status, 'pending') = 'skipped' THEN 1 ELSE 0 END)
                        as skipped_tasks,
                    SUM(CASE WHEN COALESCE(spt.status, 'pending') = 'pending'
                             AND spt.scheduled_date < ? THEN 1 ELSE 0 END) as overdue_tasks,
                    SUM(duration_minutes) as total_minutes,
                    SUM(CASE WHEN COALESCE(spt.status, 'pending') = 'done'
                             THEN duration_minutes ELSE 0 END) as completed_minutes
                FROM study_plan_tasks spt
                JOIN study_plans sp ON spt.plan_id = sp.plan_id
                WHERE sp.student_id = ?
            """, (date.today().isoformat(), sid)).fetchone()

            flashcard_stats = conn.execute("""
                SELECT
                    COUNT(*) as total_cards,
                    COUNT(DISTINCT deck_name) as total_decks,
                    COALESCE(SUM(correct_count) * 100.0 / NULLIF(SUM(review_count), 0), 0)
                        as avg_accuracy,
                    SUM(CASE WHEN COALESCE(repetitions, 0) >= 3 THEN 1 ELSE 0 END) as mature_cards
                FROM flashcards
                WHERE student_id = ?
            """, (sid,)).fetchone()

            reviews = _dicts(conn.execute(
                "SELECT quality FROM flashcard_reviews WHERE student_id = ? AND reviewed_at >= ?",
                (sid, since)))
            weak = study_context.weak_modules(conn, sid)

        try:
            streak = self.sessions.streak(sid)
        except Exception:
            streak = 0
        return {
            'study_plans': dict(plan_stats) if plan_stats else {},
            'tasks': dict(task_stats) if task_stats else {},
            'flashcards': dict(flashcard_stats) if flashcard_stats else {},
            'reviews': {'last_30_days': len(reviews),
                        'retention_pct': spaced_repetition.retention(reviews)},
            'streak_days': streak,
            'weak_modules': weak,
        }

    # ========== Today, reminders and settings ==========

    def today(self, student_id: str) -> Dict:
        with get_connection() as conn:
            return companion_reminders.today_summary(conn, student_id)

    def get_settings(self, student_id: str) -> Dict:
        with get_connection() as conn:
            return companion_reminders.settings(conn, student_id)

    def save_settings(self, student_id: str, **values) -> Dict:
        with transaction() as conn:
            saved = companion_reminders.save_settings(conn, student_id, **values)
        log_activity('update', 'study_companion_settings',
                     details={'student_id': student_id, **saved})
        return saved

    def send_my_reminder(self, student_id: str) -> Dict:
        """Today's reminder for one student, once a day (run when they open
        the companion)."""
        with transaction() as conn:
            result = companion_reminders.send_for(conn, student_id)
        result["emailed"] = _send_emails(result.pop("emails"))
        return result

    def send_all_reminders(self) -> Dict:
        """Today's reminder for everyone who uses the companion (staff)."""
        with transaction() as conn:
            result = companion_reminders.send_all(conn)
        result["emailed"] = _send_emails(result.pop("emails"))
        log_activity('create', 'study_companion_reminders',
                     details={'sent': result['sent'], 'checked': result['checked']})
        return result

    # ========== Staff ==========

    def staff_overview(self, viewer, module_code: Optional[str] = None) -> List[Dict]:
        if not study_context.is_staff(viewer):
            raise PermissionError("The student overview is for staff")
        with get_connection() as conn:
            return companion_staff.overview(conn, viewer, module_code)

    def staff_student_detail(self, viewer, student_id: str) -> Dict:
        with get_connection() as conn:
            return companion_staff.student_detail(conn, viewer, student_id)

    def can_view_student(self, viewer, student_id: str) -> bool:
        with get_connection() as conn:
            return companion_staff.can_view(conn, viewer, student_id)

    def engagement_scan(self, actor: str = "study companion") -> Dict:
        """Raise / resolve study-plan slippage early-warning indicators."""
        with transaction() as conn:
            result = companion_staff.engagement_scan(conn, actor=actor)
        log_activity('update', 'study_companion_engagement_scan', details=result)
        return result
