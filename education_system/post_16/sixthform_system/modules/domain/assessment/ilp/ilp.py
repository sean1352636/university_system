"""ILP — Individual Learning Plans for the Sixth Form System.

A holistic per-student plan covering academic, pastoral, SEND, attendance
or combined needs. Multiple plans per student are allowed (historic
plans coexist with the active one).

Three FK-linked tables:

* ``ilp_plans``    — one row per ILP (header).
* ``ilp_goals``    — SMART-style goals belonging to a plan.
* ``ilp_reviews``  — periodic review snapshots against a plan.

Cascade: deleting a student wipes all of their plans; deleting a plan
wipes its goals and reviews.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any
from education_system.post_16.sixthform_system.core import paths
from education_system.post_16.sixthform_system.modules.domain.assessment.ilp import (
    ilp as data,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.ILP_DB


PLAN_TYPES: tuple[str, ...] = (
    "Academic",
    "SEND",
    "Pastoral",
    "Behaviour",
    "Attendance",
    "Wellbeing",
    "Combined",
    "Transition",
    "Other",
)
DEFAULT_PLAN_TYPE: str = "Academic"

PLAN_STATUSES: tuple[str, ...] = (
    "Draft", "Active", "On Hold", "Completed",
    "Withdrawn", "Archived",
)
DEFAULT_PLAN_STATUS: str = "Draft"
OPEN_PLAN_STATUSES: tuple[str, ...] = ("Draft", "Active", "On Hold")

REVIEW_FREQUENCIES: tuple[str, ...] = (
    "Weekly", "Fortnightly", "Monthly",
    "Half-Termly", "Termly", "Ad-hoc",
)
DEFAULT_REVIEW_FREQUENCY: str = "Half-Termly"

GOAL_STATUSES: tuple[str, ...] = (
    "Open", "In Progress", "Achieved", "Partially Met",
    "Not Met", "Withdrawn",
)
DEFAULT_GOAL_STATUS: str = "Open"
ACHIEVED_GOAL_STATUSES: tuple[str, ...] = (
    "Achieved", "Partially Met",
)

GOAL_CATEGORIES: tuple[str, ...] = (
    "Academic",
    "Study Skills",
    "Behaviour",
    "Attendance",
    "Wellbeing",
    "Independence",
    "Communication",
    "Organisation",
    "Other",
)
DEFAULT_GOAL_CATEGORY: str = "Academic"

PROGRESS_TAGS: tuple[str, ...] = (
    "On Track", "Above Plan", "At Risk", "Off Plan", "Complete",
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS ilp_plans (
    plan_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id        TEXT NOT NULL,
    title             TEXT NOT NULL,
    plan_type         TEXT NOT NULL DEFAULT 'Academic',
    status            TEXT NOT NULL DEFAULT 'Draft',
    lead_staff        TEXT,
    start_date        TEXT,
    end_date          TEXT,
    review_frequency  TEXT NOT NULL DEFAULT 'Half-Termly',
    last_reviewed     TEXT,
    next_review_due   TEXT,
    strengths         TEXT,
    barriers          TEXT,
    strategies        TEXT,
    support_provided  TEXT,
    parental_involvement TEXT,
    success_criteria  TEXT,
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ilp_goals (
    goal_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id           INTEGER NOT NULL,
    title             TEXT NOT NULL,
    description       TEXT,
    category          TEXT NOT NULL DEFAULT 'Academic',
    target_date       TEXT,
    status            TEXT NOT NULL DEFAULT 'Open',
    success_criteria  TEXT,
    completed_on      TEXT,
    notes             TEXT,
    sort_order        INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (plan_id) REFERENCES ilp_plans(plan_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ilp_reviews (
    review_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id           INTEGER NOT NULL,
    review_date       TEXT NOT NULL,
    reviewer          TEXT,
    progress          TEXT,
    comments          TEXT,
    next_steps        TEXT,
    next_review_due   TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (plan_id) REFERENCES ilp_plans(plan_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ilp_plan_student ON ilp_plans(student_id);
CREATE INDEX IF NOT EXISTS idx_ilp_plan_status  ON ilp_plans(status);
CREATE INDEX IF NOT EXISTS idx_ilp_goal_plan    ON ilp_goals(plan_id);
CREATE INDEX IF NOT EXISTS idx_ilp_goal_status  ON ilp_goals(status);
CREATE INDEX IF NOT EXISTS idx_ilp_review_plan  ON ilp_reviews(plan_id);
"""


