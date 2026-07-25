"""Progress Tracking data layer for the Sixth Form System.

Two-table model:

* ``progress_reviews``  — one periodic review per (student, period).
                          Captures a snapshot in time: traffic-light
                          grades for overall progress / attitude /
                          homework, an attendance %, narrative
                          summaries, and the reviewer.
* ``progress_targets``  — one row per SMART-ish target attached to
                          a review. Status: Open / On Track /
                          At Risk / Met / Missed.

Lifecycle of a review:
    Draft → Published → Shared (with parents/student) → Archived
A Draft can be edited freely; a Published review is what's used in
reports; sharing just stamps when it went out.

Optional ``populate_from_data()`` helper auto-fills attendance % from
``attendance_report`` and a notes line from ``grades_report`` when
the staff member creates a new review.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date as _date
from typing import Any
from education_system.systems.sixth_form.infrastructure import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.PROGRESS_DB

# Traffic-light 1..4 scale: 1=Outstanding, 2=Good,
# 3=Requires Improvement, 4=Inadequate. Used for overall progress,
# attitude to learning, homework completion, risk.
RATINGS: tuple[str, ...] = (
    "1 — Outstanding", "2 — Good",
    "3 — Requires Improvement", "4 — Inadequate",
)
DEFAULT_RATING: str = "2 — Good"

RISK_LEVELS: tuple[str, ...] = ("Low", "Medium", "High", "Critical")
DEFAULT_RISK: str = "Low"

REVIEW_PERIODS: tuple[str, ...] = (
    "Autumn Half-Term 1", "Autumn Half-Term 2",
    "Spring Half-Term 1", "Spring Half-Term 2",
    "Summer Half-Term 1", "Summer Half-Term 2",
    "End of Year", "Mid-Cycle Check",
    "Ad Hoc",
)
DEFAULT_PERIOD: str = "Mid-Cycle Check"

REVIEW_STATUSES: tuple[str, ...] = (
    "Draft", "Published", "Shared", "Archived",
)
DEFAULT_REVIEW_STATUS: str = "Draft"
ACTIVE_REVIEW_STATUSES: tuple[str, ...] = (
    "Draft", "Published", "Shared")

TARGET_STATUSES: tuple[str, ...] = (
    "Open", "On Track", "At Risk", "Met", "Missed",
)
DEFAULT_TARGET_STATUS: str = "Open"
OPEN_TARGET_STATUSES: tuple[str, ...] = ("Open", "On Track", "At Risk")

TARGET_AREAS: tuple[str, ...] = (
    "Academic", "Attendance", "Punctuality", "Behaviour",
    "Homework", "Attitude", "Independent Study",
    "Exam Prep", "UCAS", "Wellbeing", "Other",
)
DEFAULT_TARGET_AREA: str = "Academic"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS progress_reviews (
    review_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id         TEXT NOT NULL,
    review_date        TEXT NOT NULL,
    period             TEXT NOT NULL DEFAULT 'Mid-Cycle Check',
    academic_year      TEXT,
    reviewer_staff_id  TEXT,
    overall            TEXT NOT NULL DEFAULT '2 — Good',
    attitude           TEXT NOT NULL DEFAULT '2 — Good',
    homework           TEXT NOT NULL DEFAULT '2 — Good',
    attendance_pct     REAL,
    risk_level         TEXT NOT NULL DEFAULT 'Low',
    status             TEXT NOT NULL DEFAULT 'Draft',
    academic_summary   TEXT,
    behaviour_summary  TEXT,
    next_steps         TEXT,
    notes              TEXT,
    shared_at          TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now')),
    UNIQUE (student_id, period, academic_year),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE,
    FOREIGN KEY (reviewer_staff_id) REFERENCES staff(staff_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS progress_targets (
    target_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id    INTEGER NOT NULL,
    area         TEXT NOT NULL DEFAULT 'Academic',
    description  TEXT NOT NULL,
    measure      TEXT,
    due_date     TEXT,
    status       TEXT NOT NULL DEFAULT 'Open',
    progress_note TEXT,
    closed_on    TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (review_id) REFERENCES progress_reviews(review_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pr_student ON progress_reviews(student_id);
CREATE INDEX IF NOT EXISTS idx_pr_period  ON progress_reviews(period);
CREATE INDEX IF NOT EXISTS idx_pr_status  ON progress_reviews(status);
CREATE INDEX IF NOT EXISTS idx_pr_date    ON progress_reviews(review_date);
CREATE INDEX IF NOT EXISTS idx_pt_review  ON progress_targets(review_id);
CREATE INDEX IF NOT EXISTS idx_pt_status  ON progress_targets(status);
CREATE INDEX IF NOT EXISTS idx_pt_due     ON progress_targets(due_date);
"""


