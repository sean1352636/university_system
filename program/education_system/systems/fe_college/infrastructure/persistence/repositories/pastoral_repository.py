"""Pastoral persistence: tutorials, behaviour records, referrals and wellbeing."""

from __future__ import annotations

from datetime import date, timedelta

from education_system.systems.fe_college.domain.pastoral.behaviour import BehaviourRecord
from education_system.systems.fe_college.domain.pastoral.referrals import Referral
from education_system.systems.fe_college.domain.pastoral.tutorials import Tutorial
from education_system.systems.fe_college.domain.pastoral.wellbeing import WellbeingCheckIn
from education_system.systems.fe_college.domain.students.models import (
    ValidationError,
    parse_date,
)
from education_system.systems.fe_college.infrastructure.persistence import (
    read_only,
    transaction,
)


def _insert(table: str, pk: str, obj) -> object:
    """Insert a validated domain object and stamp its generated key back."""
    obj.validate()
    row = obj.to_row()
    placeholders = ", ".join("?" for _ in row)
    with transaction() as conn:
        cur = conn.execute(
            f"INSERT INTO {table} ({', '.join(row)}) VALUES ({placeholders})",
            list(row.values()),
        )
        setattr(obj, pk, cur.lastrowid)
    return obj


def _update(table: str, pk: str, obj) -> object:
    key = getattr(obj, pk)
    if key is None:
        raise ValidationError(f"Cannot update a {table[:-1]} without an ID")
    obj.validate()
    row = obj.to_row()
    assignments = ", ".join(f"{col} = ?" for col in row)
    with transaction() as conn:
        conn.execute(
            f"UPDATE {table} SET {assignments} WHERE {pk} = ?", [*row.values(), key]
        )
    return obj


# ── Tutorials ───────────────────────────────────────────────────────────────

def list_tutorials(*, student_id: str | None = None, tutor_id: str | None = None,
                   status: str | None = None) -> list[Tutorial]:
    where, params = [], []
    for column, value in (
        ("student_id", student_id), ("tutor_id", tutor_id), ("status", status)
    ):
        if value:
            where.append(f"{column} = ?")
            params.append(value)
    sql = "SELECT * FROM tutorials"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY COALESCE(held_on, scheduled_for) DESC, tutorial_id DESC"
    with read_only() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [Tutorial.from_row(r) for r in rows]


def add_tutorial(tutorial: Tutorial) -> Tutorial:
    return _insert("tutorials", "tutorial_id", tutorial)


def update_tutorial(tutorial: Tutorial) -> Tutorial:
    return _update("tutorials", "tutorial_id", tutorial)


def last_tutorial_dates() -> dict[str, date]:
    """Most recent held tutorial per learner — drives the overdue report."""
    with read_only() as conn:
        rows = conn.execute(
            "SELECT student_id, MAX(held_on) AS last_held FROM tutorials "
            "WHERE status = 'held' AND held_on IS NOT NULL GROUP BY student_id"
        ).fetchall()
    result: dict[str, date] = {}
    for r in rows:
        parsed = parse_date(r["last_held"])
        if parsed:
            result[r["student_id"]] = parsed
    return result


# ── Behaviour ───────────────────────────────────────────────────────────────

def list_behaviour(*, student_id: str | None = None,
                   behaviour_type: str | None = None,
                   since: date | None = None) -> list[BehaviourRecord]:
    where, params = [], []
    if student_id:
        where.append("student_id = ?")
        params.append(student_id)
    if behaviour_type:
        where.append("behaviour_type = ?")
        params.append(behaviour_type)
    if since:
        where.append("logged_on >= ?")
        params.append(since.isoformat())
    sql = "SELECT * FROM behaviour_records"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY logged_on DESC, record_id DESC"
    with read_only() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [BehaviourRecord.from_row(r) for r in rows]


def add_behaviour(record: BehaviourRecord) -> BehaviourRecord:
    return _insert("behaviour_records", "record_id", record)


# ── Referrals ───────────────────────────────────────────────────────────────

def list_referrals(*, student_id: str | None = None, status: str | None = None,
                   referral_type: str | None = None,
                   assigned_to: str | None = None,
                   open_only: bool = False) -> list[Referral]:
    where, params = [], []
    for column, value in (
        ("student_id", student_id), ("status", status),
        ("referral_type", referral_type), ("assigned_to", assigned_to),
    ):
        if value:
            where.append(f"{column} = ?")
            params.append(value)
    if open_only:
        where.append("status IN ('open', 'in_progress')")
    sql = "SELECT * FROM referrals"
    if where:
        sql += " WHERE " + " AND ".join(where)
    # Urgent first, then oldest — the order the support team works the queue.
    sql += (
        " ORDER BY CASE urgency WHEN 'urgent' THEN 0 WHEN 'priority' THEN 1 ELSE 2 END,"
        " referred_on"
    )
    with read_only() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [Referral.from_row(r) for r in rows]


def add_referral(referral: Referral) -> Referral:
    return _insert("referrals", "referral_id", referral)


def update_referral(referral: Referral) -> Referral:
    return _update("referrals", "referral_id", referral)


def open_referral_counts() -> dict[str, int]:
    with read_only() as conn:
        rows = conn.execute(
            "SELECT referral_type, COUNT(*) AS n FROM referrals "
            "WHERE status IN ('open', 'in_progress') GROUP BY referral_type"
        ).fetchall()
    return {r["referral_type"]: r["n"] for r in rows}


# ── Wellbeing ───────────────────────────────────────────────────────────────

def list_checkins(student_id: str | None = None,
                  days: int | None = None) -> list[WellbeingCheckIn]:
    where, params = [], []
    if student_id:
        where.append("student_id = ?")
        params.append(student_id)
    if days:
        where.append("checked_on >= ?")
        params.append((date.today() - timedelta(days=days)).isoformat())
    sql = "SELECT * FROM wellbeing_checkins"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY checked_on DESC, checkin_id DESC"
    with read_only() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [WellbeingCheckIn.from_row(r) for r in rows]


def add_checkin(checkin: WellbeingCheckIn) -> WellbeingCheckIn:
    return _insert("wellbeing_checkins", "checkin_id", checkin)


__all__ = [
    "add_behaviour",
    "add_checkin",
    "add_referral",
    "add_tutorial",
    "last_tutorial_dates",
    "list_behaviour",
    "list_checkins",
    "list_referrals",
    "list_tutorials",
    "open_referral_counts",
    "update_referral",
    "update_tutorial",
]
