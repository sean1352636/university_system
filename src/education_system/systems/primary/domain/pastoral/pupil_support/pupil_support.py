"""Pupil-support plans data layer for the Primary School System.

Two tables:

* ``support_plans``     — one row per support plan. A plan is broader
                           than a one-off intervention: it has a type
                           (Academic / Behaviour / Pastoral / SEMH /
                           Reintegration / Transition / Other), a
                           target + success criteria, dates,
                           coordinator and status workflow.
* ``support_plan_reviews`` — periodic reviews attached to a plan,
                              capturing progress, next steps, and
                              an outcome rating.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Any

from education_system.systems.primary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

PLAN_TYPES: tuple[str, ...] = (
    "Academic", "Behaviour", "Pastoral", "SEMH",
    "Reintegration", "Transition", "Attendance",
    "Wellbeing", "Multi-agency", "Other")
DEFAULT_TYPE: str = "Academic"

PLAN_STATUSES: tuple[str, ...] = (
    "Draft", "Active", "Review", "Complete",
    "Closed", "Discontinued")
DEFAULT_STATUS: str = "Draft"

PRIORITIES: tuple[str, ...] = ("Low", "Medium", "High", "Critical")
DEFAULT_PRIORITY: str = "Medium"

REVIEW_OUTCOMES: tuple[str, ...] = (
    "On track", "Off track", "Continue",
    "Adjust", "Discharge", "Escalate")
DEFAULT_REVIEW_OUTCOME: str = "On track"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_AY_RE = re.compile(r"^\d{4}/\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS support_plans (
    plan_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id          TEXT NOT NULL,
    academic_year     TEXT NOT NULL,
    plan_type         TEXT NOT NULL DEFAULT 'Academic',
    title             TEXT NOT NULL,
    target            TEXT,
    success_criteria  TEXT,
    coordinator       TEXT,
    priority          TEXT NOT NULL DEFAULT 'Medium',
    start_date        TEXT NOT NULL DEFAULT (date('now')),
    end_date          TEXT,
    next_review_date  TEXT,
    status            TEXT NOT NULL DEFAULT 'Draft',
    outcome           TEXT,
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS support_plan_reviews (
    review_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id       INTEGER NOT NULL,
    review_date   TEXT NOT NULL DEFAULT (date('now')),
    reviewer      TEXT,
    progress      TEXT,
    next_steps    TEXT,
    outcome       TEXT NOT NULL DEFAULT 'On track',
    next_review_date TEXT,
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (plan_id) REFERENCES support_plans(plan_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sp_pupil
    ON support_plans(pupil_id);
CREATE INDEX IF NOT EXISTS idx_sp_status
    ON support_plans(status);
CREATE INDEX IF NOT EXISTS idx_sp_reviews_plan
    ON support_plan_reviews(plan_id);
"""


@dataclass
class SupportPlan:
    plan_id: int
    pupil_id: str
    academic_year: str
    plan_type: str
    title: str
    target: str | None
    success_criteria: str | None
    coordinator: str | None
    priority: str
    start_date: str
    end_date: str | None
    next_review_date: str | None
    status: str
    outcome: str | None
    notes: str | None
    pupil_name: str | None = None
    pupil_year: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class SupportReview:
    review_id: int
    plan_id: int
    review_date: str
    reviewer: str | None
    progress: str | None
    next_steps: str | None
    outcome: str
    next_review_date: str | None
    notes: str | None
    created_at: str | None = None


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise pupil_support tables")
        raise
    logger.info("Secondary pupil_support tables ready")
    _DB_READY = True