@dataclass
class Review:
    review_id: int
    student_id: str
    review_date: str
    period: str
    academic_year: str | None
    reviewer_staff_id: str | None
    overall: str
    attitude: str
    homework: str
    attendance_pct: float | None
    risk_level: str
    status: str
    academic_summary: str | None
    behaviour_summary: str | None
    next_steps: str | None
    notes: str | None
    shared_at: str | None
    created_at: str
    updated_at: str

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_REVIEW_STATUSES

    @property
    def overall_score(self) -> int | None:
        try:
            return int(self.overall.split()[0])
        except (IndexError, ValueError):
            return None


@dataclass
class Target:
    target_id: int
    review_id: int
    area: str
    description: str
    measure: str | None
    due_date: str | None
    status: str
    progress_note: str | None
    closed_on: str | None
    created_at: str
    updated_at: str

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_TARGET_STATUSES


@dataclass
class ReviewView:
    review: Review
    student_name: str
    reviewer_name: str | None
    targets: list[Target]
    open_targets: int
    met_targets: int


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.systems.sixth_form.domain.staff import staff
    from education_system.systems.sixth_form.domain.staff import staff as _staff
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    _students.init_db()
    _staff.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Progress schema ready at %s", DB_PATH)

    _DB_READY = True


def _row_review(r: sqlite3.Row) -> Review:
    return Review(
        review_id=r["review_id"], student_id=r["student_id"],
        review_date=r["review_date"], period=r["period"],
        academic_year=r["academic_year"],
        reviewer_staff_id=r["reviewer_staff_id"],
        overall=r["overall"], attitude=r["attitude"],
        homework=r["homework"], attendance_pct=r["attendance_pct"],
        risk_level=r["risk_level"], status=r["status"],
        academic_summary=r["academic_summary"],
        behaviour_summary=r["behaviour_summary"],
        next_steps=r["next_steps"], notes=r["notes"],
        shared_at=r["shared_at"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_target(r: sqlite3.Row) -> Target:
    return Target(
        target_id=r["target_id"], review_id=r["review_id"],
        area=r["area"], description=r["description"],
        measure=r["measure"], due_date=r["due_date"],
        status=r["status"], progress_note=r["progress_note"],
        closed_on=r["closed_on"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _require(v, label: str):
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        raise ValidationError(f"{label} is required")
    return v


def _validate_date(v: Any, label: str, *,
                    required: bool = False) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(v).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _validate_student(v: Any) -> str:
    sid = _require(v, "Student ID").strip()
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    return sid


def _validate_staff(v: Any) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        return None
    sid = str(v).strip().upper()
    from education_system.systems.sixth_form.domain.staff import staff as _staff
    if _staff.get_staff(sid) is None:
        raise ValidationError(f"No staff with id {sid}")
    return sid


def _validate_rating(v: Any, label: str) -> str:
    s = (v or DEFAULT_RATING).strip()
    if s not in RATINGS:
        raise ValidationError(
            f"{label} must be one of: {', '.join(RATINGS)}")
    return s


def _validate_pct(v: Any, label: str) -> float | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a number") from None
    if not (0.0 <= f <= 100.0):
        raise ValidationError(f"{label} must be between 0 and 100")
    return round(f, 1)


def _validate_review_payload(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["student_id"] = _validate_student(d.get("student_id"))
    out["review_date"] = _validate_date(
        d.get("review_date") or _date.today().isoformat(),
        "Review date", required=True)
    period = (d.get("period") or DEFAULT_PERIOD).strip()
    if period not in REVIEW_PERIODS:
        raise ValidationError(
            f"Period must be one of: {', '.join(REVIEW_PERIODS)}")
    out["period"] = period
    out["academic_year"] = (d.get("academic_year") or "").strip() or None
    out["reviewer_staff_id"] = _validate_staff(d.get("reviewer_staff_id"))

    out["overall"]  = _validate_rating(d.get("overall"), "Overall")
    out["attitude"] = _validate_rating(d.get("attitude"), "Attitude")
    out["homework"] = _validate_rating(d.get("homework"), "Homework")
    out["attendance_pct"] = _validate_pct(
        d.get("attendance_pct"), "Attendance %")

    risk = (d.get("risk_level") or DEFAULT_RISK).strip()
    if risk not in RISK_LEVELS:
        raise ValidationError(
            f"Risk level must be one of: {', '.join(RISK_LEVELS)}")
    out["risk_level"] = risk

    status = (d.get("status") or DEFAULT_REVIEW_STATUS).strip()
    if status not in REVIEW_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(REVIEW_STATUSES)}")
    out["status"] = status

    out["academic_summary"]  = (d.get("academic_summary") or "").strip() or None
    out["behaviour_summary"] = (d.get("behaviour_summary") or "").strip() or None
    out["next_steps"]        = (d.get("next_steps") or "").strip() or None
    out["notes"]             = (d.get("notes") or "").strip() or None
    return out


def _validate_target_payload(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    area = (d.get("area") or DEFAULT_TARGET_AREA).strip()
    if area not in TARGET_AREAS:
        raise ValidationError(
            f"Area must be one of: {', '.join(TARGET_AREAS)}")
    out["area"] = area
    out["description"] = _require(d.get("description"),
                                     "Description").strip()
    out["measure"]    = (d.get("measure") or "").strip() or None
    out["due_date"]   = _validate_date(d.get("due_date"), "Due date")
    status = (d.get("status") or DEFAULT_TARGET_STATUS).strip()
    if status not in TARGET_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(TARGET_STATUSES)}")
    out["status"] = status
    out["progress_note"] = (
        d.get("progress_note") or "").strip() or None
    out["closed_on"] = _validate_date(d.get("closed_on"), "Closed on")
    if status in ("Met", "Missed") and not out["closed_on"]:
        out["closed_on"] = _date.today().isoformat()
    if status in OPEN_TARGET_STATUSES:
        out["closed_on"] = None
    return out


# ── Review CRUD ──────────────────────────────────────────────────

def create_review(d: dict[str, Any]) -> Review:
    init_db()
    p = _validate_review_payload(d)
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO progress_reviews (
                      student_id, review_date, period, academic_year,
                      reviewer_staff_id, overall, attitude, homework,
                      attendance_pct, risk_level, status,
                      academic_summary, behaviour_summary,
                      next_steps, notes, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           datetime('now'), datetime('now'))""",
                (p["student_id"], p["review_date"], p["period"],
                 p["academic_year"], p["reviewer_staff_id"],
                 p["overall"], p["attitude"], p["homework"],
                 p["attendance_pct"], p["risk_level"], p["status"],
                 p["academic_summary"], p["behaviour_summary"],
                 p["next_steps"], p["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e).upper():
            raise ValidationError(
                f"{p['student_id']} already has a review for "
                f"{p['period']} ({p['academic_year'] or 'no year'}). "
                f"Edit that one instead.") from e
        raise
    out = get_review(new_id)
    assert out is not None
    logger.info(
        "Created progress review #%d for %s (%s, status=%s)",
        new_id, p["student_id"], p["period"], p["status"])
    return out


def get_review(review_id: int) -> Review | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM progress_reviews WHERE review_id = ?",
            (review_id,)).fetchone()
        return _row_review(r) if r else None


def list_reviews(
    *,
    student_id: str | None = None,
    period: str | None = None,
    academic_year: str | None = None,
    status: str | None = None,
    risk_level: str | None = None,
    reviewer_staff_id: str | None = None,
    active_only: bool = False,
) -> list[Review]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if period:
        if period not in REVIEW_PERIODS:
            raise ValidationError(
                f"Period must be one of: {', '.join(REVIEW_PERIODS)}")
        clauses.append("period = ?")
        args.append(period)
    if academic_year:
        clauses.append("academic_year = ?")
        args.append(academic_year.strip())
    if status:
        if status not in REVIEW_STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(REVIEW_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if risk_level:
        if risk_level not in RISK_LEVELS:
            raise ValidationError(
                f"Risk must be one of: {', '.join(RISK_LEVELS)}")
        clauses.append("risk_level = ?")
        args.append(risk_level)
    if reviewer_staff_id:
        clauses.append("reviewer_staff_id = ?")
        args.append(reviewer_staff_id.strip().upper())
    if active_only:
        ph = ",".join("?" * len(ACTIVE_REVIEW_STATUSES))
        clauses.append(f"status IN ({ph})")
        args.extend(ACTIVE_REVIEW_STATUSES)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM progress_reviews {where} "
           "ORDER BY review_date DESC, review_id DESC")
    with _connect() as conn:
        return [_row_review(r)
                 for r in conn.execute(sql, args).fetchall()]


def view_review(review_id: int) -> ReviewView | None:
    r = get_review(review_id)
    from education_system.systems.sixth_form.domain.staff import staff as _staff
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    if r is None:
        return None
    s = _students.get_student(r.student_id)
    student_name = s.full_name if s else "(unknown)"
    reviewer_name = None
    if r.reviewer_staff_id:
        rs = _staff.get_staff(r.reviewer_staff_id)
        if rs:
            reviewer_name = rs.full_name
    targets = list_targets(review_id=review_id)
    return ReviewView(
        review=r, student_name=student_name,
        reviewer_name=reviewer_name, targets=targets,
        open_targets=sum(1 for t in targets if t.is_open),
        met_targets=sum(1 for t in targets if t.status == "Met"),
    )


def update_review(review_id: int, d: dict[str, Any]) -> Review:
    init_db()
    existing = get_review(review_id)
    if existing is None:
        raise ValidationError(f"No review #{review_id}")
    if existing.status == "Archived":
        raise ValidationError(
            "Cannot edit an Archived review — un-archive first")
    merged = {
        "student_id":        existing.student_id,
        "review_date":       d.get("review_date", existing.review_date),
        "period":            d.get("period", existing.period),
        "academic_year":     d.get("academic_year",
                                     existing.academic_year),
        "reviewer_staff_id": d.get("reviewer_staff_id",
                                     existing.reviewer_staff_id),
        "overall":           d.get("overall", existing.overall),
        "attitude":          d.get("attitude", existing.attitude),
        "homework":          d.get("homework", existing.homework),
        "attendance_pct":    d.get("attendance_pct",
                                     existing.attendance_pct),
        "risk_level":        d.get("risk_level", existing.risk_level),
        "status":            d.get("status", existing.status),
        "academic_summary":  d.get("academic_summary",
                                     existing.academic_summary),
        "behaviour_summary": d.get("behaviour_summary",
                                     existing.behaviour_summary),
        "next_steps":        d.get("next_steps", existing.next_steps),
        "notes":             d.get("notes", existing.notes),
    }
    p = _validate_review_payload(merged)

    new_shared = existing.shared_at
    if p["status"] == "Shared" and not new_shared:
        new_shared = _date.today().isoformat()

    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE progress_reviews SET
                      review_date=?, period=?, academic_year=?,
                      reviewer_staff_id=?, overall=?, attitude=?,
                      homework=?, attendance_pct=?, risk_level=?,
                      status=?, academic_summary=?, behaviour_summary=?,
                      next_steps=?, notes=?, shared_at=?,
                      updated_at=datetime('now')
                   WHERE review_id=?""",
                (p["review_date"], p["period"], p["academic_year"],
                 p["reviewer_staff_id"], p["overall"], p["attitude"],
                 p["homework"], p["attendance_pct"], p["risk_level"],
                 p["status"], p["academic_summary"],
                 p["behaviour_summary"], p["next_steps"], p["notes"],
                 new_shared, review_id),
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e).upper():
            raise ValidationError(
                f"Another review already exists for "
                f"{existing.student_id} / {p['period']} / "
                f"{p['academic_year'] or 'no year'}.") from e
        raise
    out = get_review(review_id)
    assert out is not None
    logger.info("Updated review #%d (status=%s)",
                review_id, out.status)
    return out


def set_review_status(review_id: int, status: str) -> Review:
    if status not in REVIEW_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(REVIEW_STATUSES)}")
    return update_review(review_id, {"status": status})


def publish(review_id: int) -> Review:
    return set_review_status(review_id, "Published")


def share(review_id: int) -> Review:
    return set_review_status(review_id, "Shared")


def archive(review_id: int) -> Review:
    init_db()
    existing = get_review(review_id)
    if existing is None:
        raise ValidationError(f"No review #{review_id}")
    with _connect() as conn:
        conn.execute(
            "UPDATE progress_reviews SET status='Archived', "
            "updated_at=datetime('now') WHERE review_id=?",
            (review_id,))
        conn.commit()
    out = get_review(review_id)
    assert out is not None
    logger.info("Archived review #%d", review_id)
    return out


def delete_review(review_id: int) -> bool:
    init_db()
    existing = get_review(review_id)
    if existing is None:
        return False
    if existing.status != "Draft":
        raise ValidationError(
            f"Only Draft reviews can be deleted "
            f"(this one is {existing.status}). Archive it instead.")
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM progress_reviews WHERE review_id = ?",
            (review_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted draft review #%d", review_id)
            return True
        return False


def reviews_for_student(student_id: str) -> list[Review]:
    return list_reviews(student_id=student_id)


# ── Target CRUD ──────────────────────────────────────────────────

def add_target(review_id: int, d: dict[str, Any]) -> Target:
    init_db()
    if get_review(review_id) is None:
        raise ValidationError(f"No review #{review_id}")
    p = _validate_target_payload(d)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO progress_targets (
                  review_id, area, description, measure, due_date,
                  status, progress_note, closed_on,
                  created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (review_id, p["area"], p["description"], p["measure"],
             p["due_date"], p["status"], p["progress_note"],
             p["closed_on"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_target(new_id)
    assert out is not None
    logger.info("Added target #%d to review #%d (%s)",
                new_id, review_id, p["area"])
    return out


def get_target(target_id: int) -> Target | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM progress_targets WHERE target_id = ?",
            (target_id,)).fetchone()
        return _row_target(r) if r else None


def list_targets(
    *,
    review_id: int | None = None,
    student_id: str | None = None,
    status: str | None = None,
    area: str | None = None,
    open_only: bool = False,
    due_before: str | None = None,
) -> list[Target]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if review_id is not None:
        clauses.append("review_id = ?")
        args.append(review_id)
    if student_id:
        clauses.append("review_id IN (SELECT review_id "
                        "  FROM progress_reviews WHERE student_id = ?)")
        args.append(student_id.strip())
    if status:
        if status not in TARGET_STATUSES:
            raise ValidationError(
                f"Status must be one of: "
                f"{', '.join(TARGET_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if area:
        if area not in TARGET_AREAS:
            raise ValidationError(
                f"Area must be one of: {', '.join(TARGET_AREAS)}")
        clauses.append("area = ?")
        args.append(area)
    if open_only:
        ph = ",".join("?" * len(OPEN_TARGET_STATUSES))
        clauses.append(f"status IN ({ph})")
        args.extend(OPEN_TARGET_STATUSES)
    if due_before:
        clauses.append("due_date IS NOT NULL AND due_date <= ?")
        args.append(_validate_date(due_before, "due_before"))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM progress_targets {where} "
           "ORDER BY COALESCE(due_date, created_at), target_id")
    with _connect() as conn:
        return [_row_target(r)
                 for r in conn.execute(sql, args).fetchall()]


def update_target(target_id: int, d: dict[str, Any]) -> Target:
    init_db()
    existing = get_target(target_id)
    if existing is None:
        raise ValidationError(f"No target #{target_id}")
    merged = {
        "area":          d.get("area", existing.area),
        "description":   d.get("description", existing.description),
        "measure":       d.get("measure", existing.measure),
        "due_date":      d.get("due_date", existing.due_date),
        "status":        d.get("status", existing.status),
        "progress_note": d.get("progress_note",
                                 existing.progress_note),
        "closed_on":     d.get("closed_on", existing.closed_on),
    }
    p = _validate_target_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE progress_targets SET
                  area=?, description=?, measure=?, due_date=?,
                  status=?, progress_note=?, closed_on=?,
                  updated_at=datetime('now')
               WHERE target_id=?""",
            (p["area"], p["description"], p["measure"], p["due_date"],
             p["status"], p["progress_note"], p["closed_on"],
             target_id),
        )
        conn.commit()
    out = get_target(target_id)
    assert out is not None
    logger.info("Updated target #%d (status=%s)",
                target_id, out.status)
    return out


def set_target_status(target_id: int, status: str) -> Target:
    if status not in TARGET_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(TARGET_STATUSES)}")
    return update_target(target_id, {"status": status})


def delete_target(target_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM progress_targets WHERE target_id = ?",
            (target_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted target #%d", target_id)
            return True
        return False


# ── Auto-populate helper ─────────────────────────────────────────

def populate_from_data(
    student_id: str,
    *,
    window_days: int = 28,
) -> dict[str, Any]:
    """Return a dict of suggested defaults for a new review: attendance %
    from the attendance module and a one-line academic summary built
    from the grades report."""
    out: dict[str, Any] = {}
    from education_system.systems.sixth_form.domain.operations.reporting.attendance_report import attendance_report as _ar
    try:
        ps = _ar.per_student_report(student_id, window_days=window_days)
        out["attendance_pct"] = ps.breakdown.percentage
    except _ar.ValidationError:
        out["attendance_pct"] = None

    try:
        from education_system.systems.sixth_form.domain.operations.reporting.grades_report import grades_report as _gr
        gs = _gr.per_student_grade_report(student_id)
        if gs.subjects:
            parts = []
            for row in gs.subjects:
                pieces = []
                if row.predicted_grade:
                    pieces.append(f"pred {row.predicted_grade}")
                if row.latest_mock_grade:
                    pieces.append(f"mock {row.latest_mock_grade}")
                if row.best_actual_grade:
                    pieces.append(f"actual {row.best_actual_grade}")
                if pieces:
                    parts.append(f"{row.subject}: {', '.join(pieces)}")
            if parts:
                out["academic_summary"] = " | ".join(parts)
        if gs.notes:
            existing_notes = out.get("notes", "")
            joined = (existing_notes + "\n" if existing_notes else "")
            joined += "\n".join(f"- {n}" for n in gs.notes)
            out["notes"] = joined
    except Exception:
        pass

    return out


# ── Summary ──────────────────────────────────────────────────────

@dataclass
class Summary:
    total_reviews: int
    drafts: int
    published: int
    shared: int
    archived: int
    by_period: dict[str, int]
    by_risk: dict[str, int]
    by_overall: dict[str, int]   # rating label → count

    total_targets: int
    open_targets: int
    met_targets: int
    missed_targets: int
    overdue_open_targets: int
    by_target_area: dict[str, int]
    students_at_high_risk: int   # active reviews with High/Critical


def summary(*, overdue_window_today: str | None = None) -> Summary:
    init_db()
    today = overdue_window_today or _date.today().isoformat()

    reviews = list_reviews()
    by_period = {p: 0 for p in REVIEW_PERIODS}
    by_risk = {r: 0 for r in RISK_LEVELS}
    by_overall = {r: 0 for r in RATINGS}
    drafts = pub = shared = arch = 0
    high_risk = 0
    for r in reviews:
        by_period[r.period] = by_period.get(r.period, 0) + 1
        by_risk[r.risk_level] = by_risk.get(r.risk_level, 0) + 1
        by_overall[r.overall] = by_overall.get(r.overall, 0) + 1
        if r.status == "Draft":
            drafts += 1
        elif r.status == "Published":
            pub += 1
        elif r.status == "Shared":
            shared += 1
        elif r.status == "Archived":
            arch += 1
        if r.is_active and r.risk_level in ("High", "Critical"):
            high_risk += 1

    targets = list_targets()
    by_area = {a: 0 for a in TARGET_AREAS}
    open_n = met = missed = overdue = 0
    for t in targets:
        by_area[t.area] = by_area.get(t.area, 0) + 1
        if t.is_open:
            open_n += 1
            if t.due_date and t.due_date < today:
                overdue += 1
        if t.status == "Met":
            met += 1
        if t.status == "Missed":
            missed += 1

    return Summary(
        total_reviews=len(reviews),
        drafts=drafts, published=pub, shared=shared, archived=arch,
        by_period=by_period, by_risk=by_risk,
        by_overall=by_overall,
        total_targets=len(targets),
        open_targets=open_n, met_targets=met,
        missed_targets=missed,
        overdue_open_targets=overdue,
        by_target_area=by_area,
        students_at_high_risk=high_risk,
    )
