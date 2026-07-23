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
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any
from education_system.post_16.sixthform_system.core import paths
from education_system.post_16.sixthform_system.modules.domain.assessment.target_setting import (
    target_setting as data,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.TARGET_SETTING_DB


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

# UCAS-style points for grade arithmetic.
_POINTS: dict[str, int] = {
    "A*": 6, "A": 5, "B": 4, "C": 3, "D": 2, "E": 1, "U": 0,
}


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
    def mte_points(self) -> int | None:
        return _POINTS.get(self.mte_grade) if self.mte_grade else None

    @property
    def current_points(self) -> int | None:
        if not self.current_grade:
            return None
        return _POINTS.get(self.current_grade)

    @property
    def aspirational_points(self) -> int | None:
        if not self.aspirational_grade:
            return None
        return _POINTS.get(self.aspirational_grade)

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
    from education_system.post_16.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Target-setting schema ready at %s", DB_PATH)

    _DB_READY = True


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
                     required: bool = False) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(value).strip()
    if s not in A_LEVEL_GRADES:
        raise ValidationError(
            f"{label} must be one of: {', '.join(A_LEVEL_GRADES)}")
    return s


def _validate_student(value: Any) -> str:
    sid = _require(value, "Student").strip()
    from education_system.post_16.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    return sid


def _validate_subject(value: Any) -> str:
    name = _require(value, "Subject").strip()
    try:
        from education_system.post_16.sixthform_system.modules.domain.academics.subjects import (
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
    from education_system.post_16.sixthform_system.modules.domain.assessment.baseline_assessment import (
        baseline_assessment as _baseline,
    )
    if _baseline.get_record(bid) is None:
        raise ValidationError(f"No baseline record #{bid}")
    return bid


def _compute_status(mte: str | None, aspirational: str | None,
                     current: str | None,
                     manual_status: str | None = None) -> str:
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
    mte_pts = _POINTS.get(mte)
    cur_pts = _POINTS.get(current)
    if mte_pts is None or cur_pts is None:
        return manual_status or "Not Started"
    asp_pts = _POINTS.get(aspirational) if aspirational else None
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

    out["mte_grade"] = _validate_grade(
        payload.get("mte_grade"), "Minimum target",
        required=True)
    out["aspirational_grade"] = _validate_grade(
        payload.get("aspirational_grade"), "Aspirational target")
    out["current_grade"] = _validate_grade(
        payload.get("current_grade"), "Current grade")

    # Aspirational should not be lower than MTE on the points scale.
    if (out["aspirational_grade"]
            and out["mte_grade"]
            and _POINTS[out["aspirational_grade"]]
                < _POINTS[out["mte_grade"]]):
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
        manual_status or None)

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
    if get_target(out["target_id"]) is None:
        raise ValidationError(
            f"No target #{out['target_id']}")

    out["review_date"] = _validate_date(
        payload.get("review_date"), "Review date",
        required=True)
    out["current_grade"] = _validate_grade(
        payload.get("current_grade"), "Current grade")

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
        if mte_grade not in A_LEVEL_GRADES:
            raise ValidationError(
                f"Grade must be one of: "
                f"{', '.join(A_LEVEL_GRADES)}")
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
    from education_system.post_16.sixthform_system.modules.domain.students.students import (
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
    from education_system.post_16.sixthform_system.modules.domain.assessment.baseline_assessment import (
        baseline_assessment as _baseline,
    )
    baselines = _baseline.list_records(
        student_id=student_id, primary_only=True)
    created: list[Target] = []
    for b in baselines:
        if not (b.subject_name and b.baseline_grade
                and b.baseline_grade in A_LEVEL_GRADES):
            continue
        if get_target_for(student_id, b.subject_name) is not None:
            continue
        # Bump the aspirational by ``plus_grades`` points.
        mte_pts = _POINTS[b.baseline_grade]
        asp_pts = min(_POINTS["A*"], mte_pts + plus_grades)
        asp = next((g for g, p in _POINTS.items() if p == asp_pts),
                     b.baseline_grade)
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