def _row_plan(r: sqlite3.Row) -> SupportPlan:
    keys = r.keys()
    return SupportPlan(
        plan_id=r["plan_id"], pupil_id=r["pupil_id"],
        academic_year=r["academic_year"], plan_type=r["plan_type"],
        title=r["title"], target=r["target"],
        success_criteria=r["success_criteria"],
        coordinator=r["coordinator"], priority=r["priority"],
        start_date=r["start_date"], end_date=r["end_date"],
        next_review_date=r["next_review_date"],
        status=r["status"], outcome=r["outcome"],
        notes=r["notes"],
        pupil_name=r["pupil_name"] if "pupil_name" in keys else None,
        pupil_year=r["pupil_year"] if "pupil_year" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_review(r: sqlite3.Row) -> SupportReview:
    return SupportReview(
        review_id=r["review_id"], plan_id=r["plan_id"],
        review_date=r["review_date"], reviewer=r["reviewer"],
        progress=r["progress"], next_steps=r["next_steps"],
        outcome=r["outcome"],
        next_review_date=r["next_review_date"],
        notes=r["notes"], created_at=r["created_at"],
    )


def _validate_date(value: Any, label: str, *,
                   required: bool = True) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        if required:
            return _dt.date.today().isoformat()
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _validate_plan(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    pid = (data.get("pupil_id") or "").strip()
    if not pid:
        raise ValidationError("Pupil ID is required")
    from education_system.systems.primary.domain.learners.pupils import (
        pupils as pupils_data,
    )
    if pupils_data.get_pupil(pid) is None:
        raise ValidationError(f"No pupil with id {pid}")
    out["pupil_id"] = pid

    ay = (data.get("academic_year") or "").strip()
    if not ay:
        raise ValidationError("Academic year is required (e.g. 2025/26)")
    if not _AY_RE.match(ay):
        raise ValidationError(
            "Academic year must be in form YYYY/YY (e.g. 2025/26)")
    out["academic_year"] = ay

    ptype = (data.get("plan_type") or DEFAULT_TYPE).strip()
    if ptype not in PLAN_TYPES:
        raise ValidationError(
            f"Plan type must be one of {', '.join(PLAN_TYPES)}")
    out["plan_type"] = ptype

    title = (data.get("title") or "").strip()
    if not title:
        raise ValidationError("Title is required")
    if len(title) > 120:
        raise ValidationError("Title must be 120 chars or fewer")
    out["title"] = title

    out["target"]           = (data.get("target") or "").strip() or None
    out["success_criteria"] = (
        data.get("success_criteria") or "").strip() or None
    out["coordinator"]      = (data.get("coordinator") or "").strip() or None

    priority = (data.get("priority") or DEFAULT_PRIORITY).strip()
    if priority not in PRIORITIES:
        raise ValidationError(
            f"Priority must be one of {', '.join(PRIORITIES)}")
    out["priority"] = priority

    out["start_date"]      = _validate_date(
        data.get("start_date"), "Start date")
    out["end_date"]        = _validate_date(
        data.get("end_date"), "End date", required=False)
    out["next_review_date"] = _validate_date(
        data.get("next_review_date"), "Next review date",
        required=False)
    if out["end_date"] and out["end_date"] < out["start_date"]:
        raise ValidationError("End date cannot be before start date")
    if (out["next_review_date"]
            and out["next_review_date"] < out["start_date"]):
        raise ValidationError(
            "Next review date cannot be before start date")

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in PLAN_STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(PLAN_STATUSES)}")
    out["status"] = status

    out["outcome"] = (data.get("outcome") or "").strip() or None
    out["notes"]   = (data.get("notes") or "").strip() or None

    if status in ("Complete", "Closed") and not out["outcome"]:
        raise ValidationError(
            f"Outcome is required when status is {status}")
    return out


def _validate_review(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    pid_raw = data.get("plan_id")
    if pid_raw in (None, ""):
        raise ValidationError("Plan ID is required")
    try:
        out["plan_id"] = int(pid_raw)
    except (TypeError, ValueError):
        raise ValidationError("Plan ID must be a number") from None

    out["review_date"] = _validate_date(data.get("review_date"),
                                          "Review date")
    out["reviewer"]    = (data.get("reviewer") or "").strip() or None
    out["progress"]    = (data.get("progress") or "").strip() or None
    out["next_steps"]  = (data.get("next_steps") or "").strip() or None

    outcome = (data.get("outcome") or DEFAULT_REVIEW_OUTCOME).strip()
    if outcome not in REVIEW_OUTCOMES:
        raise ValidationError(
            f"Outcome must be one of {', '.join(REVIEW_OUTCOMES)}")
    out["outcome"] = outcome

    out["next_review_date"] = _validate_date(
        data.get("next_review_date"), "Next review date",
        required=False)
    if (out["next_review_date"]
            and out["next_review_date"] < out["review_date"]):
        raise ValidationError(
            "Next review date cannot be before review date")
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


# ── Plan CRUD ───────────────────────────────────────────────────

def create_plan(data: dict[str, Any]) -> SupportPlan:
    init_db()
    payload = _validate_plan(data)
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO support_plans
                       (pupil_id, academic_year, plan_type, title,
                        target, success_criteria, coordinator,
                        priority, start_date, end_date,
                        next_review_date, status, outcome, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["pupil_id"], payload["academic_year"],
                 payload["plan_type"], payload["title"],
                 payload["target"], payload["success_criteria"],
                 payload["coordinator"], payload["priority"],
                 payload["start_date"], payload["end_date"],
                 payload["next_review_date"], payload["status"],
                 payload["outcome"], payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create support plan")
        raise
    rec = get_plan(new_id)
    assert rec is not None
    logger.info("Created support plan #%d pupil=%s type=%s "
                "priority=%s status=%s",
                rec.plan_id, rec.pupil_id, rec.plan_type,
                rec.priority, rec.status)
    return rec


def get_plan(plan_id: int) -> SupportPlan | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT s.*,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM support_plans s
                   LEFT JOIN pupils p ON p.pupil_id = s.pupil_id
                   WHERE s.plan_id = ?""",
                (plan_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_plan(%s) failed", plan_id)
        raise
    return _row_plan(r) if r else None


def list_plans(*, pupil_id: str | None = None,
               year_group: str | None = None,
               academic_year: str | None = None,
               plan_type: str | None = None,
               status: str | None = None,
               priority: str | None = None) -> list[SupportPlan]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if pupil_id:
        where.append("s.pupil_id = ?")
        params.append(pupil_id.strip())
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
        where.append("p.year_group = ?")
        params.append(year_group)
    if academic_year:
        where.append("s.academic_year = ?")
        params.append(academic_year.strip())
    if plan_type:
        if plan_type not in PLAN_TYPES:
            raise ValidationError(
                f"Type filter must be one of {', '.join(PLAN_TYPES)}")
        where.append("s.plan_type = ?")
        params.append(plan_type)
    if status:
        if status not in PLAN_STATUSES:
            raise ValidationError(
                f"Status filter must be one of "
                f"{', '.join(PLAN_STATUSES)}")
        where.append("s.status = ?")
        params.append(status)
    if priority:
        if priority not in PRIORITIES:
            raise ValidationError(
                f"Priority filter must be one of "
                f"{', '.join(PRIORITIES)}")
        where.append("s.priority = ?")
        params.append(priority)
    sql = ("""SELECT s.*,
                     (p.first_name || ' ' || p.last_name) AS pupil_name,
                     p.year_group AS pupil_year
              FROM support_plans s
              LEFT JOIN pupils p ON p.pupil_id = s.pupil_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += (" ORDER BY CASE s.priority "
            " WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 "
            " WHEN 'Medium' THEN 3 WHEN 'Low' THEN 4 END, "
            "s.start_date DESC, s.plan_id DESC")
    try:
        with _connect() as conn:
            return [_row_plan(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_plans failed")
        raise


def update_plan(plan_id: int, data: dict[str, Any]) -> SupportPlan:
    init_db()
    existing = get_plan(plan_id)
    if existing is None:
        raise ValidationError(f"No support plan #{plan_id}")
    merged = {k: data.get(k, getattr(existing, k))
              for k in ("pupil_id", "academic_year", "plan_type",
                         "title", "target", "success_criteria",
                         "coordinator", "priority", "start_date",
                         "end_date", "next_review_date", "status",
                         "outcome", "notes")}
    payload = _validate_plan(merged)
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE support_plans SET
                       pupil_id = ?, academic_year = ?, plan_type = ?,
                       title = ?, target = ?, success_criteria = ?,
                       coordinator = ?, priority = ?, start_date = ?,
                       end_date = ?, next_review_date = ?, status = ?,
                       outcome = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE plan_id = ?""",
                (payload["pupil_id"], payload["academic_year"],
                 payload["plan_type"], payload["title"],
                 payload["target"], payload["success_criteria"],
                 payload["coordinator"], payload["priority"],
                 payload["start_date"], payload["end_date"],
                 payload["next_review_date"], payload["status"],
                 payload["outcome"], payload["notes"], plan_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to update support plan #%d", plan_id)
        raise
    rec = get_plan(plan_id)
    assert rec is not None
    logger.info("Updated support plan #%d (status %s)",
                rec.plan_id, rec.status)
    return rec


def set_status(plan_id: int, status: str,
                *, outcome: str | None = None) -> SupportPlan:
    payload: dict[str, Any] = {"status": status}
    if outcome is not None:
        payload["outcome"] = outcome
    return update_plan(plan_id, payload)


def delete_plan(plan_id: int) -> bool:
    init_db()
    existing = get_plan(plan_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            cur = conn.execute(
                "DELETE FROM support_plans WHERE plan_id = ?",
                (plan_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception(
            "Failed to delete support plan #%d", plan_id)
        raise
    if deleted:
        logger.info("Deleted support plan #%d (cascade: reviews)",
                    plan_id)
    return deleted


# ── Reviews ─────────────────────────────────────────────────────

def add_review(data: dict[str, Any]) -> SupportReview:
    init_db()
    payload = _validate_review(data)
    if get_plan(payload["plan_id"]) is None:
        raise ValidationError(f"No support plan #{payload['plan_id']}")
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO support_plan_reviews
                       (plan_id, review_date, reviewer, progress,
                        next_steps, outcome, next_review_date, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["plan_id"], payload["review_date"],
                 payload["reviewer"], payload["progress"],
                 payload["next_steps"], payload["outcome"],
                 payload["next_review_date"], payload["notes"]),
            )
            # Mirror next_review_date back onto the parent plan.
            if payload["next_review_date"]:
                conn.execute(
                    "UPDATE support_plans SET next_review_date = ?, "
                    "updated_at = datetime('now') WHERE plan_id = ?",
                    (payload["next_review_date"], payload["plan_id"]),
                )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception(
            "Failed to add review to plan %d", payload["plan_id"])
        raise
    logger.info("Added support review #%d to plan #%d "
                "(outcome=%s, next=%s)",
                new_id, payload["plan_id"], payload["outcome"],
                payload["next_review_date"])
    rec = get_review(new_id)
    assert rec is not None
    return rec


def get_review(review_id: int) -> SupportReview | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM support_plan_reviews "
                "WHERE review_id = ?", (review_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_review(%s) failed", review_id)
        raise
    return _row_review(r) if r else None


def list_reviews(plan_id: int) -> list[SupportReview]:
    init_db()
    try:
        with _connect() as conn:
            return [_row_review(r) for r in conn.execute(
                "SELECT * FROM support_plan_reviews WHERE plan_id = ? "
                "ORDER BY review_date DESC, review_id DESC",
                (plan_id,),
            ).fetchall()]
    except sqlite3.Error:
        logger.exception("list_reviews(%s) failed", plan_id)
        raise


def delete_review(review_id: int) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM support_plan_reviews "
                "WHERE review_id = ?", (review_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception(
            "Failed to delete support review #%d", review_id)
        raise
    if deleted:
        logger.info("Deleted support review #%d", review_id)
    return deleted


def plan_summary(plan_id: int) -> dict[str, Any]:
    init_db()
    rec = get_plan(plan_id)
    if rec is None:
        raise ValidationError(f"No support plan #{plan_id}")
    reviews = list_reviews(plan_id)
    return {
        "plan":         rec,
        "reviews":      reviews,
        "review_count": len(reviews),
        "by_outcome":   dict(Counter(r.outcome for r in reviews)),
        "last_review":  reviews[0].review_date if reviews else None,
    }


def cohort_summary(*, year_group: str | None = None,
                   academic_year: str | None = None) -> dict[str, Any]:
    rows = list_plans(year_group=year_group,
                        academic_year=academic_year)
    return {
        "total":       len(rows),
        "by_status":   dict(Counter(r.status for r in rows)),
        "by_type":     dict(Counter(r.plan_type for r in rows)),
        "by_priority": dict(Counter(r.priority for r in rows)),
        "active":      sum(1 for r in rows if r.status == "Active"),
    }


def overdue_reviews(today: str | None = None) -> list[SupportPlan]:
    """Return Active plans whose ``next_review_date`` is before
    today (or ``today`` if supplied)."""
    init_db()
    cmp_date = today or _dt.date.today().isoformat()
    rows = list_plans(status="Active")
    return [r for r in rows
            if r.next_review_date and r.next_review_date < cmp_date]
