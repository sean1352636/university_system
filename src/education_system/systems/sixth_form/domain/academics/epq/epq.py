"""Extended Project Qualification (EPQ) data layer.

Three tables:

* ``epq_projects`` — one project per student (UNIQUE ``student_id``),
  capturing artefact type, supervisor, proposed research question,
  working title, stage, and final mark/grade.
* ``epq_logentries`` — production-log entries (a JCQ requirement for
  EPQ): one row per logged activity with date, hours, activity, and
  reflection.
* ``epq_milestones`` — one row per (project, milestone-type) pair with
  a due date and status. Milestone types are fixed (PROPOSAL,
  MID_REVIEW, DRAFT, PRESENTATION) so reports stay consistent.

Cascade: deleting a project removes its log entries and milestones;
deleting a student removes the project (and therefore the rest).
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system import paths
from education_system.systems.sixth_form.domain.academics.qualifications import (
    grade_scales as _gs,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_EPQ_DB

ARTEFACT_TYPES: tuple[str, ...] = (
    "Dissertation", "Artefact", "Performance", "Investigation",
)
DEFAULT_ARTEFACT_TYPE: str = "Dissertation"

STAGES: tuple[str, ...] = (
    "Proposal", "Research", "Drafting", "Production",
    "Review", "Presentation", "Complete", "Withdrawn",
)
DEFAULT_STAGE: str = "Proposal"

# The EPQ scale from qualifications.grade_scales (A*-U, as before).
GRADES: tuple[str, ...] = _gs.scale_for("EPQ").grades

#: Guided learning hours the EPQ specification sets for the project.
#: Logged production-log hours are checked against it.
EPQ_TARGET_HOURS: float = 120.0

MILESTONE_TYPES: tuple[str, ...] = (
    "PROPOSAL", "MID_REVIEW", "DRAFT", "PRESENTATION",
)
MILESTONE_LABELS: dict[str, str] = {
    "PROPOSAL":     "Proposal approved",
    "MID_REVIEW":   "Mid-project review",
    "DRAFT":        "Full draft submitted",
    "PRESENTATION": "Presentation delivered",
}

MILESTONE_STATUSES: tuple[str, ...] = (
    "Pending", "In Progress", "Completed",
)
DEFAULT_MILESTONE_STATUS: str = "Pending"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS epq_projects (
    project_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id              TEXT NOT NULL UNIQUE,
    working_title           TEXT NOT NULL,
    research_question       TEXT,
    artefact_type           TEXT NOT NULL DEFAULT 'Dissertation',
    supervisor              TEXT,
    stage                   TEXT NOT NULL DEFAULT 'Proposal',
    final_mark              INTEGER,
    final_grade             TEXT,
    notes                   TEXT,
    created_at              TEXT DEFAULT (datetime('now')),
    updated_at              TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS epq_logentries (
    log_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id    INTEGER NOT NULL,
    entry_date    TEXT NOT NULL,
    hours         REAL NOT NULL,
    activity      TEXT NOT NULL,
    reflection    TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES epq_projects(project_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS epq_milestones (
    milestone_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL,
    milestone_type  TEXT NOT NULL,
    due_date        TEXT,
    completed_date  TEXT,
    status          TEXT NOT NULL DEFAULT 'Pending',
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE (project_id, milestone_type),
    FOREIGN KEY (project_id) REFERENCES epq_projects(project_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_epq_stage     ON epq_projects(stage);
CREATE INDEX IF NOT EXISTS idx_epq_supervisor ON epq_projects(supervisor);
CREATE INDEX IF NOT EXISTS idx_epq_log_proj  ON epq_logentries(project_id);
CREATE INDEX IF NOT EXISTS idx_epq_log_date  ON epq_logentries(entry_date);
CREATE INDEX IF NOT EXISTS idx_epq_ms_proj   ON epq_milestones(project_id);
CREATE INDEX IF NOT EXISTS idx_epq_ms_status ON epq_milestones(status);
"""


