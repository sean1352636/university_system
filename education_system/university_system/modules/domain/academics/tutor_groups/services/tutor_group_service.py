"""Tutor-group service: first-class entity with pastoral assignment.

Provides tutor groups, membership, pastoral tutor assignments and
scheduled meetings for the university system. This is a first-class
domain entity (distinct from the analytics-only cohorts in
`shared/services/analytics/student_analytics/cohorts.py`).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from education_system.university_system.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)


class TutorGroupError(Exception):
    """Raised for any tutor-group data or workflow failure."""


_VALID_MEMBER_ROLES = {"student", "co-tutor", "observer"}
_VALID_ASSIGNMENT_ROLES = {"personal_tutor", "co-tutor", "pastoral_lead"}
_VALID_MEETING_STATUS = {"scheduled", "held", "cancelled"}


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _validate_date(value: str, field: str) -> None:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except (ValueError, TypeError) as exc:
        raise TutorGroupError(f"{field} must be YYYY-MM-DD") from exc


def _validate_datetime(value: str, field: str) -> None:
    try:
        datetime.strptime(value, "%Y-%m-%d %H:%M")
    except (ValueError, TypeError) as exc:
        raise TutorGroupError(f"{field} must be 'YYYY-MM-DD HH:MM'") from exc


class TutorGroupService:
    """Manage tutor groups, members, pastoral assignments and meetings."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = db_path
        self.init_schema()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _conn(self):
        return get_connection(self._db_path)

    def init_schema(self) -> None:
        """Create tutor-group tables if they do not exist."""
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS tutor_groups (
                    group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    academic_year TEXT NOT NULL,
                    programme TEXT,
                    lead_tutor_id INTEGER,
                    capacity INTEGER NOT NULL DEFAULT 20,
                    meeting_pattern TEXT DEFAULT 'weekly',
                    notes TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS tutor_group_members (
                    membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    student_id INTEGER NOT NULL,
                    role TEXT NOT NULL DEFAULT 'student',
                    joined_date TEXT NOT NULL,
                    left_date TEXT,
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (group_id) REFERENCES tutor_groups (group_id)
                );

                CREATE UNIQUE INDEX IF NOT EXISTS idx_tutor_group_members_active
                    ON tutor_group_members (group_id, student_id)
                    WHERE is_active = 1;

                CREATE TABLE IF NOT EXISTS pastoral_assignments (
                    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    tutor_id INTEGER NOT NULL,
                    role TEXT NOT NULL DEFAULT 'personal_tutor',
                    assigned_date TEXT NOT NULL,
                    ended_date TEXT,
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (group_id) REFERENCES tutor_groups (group_id)
                );

                CREATE TABLE IF NOT EXISTS tutor_group_meetings (
                    meeting_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    scheduled_at TEXT NOT NULL,
                    duration_minutes INTEGER DEFAULT 60,
                    location TEXT,
                    agenda TEXT,
                    attendance_count INTEGER,
                    notes TEXT,
                    status TEXT DEFAULT 'scheduled',
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (group_id) REFERENCES tutor_groups (group_id)
                );

                CREATE INDEX IF NOT EXISTS idx_tutor_groups_year
                    ON tutor_groups (academic_year);
                CREATE INDEX IF NOT EXISTS idx_pastoral_assignments_group
                    ON pastoral_assignments (group_id);
                CREATE INDEX IF NOT EXISTS idx_tutor_group_meetings_group
                    ON tutor_group_meetings (group_id);
                """
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Groups
    # ------------------------------------------------------------------

    def create_group(
        self,
        name: str,
        academic_year: str,
        programme: str,
        lead_tutor_id: int,
        capacity: int = 20,
        meeting_pattern: str = "weekly",
        notes: str = "",
    ) -> int:
        if not name.strip():
            raise TutorGroupError("name is required")
        if not academic_year.strip():
            raise TutorGroupError("academic_year is required")
        if not isinstance(capacity, int) or capacity <= 0:
            raise TutorGroupError("capacity must be a positive integer")
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    """INSERT INTO tutor_groups
                       (name, academic_year, programme, lead_tutor_id, capacity,
                        meeting_pattern, notes, is_active, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 1, datetime('now'), datetime('now'))""",
                    (name, academic_year, programme, lead_tutor_id, capacity,
                     meeting_pattern, notes),
                )
                conn.commit()
                logger.info("Created tutor group '%s' (id=%s)", name, cur.lastrowid)
                return cur.lastrowid
        except TutorGroupError:
            raise
        except Exception as exc:
            logger.error("create_group failed: %s", exc)
            raise TutorGroupError(f"Failed to create tutor group: {exc}") from exc

    def list_groups(
        self,
        academic_year: Optional[str] = None,
        programme: Optional[str] = None,
        active_only: bool = True,
    ) -> list[dict]:
        sql = "SELECT * FROM tutor_groups WHERE 1=1"
        params: list[Any] = []
        if active_only:
            sql += " AND is_active = 1"
        if academic_year:
            sql += " AND academic_year = ?"
            params.append(academic_year)
        if programme:
            sql += " AND programme = ?"
            params.append(programme)
        sql += " ORDER BY academic_year DESC, name"
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def get_group(self, group_id: int) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM tutor_groups WHERE group_id = ?",
                (group_id,),
            ).fetchone()
            return dict(row) if row else None

    def update_group(self, group_id: int, **fields: Any) -> None:
        allowed = {
            "name", "academic_year", "programme", "lead_tutor_id",
            "capacity", "meeting_pattern", "notes", "is_active",
        }
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return
        if "capacity" in updates:
            cap = updates["capacity"]
            if not isinstance(cap, int) or cap <= 0:
                raise TutorGroupError("capacity must be a positive integer")
        sets = ", ".join(f"{k} = ?" for k in updates)
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    f"UPDATE tutor_groups SET {sets}, updated_at = datetime('now') "
                    "WHERE group_id = ?",
                    list(updates.values()) + [group_id],
                )
                if cur.rowcount == 0:
                    raise TutorGroupError(f"tutor group {group_id} not found")
                conn.commit()
        except TutorGroupError:
            raise
        except Exception as exc:
            raise TutorGroupError(f"Failed to update tutor group: {exc}") from exc

    # ------------------------------------------------------------------
    # Members
    # ------------------------------------------------------------------

    def add_member(
        self, group_id: int, student_id: int, role: str = "student",
    ) -> int:
        if role not in _VALID_MEMBER_ROLES:
            raise TutorGroupError(
                f"role must be one of {sorted(_VALID_MEMBER_ROLES)}",
            )
        with self._conn() as conn:
            group = conn.execute(
                "SELECT * FROM tutor_groups WHERE group_id = ?", (group_id,),
            ).fetchone()
            if not group:
                raise TutorGroupError(f"tutor group {group_id} not found")
            group = dict(group)

            # Already-active in this group? (check first so we don't mistakenly
            # report capacity for an existing member)
            dupe = conn.execute(
                "SELECT membership_id FROM tutor_group_members "
                "WHERE group_id = ? AND student_id = ? AND is_active = 1",
                (group_id, student_id),
            ).fetchone()
            if dupe:
                raise TutorGroupError(
                    f"student {student_id} is already an active member of group {group_id}",
                )

            # Capacity check (count active members of any role)
            count_row = conn.execute(
                "SELECT COUNT(*) AS c FROM tutor_group_members "
                "WHERE group_id = ? AND is_active = 1",
                (group_id,),
            ).fetchone()
            current = (count_row["c"] if count_row else 0) or 0
            if current >= int(group["capacity"]):
                raise TutorGroupError(
                    f"tutor group {group_id} is at capacity ({group['capacity']})",
                )

            # Active in another group within the same academic year?
            other = conn.execute(
                """SELECT m.membership_id, m.group_id
                   FROM tutor_group_members m
                   JOIN tutor_groups g ON g.group_id = m.group_id
                   WHERE m.student_id = ? AND m.is_active = 1
                     AND g.academic_year = ? AND m.group_id != ?""",
                (student_id, group["academic_year"], group_id),
            ).fetchone()
            if other:
                raise TutorGroupError(
                    f"student {student_id} already active in tutor group "
                    f"{other['group_id']} for academic year {group['academic_year']}",
                )

            try:
                cur = conn.execute(
                    """INSERT INTO tutor_group_members
                       (group_id, student_id, role, joined_date, is_active)
                       VALUES (?, ?, ?, ?, 1)""",
                    (group_id, student_id, role, _today()),
                )
                conn.commit()
                return cur.lastrowid
            except Exception as exc:
                raise TutorGroupError(f"Failed to add member: {exc}") from exc

    def remove_member(
        self,
        group_id: int,
        student_id: int,
        left_date: Optional[str] = None,
    ) -> None:
        ld = left_date or _today()
        _validate_date(ld, "left_date")
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    """UPDATE tutor_group_members
                       SET is_active = 0, left_date = ?
                       WHERE group_id = ? AND student_id = ? AND is_active = 1""",
                    (ld, group_id, student_id),
                )
                if cur.rowcount == 0:
                    raise TutorGroupError(
                        f"no active membership for student {student_id} in group {group_id}",
                    )
                conn.commit()
        except TutorGroupError:
            raise
        except Exception as exc:
            raise TutorGroupError(f"Failed to remove member: {exc}") from exc

    def list_members(self, group_id: int, active_only: bool = True) -> list[dict]:
        sql = "SELECT * FROM tutor_group_members WHERE group_id = ?"
        params: list[Any] = [group_id]
        if active_only:
            sql += " AND is_active = 1"
        sql += " ORDER BY joined_date, student_id"
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    # ------------------------------------------------------------------
    # Pastoral assignments
    # ------------------------------------------------------------------

    def assign_tutor(
        self,
        group_id: int,
        tutor_id: int,
        role: str = "personal_tutor",
        assigned_date: Optional[str] = None,
    ) -> int:
        if role not in _VALID_ASSIGNMENT_ROLES:
            raise TutorGroupError(
                f"role must be one of {sorted(_VALID_ASSIGNMENT_ROLES)}",
            )
        ad = assigned_date or _today()
        _validate_date(ad, "assigned_date")
        try:
            with self._conn() as conn:
                grp = conn.execute(
                    "SELECT group_id FROM tutor_groups WHERE group_id = ?",
                    (group_id,),
                ).fetchone()
                if not grp:
                    raise TutorGroupError(f"tutor group {group_id} not found")
                cur = conn.execute(
                    """INSERT INTO pastoral_assignments
                       (group_id, tutor_id, role, assigned_date, is_active)
                       VALUES (?, ?, ?, ?, 1)""",
                    (group_id, tutor_id, role, ad),
                )
                conn.commit()
                return cur.lastrowid
        except TutorGroupError:
            raise
        except Exception as exc:
            raise TutorGroupError(f"Failed to assign tutor: {exc}") from exc

    def end_assignment(
        self, assignment_id: int, ended_date: Optional[str] = None,
    ) -> None:
        ed = ended_date or _today()
        _validate_date(ed, "ended_date")
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    """UPDATE pastoral_assignments
                       SET is_active = 0, ended_date = ?
                       WHERE assignment_id = ? AND is_active = 1""",
                    (ed, assignment_id),
                )
                if cur.rowcount == 0:
                    raise TutorGroupError(
                        f"no active pastoral assignment {assignment_id}",
                    )
                conn.commit()
        except TutorGroupError:
            raise
        except Exception as exc:
            raise TutorGroupError(f"Failed to end assignment: {exc}") from exc

    def list_assignments(
        self,
        group_id: Optional[int] = None,
        tutor_id: Optional[int] = None,
        active_only: bool = True,
    ) -> list[dict]:
        sql = "SELECT * FROM pastoral_assignments WHERE 1=1"
        params: list[Any] = []
        if active_only:
            sql += " AND is_active = 1"
        if group_id is not None:
            sql += " AND group_id = ?"
            params.append(group_id)
        if tutor_id is not None:
            sql += " AND tutor_id = ?"
            params.append(tutor_id)
        sql += " ORDER BY assigned_date DESC"
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    # ------------------------------------------------------------------
    # Meetings
    # ------------------------------------------------------------------

    def schedule_meeting(
        self,
        group_id: int,
        scheduled_at: str,
        duration_minutes: int = 60,
        location: str = "",
        agenda: str = "",
    ) -> int:
        _validate_datetime(scheduled_at, "scheduled_at")
        if not isinstance(duration_minutes, int) or duration_minutes <= 0:
            raise TutorGroupError("duration_minutes must be a positive integer")
        try:
            with self._conn() as conn:
                grp = conn.execute(
                    "SELECT group_id FROM tutor_groups WHERE group_id = ?",
                    (group_id,),
                ).fetchone()
                if not grp:
                    raise TutorGroupError(f"tutor group {group_id} not found")
                cur = conn.execute(
                    """INSERT INTO tutor_group_meetings
                       (group_id, scheduled_at, duration_minutes, location,
                        agenda, status, created_at)
                       VALUES (?, ?, ?, ?, ?, 'scheduled', datetime('now'))""",
                    (group_id, scheduled_at, duration_minutes, location, agenda),
                )
                conn.commit()
                return cur.lastrowid
        except TutorGroupError:
            raise
        except Exception as exc:
            raise TutorGroupError(f"Failed to schedule meeting: {exc}") from exc

    def record_meeting(
        self,
        meeting_id: int,
        attendance_count: int,
        notes: str = "",
        status: str = "held",
    ) -> None:
        if status not in _VALID_MEETING_STATUS:
            raise TutorGroupError(
                f"status must be one of {sorted(_VALID_MEETING_STATUS)}",
            )
        if not isinstance(attendance_count, int) or attendance_count < 0:
            raise TutorGroupError("attendance_count must be a non-negative integer")
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    """UPDATE tutor_group_meetings
                       SET attendance_count = ?, notes = ?, status = ?
                       WHERE meeting_id = ?""",
                    (attendance_count, notes, status, meeting_id),
                )
                if cur.rowcount == 0:
                    raise TutorGroupError(f"meeting {meeting_id} not found")
                conn.commit()
        except TutorGroupError:
            raise
        except Exception as exc:
            raise TutorGroupError(f"Failed to record meeting: {exc}") from exc

    def list_meetings(
        self, group_id: int, upcoming_only: bool = False,
    ) -> list[dict]:
        sql = "SELECT * FROM tutor_group_meetings WHERE group_id = ?"
        params: list[Any] = [group_id]
        if upcoming_only:
            sql += " AND status = 'scheduled' AND scheduled_at >= ?"
            params.append(datetime.now().strftime("%Y-%m-%d %H:%M"))
        sql += " ORDER BY scheduled_at DESC"
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def group_summary(self, group_id: int) -> dict:
        group = self.get_group(group_id)
        if not group:
            raise TutorGroupError(f"tutor group {group_id} not found")
        members = self.list_members(group_id, active_only=True)
        assignments = self.list_assignments(group_id=group_id, active_only=True)

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        with self._conn() as conn:
            recent = [
                dict(r) for r in conn.execute(
                    """SELECT * FROM tutor_group_meetings
                       WHERE group_id = ? AND (status = 'held' OR scheduled_at < ?)
                       ORDER BY scheduled_at DESC LIMIT 5""",
                    (group_id, now),
                ).fetchall()
            ]
            upcoming = [
                dict(r) for r in conn.execute(
                    """SELECT * FROM tutor_group_meetings
                       WHERE group_id = ? AND status = 'scheduled'
                         AND scheduled_at >= ?
                       ORDER BY scheduled_at ASC LIMIT 3""",
                    (group_id, now),
                ).fetchall()
            ]

        return {
            "group": group,
            "member_count": len(members),
            "assignments": assignments,
            "recent_meetings": recent,
            "upcoming_meetings": upcoming,
        }
