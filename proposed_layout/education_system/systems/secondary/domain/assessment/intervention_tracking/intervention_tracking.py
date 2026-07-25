"""Intervention-tracking data layer for the Secondary School System.

Two tables:

* ``interventions``         — one row per pupil intervention. Records
                              the goal, baseline/target/current grades,
                              who is leading it, where + how often it
                              happens, and a status workflow:
                              Planned → Active → Complete → Cancelled.
* ``intervention_reviews``  — periodic review checkpoints attached to
                              each intervention with attendance %,
                              on-track flag, and notes.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Any

from education_system.systems.secondary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

INTERVENTION_TYPES: tuple[str, ...] = (
    "Catch-up", "Mentoring", "Tutoring", "In-class support",
    "Small group", "Pastoral", "Behaviour", "Attendance", "Other")
DEFAULT_TYPE: str = "Catch-up"

INTERVENTION_STATUSES: tuple[str, ...] = (
    "Planned", "Active", "Paused", "Complete", "Cancelled")
DEFAULT_STATUS: str = "Planned"

FREQUENCIES: tuple[str, ...] = (
    "Daily", "Twice weekly", "Weekly", "Fortnightly",
    "Monthly", "One-off", "Other")
DEFAULT_FREQUENCY: str = "Weekly"

OUTCOMES: tuple[str, ...] = (
    "Successful", "Partial", "Unsuccessful", "Pending")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_GRADE_RE = re.compile(r"^[A-Za-z0-9*+\-]{1,3}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS interventions (
    intervention_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id          TEXT NOT NULL,
    subject_id        INTEGER,
    intervention_type TEXT NOT NULL DEFAULT 'Catch-up',
    goal              TEXT,
    start_date        TEXT NOT NULL DEFAULT (date('now')),
    end_date          TEXT,
    status            TEXT NOT NULL DEFAULT 'Planned',
    led_by            TEXT,
    location          TEXT,
    frequency         TEXT NOT NULL DEFAULT 'Weekly',
    baseline_grade    TEXT,
    target_grade      TEXT,
    current_grade     TEXT,
    outcome           TEXT,
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id)
);

CREATE TABLE IF NOT EXISTS intervention_reviews (
    review_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    intervention_id   INTEGER NOT NULL,
    review_date       TEXT NOT NULL DEFAULT (date('now')),
    reviewer          TEXT,
    attendance_pct    REAL,
    on_track          INTEGER NOT NULL DEFAULT 1,
    progress_notes    TEXT,
    next_action       TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (intervention_id) REFERENCES interventions(intervention_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_int_pupil ON interventions(pupil_id);
CREATE INDEX IF NOT EXISTS idx_int_status ON interventions(status);
CREATE INDEX IF NOT EXISTS idx_intrev_int
    ON intervention_reviews(intervention_id);
"""


@dataclass
class Intervention:
    intervention_id: int
    pupil_id: str
    subject_id: int | None
    intervention_type: str
    goal: str | None
    start_date: str
    end_date: str | None
    status: str
    led_by: str | None
    location: str | None
    frequency: str
    baseline_grade: str | None
    target_grade: str | None
    current_grade: str | None
    outcome: str | None
    notes: str | None
    subject_code: str | None = None
    subject_name: str | None = None
    pupil_name: str | None = None
    pupil_year: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class InterventionReview:
    review_id: int
    intervention_id: int
    review_date: str
    reviewer: str | None
    attendance_pct: float | None
    on_track: bool
    progress_notes: str | None
    next_action: str | None
    created_at: str | None = None


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.systems.secondary.domain.academics.subjects import (
        subjects as subjects_data,
    )
    subjects_data.init_db()
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise interventions tables")
        raise
    logger.info("Secondary interventions tables ready")
    _DB_READY = True