@dataclass
class EPQProject:
    project_id: int
    student_id: str
    working_title: str
    research_question: str | None
    artefact_type: str
    supervisor: str | None
    stage: str
    final_mark: int | None
    final_grade: str | None
    notes: str | None
    created_at: str
    updated_at: str
    # Teacher authentication (JCQ): the supervisor confirms the work is
    # the candidate's own, after the candidate's declaration.
    candidate_declared_at: str | None = None
    authenticated_by: str | None = None
    authenticated_at: str | None = None
    authentication_notes: str | None = None

    @property
    def is_authenticated(self) -> bool:
        return bool(self.authenticated_by and self.authenticated_at)


@dataclass
class HoursCheck:
    project_id: int
    logged_hours: float
    target_hours: float
    remaining: float
    met: bool

    @property
    def label(self) -> str:
        if self.met:
            return f"{self.logged_hours:g} / {self.target_hours:g} h — target met"
        return (f"{self.logged_hours:g} / {self.target_hours:g} h — "
                f"{self.remaining:g} h short")


@dataclass
class EPQLogEntry:
    log_id: int
    project_id: int
    entry_date: str
    hours: float
    activity: str
    reflection: str | None
    created_at: str


@dataclass
class EPQMilestone:
    milestone_id: int
    project_id: int
    milestone_type: str
    due_date: str | None
    completed_date: str | None
    status: str
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class ProjectRow:
    project: EPQProject
    student_name: str
    total_hours: float
    log_count: int
    milestones_completed: int
    milestones_total: int


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
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(epq_projects)")}
        for col in ("candidate_declared_at", "authenticated_by",
                    "authenticated_at", "authentication_notes"):
            if col not in cols:
                conn.execute(f"ALTER TABLE epq_projects ADD COLUMN {col} TEXT")
                logger.info("EPQ: added column %s", col)
        conn.commit()
    logger.debug("EPQ schema ready at %s", DB_PATH)
    _DB_READY = True


def _row_project(r: sqlite3.Row) -> EPQProject:
    return EPQProject(
        project_id=r["project_id"], student_id=r["student_id"],
        working_title=r["working_title"],
        research_question=r["research_question"],
        artefact_type=r["artefact_type"], supervisor=r["supervisor"],
        stage=r["stage"],
        final_mark=r["final_mark"], final_grade=r["final_grade"],
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
        candidate_declared_at=(r["candidate_declared_at"]
                               if "candidate_declared_at" in r.keys() else None),
        authenticated_by=(r["authenticated_by"]
                          if "authenticated_by" in r.keys() else None),
        authenticated_at=(r["authenticated_at"]
                          if "authenticated_at" in r.keys() else None),
        authentication_notes=(r["authentication_notes"]
                              if "authentication_notes" in r.keys() else None),
    )


def _row_log(r: sqlite3.Row) -> EPQLogEntry:
    return EPQLogEntry(
        log_id=r["log_id"], project_id=r["project_id"],
        entry_date=r["entry_date"], hours=r["hours"],
        activity=r["activity"], reflection=r["reflection"],
        created_at=r["created_at"],
    )


