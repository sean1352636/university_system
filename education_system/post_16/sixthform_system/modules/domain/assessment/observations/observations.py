"""Observations — teacher lesson observations for the Sixth Form System.

One row per observation: a senior member of staff, peer, or appraiser
watches another teacher's lesson and records what they saw. Used for
QA, performance management, and CPD planning.

Cascade is intentionally not on a foreign-keyed table — the teacher /
observer fields are free-text so observations survive staff turnover
intact. ``class_group_id`` is captured as a soft pointer (validated at
write time but not enforced after).
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.post_16.sixthform_system.core import paths
from education_system.post_16.sixthform_system.modules.domain.assessment.observations import (
    observations as data,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.OBSERVATIONS_DB


OBSERVATION_TYPES: tuple[str, ...] = (
    "Formal",
    "Drop-In",
    "Learning Walk",
    "Peer",
    "Self",
    "Paired",
    "Appraisal",
    "Other",
)
DEFAULT_OBSERVATION_TYPE: str = "Drop-In"

# Numbered grading 1-4 with labels (1 = top), per the common OFSTED
# four-point scale. Stored as int + auto-labelled.
JUDGEMENTS: tuple[int, ...] = (1, 2, 3, 4)
_JUDGEMENT_LABELS: dict[int, str] = {
    1: "Outstanding",
    2: "Good",
    3: "Requires Improvement",
    4: "Inadequate",
}

STATUSES: tuple[str, ...] = (
    "Draft", "Submitted", "Discussed", "Acknowledged",
    "Action Required", "Closed",
)
DEFAULT_STATUS: str = "Draft"
OPEN_STATUSES: tuple[str, ...] = (
    "Draft", "Submitted", "Discussed", "Action Required",
)

YEAR_GROUPS: tuple[str, ...] = ("Year 12", "Year 13", "Mixed")

FOCUS_AREAS: tuple[str, ...] = (
    "Whole Lesson",
    "Behaviour Management",
    "Differentiation",
    "Assessment for Learning",
    "Questioning",
    "Pace",
    "Subject Knowledge",
    "Literacy",
    "Numeracy",
    "Stretch & Challenge",
    "SEND Provision",
    "Use of Technology",
    "Modelling",
    "Marking & Feedback",
    "Other",
)
DEFAULT_FOCUS_AREA: str = "Whole Lesson"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}(:\d{2})?$")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    observation_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    observer          TEXT NOT NULL,
    observed_teacher  TEXT NOT NULL,
    observation_date  TEXT NOT NULL,
    observation_time  TEXT,
    duration_minutes  INTEGER,
    observation_type  TEXT NOT NULL DEFAULT 'Drop-In',
    focus_area        TEXT,
    subject_name      TEXT,
    class_group_id    INTEGER,
    class_group_label TEXT,
    year_group        TEXT,
    room              TEXT,
    judgement         INTEGER,
    strengths         TEXT,
    areas_to_develop  TEXT,
    student_engagement TEXT,
    student_progress  TEXT,
    follow_up_required INTEGER NOT NULL DEFAULT 0,
    follow_up_due     TEXT,
    follow_up_by      TEXT,
    shared_with_teacher INTEGER NOT NULL DEFAULT 0,
    teacher_response  TEXT,
    status            TEXT NOT NULL DEFAULT 'Draft',
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_obs_observer ON observations(observer);
CREATE INDEX IF NOT EXISTS idx_obs_teacher  ON observations(observed_teacher);
CREATE INDEX IF NOT EXISTS idx_obs_date     ON observations(observation_date);
CREATE INDEX IF NOT EXISTS idx_obs_status   ON observations(status);
CREATE INDEX IF NOT EXISTS idx_obs_type     ON observations(observation_type);
CREATE INDEX IF NOT EXISTS idx_obs_judge    ON observations(judgement);
"""


@dataclass
class Observation:
    observation_id: int
    observer: str
    observed_teacher: str
    observation_date: str
    observation_time: str | None
    duration_minutes: int | None
    observation_type: str
    focus_area: str | None
    subject_name: str | None
    class_group_id: int | None
    class_group_label: str | None
    year_group: str | None
    room: str | None
    judgement: int | None
    strengths: str | None
    areas_to_develop: str | None
    student_engagement: str | None
    student_progress: str | None
    follow_up_required: bool
    follow_up_due: str | None
    follow_up_by: str | None
    shared_with_teacher: bool
    teacher_response: str | None
    status: str
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    @property
    def judgement_label(self) -> str:
        return (_JUDGEMENT_LABELS.get(self.judgement, "—")
                if self.judgement else "—")

    @property
    def follow_up_overdue(self) -> bool:
        if not (self.follow_up_required and self.follow_up_due
                  and self.is_open):
            return False
        return self.follow_up_due < _dt.date.today().isoformat()


