"""
Performance Manager

Handles appraisal cycles, performance reviews,
goals tracking, and development plans.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
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

#: Appraisals waiting for the manager (``self_review`` is the older screens' word).
AWAITING_MANAGER = ('self_review_complete', 'self_review', 'manager_review')


#: How far behind schedule (percentage points) an open goal may fall before
#: it counts as at risk.
GOAL_RISK_MARGIN = 25


def _as_date(value: Any) -> Optional[date]:
    """The date a stored date or timestamp starts with, else None."""
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _now() -> str:
    return datetime.now().isoformat()


def _record(conn, appraisal_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute('''
        SELECT a.*, c.name AS cycle_name, c.status AS cycle_status
        FROM appraisal_records a JOIN appraisal_cycles c ON a.cycle_id = c.cycle_id
        WHERE a.appraisal_id = ?
    ''', (appraisal_id,)).fetchone()
    return dict(row) if row else None


def _require_reviewer(actor: Any, staff: str, conn) -> str:
    """Anyone above ``staff`` in the line, or HR — never themselves."""
    name = people.me(actor)
    if not access.can_manage_person(actor, staff, conn):
        raise PermissionError("Only their line manager or HR can review this appraisal")
    return name


class PerformanceManager:
    """Manager for performance appraisals and goals."""

    @staticmethod
    def get_active_cycle() -> Optional[Dict[str, Any]]:
        """Get the current active appraisal cycle."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM appraisal_cycles
                WHERE status = 'active'
                ORDER BY start_date DESC LIMIT 1
            ''').fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_cycles(status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all appraisal cycles."""
        with get_connection() as conn:
            if status:
                rows = conn.execute('''
                    SELECT * FROM appraisal_cycles WHERE status = ?
                    ORDER BY start_date DESC
                ''', (status,)).fetchall()
            else:
                rows = conn.execute('''
                    SELECT * FROM appraisal_cycles ORDER BY start_date DESC
                ''').fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def create_cycle(name: str, start_date: str, end_date: str,
                     created_by: Optional[str] = None, actor: Any = None, **data) -> int:
        """Create a new appraisal cycle (with ``actor``: HR only)."""
        if not str(name or '').strip():
            raise ValueError("Cycle name is required")
        with transaction() as conn:
            if actor is not None:
                created_by = people.require_hr(actor, conn, "create appraisal cycles")
            cursor = conn.execute('''
                INSERT INTO appraisal_cycles (
                    name, description, start_date, end_date,
                    self_review_deadline, manager_review_deadline,
                    status, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, data.get('description'), start_date, end_date,
                  data.get('self_review_deadline'), data.get('manager_review_deadline'),
                  data.get('status', 'draft'), created_by))
            cycle_id = cursor.lastrowid
            if actor is not None:
                access.audit(conn, actor, 'create_appraisal_cycle', None, 'appraisal_cycles',
                             cycle_id, {'name': name})
            log_activity('create', 'appraisal_cycle', details={'cycle_id': cycle_id})
            return cycle_id

    @staticmethod
    def activate_cycle(cycle_id: int, actor: Any = None) -> bool:
        """Activate an appraisal cycle, retiring any other active one (with
        ``actor``: HR only)."""
        with transaction() as conn:
            if actor is not None:
                people.require_hr(actor, conn, "start appraisal cycles")
            conn.execute('''
                UPDATE appraisal_cycles SET status = 'inactive'
                WHERE status = 'active'
            ''')
            conn.execute('''
                UPDATE appraisal_cycles SET status = 'active', updated_at = ?
                WHERE cycle_id = ?
            ''', (datetime.now().isoformat(), cycle_id))
            return True

    @staticmethod
    def start_cycle(cycle_id: int, actor: Any = None) -> int:
        """Start a draft cycle and open an appraisal for every member of staff
        with a profile (reviewer: their line manager). Returns how many
        appraisals were opened."""
        with transaction() as conn:
            if actor is not None:
                people.require_hr(actor, conn, "start appraisal cycles")
            row = conn.execute('SELECT status FROM appraisal_cycles WHERE cycle_id = ?',
                               (cycle_id,)).fetchone()
            if not row:
                raise ValueError("No such appraisal cycle")
            if row[0] != 'draft':
                raise ValueError("Only draft cycles can be started")
            conn.execute("UPDATE appraisal_cycles SET status = 'active', updated_at = ? "
                         "WHERE cycle_id = ?", (_now(), cycle_id))
            have = {r[0] for r in conn.execute(
                'SELECT user_id FROM appraisal_records WHERE cycle_id = ?', (cycle_id,))}
            opened = 0
            for (staff,) in conn.execute('SELECT user_id FROM staff_profiles').fetchall():
                if staff in have:
                    continue
                conn.execute("INSERT INTO appraisal_records (user_id, cycle_id, reviewer_id, "
                             "status) VALUES (?, ?, ?, 'pending')",
                             (staff, cycle_id, access.manager_of(staff, conn)))
                opened += 1
            if actor is not None:
                access.audit(conn, actor, 'start_appraisal_cycle', None, 'appraisal_cycles',
                             cycle_id, {'opened': opened})
        log_activity('update', 'appraisal_cycle', details={'cycle_id': cycle_id,
                                                           'status': 'active'})
        return opened

    @staticmethod
    def complete_cycle(cycle_id: int, actor: Any = None) -> bool:
        """Close a cycle (with ``actor``: HR only)."""
        with transaction() as conn:
            if actor is not None:
                people.require_hr(actor, conn, "complete appraisal cycles")
            cur = conn.execute("UPDATE appraisal_cycles SET status = 'completed', updated_at = ? "
                               "WHERE cycle_id = ?", (_now(), cycle_id))
            if actor is not None and cur.rowcount:
                access.audit(conn, actor, 'complete_appraisal_cycle', None, 'appraisal_cycles',
                             cycle_id)
            return bool(cur.rowcount)

    @staticmethod
    def get_appraisals(user_id: str, actor: Any = None) -> List[Dict[str, Any]]:
        """Every appraisal of a person, newest cycle first (with ``actor``:
        the person, their line managers or HR)."""
        with get_connection() as conn:
            user_id = people.key(user_id, conn)
            if actor is not None:
                people.require_view(actor, user_id, conn, "these appraisals")
            rows = conn.execute('''
                SELECT a.*, c.name AS cycle_name, c.status AS cycle_status
                FROM appraisal_records a JOIN appraisal_cycles c ON a.cycle_id = c.cycle_id
                WHERE a.user_id = ? ORDER BY c.start_date DESC
            ''', (user_id,)).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_appraisal_by_id(appraisal_id: int, actor: Any = None) -> Optional[Dict[str, Any]]:
        """One appraisal with its cycle name (with ``actor``: the person,
        their line managers or HR; HR reading someone else's is audited)."""
        with get_connection() as conn:
            record = _record(conn, appraisal_id)
            if record and actor is not None:
                staff = people.key(record['user_id'], conn)
                if people.require_view(actor, staff, conn, "this appraisal") != staff and \
                        not access.manages(actor, staff, conn):
                    access.audit(conn, actor, 'view_appraisal', staff, 'appraisal_records',
                                 appraisal_id)
            return record

    @staticmethod
    def get_team_reviews(actor: Any, include_done: bool = False) -> List[Dict[str, Any]]:
        """Appraisals in active cycles the signed-in reviewer may review: their
        reports' (the whole line below them), everyone's for HR — never their
        own. ``include_done``: completed ones too."""
        with get_connection() as conn:
            me = people.me(actor)
            statuses = AWAITING_MANAGER + (('completed',) if include_done else ())
            rows = [dict(r) for r in conn.execute(
                '''SELECT a.*, c.name AS cycle_name FROM appraisal_records a
                   JOIN appraisal_cycles c ON a.cycle_id = c.cycle_id
                   WHERE c.status = 'active' AND a.status IN (''' +
                ', '.join('?' * len(statuses)) + ') ORDER BY a.user_id', statuses).fetchall()]
            mine = access.visible_people(actor, conn)
            allowed = None if mine is None else set(mine)
            return [r for r in rows if r['user_id'] != me and
                    (allowed is None or r['user_id'] in allowed)]

    @staticmethod
    def get_appraisal(user_id: str, cycle_id: int) -> Optional[Dict[str, Any]]:
        """Get a user's appraisal record for a cycle."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM appraisal_records
                WHERE user_id = ? AND cycle_id = ?
            ''', (user_id, cycle_id)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def create_appraisal(user_id: str, cycle_id: int,
                         reviewer_id: Optional[str] = None, actor: Any = None) -> int:
        """Create an appraisal record for a user (with ``actor``: HR only;
        the reviewer defaults to the line manager)."""
        with transaction() as conn:
            if actor is not None:
                people.require_hr(actor, conn, "open appraisals")
                user_id = people.key(user_id, conn)
                reviewer_id = people.key(reviewer_id, conn) if reviewer_id else \
                    access.manager_of(user_id, conn)
            cursor = conn.execute('''
                INSERT INTO appraisal_records (user_id, cycle_id, reviewer_id)
                VALUES (?, ?, ?)
            ''', (user_id, cycle_id, reviewer_id))
            return cursor.lastrowid

    @staticmethod
    def submit_self_review(user_id: str, cycle_id: int, self_rating: float,
                           self_comments: str, actor: Any = None, **data) -> bool:
        """Submit self-review for an appraisal (with ``actor``: only the
        person themselves, and not once the manager has completed it).
        ``data`` may carry ``strengths`` and ``areas_for_improvement``."""
        if not 1 <= float(self_rating) <= 5:
            raise ValueError("Rating must be between 1 and 5")
        with transaction() as conn:
            if actor is not None:
                user_id = people.key(user_id, conn)
                if people.me(actor) != user_id:
                    raise PermissionError("Only the person themselves can write their self-review")
            existing = conn.execute('''
                SELECT appraisal_id, status FROM appraisal_records
                WHERE user_id = ? AND cycle_id = ?
            ''', (user_id, cycle_id)).fetchone()
            if existing and existing[1] == 'completed':
                raise ValueError("This appraisal has already been completed")

            if existing:
                conn.execute('''
                    UPDATE appraisal_records
                    SET self_rating = ?, self_comments = ?,
                        strengths = COALESCE(?, strengths),
                        areas_for_improvement = COALESCE(?, areas_for_improvement),
                        self_submitted_date = ?, status = 'self_review_complete',
                        updated_at = ?
                    WHERE appraisal_id = ?
                ''', (self_rating, self_comments, data.get('strengths'),
                      data.get('areas_for_improvement'), _now(), _now(), existing[0]))
            else:
                conn.execute('''
                    INSERT INTO appraisal_records (
                        user_id, cycle_id, reviewer_id, self_rating, self_comments,
                        strengths, areas_for_improvement, self_submitted_date, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'self_review_complete')
                ''', (user_id, cycle_id, access.manager_of(user_id, conn), self_rating,
                      self_comments, data.get('strengths'), data.get('areas_for_improvement'),
                      _now()))
            log_activity('submit', 'self_review', user_id=user_id,
                        details={'cycle_id': cycle_id})
            return True

    @staticmethod
    def submit_manager_review(reviewer_id: str, user_id: str, cycle_id: int,
                              manager_rating: float, manager_comments: str,
                              actor: Any = None, **data) -> bool:
        """Submit manager review for an appraisal (with ``actor``: their line
        manager — anyone above them — or HR; the reviewer recorded is the
        actor)."""
        if not 1 <= float(manager_rating) <= 5:
            raise ValueError("Rating must be between 1 and 5")
        with transaction() as conn:
            if actor is not None:
                user_id = people.key(user_id, conn)
                reviewer_id = _require_reviewer(actor, user_id, conn)
                if not conn.execute('SELECT 1 FROM appraisal_records WHERE user_id = ? '
                                    'AND cycle_id = ?', (user_id, cycle_id)).fetchone():
                    raise ValueError("No appraisal to review")
                access.audit(conn, actor, 'manager_review', user_id, 'appraisal_records',
                             f"{user_id}:{cycle_id}")
            conn.execute('''
                UPDATE appraisal_records
                SET reviewer_id = ?, manager_rating = ?, manager_comments = ?,
                    final_rating = ?, strengths = COALESCE(?, strengths),
                    areas_for_improvement = COALESCE(?, areas_for_improvement),
                    development_plan = ?, manager_submitted_date = ?,
                    status = 'completed', updated_at = ?
                WHERE user_id = ? AND cycle_id = ?
            ''', (reviewer_id, manager_rating, manager_comments,
                  data.get('final_rating', manager_rating),
                  data.get('strengths'), data.get('areas_for_improvement'),
                  data.get('development_plan'), datetime.now().isoformat(),
                  datetime.now().isoformat(), user_id, cycle_id))
            log_activity('submit', 'manager_review', details={
                'reviewer': reviewer_id, 'user_id': user_id, 'cycle_id': cycle_id
            })
        try:
            from education_system.systems.university.services.bus.integration_bus import (
                publish_appraisal_completed,
            )
            publish_appraisal_completed(
                user_id, cycle_id=cycle_id,
                rating=float(data.get('final_rating', manager_rating)),
            )
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)
        return True

    @staticmethod
    def self_review_by_id(appraisal_id: int, actor: Any, self_rating: float,
                          self_comments: str, **data) -> bool:
        """:meth:`submit_self_review` for one appraisal record."""
        with get_connection() as conn:
            record = _record(conn, appraisal_id)
        if not record:
            raise ValueError("No such appraisal")
        return PerformanceManager.submit_self_review(record['user_id'], record['cycle_id'],
                                                     self_rating, self_comments, actor=actor,
                                                     **data)

    @staticmethod
    def manager_review_by_id(appraisal_id: int, actor: Any, manager_rating: float,
                             manager_comments: str, **data) -> bool:
        """:meth:`submit_manager_review` for one appraisal record; the final
        rating defaults to the mean of the self and manager ratings."""
        with get_connection() as conn:
            record = _record(conn, appraisal_id)
        if not record:
            raise ValueError("No such appraisal")
        if 'final_rating' not in data:
            own = record.get('self_rating')
            data['final_rating'] = (float(own) + float(manager_rating)) / 2 if own \
                else float(manager_rating)
        return PerformanceManager.submit_manager_review(
            people.me(actor), record['user_id'], record['cycle_id'], manager_rating,
            manager_comments, actor=actor, **data)

    @staticmethod
    def get_goals(user_id: str, cycle_id: Optional[int] = None,
                  status: Optional[str] = None, actor: Any = None) -> List[Dict[str, Any]]:
        """Get goals for a user (with ``actor``: the person, their line
        managers or HR)."""
        with get_connection() as conn:
            if actor is not None:
                user_id = people.key(user_id, conn)
                people.require_view(actor, user_id, conn, "these goals")
            if status:
                rows = conn.execute('''
                    SELECT * FROM appraisal_goals WHERE user_id = ? AND status = ?
                    AND (? IS NULL OR cycle_id = ?) ORDER BY target_date
                ''', (user_id, status, cycle_id, cycle_id)).fetchall()
                return [dict(row) for row in rows]
            if cycle_id:
                rows = conn.execute('''
                    SELECT * FROM appraisal_goals
                    WHERE user_id = ? AND cycle_id = ?
                    ORDER BY target_date
                ''', (user_id, cycle_id)).fetchall()
            else:
                rows = conn.execute('''
                    SELECT * FROM appraisal_goals
                    WHERE user_id = ? ORDER BY target_date
                ''', (user_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def add_goal(user_id: str, title: str, actor: Any = None, **data) -> int:
        """Add a goal for a user (with ``actor``: the person, their line
        managers or HR)."""
        if not str(title or '').strip():
            raise ValueError("Goal title is required")
        with transaction() as conn:
            if actor is not None:
                user_id = people.key(user_id, conn)
                people.require_self_or_manager(actor, user_id, conn, "set goals")
            cursor = conn.execute('''
                INSERT INTO appraisal_goals (
                    user_id, cycle_id, title, description, category,
                    target_date, weight, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, data.get('cycle_id'), title, data.get('description'),
                  data.get('category', 'performance'), data.get('target_date'),
                  data.get('weight', 1.0), data.get('status', 'active')))
            return cursor.lastrowid

    @staticmethod
    def update_goal_progress(goal_id: int, progress: int,
                             notes: Optional[str] = None, actor: Any = None,
                             completed: bool = False) -> bool:
        """Update goal progress (``completed`` marks it done below 100%;
        with ``actor``: the goal's owner, their line managers or HR)."""
        progress = max(0, min(100, int(progress)))
        with transaction() as conn:
            if actor is not None:
                row = conn.execute('SELECT user_id FROM appraisal_goals WHERE goal_id = ?',
                                   (goal_id,)).fetchone()
                if not row:
                    return False
                people.require_self_or_manager(actor, people.key(row[0], conn), conn,
                                               "update this goal")
            status = 'completed' if completed or progress >= 100 else 'active'
            conn.execute('''
                UPDATE appraisal_goals
                SET progress = ?, status = ?, completion_notes = ?, updated_at = ?
                WHERE goal_id = ?
            ''', (progress, status, notes, datetime.now().isoformat(), goal_id))
            return True

    @staticmethod
    def get_pending_reviews(reviewer_id: str) -> List[Dict[str, Any]]:
        """Get appraisals pending manager review: the reviewer's own reports
        (anyone below them in the line) or ones naming them as reviewer."""
        with get_connection() as conn:
            reviewer = people.key(reviewer_id, conn)
            below = set(access.reports_of(reviewer, conn, deep=True)) if reviewer else set()
            rows = conn.execute('''
                SELECT ar.*, p.department, p.job_title,
                       u.first_name, u.last_name, ac.name as cycle_name
                FROM appraisal_records ar
                JOIN appraisal_cycles ac ON ar.cycle_id = ac.cycle_id
                LEFT JOIN staff_profiles p ON ar.user_id = p.user_id
                LEFT JOIN users u ON u.username = ar.user_id
                WHERE ar.status IN ('self_review_complete', 'self_review')
                ORDER BY ar.self_submitted_date
            ''').fetchall()
            return [dict(row) for row in rows if row['user_id'] != reviewer and
                    (row['user_id'] in below or row['reviewer_id'] == reviewer)]

    # ==================== REPORTS ====================

    @staticmethod
    def get_appraisal_summary(cycle_id: Optional[int] = None) -> Dict[str, Any]:
        """Progress and final ratings for one appraisal cycle (default the
        active one, else the latest). Empty when there are no cycles."""
        with get_connection() as conn:
            if cycle_id is None:
                cycle = conn.execute('''
                    SELECT * FROM appraisal_cycles
                    ORDER BY status = 'active' DESC, start_date DESC LIMIT 1
                ''').fetchone()
            else:
                cycle = conn.execute('SELECT * FROM appraisal_cycles WHERE cycle_id = ?',
                                     (cycle_id,)).fetchone()
            if not cycle:
                return {}
            rows = conn.execute('''
                SELECT status, COALESCE(final_rating, manager_rating) AS rating
                FROM appraisal_records WHERE cycle_id = ?
            ''', (cycle['cycle_id'],)).fetchall()
        completed = sum(1 for r in rows if r['status'] == 'completed')
        ratings: Dict[str, int] = {}
        for row in rows:
            if row['status'] == 'completed' and row['rating'] is not None:
                band = str(int(round(row['rating'])))
                ratings[band] = ratings.get(band, 0) + 1
        return {
            'period': f"{cycle['name']} ({cycle['start_date']} to {cycle['end_date']})",
            'total': len(rows),
            'completed': completed,
            'pending': len(rows) - completed,
            'completion_rate': completed * 100.0 / len(rows) if rows else 0.0,
            'ratings': dict(sorted(ratings.items())),
        }

    @staticmethod
    def get_goal_progress_report(cycle_id: Optional[int] = None) -> Dict[str, Any]:
        """Where everyone's goals stand (optionally one cycle's). An open goal
        is overdue once past its target date, and at risk when its progress is
        more than ``GOAL_RISK_MARGIN`` points behind the share of its time
        already gone; otherwise it is on track."""
        today = date.today()
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT status, progress, target_date, created_at FROM appraisal_goals
                WHERE COALESCE(status, 'active') <> 'cancelled'
                  AND (? IS NULL OR cycle_id = ?)
            ''', (cycle_id, cycle_id)).fetchall()
        completed = on_track = at_risk = overdue = 0
        progress_total = 0
        for row in rows:
            progress = row['progress'] or 0
            if row['status'] == 'completed':
                completed += 1
                progress_total += 100
                continue
            progress_total += progress
            target = _as_date(row['target_date'])
            if target is None:
                on_track += 1
            elif target < today:
                overdue += 1
            else:
                began = _as_date(row['created_at']) or today
                span = (target - began).days
                expected = (today - began).days * 100.0 / span if span > 0 else 100.0
                if progress < expected - GOAL_RISK_MARGIN:
                    at_risk += 1
                else:
                    on_track += 1
        return {
            'total_goals': len(rows),
            'completed': completed,
            'on_track': on_track,
            'at_risk': at_risk,
            'overdue': overdue,
            'overall_progress': progress_total / len(rows) if rows else 0.0,
        }
