"""Lesson-observation data layer for the Secondary School System.

One row per ``observations`` event. Captures who taught the lesson,
when and where, the observer + observation type, the overall judgement,
free-text strengths/development_areas/action_points, and a status
workflow (Scheduled → Complete → FollowUp → Closed).
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Any

from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
    ValidationError, YEAR_GROUPS, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

OBSERVATION_TYPES: tuple[str, ...] = (
    "Formal", "Learning walk", "Departmental", "Performance",
    "Coaching", "Peer", "External", "Other")
DEFAULT_TYPE: str = "Learning walk"

JUDGEMENTS: tuple[str, ...] = (
    "Outstanding", "Good", "Requires improvement",
    "Inadequate", "Not judged")
DEFAULT_JUDGEMENT: str = "Not judged"

OBSERVATION_STATUSES: tuple[str, ...] = (
    "Scheduled", "Complete", "FollowUp", "Cancelled", "Closed")
DEFAULT_STATUS: str = "Scheduled"

MIN_PERIOD = 1
MAX_PERIOD = 8

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    observation_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher          TEXT NOT NULL,
    subject_id       INTEGER,
    year_group       TEXT,
    form_group       TEXT,
    observation_date TEXT NOT NULL DEFAULT (date('now')),
    period           INTEGER,
    observer         TEXT NOT NULL,
    observation_type TEXT NOT NULL DEFAULT 'Learning walk',
    focus            TEXT,
    judgement        TEXT NOT NULL DEFAULT 'Not judged',
    strengths        TEXT,
    development_areas TEXT,
    action_points    TEXT,
    follow_up_date   TEXT,
    status           TEXT NOT NULL DEFAULT 'Scheduled',
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id)
);

CREATE INDEX IF NOT EXISTS idx_obs_teacher
    ON observations(teacher);
CREATE INDEX IF NOT EXISTS idx_obs_date
    ON observations(observation_date);
CREATE INDEX IF NOT EXISTS idx_obs_status
    ON observations(status);
"""


