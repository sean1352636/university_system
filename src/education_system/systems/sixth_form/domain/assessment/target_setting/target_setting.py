"""Target Setting — per-student, per-subject grade targets + reviews.

One row per (student, subject) target with the headline grades:

* ``mte_grade``           — Minimum Target Expected (the floor)
* ``aspirational_grade``  — stretch / ceiling target
* ``current_grade``       — most recent assessed grade
* ``baseline_record_id``  — optional FK to a ``baseline_records`` row

``UNIQUE(student_id, subject_name)`` enforces one target per pair.

A child ``target_reviews`` table stores periodic review snapshots so
you can track progress over time without losing the headline values.

Cascade: deleting a target wipes its reviews; deleting a student wipes
both.

The module derives an ``on_track`` flag and a status by comparing
``current_grade`` against ``mte_grade`` on the A-Level point scale:

* ``current >= aspirational``  →  "Above target"  (on-track ✓)
* ``current >= mte``           →  "On target"     (on-track ✓)
* ``current == mte - 1``       →  "At risk"       (on-track ⚠)
* ``current < mte - 1``        →  "Below target"  (on-track ✗)
"""

from __future__ import annotations

import datetime as _dt
import functools
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any
from education_system import paths
from education_system.systems.sixth_form.domain.academics.qualifications import (
    grade_scales,
)
from education_system.systems.sixth_form.domain.assessment.target_setting import (
    target_setting as data,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_TARGET_SETTING_DB


# A-Level grade scale shared with baseline_assessment.
A_LEVEL_GRADES: tuple[str, ...] = ("A*", "A", "B", "C", "D", "E", "U")

# Status values stored on each target row. "On Track" / "At Risk" /
# "Below" / "Above" are auto-computed by ``set_current``; the manual
# states ("Withdrawn", "Met", "Not Started") are settable too.
STATUSES: tuple[str, ...] = (
    "Not Started",
    "On Track",
    "Above Target",
    "At Risk",
    "Below Target",
    "Met",
    "Withdrawn",
)
DEFAULT_STATUS: str = "Not Started"
OPEN_STATUSES: tuple[str, ...] = (
    "Not Started", "On Track", "At Risk", "Below Target",
    "Above Target",
)

PROGRESS_TAGS: tuple[str, ...] = (
    "On Track", "Above Target", "At Risk", "Below Target", "Met",
)

YEAR_GROUPS: tuple[str, ...] = ("Year 12", "Year 13", "Mixed")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# UCAS-style points for grade arithmetic on the A-level scale. Kept
# for callers that import it; grade maths now goes through
# :func:`grade_points`, which uses the scale of the learner's own
# qualification (BTEC, T Level, GCSE resit ...).
_POINTS: dict[str, int] = {
    "A*": 6, "A": 5, "B": 4, "C": 3, "D": 2, "E": 1, "U": 0,
}


@functools.lru_cache(maxsize=4096)
def qualification_type_of(student_id: str | None,
                          subject: str | None) -> str | None:
    """Qualification type the student takes *subject* as (None = A level)."""
    try:
        from education_system.systems.sixth_form.domain.academics.qualifications import (
            learning_aims,
        )
        return learning_aims.qualification_type_for(student_id, subject)
    except Exception:
        logger.debug("qualification type lookup failed", exc_info=True)
        return None


def grade_points(grade: str | None,
                 qualification_type: str | None = None) -> int | None:
    """Ordinal points on the qualification's scale, lowest grade = 0.

    On the A-level scale this gives the same numbers as ``_POINTS``.
    """
    return grade_scales.grade_points(grade, qualification_type)


def grades_for(student_id: str | None, subject: str | None) -> tuple[str, ...]:
    """Grades (best first) a target for this student and subject may use."""
    return grade_scales.scale_for(
        qualification_type_of(student_id, subject)).grades


def _grade_at(points: int, qualification_type: str | None) -> str | None:
    grades = grade_scales.scale_for(qualification_type).grades
    idx = len(grades) - 1 - points
    return grades[idx] if 0 <= idx < len(grades) else None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS targets (
    target_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id         TEXT NOT NULL,
    subject_name       TEXT NOT NULL,
    year_group         TEXT,
    mte_grade          TEXT NOT NULL,
    aspirational_grade TEXT,
    current_grade      TEXT,
    baseline_record_id INTEGER,
    set_on             TEXT,
    set_by             TEXT,
    last_reviewed      TEXT,
    next_review_due    TEXT,
    status             TEXT NOT NULL DEFAULT 'Not Started',
    rationale          TEXT,
    notes              TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE,
    UNIQUE (student_id, subject_name)
);

CREATE TABLE IF NOT EXISTS target_reviews (
    review_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id          INTEGER NOT NULL,
    review_date        TEXT NOT NULL,
    current_grade      TEXT,
    on_track           TEXT,
    reviewer           TEXT,
    comments           TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (target_id) REFERENCES targets(target_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tg_student ON targets(student_id);
CREATE INDEX IF NOT EXISTS idx_tg_subject ON targets(subject_name);
CREATE INDEX IF NOT EXISTS idx_tg_status  ON targets(status);
CREATE INDEX IF NOT EXISTS idx_tr_target  ON target_reviews(target_id);
CREATE INDEX IF NOT EXISTS idx_tr_date    ON target_reviews(review_date);
"""


# Academic target *actions* — the SMART steps ("complete weekly essays
# on time") that progress reviews set. They live here, beside the grade
# targets they serve, so there is one store for academic targets:
# progress reviews write through to it and read back from it.
ACTION_STATUSES: tuple[str, ...] = (
    "Open", "On Track", "At Risk", "Met", "Missed",
)
DEFAULT_ACTION_STATUS: str = "Open"
OPEN_ACTION_STATUSES: tuple[str, ...] = ("Open", "On Track", "At Risk")

ACTION_SOURCES: tuple[str, ...] = ("Target Setting", "Progress Review")

_ACTIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS target_actions (
    action_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id         TEXT NOT NULL,
    target_id          INTEGER,
    subject_name       TEXT,
    description        TEXT NOT NULL,
    measure            TEXT,
    due_date           TEXT,
    status             TEXT NOT NULL DEFAULT 'Open',
    progress_note      TEXT,
    closed_on          TEXT,
    source             TEXT NOT NULL DEFAULT 'Target Setting',
    progress_review_id INTEGER,
    legacy_progress_target_id INTEGER UNIQUE,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES targets(target_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_ta_student ON target_actions(student_id);
CREATE INDEX IF NOT EXISTS idx_ta_target  ON target_actions(target_id);
CREATE INDEX IF NOT EXISTS idx_ta_status  ON target_actions(status);
CREATE INDEX IF NOT EXISTS idx_ta_review  ON target_actions(progress_review_id);
"""


@dataclass
class Target:
    target_id: int
    student_id: str
    subject_name: str
    year_group: str | None
    mte_grade: str
    aspirational_grade: str | None
    current_grade: str | None
    baseline_record_id: int | None
    set_on: str | None
    set_by: str | None
    last_reviewed: str | None
    next_review_due: str | None
    status: str
    rationale: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def qualification_type(self) -> str | None:
        return qualification_type_of(self.student_id, self.subject_name)

    @property
    def mte_points(self) -> int | None:
        return grade_points(self.mte_grade, self.qualification_type)

    @property
    def current_points(self) -> int | None:
        return grade_points(self.current_grade, self.qualification_type)

    @property
    def aspirational_points(self) -> int | None:
        return grade_points(self.aspirational_grade, self.qualification_type)

    @property
    def points_vs_target(self) -> int | None:
        """current_points − mte_points (positive = above target)."""
        if self.mte_points is None or self.current_points is None:
            return None
        return self.current_points - self.mte_points


@dataclass
class Review:
    review_id: int
    target_id: int
    review_date: str
    current_grade: str | None
    on_track: str | None
    reviewer: str | None
    comments: str | None
    created_at: str
    updated_at: str


@dataclass
class TargetDetail:
    target: Target
    reviews: list[Review] = field(default_factory=list)


@dataclass
class TargetRow:
    target: Target
    student_name: str
    review_count: int = 0


@dataclass
class Summary:
    total_targets: int
    by_status: dict[str, int]
    by_subject: dict[str, int]
    by_year: dict[str, int]
    distinct_students: int
    on_track: int                  # status in On Track / Above / Met
    at_risk: int                   # status = At Risk
    below_target: int              # status = Below Target
    overdue_review: int            # next_review_due < today and open
    upcoming_review: int           # next_review_due in [today, today+window]


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.executescript(_ACTIONS_SCHEMA)
    logger.debug("Target-setting schema ready at %s", DB_PATH)

    _DB_READY = True
    # Academic targets set in progress reviews before the stores were
    # unified are copied in once; re-running is a no-op (unique legacy id).
    try:
        migrate_progress_targets()
    except Exception:
        logger.exception("Progress-target migration failed; will retry "
                         "on the next explicit sync")


def _row_target(r: sqlite3.Row) -> Target:
    return Target(
        target_id=r["target_id"], student_id=r["student_id"],
        subject_name=r["subject_name"], year_group=r["year_group"],
        mte_grade=r["mte_grade"],
        aspirational_grade=r["aspirational_grade"],
        current_grade=r["current_grade"],
        baseline_record_id=r["baseline_record_id"],
        set_on=r["set_on"], set_by=r["set_by"],
        last_reviewed=r["last_reviewed"],
        next_review_due=r["next_review_due"],
        status=r["status"], rationale=r["rationale"],
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_review(r: sqlite3.Row) -> Review:
    return Review(
        review_id=r["review_id"], target_id=r["target_id"],
        review_date=r["review_date"],
        current_grade=r["current_grade"],
        on_track=r["on_track"], reviewer=r["reviewer"],
        comments=r["comments"],
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


def _validate_grade(value: Any, label: str, *,
                     required: bool = False,
                     qualification_type: str | None = None) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    try:
        return grade_scales.validate_grade(str(value), qualification_type)
    except ValueError as e:
        raise ValidationError(f"{label}: {e}") from None


def _validate_student(value: Any) -> str:
    sid = _require(value, "Student").strip()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    return sid


def _validate_subject(value: Any) -> str:
    name = _require(value, "Subject").strip()
    try:
        from education_system.systems.sixth_form.domain.academics.subjects import (
            subjects as _subjects,
        )
        names = {x.name for x in _subjects.list_subjects()}
        if names and name not in names:
            raise ValidationError(
                f"Subject {name!r} is not in the catalogue")
    except ValidationError:
        raise
    except Exception:
        pass
    return name


def _validate_baseline(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        bid = int(value)
    except (TypeError, ValueError):
        raise ValidationError(
            "baseline_record_id must be a number") from None
    from education_system.systems.sixth_form.domain.assessment.baseline_assessment import (
        baseline_assessment as _baseline,
    )
    if _baseline.get_record(bid) is None:
        raise ValidationError(f"No baseline record #{bid}")
    return bid


def _compute_status(mte: str | None, aspirational: str | None,
                     current: str | None,
                     manual_status: str | None = None,
                     qualification_type: str | None = None) -> str:
    """Derive the on-track status from current vs MTE.

    Manual states ``Withdrawn`` and ``Met`` always take precedence —
    those are decisions, not derived facts. ``Not Started`` is only
    respected as an override when there's no current grade to compare
    against; otherwise we auto-compute so callers don't have to clear
    a stale "Not Started" status to get the row to re-evaluate.
    """
    if manual_status in ("Withdrawn", "Met"):
        return manual_status
    if not (mte and current):
        # Nothing to compute against — honour the supplied status
        # (defaulting to Not Started) so manual flags survive a no-op
        # update.
        return manual_status or "Not Started"
    mte_pts = grade_points(mte, qualification_type)
    cur_pts = grade_points(current, qualification_type)
    if mte_pts is None or cur_pts is None:
        return manual_status or "Not Started"
    asp_pts = grade_points(aspirational, qualification_type)
    if asp_pts is not None and cur_pts >= asp_pts:
        return "Above Target"
    if cur_pts >= mte_pts:
        return "On Track"
    if cur_pts == mte_pts - 1:
        return "At Risk"
    return "Below Target"


def _validate_target_payload(payload: dict[str, Any]
                              ) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["student_id"]  = _validate_student(payload.get("student_id"))
    out["subject_name"] = _validate_subject(payload.get("subject_name"))
    year = (payload.get("year_group") or "").strip()
    if year and year not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of: "
            f"{', '.join(YEAR_GROUPS)}")
    out["year_group"] = year or None

    qtype = qualification_type_of(out["student_id"], out["subject_name"])
    out["mte_grade"] = _validate_grade(
        payload.get("mte_grade"), "Minimum target",
        required=True, qualification_type=qtype)
    out["aspirational_grade"] = _validate_grade(
        payload.get("aspirational_grade"), "Aspirational target",
        qualification_type=qtype)
    out["current_grade"] = _validate_grade(
        payload.get("current_grade"), "Current grade",
        qualification_type=qtype)

    # Aspirational should not be lower than MTE on the points scale.
    if (out["aspirational_grade"]
            and out["mte_grade"]
            and grade_points(out["aspirational_grade"], qtype)
                < grade_points(out["mte_grade"], qtype)):
        raise ValidationError(
            "Aspirational grade cannot be lower than minimum target")

    out["baseline_record_id"] = _validate_baseline(
        payload.get("baseline_record_id"))

    out["set_on"]         = _validate_date(payload.get("set_on"),
                                                "Set on")
    out["set_by"]         = (payload.get("set_by") or "").strip() or None
    out["last_reviewed"]  = _validate_date(payload.get("last_reviewed"),
                                                "Last reviewed")
    out["next_review_due"] = _validate_date(
        payload.get("next_review_due"), "Next review due")

    manual_status = (payload.get("status") or "").strip()
    if manual_status and manual_status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = _compute_status(
        out["mte_grade"], out["aspirational_grade"],
        out["current_grade"],
        manual_status or None, qtype)

    out["rationale"] = (payload.get("rationale")
                          or "").strip() or None
    out["notes"]     = (payload.get("notes") or "").strip() or None
    if not out["set_on"]:
        out["set_on"] = _dt.date.today().isoformat()
    return out


def _validate_review_payload(payload: dict[str, Any]
                              ) -> dict[str, Any]:
    out: dict[str, Any] = {}
    tid = payload.get("target_id")
    if tid in (None, ""):
        raise ValidationError("Target id is required")
    try:
        out["target_id"] = int(tid)
    except (TypeError, ValueError):
        raise ValidationError(
            "Target id must be a number") from None
    parent = get_target(out["target_id"])
    if parent is None:
        raise ValidationError(
            f"No target #{out['target_id']}")

    out["review_date"] = _validate_date(
        payload.get("review_date"), "Review date",
        required=True)
    out["current_grade"] = _validate_grade(
        payload.get("current_grade"), "Current grade",
        qualification_type=parent.qualification_type)

    on_track = (payload.get("on_track") or "").strip()
    if on_track and on_track not in PROGRESS_TAGS:
        raise ValidationError(
            f"on_track must be one of: "
            f"{', '.join(PROGRESS_TAGS)}")
    out["on_track"] = on_track or None

    out["reviewer"] = (payload.get("reviewer") or "").strip() or None
    out["comments"] = (payload.get("comments") or "").strip() or None
    return out


# ── Target CRUD ───────────────────────────────────────────────────

def create_target(payload: dict[str, Any]) -> Target:
    init_db()
    p = _validate_target_payload(payload)
    with _connect() as conn:
        if conn.execute(
                "SELECT 1 FROM targets "
                "WHERE student_id = ? AND subject_name = ?",
                (p["student_id"], p["subject_name"])).fetchone():
            raise ValidationError(
                f"Target for {p['student_id']} × "
                f"{p['subject_name']!r} already exists — edit it "
                "instead")
        cur = conn.execute(
            """INSERT INTO targets
                   (student_id, subject_name, year_group, mte_grade,
                    aspirational_grade, current_grade,
                    baseline_record_id, set_on, set_by,
                    last_reviewed, next_review_due, status,
                    rationale, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["student_id"], p["subject_name"], p["year_group"],
             p["mte_grade"], p["aspirational_grade"],
             p["current_grade"], p["baseline_record_id"],
             p["set_on"], p["set_by"], p["last_reviewed"],
             p["next_review_due"], p["status"],
             p["rationale"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_target(new_id)
    assert out is not None
    logger.info(
        "Created target #%d for %s × %s (MTE=%s, current=%s, %s)",
        new_id, p["student_id"], p["subject_name"],
        p["mte_grade"], p["current_grade"], p["status"])
    return out


def get_target(target_id: int) -> Target | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM targets WHERE target_id = ?",
            (target_id,)).fetchone()
        return _row_target(r) if r else None


def get_target_for(student_id: str,
                    subject_name: str) -> Target | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM targets "
            "WHERE student_id = ? AND subject_name = ?",
            (student_id.strip(), subject_name.strip())).fetchone()
        return _row_target(r) if r else None


def list_targets(
    *,
    student_id: str | None = None,
    subject_name: str | None = None,
    status: str | None = None,
    year_group: str | None = None,
    on_track_only: bool = False,
    at_risk_only: bool = False,
    review_overdue: bool = False,
    mte_grade: str | None = None,
) -> list[Target]:
    init_db()
    clauses, args = [], []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if subject_name:
        clauses.append("subject_name = ?")
        args.append(subject_name.strip())
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year group must be one of: "
                f"{', '.join(YEAR_GROUPS)}")
        clauses.append("year_group = ?")
        args.append(year_group)
    if on_track_only:
        clauses.append(
            "status IN ('On Track', 'Above Target', 'Met')")
    if at_risk_only:
        clauses.append("status IN ('At Risk', 'Below Target')")
    if review_overdue:
        today = _dt.date.today().isoformat()
        ph = ",".join("?" * len(OPEN_STATUSES))
        clauses.append(
            f"next_review_due IS NOT NULL AND next_review_due < ? "
            f"AND status IN ({ph})")
        args.append(today)
        args.extend(OPEN_STATUSES)
    if mte_grade:
        if mte_grade not in grade_scales.ALL_GRADES:
            raise ValidationError(f"Unknown grade {mte_grade!r}")
        clauses.append("mte_grade = ?")
        args.append(mte_grade)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM targets {where} "
           "ORDER BY CASE status "
           "  WHEN 'Below Target' THEN 0 "
           "  WHEN 'At Risk'      THEN 1 "
           "  WHEN 'Not Started'  THEN 2 "
           "  WHEN 'On Track'     THEN 3 "
           "  WHEN 'Above Target' THEN 4 "
           "  WHEN 'Met'          THEN 5 "
           "  WHEN 'Withdrawn'    THEN 6 "
           "  ELSE 7 END, "
           "student_id ASC, subject_name ASC")
    with _connect() as conn:
        return [_row_target(r)
                for r in conn.execute(sql, args).fetchall()]


def list_targets_with_detail(**kwargs) -> list[TargetRow]:
    rows = list_targets(**kwargs)
    if not rows:
        return []
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    names = {s.student_id: s.full_name
              for s in _students.list_students()}
    out: list[TargetRow] = []
    with _connect() as conn:
        for t in rows:
            rc = conn.execute(
                "SELECT COUNT(*) FROM target_reviews "
                "WHERE target_id = ?",
                (t.target_id,)).fetchone()[0]
            out.append(TargetRow(
                target=t,
                student_name=names.get(t.student_id, "(unknown)"),
                review_count=rc,
            ))
    return out


def get_target_detail(target_id: int) -> TargetDetail | None:
    init_db()
    t = get_target(target_id)
    if t is None:
        return None
    reviews = list_reviews(target_id=target_id)
    return TargetDetail(target=t, reviews=reviews)


def update_target(target_id: int,
                   payload: dict[str, Any]) -> Target:
    init_db()
    existing = get_target(target_id)
    if existing is None:
        raise ValidationError(f"No target #{target_id}")
    merged = {
        "student_id":         existing.student_id,
        "subject_name":       existing.subject_name,
        "year_group":         payload.get("year_group",
                                           existing.year_group),
        "mte_grade":          payload.get("mte_grade",
                                           existing.mte_grade),
        "aspirational_grade": payload.get("aspirational_grade",
                                           existing.aspirational_grade),
        "current_grade":      payload.get("current_grade",
                                           existing.current_grade),
        "baseline_record_id": payload.get("baseline_record_id",
                                           existing.baseline_record_id),
        "set_on":             payload.get("set_on", existing.set_on),
        "set_by":             payload.get("set_by", existing.set_by),
        "last_reviewed":      payload.get("last_reviewed",
                                           existing.last_reviewed),
        "next_review_due":    payload.get("next_review_due",
                                           existing.next_review_due),
        "status":             payload.get("status", existing.status),
        "rationale":          payload.get("rationale",
                                           existing.rationale),
        "notes":              payload.get("notes", existing.notes),
    }
    p = _validate_target_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE targets SET
                   year_group = ?, mte_grade = ?,
                   aspirational_grade = ?, current_grade = ?,
                   baseline_record_id = ?, set_on = ?, set_by = ?,
                   last_reviewed = ?, next_review_due = ?,
                   status = ?, rationale = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE target_id = ?""",
            (p["year_group"], p["mte_grade"],
             p["aspirational_grade"], p["current_grade"],
             p["baseline_record_id"], p["set_on"], p["set_by"],
             p["last_reviewed"], p["next_review_due"],
             p["status"], p["rationale"], p["notes"], target_id),
        )
        conn.commit()
    out = get_target(target_id)
    assert out is not None
    return out


def set_current_grade(target_id: int, current: str | None) -> Target:
    return update_target(target_id, {"current_grade": current})


def set_status(target_id: int, status: str) -> Target:
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    return update_target(target_id, {"status": status})


def delete_target(target_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM targets WHERE target_id = ?",
            (target_id,))
        conn.commit()
        if cur.rowcount:
            logger.info(
                "Deleted target #%d (cascade: reviews)", target_id)
            return True
        return False


# ── Review CRUD ───────────────────────────────────────────────────

def add_review(target_id: int, *,
                review_date: str | None = None,
                current_grade: str | None = None,
                on_track: str | None = None,
                reviewer: str | None = None,
                comments: str | None = None) -> Review:
    """Add a review snapshot and, if a current grade is supplied,
    update the parent target's ``current_grade`` and ``last_reviewed``
    fields atomically."""
    init_db()
    payload = {
        "target_id":     target_id,
        "review_date":   review_date or _dt.date.today().isoformat(),
        "current_grade": current_grade,
        "on_track":      on_track,
        "reviewer":      reviewer,
        "comments":      comments,
    }
    r = create_review(payload)
    update_kwargs: dict[str, Any] = {
        "last_reviewed": r.review_date,
    }
    if current_grade is not None:
        update_kwargs["current_grade"] = current_grade
    update_target(target_id, update_kwargs)
    return r


def create_review(payload: dict[str, Any]) -> Review:
    init_db()
    p = _validate_review_payload(payload)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO target_reviews
                   (target_id, review_date, current_grade,
                    on_track, reviewer, comments,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["target_id"], p["review_date"], p["current_grade"],
             p["on_track"], p["reviewer"], p["comments"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_review(new_id)
    assert out is not None
    return out


def get_review(review_id: int) -> Review | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM target_reviews WHERE review_id = ?",
            (review_id,)).fetchone()
        return _row_review(r) if r else None


def list_reviews(*, target_id: int | None = None,
                  reviewer_like: str | None = None,
                  date_from: str | None = None,
                  date_to: str | None = None) -> list[Review]:
    init_db()
    clauses, args = [], []
    if target_id is not None:
        clauses.append("target_id = ?")
        args.append(int(target_id))
    if reviewer_like:
        clauses.append("reviewer LIKE ?")
        args.append(f"%{reviewer_like.strip()}%")
    if date_from:
        clauses.append("review_date >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("review_date <= ?")
        args.append(_validate_date(date_to, "date_to"))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM target_reviews {where} "
           "ORDER BY review_date DESC, review_id DESC")
    with _connect() as conn:
        return [_row_review(r)
                for r in conn.execute(sql, args).fetchall()]


def update_review(review_id: int,
                   payload: dict[str, Any]) -> Review:
    init_db()
    existing = get_review(review_id)
    if existing is None:
        raise ValidationError(f"No review #{review_id}")
    merged = {
        "target_id":     existing.target_id,
        "review_date":   payload.get("review_date",
                                      existing.review_date),
        "current_grade": payload.get("current_grade",
                                      existing.current_grade),
        "on_track":      payload.get("on_track", existing.on_track),
        "reviewer":      payload.get("reviewer", existing.reviewer),
        "comments":      payload.get("comments", existing.comments),
    }
    p = _validate_review_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE target_reviews SET
                   review_date = ?, current_grade = ?,
                   on_track = ?, reviewer = ?, comments = ?,
                   updated_at = datetime('now')
               WHERE review_id = ?""",
            (p["review_date"], p["current_grade"],
             p["on_track"], p["reviewer"], p["comments"],
             review_id),
        )
        conn.commit()
    out = get_review(review_id)
    assert out is not None
    return out


def delete_review(review_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM target_reviews WHERE review_id = ?",
            (review_id,))
        conn.commit()
        return bool(cur.rowcount)


# ── Bulk seeding from baselines ───────────────────────────────────

def seed_from_baseline(
    student_id: str, *,
    plus_grades: int = 1,
    set_by: str | None = None,
    year_group: str | None = None,
    next_review_due: str | None = None,
) -> list[Target]:
    """For every Primary baseline record for a student that has both
    subject_name and an A-Level baseline_grade, create a Target whose
    MTE is the baseline grade and whose aspirational grade is the
    baseline grade plus ``plus_grades`` (capped at A*).

    Existing targets are left alone — only missing (student, subject)
    pairs are seeded.
    """
    init_db()
    from education_system.systems.sixth_form.domain.assessment.baseline_assessment import (
        baseline_assessment as _baseline,
    )
    baselines = _baseline.list_records(
        student_id=student_id, primary_only=True)
    created: list[Target] = []
    for b in baselines:
        if not (b.subject_name and b.baseline_grade):
            continue
        qtype = qualification_type_of(student_id, b.subject_name)
        mte_pts = grade_points(b.baseline_grade, qtype)
        if mte_pts is None:
            # Baseline isn't on this subject's grade scale.
            continue
        if get_target_for(student_id, b.subject_name) is not None:
            continue
        # Bump the aspirational by ``plus_grades`` points, capped at
        # the top of the subject's scale.
        top = len(grade_scales.scale_for(qtype).grades) - 1
        asp = _grade_at(min(top, mte_pts + plus_grades), qtype) \
            or b.baseline_grade
        t = create_target({
            "student_id":          student_id,
            "subject_name":        b.subject_name,
            "year_group":          year_group,
            "mte_grade":           b.baseline_grade,
            "aspirational_grade":  asp,
            "baseline_record_id":  b.record_id,
            "set_by":              set_by,
            "next_review_due":     next_review_due,
            "rationale":           (f"Seeded from primary baseline "
                                       f"#{b.record_id} "
                                       f"({b.assessment_type})"),
        })
        created.append(t)
    return created


# ── Summary ───────────────────────────────────────────────────────

def summary(*, upcoming_window_days: int = 14) -> Summary:
    init_db()
    today = _dt.date.today().isoformat()
    horizon = (_dt.date.today()
                + _dt.timedelta(days=upcoming_window_days)).isoformat()
    rows = list_targets()
    by_status = {s: 0 for s in STATUSES}
    by_subject: dict[str, int] = {}
    by_year = {y: 0 for y in YEAR_GROUPS}
    on_track = 0
    at_risk = 0
    below = 0
    overdue = 0
    upcoming = 0
    students: set[str] = set()
    for t in rows:
        by_status[t.status] = by_status.get(t.status, 0) + 1
        by_subject[t.subject_name] = by_subject.get(
            t.subject_name, 0) + 1
        if t.year_group:
            by_year[t.year_group] = by_year.get(t.year_group, 0) + 1
        if t.status in ("On Track", "Above Target", "Met"):
            on_track += 1
        if t.status == "At Risk":
            at_risk += 1
        if t.status == "Below Target":
            below += 1
        if t.status in OPEN_STATUSES and t.next_review_due:
            if t.next_review_due < today:
                overdue += 1
            elif t.next_review_due <= horizon:
                upcoming += 1
        students.add(t.student_id)
    return Summary(
        total_targets=len(rows),
        by_status=by_status,
        by_subject=dict(sorted(by_subject.items(),
                                  key=lambda kv: kv[1],
                                  reverse=True)),
        by_year=by_year,
        distinct_students=len(students),
        on_track=on_track,
        at_risk=at_risk,
        below_target=below,
        overdue_review=overdue,
        upcoming_review=upcoming,
    )


# ── Academic target actions (shared with progress reviews) ─────────

@dataclass
class TargetAction:
    action_id: int
    student_id: str
    target_id: int | None
    subject_name: str | None
    description: str
    measure: str | None
    due_date: str | None
    status: str
    progress_note: str | None
    closed_on: str | None
    source: str
    progress_review_id: int | None
    legacy_progress_target_id: int | None
    created_at: str
    updated_at: str

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_ACTION_STATUSES

    @property
    def is_overdue(self) -> bool:
        return (self.is_open and bool(self.due_date)
                and self.due_date < _dt.date.today().isoformat())


@dataclass
class StudentAcademicTargets:
    """Everything academic set for one student: the per-subject grade
    targets and the action steps working towards them."""
    student_id: str
    grade_targets: list[Target] = field(default_factory=list)
    actions: list[TargetAction] = field(default_factory=list)

    @property
    def open_actions(self) -> list[TargetAction]:
        return [a for a in self.actions if a.is_open]


def _row_action(r: sqlite3.Row) -> TargetAction:
    return TargetAction(
        action_id=r["action_id"], student_id=r["student_id"],
        target_id=r["target_id"], subject_name=r["subject_name"],
        description=r["description"], measure=r["measure"],
        due_date=r["due_date"], status=r["status"],
        progress_note=r["progress_note"], closed_on=r["closed_on"],
        source=r["source"],
        progress_review_id=r["progress_review_id"],
        legacy_progress_target_id=r["legacy_progress_target_id"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _validate_action_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["student_id"] = _validate_student(payload.get("student_id"))
    subject = (payload.get("subject_name") or "").strip() or None
    out["subject_name"] = subject
    tid = payload.get("target_id")
    if tid in (None, ""):
        out["target_id"] = None
    else:
        try:
            out["target_id"] = int(tid)
        except (TypeError, ValueError):
            raise ValidationError("Target id must be a number") from None
        t = get_target(out["target_id"])
        if t is None:
            raise ValidationError(f"No target #{out['target_id']}")
        if t.student_id != out["student_id"]:
            raise ValidationError(
                f"Target #{t.target_id} belongs to another student")
        out["subject_name"] = out["subject_name"] or t.subject_name
    # Link to the student's grade target for the subject when one exists.
    if out["target_id"] is None and subject:
        t = get_target_for(out["student_id"], subject)
        if t is not None:
            out["target_id"] = t.target_id
    out["description"] = _require(payload.get("description"),
                                  "Description").strip()
    out["measure"] = (payload.get("measure") or "").strip() or None
    out["due_date"] = _validate_date(payload.get("due_date"), "Due date")
    status = (payload.get("status") or DEFAULT_ACTION_STATUS).strip()
    if status not in ACTION_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(ACTION_STATUSES)}")
    out["status"] = status
    out["progress_note"] = (payload.get("progress_note")
                            or "").strip() or None
    out["closed_on"] = _validate_date(payload.get("closed_on"),
                                      "Closed on")
    if status in ("Met", "Missed") and not out["closed_on"]:
        out["closed_on"] = _dt.date.today().isoformat()
    if status in OPEN_ACTION_STATUSES:
        out["closed_on"] = None
    source = (payload.get("source") or "Target Setting").strip()
    if source not in ACTION_SOURCES:
        raise ValidationError(
            f"Source must be one of: {', '.join(ACTION_SOURCES)}")
    out["source"] = source
    rid = payload.get("progress_review_id")
    out["progress_review_id"] = int(rid) if rid not in (None, "") else None
    lid = payload.get("legacy_progress_target_id")
    out["legacy_progress_target_id"] = (int(lid) if lid not in (None, "")
                                        else None)
    return out


def create_action(payload: dict[str, Any]) -> TargetAction:
    """Add an academic action step for a student."""
    init_db()
    p = _validate_action_payload(payload)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO target_actions
                   (student_id, target_id, subject_name, description,
                    measure, due_date, status, progress_note, closed_on,
                    source, progress_review_id,
                    legacy_progress_target_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["student_id"], p["target_id"], p["subject_name"],
             p["description"], p["measure"], p["due_date"], p["status"],
             p["progress_note"], p["closed_on"], p["source"],
             p["progress_review_id"], p["legacy_progress_target_id"]))
        conn.commit()
        new_id = cur.lastrowid
    out = get_action(new_id)
    assert out is not None
    logger.info("Created academic action #%d for %s (%s)",
                new_id, p["student_id"], p["source"])
    return out


def get_action(action_id: int) -> TargetAction | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM target_actions WHERE action_id = ?",
                         (action_id,)).fetchone()
    return _row_action(r) if r else None


def action_for_progress_target(progress_target_id: int
                               ) -> TargetAction | None:
    """The action a progress-review target is stored as, if any."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM target_actions "
            "WHERE legacy_progress_target_id = ?",
            (int(progress_target_id),)).fetchone()
    return _row_action(r) if r else None


def list_actions(
    *,
    student_id: str | None = None,
    target_id: int | None = None,
    subject_name: str | None = None,
    status: str | None = None,
    source: str | None = None,
    progress_review_id: int | None = None,
    open_only: bool = False,
    due_before: str | None = None,
) -> list[TargetAction]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if target_id is not None:
        clauses.append("target_id = ?")
        args.append(int(target_id))
    if subject_name:
        clauses.append("subject_name = ?")
        args.append(subject_name.strip())
    if status:
        if status not in ACTION_STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(ACTION_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if source:
        clauses.append("source = ?")
        args.append(source)
    if progress_review_id is not None:
        clauses.append("progress_review_id = ?")
        args.append(int(progress_review_id))
    if open_only:
        ph = ",".join("?" * len(OPEN_ACTION_STATUSES))
        clauses.append(f"status IN ({ph})")
        args.extend(OPEN_ACTION_STATUSES)
    if due_before:
        clauses.append("due_date IS NOT NULL AND due_date <= ?")
        args.append(_validate_date(due_before, "Due before"))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM target_actions {where} "
            "ORDER BY COALESCE(due_date, created_at), action_id",
            args).fetchall()
    return [_row_action(r) for r in rows]


def update_action(action_id: int,
                  payload: dict[str, Any]) -> TargetAction:
    init_db()
    existing = get_action(action_id)
    if existing is None:
        raise ValidationError(f"No academic action #{action_id}")
    merged = {
        "student_id":    existing.student_id,
        "target_id":     payload.get("target_id", existing.target_id),
        "subject_name":  payload.get("subject_name",
                                     existing.subject_name),
        "description":   payload.get("description", existing.description),
        "measure":       payload.get("measure", existing.measure),
        "due_date":      payload.get("due_date", existing.due_date),
        "status":        payload.get("status", existing.status),
        "progress_note": payload.get("progress_note",
                                     existing.progress_note),
        "closed_on":     payload.get("closed_on", existing.closed_on),
        "source":        existing.source,
        "progress_review_id": existing.progress_review_id,
        "legacy_progress_target_id":
            existing.legacy_progress_target_id,
    }
    new_subject = (merged["subject_name"] or "").strip() or None
    if ("subject_name" in payload and "target_id" not in payload
            and new_subject != existing.subject_name):
        merged["target_id"] = None   # relink to the new subject's target
    p = _validate_action_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE target_actions SET
                   target_id=?, subject_name=?, description=?, measure=?,
                   due_date=?, status=?, progress_note=?, closed_on=?,
                   updated_at=datetime('now')
               WHERE action_id=?""",
            (p["target_id"], p["subject_name"], p["description"],
             p["measure"], p["due_date"], p["status"],
             p["progress_note"], p["closed_on"], action_id))
        conn.commit()
    out = get_action(action_id)
    assert out is not None
    # Keep the progress review's copy in step when this came from one.
    if out.legacy_progress_target_id is not None:
        _push_to_progress(out)
    return out


def delete_action(action_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM target_actions WHERE action_id = ?",
                           (action_id,))
        conn.commit()
    return bool(cur.rowcount)


def _push_to_progress(action: TargetAction) -> None:
    """Mirror an edit made here onto the progress review's row, so the
    review shows the same status whichever screen changed it."""
    from education_system.systems.sixth_form.domain.operations.reporting.progress import (
        progress as _prog,
    )
    try:
        with _prog._connect() as conn:
            conn.execute(
                """UPDATE progress_targets SET
                       description=?, measure=?, due_date=?, status=?,
                       progress_note=?, closed_on=?,
                       updated_at=datetime('now')
                   WHERE target_id=?""",
                (action.description, action.measure, action.due_date,
                 action.status, action.progress_note, action.closed_on,
                 action.legacy_progress_target_id))
            conn.commit()
    except sqlite3.Error:
        logger.exception("Could not mirror action #%d to progress target "
                         "#%s", action.action_id,
                         action.legacy_progress_target_id)


def student_academic_targets(student_id: str) -> StudentAcademicTargets:
    """Grade targets + action steps for one student (what ILP and the
    progress review show alongside their own records)."""
    sid = (student_id or "").strip()
    return StudentAcademicTargets(
        student_id=sid,
        grade_targets=list_targets(student_id=sid),
        actions=list_actions(student_id=sid),
    )


@dataclass
class MigrationResult:
    copied: int = 0
    already_present: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


def migrate_progress_targets() -> MigrationResult:
    """Copy Academic-area progress-review targets into ``target_actions``.

    Idempotent: each progress target is copied at most once, keyed on
    ``legacy_progress_target_id`` (a UNIQUE column). The original
    ``progress_targets`` rows are left in place.
    """
    init_db()
    result = MigrationResult()
    from education_system.systems.sixth_form.domain.operations.reporting.progress import (
        progress as _prog,
    )
    with _prog._connect() as pconn:
        have = {r[0] for r in pconn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('progress_targets', 'progress_reviews')")}
        if have != {"progress_targets", "progress_reviews"}:
            return result
        rows = pconn.execute(
            """SELECT pt.*, pr.student_id AS student_id
                 FROM progress_targets pt
                 JOIN progress_reviews pr ON pr.review_id = pt.review_id
                WHERE pt.area = 'Academic'""").fetchall()
    with _connect() as conn:
        for r in rows:
            try:
                cur = conn.execute(
                    """INSERT OR IGNORE INTO target_actions
                           (student_id, description, measure, due_date,
                            status, progress_note, closed_on, source,
                            progress_review_id, legacy_progress_target_id,
                            created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 'Progress Review',
                               ?, ?, ?, ?)""",
                    (r["student_id"], r["description"], r["measure"],
                     r["due_date"],
                     r["status"] if r["status"] in ACTION_STATUSES
                     else DEFAULT_ACTION_STATUS,
                     r["progress_note"], r["closed_on"], r["review_id"],
                     r["target_id"], r["created_at"], r["updated_at"]))
            except sqlite3.IntegrityError as e:
                result.skipped += 1
                result.errors.append(f"progress target #{r['target_id']}: {e}")
                continue
            if cur.rowcount:
                result.copied += 1
            else:
                result.already_present += 1
        conn.commit()
    if result.copied:
        logger.info("Migrated %d progress target(s) into target_actions",
                    result.copied)
    return result
