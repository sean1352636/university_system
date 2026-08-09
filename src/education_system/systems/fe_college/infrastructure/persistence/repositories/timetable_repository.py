"""Timetable persistence: sessions, rooms, bookings and lesson plans."""

from __future__ import annotations

import sqlite3
from datetime import date

from education_system.systems.fe_college.domain.facilities.bookings import Booking
from education_system.systems.fe_college.domain.facilities.equipment import Equipment
from education_system.systems.fe_college.domain.facilities.rooms import Room
from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.domain.teaching.lesson_plans import LessonPlan
from education_system.systems.fe_college.domain.teaching.timetable import Session
from education_system.systems.fe_college.infrastructure.persistence import (
    read_only,
    transaction,
)


# ── Sessions ────────────────────────────────────────────────────────────────

def get_session(session_id: int) -> Session | None:
    with read_only() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
    return Session.from_row(row) if row else None


def list_sessions(
    *,
    course_id: str | None = None,
    teacher_id: str | None = None,
    room_id: str | None = None,
    group_id: str | None = None,
    student_id: str | None = None,
    academic_year: str | None = None,
    day: str | None = None,
    period: str | None = None,
) -> list[Session]:
    """List timetabled sessions.

    ``student_id`` resolves to the sessions of the courses that learner is
    actively enrolled on — their personal timetable.
    """
    sql = ["SELECT DISTINCT t.* FROM sessions t"]
    params: list = []
    if student_id:
        sql.append(
            "JOIN enrolments e ON e.course_id = t.course_id "
            "AND e.student_id = ? AND e.status = 'active'"
        )
        params.append(student_id)

    where: list[str] = []
    for column, value in (
        ("t.course_id", course_id),
        ("t.teacher_id", teacher_id),
        ("t.room_id", room_id),
        ("t.group_id", group_id),
        ("t.academic_year", academic_year),
        ("t.day", day),
        ("t.period", period),
    ):
        if value:
            where.append(f"{column} = ?")
            params.append(value)
    if where:
        sql.append("WHERE " + " AND ".join(where))
    sql.append("ORDER BY t.day, t.period")
    with read_only() as conn:
        rows = conn.execute(" ".join(sql), params).fetchall()
    return [Session.from_row(r) for r in rows]


def sessions_in_slot(day: str, period: str,
                     academic_year: str | None = None) -> list[Session]:
    """Everything already timetabled in one slot — the clash-check input."""
    sql = "SELECT * FROM sessions WHERE day = ? AND period = ?"
    params: list = [day, period]
    if academic_year:
        sql += " AND academic_year = ?"
        params.append(academic_year)
    with read_only() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [Session.from_row(r) for r in rows]


def create_session(session: Session) -> Session:
    session.validate()
    row = session.to_row()
    placeholders = ", ".join("?" for _ in row)
    try:
        with transaction() as conn:
            cur = conn.execute(
                f"INSERT INTO sessions ({', '.join(row)}) VALUES ({placeholders})",
                list(row.values()),
            )
            session.session_id = cur.lastrowid
    except sqlite3.IntegrityError as exc:
        raise ValidationError(f"Could not save session: {exc}") from exc
    return session


def update_session(session: Session) -> Session:
    if session.session_id is None:
        raise ValidationError("Cannot update a session without an ID")
    session.validate()
    row = session.to_row()
    assignments = ", ".join(f"{col} = ?" for col in row)
    with transaction() as conn:
        conn.execute(
            f"UPDATE sessions SET {assignments} WHERE session_id = ?",
            [*row.values(), session.session_id],
        )
    return session


def delete_session(session_id: int) -> bool:
    with transaction() as conn:
        cur = conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        return cur.rowcount > 0


def teaching_hours_by_staff() -> dict[str, int]:
    """Session count per teacher — the workload report's raw input."""
    with read_only() as conn:
        rows = conn.execute(
            "SELECT teacher_id, COUNT(*) AS n FROM sessions "
            "WHERE teacher_id IS NOT NULL AND teacher_id <> '' GROUP BY teacher_id"
        ).fetchall()
    return {r["teacher_id"]: r["n"] for r in rows}


# ── Rooms ───────────────────────────────────────────────────────────────────

def get_room(room_id: str) -> Room | None:
    with read_only() as conn:
        row = conn.execute("SELECT * FROM rooms WHERE room_id = ?", (room_id,)).fetchone()
    return Room.from_row(row) if row else None


def list_rooms(*, room_type: str | None = None, campus: str | None = None,
               bookable_only: bool = False) -> list[Room]:
    where, params = [], []
    if room_type:
        where.append("room_type = ?")
        params.append(room_type)
    if campus:
        where.append("campus = ?")
        params.append(campus)
    if bookable_only:
        where.append("status = 'available'")
    sql = "SELECT * FROM rooms"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY building, room_id"
    with read_only() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [Room.from_row(r) for r in rows]


def save_room(room: Room) -> Room:
    room.validate()
    row = room.to_row()
    columns = ", ".join(row)
    placeholders = ", ".join("?" for _ in row)
    updates = ", ".join(f"{c} = excluded.{c}" for c in row if c != "room_id")
    with transaction() as conn:
        conn.execute(
            f"INSERT INTO rooms ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT(room_id) DO UPDATE SET {updates}",
            list(row.values()),
        )
    return room


def delete_room(room_id: str) -> bool:
    with transaction() as conn:
        cur = conn.execute("DELETE FROM rooms WHERE room_id = ?", (room_id,))
        return cur.rowcount > 0