def _row_intervention(r: sqlite3.Row) -> Intervention:
    keys = r.keys()
    return Intervention(
        intervention_id=r["intervention_id"], pupil_id=r["pupil_id"],
        subject_id=r["subject_id"],
        intervention_type=r["intervention_type"],
        goal=r["goal"],
        start_date=r["start_date"], end_date=r["end_date"],
        status=r["status"], led_by=r["led_by"],
        location=r["location"], frequency=r["frequency"],
        baseline_grade=r["baseline_grade"],
        target_grade=r["target_grade"],
        current_grade=r["current_grade"],
        outcome=r["outcome"], notes=r["notes"],
        subject_code=r["subject_code"] if "subject_code" in keys else None,
        subject_name=r["subject_name"] if "subject_name" in keys else None,
        pupil_name=r["pupil_name"] if "pupil_name" in keys else None,
        pupil_year=r["pupil_year"] if "pupil_year" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_review(r: sqlite3.Row) -> InterventionReview:
    return InterventionReview(
        review_id=r["review_id"],
        intervention_id=r["intervention_id"],
        review_date=r["review_date"], reviewer=r["reviewer"],
        attendance_pct=r["attendance_pct"],
        on_track=bool(r["on_track"]),
        progress_notes=r["progress_notes"],
        next_action=r["next_action"],
        created_at=r["created_at"],
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


def _validate_grade(value: Any, label: str) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                and not value.strip()):
        return None
    s = str(value).strip()
    if not _GRADE_RE.match(s):
        raise ValidationError(
            f"{label} must be 1–3 chars (letters/digits/* + -)")
    return s


def _validate_intervention(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    pid = (data.get("pupil_id") or "").strip()
    if not pid:
        raise ValidationError("Pupil ID is required")
    from education_system.systems.secondary.domain.learners.pupils import (
        pupils as pupils_data,
    )
    if pupils_data.get_pupil(pid) is None:
        raise ValidationError(f"No pupil with id {pid}")
    out["pupil_id"] = pid

    sid_raw = data.get("subject_id")
    if sid_raw in (None, "") or (isinstance(sid_raw, str)
                                  and not sid_raw.strip()):
        out["subject_id"] = None
    else:
        try:
            sid = int(sid_raw)
        except (TypeError, ValueError):
            raise ValidationError(
                "Subject ID must be a number") from None
        from education_system.systems.secondary.domain.academics.subjects import (
            subjects as subjects_data,
        )
        if subjects_data.get(sid) is None:
            raise ValidationError(f"No subject #{sid}")
        out["subject_id"] = sid

    itype = (data.get("intervention_type") or DEFAULT_TYPE).strip()
    if itype not in INTERVENTION_TYPES:
        raise ValidationError(
            f"Type must be one of {', '.join(INTERVENTION_TYPES)}")
    out["intervention_type"] = itype

    out["start_date"] = _validate_date(data.get("start_date"),
                                         "Start date")
    out["end_date"]   = _validate_date(data.get("end_date"),
                                         "End date", required=False)
    if out["end_date"] and out["end_date"] < out["start_date"]:
        raise ValidationError("End date cannot be before start date")

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in INTERVENTION_STATUSES:
        raise ValidationError(
            f"Status must be one of "
            f"{', '.join(INTERVENTION_STATUSES)}")
    out["status"] = status

    freq = (data.get("frequency") or DEFAULT_FREQUENCY).strip()
    if freq not in FREQUENCIES:
        raise ValidationError(
            f"Frequency must be one of {', '.join(FREQUENCIES)}")
    out["frequency"] = freq

    out["baseline_grade"] = _validate_grade(
        data.get("baseline_grade"), "Baseline grade")
    out["target_grade"]   = _validate_grade(
        data.get("target_grade"), "Target grade")
    out["current_grade"]  = _validate_grade(
        data.get("current_grade"), "Current grade")

    outcome = (data.get("outcome") or "").strip()
    if outcome and outcome not in OUTCOMES:
        raise ValidationError(
            f"Outcome must be one of {', '.join(OUTCOMES)}")
    out["outcome"] = outcome or None

    out["goal"]     = (data.get("goal") or "").strip() or None
    out["led_by"]   = (data.get("led_by") or "").strip() or None
    out["location"] = (data.get("location") or "").strip() or None
    out["notes"]    = (data.get("notes") or "").strip() or None

    if (out["status"] in ("Complete", "Cancelled")
            and out["outcome"] is None):
        raise ValidationError(
            f"Outcome is required when status is {out['status']}")
    return out


def _validate_review(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    iid_raw = data.get("intervention_id")
    if iid_raw in (None, ""):
        raise ValidationError("Intervention ID is required")
    try:
        out["intervention_id"] = int(iid_raw)
    except (TypeError, ValueError):
        raise ValidationError(
            "Intervention ID must be a number") from None

    out["review_date"] = _validate_date(data.get("review_date"),
                                          "Review date")
    out["reviewer"] = (data.get("reviewer") or "").strip() or None

    att = data.get("attendance_pct")
    if att in (None, "") or (isinstance(att, str) and not att.strip()):
        out["attendance_pct"] = None
    else:
        try:
            v = float(att)
        except (TypeError, ValueError):
            raise ValidationError(
                "Attendance % must be a number") from None
        if v < 0 or v > 100:
            raise ValidationError(
                "Attendance % must be between 0 and 100")
        out["attendance_pct"] = v

    out["on_track"] = bool(data.get("on_track", True))
    out["progress_notes"] = (data.get("progress_notes") or "").strip() or None
    out["next_action"]    = (data.get("next_action") or "").strip() or None
    return out


# ── Intervention CRUD ────────────────────────────────────────────

def create(data: dict[str, Any]) -> Intervention:
    init_db()
    payload = _validate_intervention(data)
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO interventions
                       (pupil_id, subject_id, intervention_type, goal,
                        start_date, end_date, status, led_by, location,
                        frequency, baseline_grade, target_grade,
                        current_grade, outcome, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["pupil_id"], payload["subject_id"],
                 payload["intervention_type"], payload["goal"],
                 payload["start_date"], payload["end_date"],
                 payload["status"], payload["led_by"],
                 payload["location"], payload["frequency"],
                 payload["baseline_grade"], payload["target_grade"],
                 payload["current_grade"], payload["outcome"],
                 payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create intervention")
        raise
    rec = get(new_id)
    assert rec is not None
    logger.info(
        "Created intervention #%d pupil=%s type=%s status=%s",
        rec.intervention_id, rec.pupil_id, rec.intervention_type,
        rec.status)
    return rec


def get(intervention_id: int) -> Intervention | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT i.*, s.code AS subject_code,
                          s.name AS subject_name,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM interventions i
                   LEFT JOIN subjects s ON s.subject_id = i.subject_id
                   LEFT JOIN pupils p ON p.pupil_id = i.pupil_id
                   WHERE i.intervention_id = ?""",
                (intervention_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get(%s) failed", intervention_id)
        raise
    return _row_intervention(r) if r else None


def list_interventions(*, year_group: str | None = None,
                       status: str | None = None,
                       intervention_type: str | None = None,
                       pupil_id: str | None = None,
                       subject_id: int | None = None
                       ) -> list[Intervention]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
        where.append("p.year_group = ?")
        params.append(year_group)
    if status:
        if status not in INTERVENTION_STATUSES:
            raise ValidationError(
                f"Status filter must be one of "
                f"{', '.join(INTERVENTION_STATUSES)}")
        where.append("i.status = ?")
        params.append(status)
    if intervention_type:
        if intervention_type not in INTERVENTION_TYPES:
            raise ValidationError(
                f"Type filter must be one of "
                f"{', '.join(INTERVENTION_TYPES)}")
        where.append("i.intervention_type = ?")
        params.append(intervention_type)
    if pupil_id:
        where.append("i.pupil_id = ?")
        params.append(pupil_id.strip())
    if subject_id is not None:
        where.append("i.subject_id = ?")
        params.append(int(subject_id))
    sql = ("""SELECT i.*, s.code AS subject_code,
                     s.name AS subject_name,
                     (p.first_name || ' ' || p.last_name) AS pupil_name,
                     p.year_group AS pupil_year
              FROM interventions i
              LEFT JOIN subjects s ON s.subject_id = i.subject_id
              LEFT JOIN pupils p ON p.pupil_id = i.pupil_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += (" ORDER BY i.status, i.start_date DESC, "
            "p.last_name, p.first_name")
    try:
        with _connect() as conn:
            return [_row_intervention(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_interventions failed")
        raise


def update(intervention_id: int,
           data: dict[str, Any]) -> Intervention:
    init_db()
    existing = get(intervention_id)
    if existing is None:
        raise ValidationError(f"No intervention #{intervention_id}")
    merged = {k: data.get(k, getattr(existing, k))
              for k in ("pupil_id", "subject_id", "intervention_type",
                         "goal", "start_date", "end_date", "status",
                         "led_by", "location", "frequency",
                         "baseline_grade", "target_grade",
                         "current_grade", "outcome", "notes")}
    payload = _validate_intervention(merged)
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE interventions SET
                       pupil_id = ?, subject_id = ?,
                       intervention_type = ?, goal = ?,
                       start_date = ?, end_date = ?, status = ?,
                       led_by = ?, location = ?, frequency = ?,
                       baseline_grade = ?, target_grade = ?,
                       current_grade = ?, outcome = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE intervention_id = ?""",
                (payload["pupil_id"], payload["subject_id"],
                 payload["intervention_type"], payload["goal"],
                 payload["start_date"], payload["end_date"],
                 payload["status"], payload["led_by"],
                 payload["location"], payload["frequency"],
                 payload["baseline_grade"], payload["target_grade"],
                 payload["current_grade"], payload["outcome"],
                 payload["notes"], intervention_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to update intervention #%d", intervention_id)
        raise
    rec = get(intervention_id)
    assert rec is not None
    logger.info("Updated intervention #%d (status %s)",
                rec.intervention_id, rec.status)
    return rec


def set_status(intervention_id: int, status: str,
               *, outcome: str | None = None) -> Intervention:
    payload: dict[str, Any] = {"status": status}
    if outcome is not None:
        payload["outcome"] = outcome
    return update(intervention_id, payload)


def delete(intervention_id: int) -> bool:
    init_db()
    existing = get(intervention_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            cur = conn.execute(
                "DELETE FROM interventions WHERE intervention_id = ?",
                (intervention_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception(
            "Failed to delete intervention #%d", intervention_id)
        raise
    if deleted:
        logger.info("Deleted intervention #%d (cascade: reviews)",
                    intervention_id)
    return deleted


# ── Reviews ──────────────────────────────────────────────────────

def add_review(data: dict[str, Any]) -> InterventionReview:
    init_db()
    payload = _validate_review(data)
    if get(payload["intervention_id"]) is None:
        raise ValidationError(
            f"No intervention #{payload['intervention_id']}")
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO intervention_reviews
                       (intervention_id, review_date, reviewer,
                        attendance_pct, on_track, progress_notes,
                        next_action)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (payload["intervention_id"], payload["review_date"],
                 payload["reviewer"], payload["attendance_pct"],
                 1 if payload["on_track"] else 0,
                 payload["progress_notes"], payload["next_action"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception(
            "Failed to add review to intervention %d",
            payload["intervention_id"])
        raise
    logger.info(
        "Added review #%d to intervention #%d (on_track=%s, att=%s%%)",
        new_id, payload["intervention_id"], payload["on_track"],
        payload["attendance_pct"])
    rec = get_review(new_id)
    assert rec is not None
    return rec


def get_review(review_id: int) -> InterventionReview | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM intervention_reviews WHERE review_id = ?",
                (review_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_review(%s) failed", review_id)
        raise
    return _row_review(r) if r else None


def list_reviews(intervention_id: int) -> list[InterventionReview]:
    init_db()
    try:
        with _connect() as conn:
            return [_row_review(r) for r in conn.execute(
                "SELECT * FROM intervention_reviews "
                "WHERE intervention_id = ? "
                "ORDER BY review_date DESC, review_id DESC",
                (intervention_id,),
            ).fetchall()]
    except sqlite3.Error:
        logger.exception("list_reviews(%s) failed", intervention_id)
        raise


def delete_review(review_id: int) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM intervention_reviews WHERE review_id = ?",
                (review_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete review #%d", review_id)
        raise
    if deleted:
        logger.info("Deleted intervention review #%d", review_id)
    return deleted


def intervention_summary(intervention_id: int) -> dict[str, Any]:
    init_db()
    rec = get(intervention_id)
    if rec is None:
        raise ValidationError(f"No intervention #{intervention_id}")
    reviews = list_reviews(intervention_id)
    atts = [r.attendance_pct for r in reviews
            if r.attendance_pct is not None]
    on_track = sum(1 for r in reviews if r.on_track)
    return {
        "intervention": rec,
        "reviews":      reviews,
        "review_count": len(reviews),
        "avg_attendance": (round(sum(atts) / len(atts), 2)
                            if atts else None),
        "on_track":     on_track,
        "off_track":    len(reviews) - on_track,
    }


def cohort_summary(*, year_group: str | None = None) -> dict[str, Any]:
    rows = list_interventions(year_group=year_group)
    return {
        "total":     len(rows),
        "by_status": dict(Counter(r.status for r in rows)),
        "by_type":   dict(Counter(r.intervention_type for r in rows)),
        "by_outcome": dict(Counter(r.outcome for r in rows
                                     if r.outcome)),
    }