@dataclass
class Plan:
    plan_id: int
    student_id: str
    title: str
    plan_type: str
    status: str
    lead_staff: str | None
    start_date: str | None
    end_date: str | None
    review_frequency: str
    last_reviewed: str | None
    next_review_due: str | None
    strengths: str | None
    barriers: str | None
    strategies: str | None
    support_provided: str | None
    parental_involvement: str | None
    success_criteria: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_PLAN_STATUSES

    @property
    def review_overdue(self) -> bool:
        if not (self.is_open and self.next_review_due):
            return False
        return self.next_review_due < _dt.date.today().isoformat()


@dataclass
class Goal:
    goal_id: int
    plan_id: int
    title: str
    description: str | None
    category: str
    target_date: str | None
    status: str
    success_criteria: str | None
    completed_on: str | None
    notes: str | None
    sort_order: int
    created_at: str
    updated_at: str

    @property
    def is_done(self) -> bool:
        return self.status in ACHIEVED_GOAL_STATUSES

    @property
    def is_open(self) -> bool:
        return self.status in ("Open", "In Progress")


@dataclass
class Review:
    review_id: int
    plan_id: int
    review_date: str
    reviewer: str | None
    progress: str | None
    comments: str | None
    next_steps: str | None
    next_review_due: str | None
    created_at: str
    updated_at: str


@dataclass
class PlanDetail:
    plan: Plan
    goals: list[Goal] = field(default_factory=list)
    reviews: list[Review] = field(default_factory=list)
    student_name: str = ""

    @property
    def goal_progress(self) -> tuple[int, int]:
        done = sum(1 for g in self.goals if g.is_done)
        return (done, len(self.goals))


@dataclass
class PlanRow:
    plan: Plan
    student_name: str
    goal_count: int = 0
    achieved_count: int = 0
    review_count: int = 0


@dataclass
class Summary:
    total_plans: int
    by_status: dict[str, int]
    by_type: dict[str, int]
    open_count: int
    distinct_students: int
    total_goals: int
    goals_achieved: int
    review_overdue: int
    upcoming_review: int          # next_review_due in [today, +window]


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
    logger.debug("ILP schema ready at %s", DB_PATH)

    _DB_READY = True