def free_rooms(day: str, period: str, *, min_capacity: int = 0,
               room_type: str | None = None) -> list[Room]:
    """Bookable rooms with nothing timetabled in a slot."""
    sql = [
        "SELECT r.* FROM rooms r WHERE r.status = 'available'",
        "AND r.room_id NOT IN ("
        "  SELECT room_id FROM sessions WHERE day = ? AND period = ?"
        "  AND room_id IS NOT NULL)",
    ]
    params: list = [day, period]
    if min_capacity:
        sql.append("AND r.capacity >= ?")
        params.append(int(min_capacity))
    if room_type:
        sql.append("AND r.room_type = ?")
        params.append(room_type)
    sql.append("ORDER BY r.capacity, r.room_id")
    with read_only() as conn:
        rows = conn.execute(" ".join(sql), params).fetchall()
    return [Room.from_row(r) for r in rows]


# ── Bookings ────────────────────────────────────────────────────────────────

def list_bookings(*, room_id: str | None = None, booking_date: date | None = None,
                  live_only: bool = True) -> list[Booking]:
    where, params = [], []
    if room_id:
        where.append("room_id = ?")
        params.append(room_id)
    if booking_date:
        where.append("booking_date = ?")
        params.append(booking_date.isoformat())
    if live_only:
        where.append("status IN ('requested', 'confirmed')")
    sql = "SELECT * FROM bookings"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY booking_date, start_time"
    with read_only() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [Booking.from_row(r) for r in rows]


def create_booking(booking: Booking) -> Booking:
    booking.validate()
    row = booking.to_row()
    placeholders = ", ".join("?" for _ in row)
    with transaction() as conn:
        cur = conn.execute(
            f"INSERT INTO bookings ({', '.join(row)}) VALUES ({placeholders})",
            list(row.values()),
        )
        booking.booking_id = cur.lastrowid
    return booking


def cancel_booking(booking_id: int) -> bool:
    with transaction() as conn:
        cur = conn.execute(
            "UPDATE bookings SET status = 'cancelled' WHERE booking_id = ?", (booking_id,)
        )
        return cur.rowcount > 0


# ── Equipment ───────────────────────────────────────────────────────────────

def list_equipment(*, category: str | None = None,
                   status: str | None = None) -> list[Equipment]:
    where, params = [], []
    if category:
        where.append("category = ?")
        params.append(category)
    if status:
        where.append("status = ?")
        params.append(status)
    sql = "SELECT * FROM equipment"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY category, asset_id"
    with read_only() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [Equipment.from_row(r) for r in rows]


def save_equipment(item: Equipment) -> Equipment:
    item.validate()
    row = item.to_row()
    columns = ", ".join(row)
    placeholders = ", ".join("?" for _ in row)
    updates = ", ".join(f"{c} = excluded.{c}" for c in row if c != "asset_id")
    with transaction() as conn:
        conn.execute(
            f"INSERT INTO equipment ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT(asset_id) DO UPDATE SET {updates}",
            list(row.values()),
        )
    return item


# ── Lesson plans ────────────────────────────────────────────────────────────

def list_lesson_plans(*, teacher_id: str | None = None, course_id: str | None = None,
                      status: str | None = None) -> list[LessonPlan]:
    where, params = [], []
    for column, value in (
        ("teacher_id", teacher_id), ("course_id", course_id), ("status", status)
    ):
        if value:
            where.append(f"{column} = ?")
            params.append(value)
    sql = "SELECT * FROM lesson_plans"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY lesson_date IS NULL, lesson_date DESC, plan_id DESC"
    with read_only() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [LessonPlan.from_row(r) for r in rows]


def get_lesson_plan(plan_id: int) -> LessonPlan | None:
    with read_only() as conn:
        row = conn.execute(
            "SELECT * FROM lesson_plans WHERE plan_id = ?", (plan_id,)
        ).fetchone()
    return LessonPlan.from_row(row) if row else None


def save_lesson_plan(plan: LessonPlan) -> LessonPlan:
    plan.validate()
    row = plan.to_row()
    if plan.plan_id is None:
        placeholders = ", ".join("?" for _ in row)
        with transaction() as conn:
            cur = conn.execute(
                f"INSERT INTO lesson_plans ({', '.join(row)}) VALUES ({placeholders})",
                list(row.values()),
            )
            plan.plan_id = cur.lastrowid
    else:
        assignments = ", ".join(f"{col} = ?" for col in row)
        with transaction() as conn:
            conn.execute(
                f"UPDATE lesson_plans SET {assignments} WHERE plan_id = ?",
                [*row.values(), plan.plan_id],
            )
    return plan


def delete_lesson_plan(plan_id: int) -> bool:
    with transaction() as conn:
        cur = conn.execute("DELETE FROM lesson_plans WHERE plan_id = ?", (plan_id,))
        return cur.rowcount > 0


__all__ = [
    "cancel_booking",
    "create_booking",
    "create_session",
    "delete_lesson_plan",
    "delete_room",
    "delete_session",
    "free_rooms",
    "get_lesson_plan",
    "get_room",
    "get_session",
    "list_bookings",
    "list_equipment",
    "list_lesson_plans",
    "list_rooms",
    "list_sessions",
    "save_equipment",
    "save_lesson_plan",
    "save_room",
    "sessions_in_slot",
    "teaching_hours_by_staff",
    "update_session",
]