@dataclass
class Observation:
    observation_id: int
    teacher: str
    subject_id: int | None
    year_group: str | None
    form_group: str | None
    observation_date: str
    period: int | None
    observer: str
    observation_type: str
    focus: str | None
    judgement: str
    strengths: str | None
    development_areas: str | None
    action_points: str | None
    follow_up_date: str | None
    status: str
    notes: str | None
    subject_code: str | None = None
    subject_name: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.secondarysch_system.modules.domain.academics.subjects import (
        subjects as subjects_data,
    )
    subjects_data.init_db()
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise observations table")
        raise
    logger.info("Secondary observations table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> Observation:
    keys = r.keys()
    return Observation(
        observation_id=r["observation_id"], teacher=r["teacher"],
        subject_id=r["subject_id"], year_group=r["year_group"],
        form_group=r["form_group"],
        observation_date=r["observation_date"], period=r["period"],
        observer=r["observer"],
        observation_type=r["observation_type"],
        focus=r["focus"], judgement=r["judgement"],
        strengths=r["strengths"],
        development_areas=r["development_areas"],
        action_points=r["action_points"],
        follow_up_date=r["follow_up_date"],
        status=r["status"], notes=r["notes"],
        subject_code=r["subject_code"] if "subject_code" in keys else None,
        subject_name=r["subject_name"] if "subject_name" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
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


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    teacher = (data.get("teacher") or "").strip()
    if not teacher:
        raise ValidationError("Teacher is required")
    if len(teacher) > 64:
        raise ValidationError("Teacher must be 64 characters or fewer")
    out["teacher"] = teacher

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
        from education_system.secondarysch_system.modules.domain.academics.subjects import (
            subjects as subjects_data,
        )
        if subjects_data.get(sid) is None:
            raise ValidationError(f"No subject #{sid}")
        out["subject_id"] = sid

    yg = (data.get("year_group") or "").strip()
    if yg and yg not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of {', '.join(YEAR_GROUPS)}")
    out["year_group"] = yg or None
    out["form_group"] = (data.get("form_group") or "").strip() or None

    out["observation_date"] = _validate_date(
        data.get("observation_date"), "Observation date")

    period = data.get("period")
    if period in (None, "") or (isinstance(period, str)
                                  and not period.strip()):
        out["period"] = None
    else:
        try:
            p = int(period)
        except (TypeError, ValueError):
            raise ValidationError("Period must be a number") from None
        if not (MIN_PERIOD <= p <= MAX_PERIOD):
            raise ValidationError(
                f"Period must be between {MIN_PERIOD} and {MAX_PERIOD}")
        out["period"] = p

    observer = (data.get("observer") or "").strip()
    if not observer:
        raise ValidationError("Observer is required")
    out["observer"] = observer

    otype = (data.get("observation_type") or DEFAULT_TYPE).strip()
    if otype not in OBSERVATION_TYPES:
        raise ValidationError(
            f"Observation type must be one of "
            f"{', '.join(OBSERVATION_TYPES)}")
    out["observation_type"] = otype

    judgement = (data.get("judgement") or DEFAULT_JUDGEMENT).strip()
    if judgement not in JUDGEMENTS:
        raise ValidationError(
            f"Judgement must be one of {', '.join(JUDGEMENTS)}")
    out["judgement"] = judgement

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in OBSERVATION_STATUSES:
        raise ValidationError(
            f"Status must be one of "
            f"{', '.join(OBSERVATION_STATUSES)}")
    out["status"] = status

    out["focus"]             = (data.get("focus") or "").strip() or None
    out["strengths"]         = (data.get("strengths") or "").strip() or None
    out["development_areas"] = (data.get("development_areas") or "").strip() or None
    out["action_points"]     = (data.get("action_points") or "").strip() or None
    out["follow_up_date"]    = _validate_date(
        data.get("follow_up_date"), "Follow-up date", required=False)
    out["notes"]             = (data.get("notes") or "").strip() or None

    if (out["status"] == "Complete"
            and out["judgement"] == "Not judged"):
        raise ValidationError(
            "Judgement is required when status is Complete")
    if (out["follow_up_date"]
            and out["follow_up_date"] < out["observation_date"]):
        raise ValidationError(
            "Follow-up date cannot be before observation date")
    return out


def create(data: dict[str, Any]) -> Observation:
    init_db()
    payload = _validate(data)
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO observations
                       (teacher, subject_id, year_group, form_group,
                        observation_date, period, observer,
                        observation_type, focus, judgement,
                        strengths, development_areas, action_points,
                        follow_up_date, status, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["teacher"], payload["subject_id"],
                 payload["year_group"], payload["form_group"],
                 payload["observation_date"], payload["period"],
                 payload["observer"], payload["observation_type"],
                 payload["focus"], payload["judgement"],
                 payload["strengths"], payload["development_areas"],
                 payload["action_points"], payload["follow_up_date"],
                 payload["status"], payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create observation")
        raise
    rec = get(new_id)
    assert rec is not None
    logger.info(
        "Created observation #%d teacher=%s observer=%s date=%s "
        "type=%s status=%s",
        rec.observation_id, rec.teacher, rec.observer,
        rec.observation_date, rec.observation_type, rec.status)
    return rec


def get(observation_id: int) -> Observation | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT o.*, s.code AS subject_code,
                          s.name AS subject_name
                   FROM observations o
                   LEFT JOIN subjects s ON s.subject_id = o.subject_id
                   WHERE o.observation_id = ?""",
                (observation_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get(%s) failed", observation_id)
        raise
    return _row(r) if r else None


def list_observations(*, teacher: str | None = None,
                      observer: str | None = None,
                      observation_type: str | None = None,
                      judgement: str | None = None,
                      status: str | None = None,
                      year_group: str | None = None,
                      date_from: str | None = None,
                      date_to: str | None = None
                      ) -> list[Observation]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if teacher:
        where.append("o.teacher = ?")
        params.append(teacher.strip())
    if observer:
        where.append("o.observer = ?")
        params.append(observer.strip())
    if observation_type:
        if observation_type not in OBSERVATION_TYPES:
            raise ValidationError(
                f"Type filter must be one of "
                f"{', '.join(OBSERVATION_TYPES)}")
        where.append("o.observation_type = ?")
        params.append(observation_type)
    if judgement:
        if judgement not in JUDGEMENTS:
            raise ValidationError(
                f"Judgement filter must be one of "
                f"{', '.join(JUDGEMENTS)}")
        where.append("o.judgement = ?")
        params.append(judgement)
    if status:
        if status not in OBSERVATION_STATUSES:
            raise ValidationError(
                f"Status filter must be one of "
                f"{', '.join(OBSERVATION_STATUSES)}")
        where.append("o.status = ?")
        params.append(status)
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
        where.append("o.year_group = ?")
        params.append(year_group)
    if date_from:
        where.append("o.observation_date >= ?")
        params.append(_validate_date(date_from, "From date"))
    if date_to:
        where.append("o.observation_date <= ?")
        params.append(_validate_date(date_to, "To date"))
    sql = ("""SELECT o.*, s.code AS subject_code,
                     s.name AS subject_name
              FROM observations o
              LEFT JOIN subjects s ON s.subject_id = o.subject_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY o.observation_date DESC, o.observation_id DESC"
    try:
        with _connect() as conn:
            return [_row(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_observations failed")
        raise


def update(observation_id: int,
           data: dict[str, Any]) -> Observation:
    init_db()
    existing = get(observation_id)
    if existing is None:
        raise ValidationError(f"No observation #{observation_id}")
    merged = {k: data.get(k, getattr(existing, k))
              for k in ("teacher", "subject_id", "year_group",
                         "form_group", "observation_date", "period",
                         "observer", "observation_type", "focus",
                         "judgement", "strengths", "development_areas",
                         "action_points", "follow_up_date", "status",
                         "notes")}
    payload = _validate(merged)
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE observations SET
                       teacher = ?, subject_id = ?, year_group = ?,
                       form_group = ?, observation_date = ?, period = ?,
                       observer = ?, observation_type = ?, focus = ?,
                       judgement = ?, strengths = ?,
                       development_areas = ?, action_points = ?,
                       follow_up_date = ?, status = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE observation_id = ?""",
                (payload["teacher"], payload["subject_id"],
                 payload["year_group"], payload["form_group"],
                 payload["observation_date"], payload["period"],
                 payload["observer"], payload["observation_type"],
                 payload["focus"], payload["judgement"],
                 payload["strengths"], payload["development_areas"],
                 payload["action_points"], payload["follow_up_date"],
                 payload["status"], payload["notes"], observation_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update observation #%d",
                         observation_id)
        raise
    rec = get(observation_id)
    assert rec is not None
    logger.info("Updated observation #%d (status %s, judgement %s)",
                rec.observation_id, rec.status, rec.judgement)
    return rec


def set_status(observation_id: int, status: str) -> Observation:
    return update(observation_id, {"status": status})


def delete(observation_id: int) -> bool:
    init_db()
    existing = get(observation_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM observations WHERE observation_id = ?",
                (observation_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete observation #%d",
                         observation_id)
        raise
    if deleted:
        logger.info("Deleted observation #%d (teacher %s)",
                    observation_id, existing.teacher)
    return deleted


def teacher_summary(teacher: str) -> dict[str, Any]:
    rows = list_observations(teacher=teacher)
    return {
        "teacher":     teacher,
        "total":       len(rows),
        "by_judgement": dict(Counter(r.judgement for r in rows)),
        "by_status":   dict(Counter(r.status for r in rows)),
        "by_type":     dict(Counter(r.observation_type for r in rows)),
        "observations": rows,
    }


def cohort_summary() -> dict[str, Any]:
    rows = list_observations()
    return {
        "total":        len(rows),
        "by_judgement": dict(Counter(r.judgement for r in rows)),
        "by_status":    dict(Counter(r.status for r in rows)),
        "by_type":      dict(Counter(r.observation_type for r in rows)),
        "follow_ups":   sum(1 for r in rows if r.status == "FollowUp"),
    }