def _row_plan(r: sqlite3.Row) -> Plan:
    return Plan(
        plan_id=r["plan_id"], student_id=r["student_id"],
        title=r["title"], plan_type=r["plan_type"],
        status=r["status"], lead_staff=r["lead_staff"],
        start_date=r["start_date"], end_date=r["end_date"],
        review_frequency=r["review_frequency"],
        last_reviewed=r["last_reviewed"],
        next_review_due=r["next_review_due"],
        strengths=r["strengths"], barriers=r["barriers"],
        strategies=r["strategies"],
        support_provided=r["support_provided"],
        parental_involvement=r["parental_involvement"],
        success_criteria=r["success_criteria"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_goal(r: sqlite3.Row) -> Goal:
    return Goal(
        goal_id=r["goal_id"], plan_id=r["plan_id"],
        title=r["title"], description=r["description"],
        category=r["category"], target_date=r["target_date"],
        status=r["status"],
        success_criteria=r["success_criteria"],
        completed_on=r["completed_on"], notes=r["notes"],
        sort_order=r["sort_order"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_review(r: sqlite3.Row) -> Review:
    return Review(
        review_id=r["review_id"], plan_id=r["plan_id"],
        review_date=r["review_date"], reviewer=r["reviewer"],
        progress=r["progress"], comments=r["comments"],
        next_steps=r["next_steps"],
        next_review_due=r["next_review_due"],
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


def _validate_student(value: Any) -> str:
    sid = _require(value, "Student").strip()
    from education_system.post_16.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    return sid


def _validate_plan_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["student_id"] = _validate_student(payload.get("student_id"))
    out["title"] = _require(payload.get("title"), "Title").strip()

    ptype = (payload.get("plan_type") or DEFAULT_PLAN_TYPE).strip()
    if ptype not in PLAN_TYPES:
        raise ValidationError(
            f"Plan type must be one of: {', '.join(PLAN_TYPES)}")
    out["plan_type"] = ptype

    status = (payload.get("status") or DEFAULT_PLAN_STATUS).strip()
    if status not in PLAN_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(PLAN_STATUSES)}")
    out["status"] = status

    freq = (payload.get("review_frequency")
             or DEFAULT_REVIEW_FREQUENCY).strip()
    if freq not in REVIEW_FREQUENCIES:
        raise ValidationError(
            f"Review frequency must be one of: "
            f"{', '.join(REVIEW_FREQUENCIES)}")
    out["review_frequency"] = freq

    out["start_date"]      = _validate_date(payload.get("start_date"),
                                                  "Start date")
    out["end_date"]        = _validate_date(payload.get("end_date"),
                                                  "End date")
    if (out["start_date"] and out["end_date"]
            and out["end_date"] < out["start_date"]):
        raise ValidationError(
            "End date cannot be before start date")

    out["last_reviewed"]   = _validate_date(
        payload.get("last_reviewed"), "Last reviewed")
    out["next_review_due"] = _validate_date(
        payload.get("next_review_due"), "Next review due")

    out["lead_staff"]           = (payload.get("lead_staff")
                                       or "").strip() or None
    out["strengths"]            = (payload.get("strengths")
                                       or "").strip() or None
    out["barriers"]             = (payload.get("barriers")
                                       or "").strip() or None
    out["strategies"]           = (payload.get("strategies")
                                       or "").strip() or None
    out["support_provided"]     = (payload.get("support_provided")
                                       or "").strip() or None
    out["parental_involvement"] = (payload.get("parental_involvement")
                                       or "").strip() or None
    out["success_criteria"]     = (payload.get("success_criteria")
                                       or "").strip() or None
    out["notes"]                = (payload.get("notes")
                                       or "").strip() or None
    return out


def _validate_goal_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    pid = payload.get("plan_id")
    if pid in (None, ""):
        raise ValidationError("Plan id is required")
    try:
        out["plan_id"] = int(pid)
    except (TypeError, ValueError):
        raise ValidationError("Plan id must be a number") from None
    if get_plan(out["plan_id"]) is None:
        raise ValidationError(f"No plan #{out['plan_id']}")

    out["title"] = _require(payload.get("title"), "Title").strip()
    category = (payload.get("category") or DEFAULT_GOAL_CATEGORY).strip()
    if category not in GOAL_CATEGORIES:
        raise ValidationError(
            f"Category must be one of: "
            f"{', '.join(GOAL_CATEGORIES)}")
    out["category"] = category

    status = (payload.get("status") or DEFAULT_GOAL_STATUS).strip()
    if status not in GOAL_STATUSES:
        raise ValidationError(
            f"Goal status must be one of: "
            f"{', '.join(GOAL_STATUSES)}")
    out["status"] = status

    out["target_date"]  = _validate_date(payload.get("target_date"),
                                               "Target date")
    out["completed_on"] = _validate_date(payload.get("completed_on"),
                                               "Completed on")
    out["description"]      = (payload.get("description")
                                  or "").strip() or None
    out["success_criteria"] = (payload.get("success_criteria")
                                  or "").strip() or None
    out["notes"]            = (payload.get("notes")
                                  or "").strip() or None
    try:
        out["sort_order"] = int(payload.get("sort_order") or 0)
    except (TypeError, ValueError):
        out["sort_order"] = 0

    if status in ACHIEVED_GOAL_STATUSES and not out["completed_on"]:
        out["completed_on"] = _dt.date.today().isoformat()
    return out


def _validate_review_payload(payload: dict[str, Any]
                              ) -> dict[str, Any]:
    out: dict[str, Any] = {}
    pid = payload.get("plan_id")
    if pid in (None, ""):
        raise ValidationError("Plan id is required")
    try:
        out["plan_id"] = int(pid)
    except (TypeError, ValueError):
        raise ValidationError("Plan id must be a number") from None
    if get_plan(out["plan_id"]) is None:
        raise ValidationError(f"No plan #{out['plan_id']}")

    out["review_date"] = _validate_date(
        payload.get("review_date"), "Review date",
        required=True)

    progress = (payload.get("progress") or "").strip()
    if progress and progress not in PROGRESS_TAGS:
        raise ValidationError(
            f"Progress must be one of: "
            f"{', '.join(PROGRESS_TAGS)}")
    out["progress"] = progress or None
    out["reviewer"]   = (payload.get("reviewer") or "").strip() or None
    out["comments"]   = (payload.get("comments") or "").strip() or None
    out["next_steps"] = (payload.get("next_steps") or "").strip() or None
    out["next_review_due"] = _validate_date(
        payload.get("next_review_due"), "Next review due")
    return out


# ── Plan CRUD ─────────────────────────────────────────────────────

def create_plan(payload: dict[str, Any]) -> Plan:
    init_db()
    p = _validate_plan_payload(payload)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO ilp_plans
                   (student_id, title, plan_type, status, lead_staff,
                    start_date, end_date, review_frequency,
                    last_reviewed, next_review_due, strengths,
                    barriers, strategies, support_provided,
                    parental_involvement, success_criteria, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, datetime('now'), datetime('now'))""",
            (p["student_id"], p["title"], p["plan_type"], p["status"],
             p["lead_staff"], p["start_date"], p["end_date"],
             p["review_frequency"], p["last_reviewed"],
             p["next_review_due"], p["strengths"], p["barriers"],
             p["strategies"], p["support_provided"],
             p["parental_involvement"], p["success_criteria"],
             p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_plan(new_id)
    assert out is not None
    logger.info(
        "Created ILP #%d for %s type=%s status=%s",
        new_id, p["student_id"], p["plan_type"], p["status"])
    return out


def get_plan(plan_id: int) -> Plan | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM ilp_plans WHERE plan_id = ?",
            (plan_id,)).fetchone()
        return _row_plan(r) if r else None


def list_plans(
    *,
    student_id: str | None = None,
    plan_type: str | None = None,
    status: str | None = None,
    open_only: bool = False,
    review_overdue: bool = False,
    lead_like: str | None = None,
    title_like: str | None = None,
) -> list[Plan]:
    init_db()
    clauses, args = [], []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if plan_type:
        if plan_type not in PLAN_TYPES:
            raise ValidationError(
                f"Plan type must be one of: "
                f"{', '.join(PLAN_TYPES)}")
        clauses.append("plan_type = ?")
        args.append(plan_type)
    if status:
        if status not in PLAN_STATUSES:
            raise ValidationError(
                f"Status must be one of: "
                f"{', '.join(PLAN_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if open_only:
        ph = ",".join("?" * len(OPEN_PLAN_STATUSES))
        clauses.append(f"status IN ({ph})")
        args.extend(OPEN_PLAN_STATUSES)
    if review_overdue:
        today = _dt.date.today().isoformat()
        ph = ",".join("?" * len(OPEN_PLAN_STATUSES))
        clauses.append(
            f"next_review_due IS NOT NULL AND next_review_due < ? "
            f"AND status IN ({ph})")
        args.append(today)
        args.extend(OPEN_PLAN_STATUSES)
    if lead_like:
        clauses.append("lead_staff LIKE ?")
        args.append(f"%{lead_like.strip()}%")
    if title_like:
        clauses.append("title LIKE ?")
        args.append(f"%{title_like.strip()}%")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM ilp_plans {where} "
           "ORDER BY CASE status "
           "  WHEN 'Active'     THEN 0 "
           "  WHEN 'Draft'      THEN 1 "
           "  WHEN 'On Hold'    THEN 2 "
           "  WHEN 'Completed'  THEN 3 "
           "  WHEN 'Withdrawn'  THEN 4 "
           "  WHEN 'Archived'   THEN 5 "
           "  ELSE 6 END, "
           "next_review_due ASC NULLS LAST, "
           "student_id ASC, plan_id ASC")
    with _connect() as conn:
        return [_row_plan(r)
                for r in conn.execute(sql, args).fetchall()]


def list_plans_with_detail(**kwargs) -> list[PlanRow]:
    rows = list_plans(**kwargs)
    if not rows:
        return []
    from education_system.post_16.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    names = {s.student_id: s.full_name
              for s in _students.list_students()}
    out: list[PlanRow] = []
    with _connect() as conn:
        for p in rows:
            stats = conn.execute(
                f"SELECT COUNT(*) total, "
                f"  SUM(CASE WHEN status IN "
                f"  ({','.join('?' * len(ACHIEVED_GOAL_STATUSES))}) "
                f"  THEN 1 ELSE 0 END) AS achieved "
                f"FROM ilp_goals WHERE plan_id = ?",
                (*ACHIEVED_GOAL_STATUSES, p.plan_id)).fetchone()
            rc = conn.execute(
                "SELECT COUNT(*) FROM ilp_reviews WHERE plan_id = ?",
                (p.plan_id,)).fetchone()[0]
            out.append(PlanRow(
                plan=p,
                student_name=names.get(p.student_id, "(unknown)"),
                goal_count=stats["total"] or 0,
                achieved_count=stats["achieved"] or 0,
                review_count=rc or 0,
            ))
    return out


def get_plan_detail(plan_id: int) -> PlanDetail | None:
    init_db()
    p = get_plan(plan_id)
    if p is None:
        return None
    goals = list_goals(plan_id=plan_id)
    reviews = list_reviews(plan_id=plan_id)
    from education_system.post_16.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    student = _students.get_student(p.student_id)
    name = student.full_name if student else "(unknown)"
    return PlanDetail(plan=p, goals=goals, reviews=reviews,
                       student_name=name)


def update_plan(plan_id: int, payload: dict[str, Any]) -> Plan:
    init_db()
    existing = get_plan(plan_id)
    if existing is None:
        raise ValidationError(f"No plan #{plan_id}")
    merged = {
        "student_id":           existing.student_id,
        "title":                payload.get("title", existing.title),
        "plan_type":            payload.get("plan_type",
                                             existing.plan_type),
        "status":               payload.get("status", existing.status),
        "lead_staff":           payload.get("lead_staff",
                                             existing.lead_staff),
        "start_date":           payload.get("start_date",
                                             existing.start_date),
        "end_date":             payload.get("end_date",
                                             existing.end_date),
        "review_frequency":     payload.get("review_frequency",
                                             existing.review_frequency),
        "last_reviewed":        payload.get("last_reviewed",
                                             existing.last_reviewed),
        "next_review_due":      payload.get("next_review_due",
                                             existing.next_review_due),
        "strengths":            payload.get("strengths",
                                             existing.strengths),
        "barriers":             payload.get("barriers",
                                             existing.barriers),
        "strategies":           payload.get("strategies",
                                             existing.strategies),
        "support_provided":     payload.get("support_provided",
                                             existing.support_provided),
        "parental_involvement": payload.get(
            "parental_involvement", existing.parental_involvement),
        "success_criteria":     payload.get("success_criteria",
                                             existing.success_criteria),
        "notes":                payload.get("notes", existing.notes),
    }
    p = _validate_plan_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE ilp_plans SET
                   title = ?, plan_type = ?, status = ?,
                   lead_staff = ?, start_date = ?, end_date = ?,
                   review_frequency = ?, last_reviewed = ?,
                   next_review_due = ?, strengths = ?, barriers = ?,
                   strategies = ?, support_provided = ?,
                   parental_involvement = ?, success_criteria = ?,
                   notes = ?, updated_at = datetime('now')
               WHERE plan_id = ?""",
            (p["title"], p["plan_type"], p["status"],
             p["lead_staff"], p["start_date"], p["end_date"],
             p["review_frequency"], p["last_reviewed"],
             p["next_review_due"], p["strengths"], p["barriers"],
             p["strategies"], p["support_provided"],
             p["parental_involvement"], p["success_criteria"],
             p["notes"], plan_id),
        )
        conn.commit()
    out = get_plan(plan_id)
    assert out is not None
    return out


def set_plan_status(plan_id: int, status: str) -> Plan:
    return update_plan(plan_id, {"status": status})


def delete_plan(plan_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM ilp_plans WHERE plan_id = ?",
            (plan_id,))
        conn.commit()
        if cur.rowcount:
            logger.info(
                "Deleted plan #%d (cascade: goals + reviews)",
                plan_id)
            return True
        return False


# ── Goal CRUD ─────────────────────────────────────────────────────

def create_goal(payload: dict[str, Any]) -> Goal:
    init_db()
    p = _validate_goal_payload(payload)
    with _connect() as conn:
        if not p["sort_order"]:
            max_o = conn.execute(
                "SELECT COALESCE(MAX(sort_order), 0) "
                "FROM ilp_goals WHERE plan_id = ?",
                (p["plan_id"],)).fetchone()[0]
            p["sort_order"] = (max_o or 0) + 1
        cur = conn.execute(
            """INSERT INTO ilp_goals
                   (plan_id, title, description, category,
                    target_date, status, success_criteria,
                    completed_on, notes, sort_order,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["plan_id"], p["title"], p["description"],
             p["category"], p["target_date"], p["status"],
             p["success_criteria"], p["completed_on"], p["notes"],
             p["sort_order"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_goal(new_id)
    assert out is not None
    logger.info("Created goal #%d on plan #%d", new_id, p["plan_id"])
    return out


def get_goal(goal_id: int) -> Goal | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM ilp_goals WHERE goal_id = ?",
            (goal_id,)).fetchone()
        return _row_goal(r) if r else None


def list_goals(*, plan_id: int | None = None,
                status: str | None = None,
                category: str | None = None,
                open_only: bool = False) -> list[Goal]:
    init_db()
    clauses, args = [], []
    if plan_id is not None:
        clauses.append("plan_id = ?")
        args.append(int(plan_id))
    if status:
        if status not in GOAL_STATUSES:
            raise ValidationError(
                f"Status must be one of: "
                f"{', '.join(GOAL_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if category:
        if category not in GOAL_CATEGORIES:
            raise ValidationError(
                f"Category must be one of: "
                f"{', '.join(GOAL_CATEGORIES)}")
        clauses.append("category = ?")
        args.append(category)
    if open_only:
        clauses.append("status IN ('Open', 'In Progress')")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM ilp_goals {where} "
           "ORDER BY sort_order ASC, goal_id ASC")
    with _connect() as conn:
        return [_row_goal(r)
                for r in conn.execute(sql, args).fetchall()]


def update_goal(goal_id: int, payload: dict[str, Any]) -> Goal:
    init_db()
    existing = get_goal(goal_id)
    if existing is None:
        raise ValidationError(f"No goal #{goal_id}")
    merged = {
        "plan_id":          existing.plan_id,
        "title":            payload.get("title", existing.title),
        "description":      payload.get("description",
                                         existing.description),
        "category":         payload.get("category",
                                         existing.category),
        "target_date":      payload.get("target_date",
                                         existing.target_date),
        "status":           payload.get("status", existing.status),
        "success_criteria": payload.get("success_criteria",
                                         existing.success_criteria),
        "completed_on":     payload.get("completed_on",
                                         existing.completed_on),
        "notes":            payload.get("notes", existing.notes),
        "sort_order":       payload.get("sort_order",
                                         existing.sort_order),
    }
    p = _validate_goal_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE ilp_goals SET
                   title = ?, description = ?, category = ?,
                   target_date = ?, status = ?, success_criteria = ?,
                   completed_on = ?, notes = ?, sort_order = ?,
                   updated_at = datetime('now')
               WHERE goal_id = ?""",
            (p["title"], p["description"], p["category"],
             p["target_date"], p["status"], p["success_criteria"],
             p["completed_on"], p["notes"], p["sort_order"],
             goal_id),
        )
        conn.commit()
    out = get_goal(goal_id)
    assert out is not None
    return out


def set_goal_status(goal_id: int, status: str) -> Goal:
    return update_goal(goal_id, {"status": status})


def achieve_goal(goal_id: int, *,
                  completed_on: str | None = None) -> Goal:
    return update_goal(goal_id, {
        "status": "Achieved",
        "completed_on": completed_on
            or _dt.date.today().isoformat(),
    })


def delete_goal(goal_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM ilp_goals WHERE goal_id = ?",
            (goal_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted goal #%d", goal_id)
            return True
        return False


# ── Review CRUD ───────────────────────────────────────────────────

def add_review(plan_id: int, *,
                review_date: str | None = None,
                reviewer: str | None = None,
                progress: str | None = None,
                comments: str | None = None,
                next_steps: str | None = None,
                next_review_due: str | None = None) -> Review:
    """Append a review, stamp the parent plan's ``last_reviewed`` and
    optionally ``next_review_due``."""
    payload = {
        "plan_id":         plan_id,
        "review_date":     review_date
                              or _dt.date.today().isoformat(),
        "reviewer":        reviewer,
        "progress":        progress,
        "comments":        comments,
        "next_steps":      next_steps,
        "next_review_due": next_review_due,
    }
    r = create_review(payload)
    plan_update: dict[str, Any] = {"last_reviewed": r.review_date}
    if next_review_due is not None:
        plan_update["next_review_due"] = next_review_due
    update_plan(plan_id, plan_update)
    return r


def create_review(payload: dict[str, Any]) -> Review:
    init_db()
    p = _validate_review_payload(payload)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO ilp_reviews
                   (plan_id, review_date, reviewer, progress,
                    comments, next_steps, next_review_due,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["plan_id"], p["review_date"], p["reviewer"],
             p["progress"], p["comments"], p["next_steps"],
             p["next_review_due"]),
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
            "SELECT * FROM ilp_reviews WHERE review_id = ?",
            (review_id,)).fetchone()
        return _row_review(r) if r else None


def list_reviews(*, plan_id: int | None = None,
                  reviewer_like: str | None = None,
                  date_from: str | None = None,
                  date_to: str | None = None) -> list[Review]:
    init_db()
    clauses, args = [], []
    if plan_id is not None:
        clauses.append("plan_id = ?")
        args.append(int(plan_id))
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
    sql = (f"SELECT * FROM ilp_reviews {where} "
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
        "plan_id":         existing.plan_id,
        "review_date":     payload.get("review_date",
                                        existing.review_date),
        "reviewer":        payload.get("reviewer",
                                        existing.reviewer),
        "progress":        payload.get("progress",
                                        existing.progress),
        "comments":        payload.get("comments",
                                        existing.comments),
        "next_steps":      payload.get("next_steps",
                                        existing.next_steps),
        "next_review_due": payload.get("next_review_due",
                                        existing.next_review_due),
    }
    p = _validate_review_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE ilp_reviews SET
                   review_date = ?, reviewer = ?, progress = ?,
                   comments = ?, next_steps = ?, next_review_due = ?,
                   updated_at = datetime('now')
               WHERE review_id = ?""",
            (p["review_date"], p["reviewer"], p["progress"],
             p["comments"], p["next_steps"], p["next_review_due"],
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
            "DELETE FROM ilp_reviews WHERE review_id = ?",
            (review_id,))
        conn.commit()
        return bool(cur.rowcount)


# ── Summary ───────────────────────────────────────────────────────

def summary(*, upcoming_window_days: int = 14) -> Summary:
    init_db()
    today = _dt.date.today().isoformat()
    horizon = (_dt.date.today()
                + _dt.timedelta(days=upcoming_window_days)).isoformat()
    rows = list_plans()
    by_status = {s: 0 for s in PLAN_STATUSES}
    by_type   = {t: 0 for t in PLAN_TYPES}
    open_count = 0
    overdue = 0
    upcoming = 0
    students: set[str] = set()
    for p in rows:
        by_status[p.status] = by_status.get(p.status, 0) + 1
        by_type[p.plan_type] = by_type.get(p.plan_type, 0) + 1
        if p.is_open:
            open_count += 1
            if p.next_review_due:
                if p.next_review_due < today:
                    overdue += 1
                elif p.next_review_due <= horizon:
                    upcoming += 1
        students.add(p.student_id)

    with _connect() as conn:
        tg = conn.execute(
            "SELECT COUNT(*) FROM ilp_goals").fetchone()[0]
        ach = conn.execute(
            f"SELECT COUNT(*) FROM ilp_goals WHERE status IN "
            f"({','.join('?' * len(ACHIEVED_GOAL_STATUSES))})",
            ACHIEVED_GOAL_STATUSES).fetchone()[0]

    return Summary(
        total_plans=len(rows),
        by_status=by_status,
        by_type=by_type,
        open_count=open_count,
        distinct_students=len(students),
        total_goals=tg,
        goals_achieved=ach,
        review_overdue=overdue,
        upcoming_review=upcoming,
    )