def _row_milestone(r: sqlite3.Row) -> EPQMilestone:
    return EPQMilestone(
        milestone_id=r["milestone_id"], project_id=r["project_id"],
        milestone_type=r["milestone_type"],
        due_date=r["due_date"], completed_date=r["completed_date"],
        status=r["status"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for invalid EPQ input."""


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_date(value: Any, label: str) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real calendar date") from None
    return s


def _validate_project_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    sid = _require(data.get("student_id"), "Student ID").strip()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    out["student_id"] = sid

    out["working_title"] = _require(
        data.get("working_title"), "Working title").strip()

    artefact = (data.get("artefact_type") or DEFAULT_ARTEFACT_TYPE).strip()
    if artefact not in ARTEFACT_TYPES:
        raise ValidationError(
            f"Artefact type must be one of: {', '.join(ARTEFACT_TYPES)}")
    out["artefact_type"] = artefact

    stage = (data.get("stage") or DEFAULT_STAGE).strip()
    if stage not in STAGES:
        raise ValidationError(
            f"Stage must be one of: {', '.join(STAGES)}")
    out["stage"] = stage

    mark = data.get("final_mark")
    if mark in (None, ""):
        out["final_mark"] = None
    else:
        try:
            m = int(mark)
        except (TypeError, ValueError):
            raise ValidationError(
                "Final mark must be a whole number 0-50") from None
        if m < 0 or m > 50:
            raise ValidationError("Final mark must be between 0 and 50")
        out["final_mark"] = m

    grade = (data.get("final_grade") or "").strip() or None
    if grade is not None:
        try:
            grade = _gs.validate_grade(grade, "EPQ")
        except ValueError:
            raise ValidationError(
                f"Final grade must be one of: {', '.join(GRADES)}") from None
    out["final_grade"] = grade

    out["research_question"] = (data.get("research_question") or "").strip() or None
    out["supervisor"]        = (data.get("supervisor") or "").strip() or None
    out["notes"]             = (data.get("notes") or "").strip() or None
    return out


def _validate_log_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    pid = data.get("project_id")
    if pid in (None, ""):
        raise ValidationError("Project ID is required")
    try:
        out["project_id"] = int(pid)
    except (TypeError, ValueError):
        raise ValidationError("Project ID must be a number") from None

    out["entry_date"] = _validate_date(
        _require(data.get("entry_date"), "Entry date"), "Entry date")

    hours = _require(data.get("hours"), "Hours")
    try:
        h = float(hours)
    except (TypeError, ValueError):
        raise ValidationError("Hours must be a number") from None
    if h <= 0 or h > 24:
        raise ValidationError("Hours must be between 0 and 24")
    out["hours"] = round(h, 2)

    out["activity"]   = _require(data.get("activity"), "Activity").strip()
    out["reflection"] = (data.get("reflection") or "").strip() or None
    return out


def _validate_milestone_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    pid = data.get("project_id")
    if pid in (None, ""):
        raise ValidationError("Project ID is required")
    try:
        out["project_id"] = int(pid)
    except (TypeError, ValueError):
        raise ValidationError("Project ID must be a number") from None

    mtype = _require(data.get("milestone_type"), "Milestone type").strip().upper()
    if mtype not in MILESTONE_TYPES:
        raise ValidationError(
            f"Milestone type must be one of: {', '.join(MILESTONE_TYPES)}")
    out["milestone_type"] = mtype

    out["due_date"]       = _validate_date(data.get("due_date"), "Due date")
    out["completed_date"] = _validate_date(
        data.get("completed_date"), "Completed date")

    status = (data.get("status") or DEFAULT_MILESTONE_STATUS).strip()
    if status not in MILESTONE_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(MILESTONE_STATUSES)}")
    out["status"] = status

    # If status is Completed but no date supplied, fill it in.
    if out["status"] == "Completed" and out["completed_date"] is None:
        out["completed_date"] = _dt.date.today().isoformat()

    out["notes"] = (data.get("notes") or "").strip() or None
    return out


# ── Project CRUD ──────────────────────────────────────────────────

def create_project(data: dict[str, Any]) -> EPQProject:
    init_db()
    try:
        p = _validate_project_payload(data)
    except ValidationError as e:
        logger.warning("create_project validation failed: %s", e)
        raise
    if p["final_grade"] or p["stage"] == "Complete":
        raise ValidationError(
            "A new project cannot be Complete or carry a final grade — the "
            "supervisor must authenticate the work first")
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO epq_projects
                       (student_id, working_title, research_question,
                        artefact_type, supervisor, stage, final_mark,
                        final_grade, notes, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?,
                           datetime('now'), datetime('now'))""",
                (p["student_id"], p["working_title"],
                 p["research_question"], p["artefact_type"],
                 p["supervisor"], p["stage"], p["final_mark"],
                 p["final_grade"], p["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e).upper():
            raise ValidationError(
                f"Student {p['student_id']} already has an EPQ project") from None
        logger.exception("create_project DB error")
        raise
    out = get_project(new_id)
    assert out is not None
    logger.info(
        "Created EPQ project #%d for %s (%s, stage=%s)",
        new_id, p["student_id"], p["artefact_type"], p["stage"],
    )
    return out


def get_project(project_id: int) -> EPQProject | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM epq_projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        return _row_project(r) if r else None


def get_project_for_student(student_id: str) -> EPQProject | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM epq_projects WHERE student_id = ?",
            (student_id.strip(),),
        ).fetchone()
        return _row_project(r) if r else None


def list_projects(
    *,
    stage: str | None = None,
    artefact_type: str | None = None,
    supervisor_like: str | None = None,
) -> list[EPQProject]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if stage:
        if stage not in STAGES:
            raise ValidationError(
                f"Stage must be one of: {', '.join(STAGES)}")
        clauses.append("stage = ?")
        args.append(stage)
    if artefact_type:
        if artefact_type not in ARTEFACT_TYPES:
            raise ValidationError(
                f"Artefact type must be one of: {', '.join(ARTEFACT_TYPES)}")
        clauses.append("artefact_type = ?")
        args.append(artefact_type)
    if supervisor_like:
        clauses.append("supervisor LIKE ?")
        args.append(f"%{supervisor_like.strip()}%")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM epq_projects {where} "
           "ORDER BY working_title")
    with _connect() as conn:
        return [_row_project(r) for r in conn.execute(sql, args).fetchall()]


def list_projects_with_detail(**kwargs) -> list[ProjectRow]:
    rows = list_projects(**kwargs)
    if not rows:
        return []
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    names = {s.student_id: s.full_name for s in _students.list_students()}

    out: list[ProjectRow] = []
    with _connect() as conn:
        for proj in rows:
            r = conn.execute(
                """SELECT COUNT(*) AS n, COALESCE(SUM(hours), 0) AS h
                   FROM epq_logentries WHERE project_id = ?""",
                (proj.project_id,),
            ).fetchone()
            ms = conn.execute(
                """SELECT
                       SUM(CASE WHEN status='Completed' THEN 1 ELSE 0 END) AS done,
                       COUNT(*) AS total
                   FROM epq_milestones WHERE project_id = ?""",
                (proj.project_id,),
            ).fetchone()
            out.append(ProjectRow(
                project=proj,
                student_name=names.get(proj.student_id, "(unknown)"),
                total_hours=float(r["h"] or 0.0),
                log_count=int(r["n"] or 0),
                milestones_completed=int(ms["done"] or 0),
                milestones_total=int(ms["total"] or 0),
            ))
    return out


def update_project(project_id: int, data: dict[str, Any]) -> EPQProject:
    init_db()
    existing = get_project(project_id)
    if existing is None:
        logger.warning("update_project: unknown id %d", project_id)
        raise ValidationError(f"No project with id {project_id}")
    p = _validate_project_payload({
        "student_id":        existing.student_id,
        "working_title":     data.get("working_title", existing.working_title),
        "research_question": data.get("research_question",
                                       existing.research_question),
        "artefact_type":     data.get("artefact_type",
                                       existing.artefact_type),
        "supervisor":        data.get("supervisor", existing.supervisor),
        "stage":             data.get("stage", existing.stage),
        "final_mark":        data.get("final_mark", existing.final_mark),
        "final_grade":       data.get("final_grade", existing.final_grade),
        "notes":             data.get("notes", existing.notes),
    })
    # JCQ: no final mark/grade, and no "Complete", until the supervisor
    # has authenticated the work. Only a *change* is held to this, so
    # projects graded before authentication was recorded stay editable.
    grading = (p["final_grade"] and p["final_grade"] != existing.final_grade) \
        or (p["final_mark"] is not None and p["final_mark"] != existing.final_mark) \
        or (p["stage"] == "Complete" and existing.stage != "Complete")
    if grading and not existing.is_authenticated:
        raise ValidationError(
            "The supervisor must authenticate this project (teacher "
            "authentication) before it is marked, graded or completed")
    with _connect() as conn:
        conn.execute(
            """UPDATE epq_projects SET
                   working_title = ?, research_question = ?,
                   artefact_type = ?, supervisor = ?, stage = ?,
                   final_mark = ?, final_grade = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE project_id = ?""",
            (p["working_title"], p["research_question"],
             p["artefact_type"], p["supervisor"], p["stage"],
             p["final_mark"], p["final_grade"], p["notes"], project_id),
        )
        conn.commit()
    out = get_project(project_id)
    assert out is not None
    logger.info("Updated EPQ project #%d (stage=%s, grade=%s)",
                project_id, out.stage, out.final_grade or "—")
    return out


def delete_project(project_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM epq_projects WHERE project_id = ?",
            (project_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted EPQ project #%d (cascades log + milestones)",
                        project_id)
            return True
        logger.warning("delete_project: unknown id %d", project_id)
        return False


# ── Production-log CRUD ───────────────────────────────────────────

def create_log_entry(data: dict[str, Any]) -> EPQLogEntry:
    init_db()
    p = _validate_log_payload(data)
    if get_project(p["project_id"]) is None:
        raise ValidationError(f"No project with id {p['project_id']}")
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO epq_logentries
                   (project_id, entry_date, hours, activity, reflection,
                    created_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))""",
            (p["project_id"], p["entry_date"], p["hours"],
             p["activity"], p["reflection"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_log_entry(new_id)
    assert out is not None
    logger.info(
        "Added EPQ log #%d to project #%d (%s, %.1fh)",
        new_id, p["project_id"], p["entry_date"], p["hours"],
    )
    return out


#: Stages in which the learner may still add to their own production log.
LEARNER_LOG_CLOSED_STAGES: tuple[str, ...] = ("Complete", "Withdrawn")


def add_own_log_entry(student_id: str, *, entry_date: str, hours: Any,
                      activity: str, reflection: str | None = None) -> EPQLogEntry:
    """The learner adds an entry to their *own* production log.

    The project is found from ``student_id`` — a learner never names a
    project id. The log closes once the project is Complete or
    Withdrawn, or once the supervisor has authenticated the work, and an
    entry may not be dated in the future.
    """
    proj = get_project_for_student(student_id or "")
    if proj is None:
        raise ValidationError("You do not have an EPQ project on record.")
    if proj.stage in LEARNER_LOG_CLOSED_STAGES:
        raise ValidationError(
            f"Your project is {proj.stage}; the production log is closed.")
    if proj.is_authenticated:
        raise ValidationError(
            "Your supervisor has authenticated your work, so the production "
            "log is closed. Ask them if something needs adding.")
    when = _validate_date(entry_date, "Entry date")
    if when and when > _dt.date.today().isoformat():
        raise ValidationError("A log entry cannot be dated in the future.")
    return create_log_entry({"project_id": proj.project_id, "entry_date": when,
                             "hours": hours, "activity": activity,
                             "reflection": reflection})


def get_log_entry(log_id: int) -> EPQLogEntry | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM epq_logentries WHERE log_id = ?",
            (log_id,),
        ).fetchone()
        return _row_log(r) if r else None


def list_log_entries(project_id: int) -> list[EPQLogEntry]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM epq_logentries WHERE project_id = ?
               ORDER BY entry_date DESC, log_id DESC""",
            (project_id,),
        ).fetchall()
        return [_row_log(r) for r in rows]


def delete_log_entry(log_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM epq_logentries WHERE log_id = ?", (log_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted EPQ log entry #%d", log_id)
            return True
        return False


def hours_check(project_id: int, *, target: float | None = None) -> HoursCheck:
    """Logged production-log hours against the 120-hour EPQ target."""
    tgt = float(target if target is not None else EPQ_TARGET_HOURS)
    logged = round(total_hours_for_project(project_id), 2)
    return HoursCheck(project_id=project_id, logged_hours=logged,
                      target_hours=tgt, remaining=round(max(0.0, tgt - logged), 2),
                      met=logged >= tgt)


def projects_below_target(*, target: float | None = None) -> list[tuple[EPQProject, HoursCheck]]:
    """Live (not Withdrawn) projects whose logged hours are under target."""
    out = []
    for proj in list_projects():
        if proj.stage == "Withdrawn":
            continue
        chk = hours_check(proj.project_id, target=target)
        if not chk.met:
            out.append((proj, chk))
    return out


def authenticate_project(project_id: int, *, teacher: str,
                         candidate_declared: bool,
                         notes: str | None = None,
                         hours_shortfall_reason: str | None = None) -> EPQProject:
    """Record the supervisor's authentication of the candidate's work.

    The candidate must have signed their declaration. If the production
    log is short of the 120-hour target the teacher must say why
    (``hours_shortfall_reason``) — that reason is kept with the notes.
    """
    init_db()
    proj = get_project(project_id)
    if proj is None:
        raise ValidationError(f"No project with id {project_id}")
    teacher = (teacher or "").strip()
    if not teacher:
        raise ValidationError("Authenticating teacher is required")
    if not candidate_declared:
        raise ValidationError(
            "The candidate must sign their declaration before the teacher "
            "can authenticate the work")
    chk = hours_check(project_id)
    note = (notes or "").strip()
    if not chk.met:
        reason = (hours_shortfall_reason or "").strip()
        if not reason:
            raise ValidationError(
                f"Production log shows {chk.logged_hours:g} of "
                f"{chk.target_hours:g} hours — give a reason to authenticate anyway")
        note = (note + "\n" if note else "") + f"Hours shortfall: {reason}"
    with _connect() as conn:
        conn.execute(
            """UPDATE epq_projects SET
                   candidate_declared_at = COALESCE(candidate_declared_at, datetime('now')),
                   authenticated_by = ?, authenticated_at = datetime('now'),
                   authentication_notes = ?, updated_at = datetime('now')
               WHERE project_id = ?""",
            (teacher, note or None, project_id))
        conn.commit()
    logger.info("EPQ project #%d authenticated by %s (%s)", project_id,
                teacher, chk.label)
    out = get_project(project_id)
    assert out is not None
    return out


def revoke_authentication(project_id: int) -> EPQProject:
    """Undo an authentication recorded in error (the grade stays)."""
    init_db()
    with _connect() as conn:
        conn.execute(
            """UPDATE epq_projects SET candidate_declared_at = NULL,
                   authenticated_by = NULL, authenticated_at = NULL,
                   updated_at = datetime('now') WHERE project_id = ?""",
            (project_id,))
        conn.commit()
    out = get_project(project_id)
    if out is None:
        raise ValidationError(f"No project with id {project_id}")
    logger.info("EPQ project #%d authentication revoked", project_id)
    return out


def total_hours_for_project(project_id: int) -> float:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT COALESCE(SUM(hours), 0) AS h "
            "FROM epq_logentries WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        return float(r["h"] or 0.0)


# ── Milestone CRUD (upsert per (project, type)) ───────────────────

def save_milestone(data: dict[str, Any]) -> EPQMilestone:
    init_db()
    p = _validate_milestone_payload(data)
    if get_project(p["project_id"]) is None:
        raise ValidationError(f"No project with id {p['project_id']}")
    with _connect() as conn:
        conn.execute(
            """INSERT INTO epq_milestones
                   (project_id, milestone_type, due_date,
                    completed_date, status, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))
               ON CONFLICT(project_id, milestone_type) DO UPDATE SET
                   due_date       = excluded.due_date,
                   completed_date = excluded.completed_date,
                   status         = excluded.status,
                   notes          = excluded.notes,
                   updated_at     = datetime('now')""",
            (p["project_id"], p["milestone_type"], p["due_date"],
             p["completed_date"], p["status"], p["notes"]),
        )
        conn.commit()
        r = conn.execute(
            """SELECT * FROM epq_milestones
               WHERE project_id = ? AND milestone_type = ?""",
            (p["project_id"], p["milestone_type"]),
        ).fetchone()
    assert r is not None
    out = _row_milestone(r)
    logger.info(
        "Saved EPQ milestone %s for project #%d (status=%s)",
        out.milestone_type, out.project_id, out.status,
    )
    return out


def list_milestones(project_id: int) -> list[EPQMilestone]:
    init_db()
    order_case = " ".join(
        f"WHEN '{m}' THEN {i}" for i, m in enumerate(MILESTONE_TYPES))
    sql = (
        "SELECT * FROM epq_milestones WHERE project_id = ? "
        f"ORDER BY CASE milestone_type {order_case} END"
    )
    with _connect() as conn:
        return [_row_milestone(r)
                for r in conn.execute(sql, (project_id,)).fetchall()]


def delete_milestone(milestone_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM epq_milestones WHERE milestone_id = ?",
            (milestone_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted EPQ milestone #%d", milestone_id)
            return True
        return False


# ── Summary ───────────────────────────────────────────────────────

@dataclass
class EPQSummary:
    total_projects: int
    by_stage: dict[str, int]
    by_artefact: dict[str, int]
    by_grade: dict[str, int]
    total_log_hours: float
    overdue_milestones: int
    upcoming_milestones: int      # due within N days


def summary(*, upcoming_window_days: int = 21) -> EPQSummary:
    init_db()
    today = _dt.date.today()
    today_iso = today.isoformat()
    upcoming_cutoff = (today + _dt.timedelta(days=upcoming_window_days)
                       ).isoformat()

    projects = list_projects()
    by_stage = {s: 0 for s in STAGES}
    by_artefact = {a: 0 for a in ARTEFACT_TYPES}
    by_grade = {g: 0 for g in GRADES}
    for p in projects:
        by_stage[p.stage] = by_stage.get(p.stage, 0) + 1
        by_artefact[p.artefact_type] = by_artefact.get(p.artefact_type, 0) + 1
        if p.final_grade:
            by_grade[p.final_grade] = by_grade.get(p.final_grade, 0) + 1

    with _connect() as conn:
        total_hours = float(conn.execute(
            "SELECT COALESCE(SUM(hours), 0) AS h FROM epq_logentries"
        ).fetchone()["h"] or 0.0)

        overdue = int(conn.execute(
            """SELECT COUNT(*) AS n FROM epq_milestones
               WHERE status != 'Completed'
                 AND due_date IS NOT NULL
                 AND due_date < ?""",
            (today_iso,),
        ).fetchone()["n"])

        upcoming = int(conn.execute(
            """SELECT COUNT(*) AS n FROM epq_milestones
               WHERE status != 'Completed'
                 AND due_date IS NOT NULL
                 AND due_date >= ? AND due_date <= ?""",
            (today_iso, upcoming_cutoff),
        ).fetchone()["n"])

    return EPQSummary(
        total_projects=len(projects),
        by_stage=by_stage, by_artefact=by_artefact, by_grade=by_grade,
        total_log_hours=total_hours,
        overdue_milestones=overdue,
        upcoming_milestones=upcoming,
    )