@dataclass
class ObservationRow:
    observation: Observation


@dataclass
class TeacherSummary:
    teacher: str
    total: int
    by_judgement: dict[int, int]
    average_judgement: float | None
    most_recent: str | None
    by_type: dict[str, int]


@dataclass
class Summary:
    total: int
    by_status: dict[str, int]
    by_type: dict[str, int]
    by_judgement: dict[int, int]
    by_focus: dict[str, int]
    open_count: int
    follow_up_open: int
    follow_up_overdue: int
    average_judgement: float | None
    distinct_observers: int
    distinct_teachers: int


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Observations schema ready at %s", DB_PATH)

    _DB_READY = True


def _row(r: sqlite3.Row) -> Observation:
    return Observation(
        observation_id=r["observation_id"],
        observer=r["observer"],
        observed_teacher=r["observed_teacher"],
        observation_date=r["observation_date"],
        observation_time=r["observation_time"],
        duration_minutes=r["duration_minutes"],
        observation_type=r["observation_type"],
        focus_area=r["focus_area"],
        subject_name=r["subject_name"],
        class_group_id=r["class_group_id"],
        class_group_label=r["class_group_label"],
        year_group=r["year_group"], room=r["room"],
        judgement=r["judgement"],
        strengths=r["strengths"],
        areas_to_develop=r["areas_to_develop"],
        student_engagement=r["student_engagement"],
        student_progress=r["student_progress"],
        follow_up_required=bool(r["follow_up_required"]),
        follow_up_due=r["follow_up_due"],
        follow_up_by=r["follow_up_by"],
        shared_with_teacher=bool(r["shared_with_teacher"]),
        teacher_response=r["teacher_response"],
        status=r["status"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_date(value: Any, label: str, *,
                    required: bool = False) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _validate_time(value: Any, label: str) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        return None
    s = str(value).strip()
    if not _TIME_RE.match(s):
        raise ValidationError(f"{label} must be HH:MM")
    if len(s) == 5:
        s = s + ":00"
    try:
        _dt.time.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real time") from None
    return s


def _validate_int(value: Any, label: str, *,
                   min_val: int | None = None,
                   max_val: int | None = None) -> int | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a whole number") from None
    if min_val is not None and n < min_val:
        raise ValidationError(f"{label} must be at least {min_val}")
    if max_val is not None and n > max_val:
        raise ValidationError(f"{label} must be at most {max_val}")
    return n


def _validate_class_group(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        gid = int(value)
    except (TypeError, ValueError):
        raise ValidationError(
            "class_group_id must be a number") from None
    try:
        from education_system.post_16.sixthform_system.modules.domain.academics.class_groups import (
            class_groups as _cg,
        )
        if _cg.get_group(gid) is None:
            raise ValidationError(f"No class group with id {gid}")
    except ValidationError:
        raise
    except Exception:
        pass
    return gid


def _validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["observer"] = _require(payload.get("observer"),
                                    "Observer").strip()
    out["observed_teacher"] = _require(
        payload.get("observed_teacher"), "Observed teacher").strip()
    out["observation_date"] = _validate_date(
        payload.get("observation_date"), "Observation date",
        required=True)
    out["observation_time"] = _validate_time(
        payload.get("observation_time"), "Observation time")

    out["duration_minutes"] = _validate_int(
        payload.get("duration_minutes"), "Duration (mins)",
        min_val=0, max_val=24 * 60)

    otype = (payload.get("observation_type")
              or DEFAULT_OBSERVATION_TYPE).strip()
    if otype not in OBSERVATION_TYPES:
        raise ValidationError(
            f"Type must be one of: "
            f"{', '.join(OBSERVATION_TYPES)}")
    out["observation_type"] = otype

    focus = (payload.get("focus_area") or "").strip()
    if focus and focus not in FOCUS_AREAS:
        raise ValidationError(
            f"Focus area must be one of: "
            f"{', '.join(FOCUS_AREAS)}")
    out["focus_area"] = focus or None

    year = (payload.get("year_group") or "").strip()
    if year and year not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of: "
            f"{', '.join(YEAR_GROUPS)}")
    out["year_group"] = year or None

    out["class_group_id"] = _validate_class_group(
        payload.get("class_group_id"))
    out["class_group_label"] = (payload.get("class_group_label")
                                   or "").strip() or None
    out["subject_name"] = (payload.get("subject_name")
                              or "").strip() or None
    out["room"] = (payload.get("room") or "").strip() or None

    judgement = payload.get("judgement")
    if judgement in (None, ""):
        out["judgement"] = None
    else:
        try:
            n = int(judgement)
        except (TypeError, ValueError):
            raise ValidationError(
                "Judgement must be a whole number") from None
        if n not in JUDGEMENTS:
            raise ValidationError(
                "Judgement must be 1-4 (1=Outstanding)")
        out["judgement"] = n

    out["strengths"]          = (payload.get("strengths")
                                    or "").strip() or None
    out["areas_to_develop"]   = (payload.get("areas_to_develop")
                                    or "").strip() or None
    out["student_engagement"] = (payload.get("student_engagement")
                                    or "").strip() or None
    out["student_progress"]   = (payload.get("student_progress")
                                    or "").strip() or None

    out["follow_up_required"] = bool(
        payload.get("follow_up_required"))
    out["follow_up_due"] = _validate_date(
        payload.get("follow_up_due"), "Follow-up due")
    out["follow_up_by"]  = (payload.get("follow_up_by")
                              or "").strip() or None
    out["shared_with_teacher"] = bool(
        payload.get("shared_with_teacher"))
    out["teacher_response"]    = (payload.get("teacher_response")
                                    or "").strip() or None

    status = (payload.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status
    out["notes"] = (payload.get("notes") or "").strip() or None
    return out


# ── CRUD ──────────────────────────────────────────────────────────

def create_observation(payload: dict[str, Any]) -> Observation:
    init_db()
    p = _validate_payload(payload)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO observations
                   (observer, observed_teacher, observation_date,
                    observation_time, duration_minutes,
                    observation_type, focus_area, subject_name,
                    class_group_id, class_group_label, year_group,
                    room, judgement, strengths, areas_to_develop,
                    student_engagement, student_progress,
                    follow_up_required, follow_up_due, follow_up_by,
                    shared_with_teacher, teacher_response, status,
                    notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["observer"], p["observed_teacher"],
             p["observation_date"], p["observation_time"],
             p["duration_minutes"], p["observation_type"],
             p["focus_area"], p["subject_name"],
             p["class_group_id"], p["class_group_label"],
             p["year_group"], p["room"], p["judgement"],
             p["strengths"], p["areas_to_develop"],
             p["student_engagement"], p["student_progress"],
             1 if p["follow_up_required"] else 0,
             p["follow_up_due"], p["follow_up_by"],
             1 if p["shared_with_teacher"] else 0,
             p["teacher_response"], p["status"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_observation(new_id)
    assert out is not None
    logger.info(
        "Created observation #%d %s of %s on %s (%s, judge=%s)",
        new_id, p["observer"], p["observed_teacher"],
        p["observation_date"], p["observation_type"],
        p["judgement"])
    return out


def get_observation(observation_id: int) -> Observation | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM observations WHERE observation_id = ?",
            (observation_id,)).fetchone()
        return _row(r) if r else None


def list_observations(
    *,
    observer_like: str | None = None,
    teacher_like: str | None = None,
    observation_type: str | None = None,
    status: str | None = None,
    judgement: int | None = None,
    subject_name: str | None = None,
    focus_area: str | None = None,
    year_group: str | None = None,
    open_only: bool = False,
    follow_up_overdue: bool = False,
    follow_up_only: bool = False,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[Observation]:
    init_db()
    clauses, args = [], []
    if observer_like:
        clauses.append("observer LIKE ?")
        args.append(f"%{observer_like.strip()}%")
    if teacher_like:
        clauses.append("observed_teacher LIKE ?")
        args.append(f"%{teacher_like.strip()}%")
    if observation_type:
        if observation_type not in OBSERVATION_TYPES:
            raise ValidationError(
                f"Type must be one of: "
                f"{', '.join(OBSERVATION_TYPES)}")
        clauses.append("observation_type = ?")
        args.append(observation_type)
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if judgement is not None:
        if judgement not in JUDGEMENTS:
            raise ValidationError("Judgement must be 1-4")
        clauses.append("judgement = ?")
        args.append(int(judgement))
    if subject_name:
        clauses.append("subject_name = ?")
        args.append(subject_name.strip())
    if focus_area:
        if focus_area not in FOCUS_AREAS:
            raise ValidationError(
                f"Focus area must be one of: "
                f"{', '.join(FOCUS_AREAS)}")
        clauses.append("focus_area = ?")
        args.append(focus_area)
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year group must be one of: "
                f"{', '.join(YEAR_GROUPS)}")
        clauses.append("year_group = ?")
        args.append(year_group)
    if open_only:
        ph = ",".join("?" * len(OPEN_STATUSES))
        clauses.append(f"status IN ({ph})")
        args.extend(OPEN_STATUSES)
    if follow_up_only:
        clauses.append("follow_up_required = 1")
    if follow_up_overdue:
        today = _dt.date.today().isoformat()
        ph = ",".join("?" * len(OPEN_STATUSES))
        clauses.append(
            f"follow_up_required = 1 "
            f"AND follow_up_due IS NOT NULL "
            f"AND follow_up_due < ? "
            f"AND status IN ({ph})")
        args.append(today)
        args.extend(OPEN_STATUSES)
    if date_from:
        clauses.append("observation_date >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("observation_date <= ?")
        args.append(_validate_date(date_to, "date_to"))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM observations {where} "
           "ORDER BY observation_date DESC, observation_id DESC")
    with _connect() as conn:
        return [_row(r)
                for r in conn.execute(sql, args).fetchall()]


def update_observation(observation_id: int,
                        payload: dict[str, Any]) -> Observation:
    init_db()
    existing = get_observation(observation_id)
    if existing is None:
        raise ValidationError(
            f"No observation #{observation_id}")
    merged = {
        "observer":             payload.get("observer",
                                             existing.observer),
        "observed_teacher":     payload.get("observed_teacher",
                                             existing.observed_teacher),
        "observation_date":     payload.get("observation_date",
                                             existing.observation_date),
        "observation_time":     payload.get("observation_time",
                                             existing.observation_time),
        "duration_minutes":     payload.get("duration_minutes",
                                             existing.duration_minutes),
        "observation_type":     payload.get("observation_type",
                                             existing.observation_type),
        "focus_area":           payload.get("focus_area",
                                             existing.focus_area),
        "subject_name":         payload.get("subject_name",
                                             existing.subject_name),
        "class_group_id":       payload.get("class_group_id",
                                             existing.class_group_id),
        "class_group_label":    payload.get("class_group_label",
                                             existing.class_group_label),
        "year_group":           payload.get("year_group",
                                             existing.year_group),
        "room":                 payload.get("room", existing.room),
        "judgement":            payload.get("judgement",
                                             existing.judgement),
        "strengths":            payload.get("strengths",
                                             existing.strengths),
        "areas_to_develop":     payload.get("areas_to_develop",
                                             existing.areas_to_develop),
        "student_engagement":   payload.get("student_engagement",
                                             existing.student_engagement),
        "student_progress":     payload.get("student_progress",
                                             existing.student_progress),
        "follow_up_required":   payload.get("follow_up_required",
                                             existing.follow_up_required),
        "follow_up_due":        payload.get("follow_up_due",
                                             existing.follow_up_due),
        "follow_up_by":         payload.get("follow_up_by",
                                             existing.follow_up_by),
        "shared_with_teacher":  payload.get("shared_with_teacher",
                                             existing.shared_with_teacher),
        "teacher_response":     payload.get("teacher_response",
                                             existing.teacher_response),
        "status":               payload.get("status",
                                             existing.status),
        "notes":                payload.get("notes", existing.notes),
    }
    p = _validate_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE observations SET
                   observer = ?, observed_teacher = ?,
                   observation_date = ?, observation_time = ?,
                   duration_minutes = ?, observation_type = ?,
                   focus_area = ?, subject_name = ?,
                   class_group_id = ?, class_group_label = ?,
                   year_group = ?, room = ?, judgement = ?,
                   strengths = ?, areas_to_develop = ?,
                   student_engagement = ?, student_progress = ?,
                   follow_up_required = ?, follow_up_due = ?,
                   follow_up_by = ?, shared_with_teacher = ?,
                   teacher_response = ?, status = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE observation_id = ?""",
            (p["observer"], p["observed_teacher"],
             p["observation_date"], p["observation_time"],
             p["duration_minutes"], p["observation_type"],
             p["focus_area"], p["subject_name"],
             p["class_group_id"], p["class_group_label"],
             p["year_group"], p["room"], p["judgement"],
             p["strengths"], p["areas_to_develop"],
             p["student_engagement"], p["student_progress"],
             1 if p["follow_up_required"] else 0,
             p["follow_up_due"], p["follow_up_by"],
             1 if p["shared_with_teacher"] else 0,
             p["teacher_response"], p["status"], p["notes"],
             observation_id),
        )
        conn.commit()
    out = get_observation(observation_id)
    assert out is not None
    return out


def set_status(observation_id: int, status: str) -> Observation:
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    return update_observation(observation_id, {"status": status})


def share(observation_id: int) -> Observation:
    """Flag as shared with the observed teacher. Bumps status to
    Submitted if it was a Draft."""
    existing = get_observation(observation_id)
    if existing is None:
        raise ValidationError(
            f"No observation #{observation_id}")
    payload: dict[str, Any] = {"shared_with_teacher": True}
    if existing.status == "Draft":
        payload["status"] = "Submitted"
    return update_observation(observation_id, payload)


def record_teacher_response(observation_id: int, *,
                             response: str) -> Observation:
    return update_observation(observation_id, {
        "teacher_response": response,
        "status": "Acknowledged",
    })


def close_observation(observation_id: int) -> Observation:
    return set_status(observation_id, "Closed")


def delete_observation(observation_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM observations WHERE observation_id = ?",
            (observation_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted observation #%d", observation_id)
            return True
        return False


# ── Per-teacher lookups ───────────────────────────────────────────

def observations_for_teacher(teacher: str) -> list[Observation]:
    return list_observations(teacher_like=teacher)


def teacher_summary(teacher: str) -> TeacherSummary:
    init_db()
    with _connect() as conn:
        rows = [_row(r) for r in conn.execute(
            "SELECT * FROM observations "
            "WHERE observed_teacher = ? "
            "ORDER BY observation_date DESC",
            (teacher.strip(),)).fetchall()]
    by_judgement = {j: 0 for j in JUDGEMENTS}
    by_type = {t: 0 for t in OBSERVATION_TYPES}
    j_sum = 0
    j_count = 0
    for r in rows:
        if r.judgement is not None:
            by_judgement[r.judgement] = by_judgement.get(
                r.judgement, 0) + 1
            j_sum += r.judgement
            j_count += 1
        by_type[r.observation_type] = by_type.get(
            r.observation_type, 0) + 1
    return TeacherSummary(
        teacher=teacher,
        total=len(rows),
        by_judgement=by_judgement,
        average_judgement=(round(j_sum / j_count, 2)
                              if j_count else None),
        most_recent=(rows[0].observation_date if rows else None),
        by_type=by_type,
    )


# ── Summary ───────────────────────────────────────────────────────

def summary() -> Summary:
    init_db()
    rows = list_observations()
    by_status = {s: 0 for s in STATUSES}
    by_type = {t: 0 for t in OBSERVATION_TYPES}
    by_judgement = {j: 0 for j in JUDGEMENTS}
    by_focus: dict[str, int] = {}
    open_count = 0
    follow_up_open = 0
    follow_up_overdue = 0
    j_sum = 0
    j_count = 0
    observers: set[str] = set()
    teachers: set[str] = set()
    today = _dt.date.today().isoformat()
    for r in rows:
        by_status[r.status] = by_status.get(r.status, 0) + 1
        by_type[r.observation_type] = by_type.get(
            r.observation_type, 0) + 1
        if r.judgement is not None:
            by_judgement[r.judgement] = by_judgement.get(
                r.judgement, 0) + 1
            j_sum += r.judgement
            j_count += 1
        if r.focus_area:
            by_focus[r.focus_area] = by_focus.get(
                r.focus_area, 0) + 1
        observers.add(r.observer)
        teachers.add(r.observed_teacher)
        if r.is_open:
            open_count += 1
        if r.follow_up_required and r.is_open:
            follow_up_open += 1
            if (r.follow_up_due
                    and r.follow_up_due < today):
                follow_up_overdue += 1
    return Summary(
        total=len(rows),
        by_status=by_status,
        by_type=by_type,
        by_judgement=by_judgement,
        by_focus=dict(sorted(by_focus.items(),
                                 key=lambda kv: kv[1],
                                 reverse=True)),
        open_count=open_count,
        follow_up_open=follow_up_open,
        follow_up_overdue=follow_up_overdue,
        average_judgement=(round(j_sum / j_count, 2)
                              if j_count else None),
        distinct_observers=len(observers),
        distinct_teachers=len(teachers),
    )


# ── Helpers ───────────────────────────────────────────────────────

def judgement_label(grade: int | None) -> str:
    return _JUDGEMENT_LABELS.get(grade, "—") if grade else "—"
