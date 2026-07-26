"""Assignments — coursework-style assignments with per-student submissions.

Distinct from the daily ``homework`` module: an assignment is a
substantial piece of work (essay, project, practical, controlled
assessment, coursework component) with its own brief, rubric, grade
weight, and a row per student tracking submission + marks + feedback.

Schema is two related tables:

* ``assignments``               — one row per assignment.
* ``assignment_submissions``    — one row per (assignment, student),
                                    created when a student is added to
                                    the cohort and ticked off as they
                                    submit.

Cascade: deleting an assignment removes all its submissions; deleting
a student removes their submission rows.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any
from education_system.systems.sixth_form.infrastructure import paths
from education_system.systems.sixth_form.domain.academics.assignments import (
    assignments as data,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.ASSIGNMENTS_DB


ASSIGNMENT_TYPES: tuple[str, ...] = (
    "Essay",
    "Project",
    "Practical",
    "Presentation",
    "Coursework",
    "NEA",
    "Controlled Assessment",
    "Lab Report",
    "Portfolio",
    "Group Task",
    "Other",
)
DEFAULT_ASSIGNMENT_TYPE: str = "Essay"

ASSIGNMENT_STATUSES: tuple[str, ...] = (
    "Draft", "Set", "Closed", "Graded", "Archived",
)
DEFAULT_ASSIGNMENT_STATUS: str = "Draft"

SUBMISSION_STATUSES: tuple[str, ...] = (
    "Not Started", "In Progress", "Submitted",
    "Late", "Excused", "Missing", "Returned",
)
DEFAULT_SUBMISSION_STATUS: str = "Not Started"
DONE_SUBMISSION_STATUSES: tuple[str, ...] = (
    "Submitted", "Late", "Excused", "Returned",
)

YEAR_GROUPS: tuple[str, ...] = ("Year 12", "Year 13", "Mixed")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS coursework_assignments (
    assignment_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    title             TEXT NOT NULL,
    subject_name      TEXT NOT NULL,
    course_id         INTEGER,
    class_group_id    INTEGER,
    year_group        TEXT,
    assignment_type   TEXT NOT NULL DEFAULT 'Essay',
    teacher           TEXT,
    set_date          TEXT,
    due_date          TEXT,
    max_marks         REAL,
    weight_percent    REAL,
    brief             TEXT,
    rubric            TEXT,
    resources         TEXT,
    submission_method TEXT,
    status            TEXT NOT NULL DEFAULT 'Draft',
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS coursework_submissions (
    submission_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id     INTEGER NOT NULL,
    student_id        TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'Not Started',
    submitted_on      TEXT,
    marks             REAL,
    grade             TEXT,
    feedback          TEXT,
    marked_by         TEXT,
    marked_on         TEXT,
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (assignment_id) REFERENCES coursework_assignments(assignment_id)
        ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE,
    UNIQUE (assignment_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_cw_subject   ON coursework_assignments(subject_name);
CREATE INDEX IF NOT EXISTS idx_cw_status    ON coursework_assignments(status);
CREATE INDEX IF NOT EXISTS idx_cw_due       ON coursework_assignments(due_date);
CREATE INDEX IF NOT EXISTS idx_cw_teacher   ON coursework_assignments(teacher);
CREATE INDEX IF NOT EXISTS idx_cwsub_assign  ON coursework_submissions(assignment_id);
CREATE INDEX IF NOT EXISTS idx_cwsub_student ON coursework_submissions(student_id);
CREATE INDEX IF NOT EXISTS idx_cwsub_status  ON coursework_submissions(status);
"""


@dataclass
class Assignment:
    assignment_id: int
    title: str
    subject_name: str
    course_id: int | None
    class_group_id: int | None
    year_group: str | None
    assignment_type: str
    teacher: str | None
    set_date: str | None
    due_date: str | None
    max_marks: float | None
    weight_percent: float | None
    brief: str | None
    rubric: str | None
    resources: str | None
    submission_method: str | None
    status: str
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def is_open(self) -> bool:
        return self.status in ("Draft", "Set")

    @property
    def is_overdue(self) -> bool:
        if not self.due_date or self.status not in ("Set", "Draft"):
            return False
        return self.due_date < _dt.date.today().isoformat()


@dataclass
class Submission:
    submission_id: int
    assignment_id: int
    student_id: str
    status: str
    submitted_on: str | None
    marks: float | None
    grade: str | None
    feedback: str | None
    marked_by: str | None
    marked_on: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def is_done(self) -> bool:
        return self.status in DONE_SUBMISSION_STATUSES

    @property
    def percent(self) -> float | None:
        return None    # overlay with assignment.max_marks at the row layer


@dataclass
class AssignmentDetail:
    assignment: Assignment
    submissions: list[Submission] = field(default_factory=list)

    @property
    def total_submissions(self) -> int:
        return len(self.submissions)

    @property
    def submitted_count(self) -> int:
        return sum(1 for s in self.submissions if s.is_done)

    @property
    def marked_count(self) -> int:
        return sum(1 for s in self.submissions if s.marks is not None)

    @property
    def average_mark(self) -> float | None:
        marks = [s.marks for s in self.submissions
                  if s.marks is not None]
        if not marks:
            return None
        return round(sum(marks) / len(marks), 2)

    @property
    def percent_submitted(self) -> float:
        if not self.submissions:
            return 0.0
        return round(100.0 * self.submitted_count
                      / len(self.submissions), 1)


@dataclass
class AssignmentRow:
    assignment: Assignment
    total_submissions: int = 0
    submitted_count: int = 0
    marked_count: int = 0
    average_mark: float | None = None


@dataclass
class SubmissionRow:
    submission: Submission
    student_name: str


@dataclass
class Summary:
    total_assignments: int
    by_status: dict[str, int]
    by_type: dict[str, int]
    by_subject: dict[str, int]
    open_count: int
    overdue: int
    upcoming_due: int
    total_submissions: int
    submitted_total: int
    marked_total: int


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
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Assignments schema ready at %s", DB_PATH)

    _DB_READY = True


def _row_assignment(r: sqlite3.Row) -> Assignment:
    return Assignment(
        assignment_id=r["assignment_id"], title=r["title"],
        subject_name=r["subject_name"],
        course_id=r["course_id"],
        class_group_id=r["class_group_id"],
        year_group=r["year_group"],
        assignment_type=r["assignment_type"],
        teacher=r["teacher"], set_date=r["set_date"],
        due_date=r["due_date"], max_marks=r["max_marks"],
        weight_percent=r["weight_percent"],
        brief=r["brief"], rubric=r["rubric"],
        resources=r["resources"],
        submission_method=r["submission_method"],
        status=r["status"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_submission(r: sqlite3.Row) -> Submission:
    return Submission(
        submission_id=r["submission_id"],
        assignment_id=r["assignment_id"],
        student_id=r["student_id"], status=r["status"],
        submitted_on=r["submitted_on"], marks=r["marks"],
        grade=r["grade"], feedback=r["feedback"],
        marked_by=r["marked_by"], marked_on=r["marked_on"],
        notes=r["notes"],
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


def _validate_number(value: Any, label: str, *,
                      min_val: float | None = None,
                      max_val: float | None = None) -> float | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a number") from None
    if min_val is not None and f < min_val:
        raise ValidationError(f"{label} must be at least {min_val}")
    if max_val is not None and f > max_val:
        raise ValidationError(f"{label} must be at most {max_val}")
    return f


def _validate_subject(value: Any) -> str:
    name = _require(value, "Subject").strip()
    try:
        from education_system.systems.sixth_form.domain.academics.subjects import (
            subjects as _subjects,
        )
        names = {x.name for x in _subjects.list_subjects()}
        if names and name not in names:
            raise ValidationError(
                f"Subject {name!r} not in catalogue")
    except ValidationError:
        raise
    except Exception:
        pass
    return name


def _validate_assignment_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["title"] = _require(payload.get("title"), "Title").strip()
    out["subject_name"] = _validate_subject(payload.get("subject_name"))

    atype = (payload.get("assignment_type")
              or DEFAULT_ASSIGNMENT_TYPE).strip()
    if atype not in ASSIGNMENT_TYPES:
        raise ValidationError(
            f"Type must be one of: {', '.join(ASSIGNMENT_TYPES)}")
    out["assignment_type"] = atype

    status = (payload.get("status")
                or DEFAULT_ASSIGNMENT_STATUS).strip()
    if status not in ASSIGNMENT_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(ASSIGNMENT_STATUSES)}")
    out["status"] = status

    year = (payload.get("year_group") or "").strip()
    if year and year not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of: {', '.join(YEAR_GROUPS)}")
    out["year_group"] = year or None

    out["teacher"] = (payload.get("teacher") or "").strip() or None
    out["set_date"] = _validate_date(payload.get("set_date"),
                                          "Set date")
    out["due_date"] = _validate_date(payload.get("due_date"),
                                          "Due date")
    if (out["set_date"] and out["due_date"]
            and out["due_date"] < out["set_date"]):
        raise ValidationError(
            "Due date cannot be before set date")

    out["max_marks"] = _validate_number(payload.get("max_marks"),
                                            "Max marks", min_val=0)
    out["weight_percent"] = _validate_number(
        payload.get("weight_percent"), "Weight %",
        min_val=0, max_val=100)

    out["course_id"] = None
    if payload.get("course_id") not in (None, ""):
        try:
            out["course_id"] = int(payload.get("course_id"))
        except (TypeError, ValueError):
            raise ValidationError(
                "course_id must be a number") from None
    out["class_group_id"] = None
    if payload.get("class_group_id") not in (None, ""):
        try:
            out["class_group_id"] = int(payload.get("class_group_id"))
        except (TypeError, ValueError):
            raise ValidationError(
                "class_group_id must be a number") from None

    out["brief"]             = (payload.get("brief")
                                  or "").strip() or None
    out["rubric"]            = (payload.get("rubric")
                                  or "").strip() or None
    out["resources"]         = (payload.get("resources")
                                  or "").strip() or None
    out["submission_method"] = (payload.get("submission_method")
                                  or "").strip() or None
    out["notes"]             = (payload.get("notes")
                                  or "").strip() or None
    return out


def _validate_submission_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    aid = payload.get("assignment_id")
    if aid in (None, ""):
        raise ValidationError("Assignment id is required")
    try:
        out["assignment_id"] = int(aid)
    except (TypeError, ValueError):
        raise ValidationError(
            "Assignment id must be a number") from None
    if get_assignment(out["assignment_id"]) is None:
        raise ValidationError(
            f"No assignment #{out['assignment_id']}")

    sid = _require(payload.get("student_id"), "Student").strip()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    out["student_id"] = sid

    status = (payload.get("status") or DEFAULT_SUBMISSION_STATUS).strip()
    if status not in SUBMISSION_STATUSES:
        raise ValidationError(
            f"Submission status must be one of: "
            f"{', '.join(SUBMISSION_STATUSES)}")
    out["status"] = status

    out["submitted_on"] = _validate_date(
        payload.get("submitted_on"), "Submitted on")
    out["marks"] = _validate_number(payload.get("marks"),
                                        "Marks", min_val=0)

    assignment = get_assignment(out["assignment_id"])
    if (assignment and assignment.max_marks is not None
            and out["marks"] is not None
            and out["marks"] > assignment.max_marks):
        raise ValidationError(
            f"Marks ({out['marks']}) exceed max_marks "
            f"({assignment.max_marks})")

    out["grade"]      = (payload.get("grade") or "").strip() or None
    out["feedback"]   = (payload.get("feedback") or "").strip() or None
    out["marked_by"]  = (payload.get("marked_by") or "").strip() or None
    out["marked_on"]  = _validate_date(payload.get("marked_on"),
                                            "Marked on")
    out["notes"]      = (payload.get("notes") or "").strip() or None

    if (out["status"] in DONE_SUBMISSION_STATUSES
            and not out["submitted_on"]
            and out["status"] in ("Submitted", "Late", "Returned")):
        out["submitted_on"] = _dt.date.today().isoformat()
    if out["marks"] is not None and not out["marked_on"]:
        out["marked_on"] = _dt.date.today().isoformat()
    return out


# ── Assignment CRUD ───────────────────────────────────────────────

def create_assignment(payload: dict[str, Any]) -> Assignment:
    init_db()
    p = _validate_assignment_payload(payload)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO coursework_assignments
                   (title, subject_name, course_id, class_group_id,
                    year_group, assignment_type, teacher,
                    set_date, due_date, max_marks, weight_percent,
                    brief, rubric, resources, submission_method,
                    status, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, datetime('now'), datetime('now'))""",
            (p["title"], p["subject_name"], p["course_id"],
             p["class_group_id"], p["year_group"],
             p["assignment_type"], p["teacher"],
             p["set_date"], p["due_date"], p["max_marks"],
             p["weight_percent"], p["brief"], p["rubric"],
             p["resources"], p["submission_method"],
             p["status"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_assignment(new_id)
    assert out is not None
    logger.info(
        "Created assignment #%d %r (%s, due %s, status %s)",
        new_id, p["title"], p["subject_name"], p["due_date"],
        p["status"])
    _notify_students_assignment_created(out)
    return out


def _students_on_course(course_id: int) -> list[str]:
    """Return distinct student_ids enrolled in any class group of a course."""
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    seen: set[str] = set()
    ordered: list[str] = []
    for g in _cg.list_groups(course_id=course_id):
        for sid in _cg.list_members(g.group_id):
            if sid not in seen:
                seen.add(sid)
                ordered.append(sid)
    return ordered


def _notify_students_assignment_created(a: Assignment) -> None:
    """Email every student on the assignment's course. Best-effort."""
    if a.course_id is None:
        return
    try:
        from education_system.systems.sixth_form import SYSTEM_NAME
        from education_system.systems.sixth_form.domain.academics.courses import (
            courses as _courses,
        )
        from education_system.systems.sixth_form.domain.operations.communications.messages import (
            email_templates,
        )
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        course = _courses.get_course(a.course_id)
        student_ids = _students_on_course(a.course_id)
        if not student_ids:
            logger.info(
                "Assignment #%d: no students on course #%d to notify",
                a.assignment_id, a.course_id)
            return
        sent = 0
        for sid in student_ids:
            student = _students.get_student(sid)
            if student is None:
                continue
            try:
                email_templates.send_from_template(
                    "assignment_set",
                    {
                        "system_name":       SYSTEM_NAME,
                        "first_name":        student.first_name,
                        "full_name":         student.full_name,
                        "student_id":        student.student_id,
                        "title":             a.title,
                        "subject_name":      a.subject_name,
                        "assignment_type":   a.assignment_type,
                        "teacher":           a.teacher or "your teacher",
                        "set_date":          a.set_date or "—",
                        "due_date":          a.due_date or "—",
                        "max_marks":         (str(a.max_marks)
                                                if a.max_marks is not None
                                                else "—"),
                        "submission_method": (a.submission_method
                                                or "see the portal"),
                        "brief":             (a.brief
                                                or "(See the portal for full details.)"),
                        "course_code":       (course.course_code
                                                if course else "—"),
                        "course_title":      (course.title
                                                if course else "—"),
                    },
                    to_name=student.full_name,
                    to_address=student.email,
                    student_id=student.student_id,
                )
                sent += 1
            except Exception:
                logger.exception(
                    "assignment_set email failed for student %s "
                    "(assignment #%d)",
                    sid, a.assignment_id)
        logger.info(
            "Assignment #%d: notified %d/%d student(s) on course #%d",
            a.assignment_id, sent, len(student_ids), a.course_id)
    except Exception:
        logger.exception(
            "Could not notify students for assignment #%d",
            a.assignment_id)


def get_assignment(assignment_id: int) -> Assignment | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM coursework_assignments WHERE assignment_id = ?",
            (assignment_id,)).fetchone()
        return _row_assignment(r) if r else None


def list_assignments(
    *,
    subject_name: str | None = None,
    teacher_like: str | None = None,
    status: str | None = None,
    assignment_type: str | None = None,
    year_group: str | None = None,
    course_id: int | None = None,
    class_group_id: int | None = None,
    open_only: bool = False,
    overdue_only: bool = False,
    title_like: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[Assignment]:
    init_db()
    clauses, args = [], []
    if subject_name:
        clauses.append("subject_name = ?")
        args.append(subject_name.strip())
    if teacher_like:
        clauses.append("teacher LIKE ?")
        args.append(f"%{teacher_like.strip()}%")
    if status:
        if status not in ASSIGNMENT_STATUSES:
            raise ValidationError(
                f"Status must be one of: "
                f"{', '.join(ASSIGNMENT_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if assignment_type:
        if assignment_type not in ASSIGNMENT_TYPES:
            raise ValidationError(
                f"Type must be one of: "
                f"{', '.join(ASSIGNMENT_TYPES)}")
        clauses.append("assignment_type = ?")
        args.append(assignment_type)
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year group must be one of: "
                f"{', '.join(YEAR_GROUPS)}")
        clauses.append("year_group = ?")
        args.append(year_group)
    if course_id is not None:
        clauses.append("course_id = ?")
        args.append(int(course_id))
    if class_group_id is not None:
        clauses.append("class_group_id = ?")
        args.append(int(class_group_id))
    if open_only:
        clauses.append("status IN ('Draft', 'Set')")
    if overdue_only:
        today = _dt.date.today().isoformat()
        clauses.append("due_date IS NOT NULL AND due_date < ? "
                       "AND status IN ('Draft', 'Set')")
        args.append(today)
    if title_like:
        clauses.append("title LIKE ?")
        args.append(f"%{title_like.strip()}%")
    if date_from:
        clauses.append("due_date >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("due_date <= ?")
        args.append(_validate_date(date_to, "date_to"))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM coursework_assignments {where} "
           "ORDER BY CASE WHEN due_date IS NULL THEN 1 ELSE 0 END, "
           "due_date ASC, assignment_id ASC")
    with _connect() as conn:
        return [_row_assignment(r)
                for r in conn.execute(sql, args).fetchall()]


def list_assignments_with_detail(**kwargs) -> list[AssignmentRow]:
    rows = list_assignments(**kwargs)
    if not rows:
        return []
    with _connect() as conn:
        out: list[AssignmentRow] = []
        for a in rows:
            stats = conn.execute(
                f"SELECT COUNT(*) total, "
                f"  SUM(CASE WHEN status IN "
                f"    ({','.join('?' * len(DONE_SUBMISSION_STATUSES))}) "
                f"    THEN 1 ELSE 0 END) AS done, "
                f"  SUM(CASE WHEN marks IS NOT NULL "
                f"    THEN 1 ELSE 0 END) AS marked, "
                f"  AVG(marks) AS avg_marks "
                f"FROM coursework_submissions "
                f"WHERE assignment_id = ?",
                (*DONE_SUBMISSION_STATUSES, a.assignment_id)).fetchone()
            out.append(AssignmentRow(
                assignment=a,
                total_submissions=stats["total"] or 0,
                submitted_count=stats["done"] or 0,
                marked_count=stats["marked"] or 0,
                average_mark=(round(stats["avg_marks"], 2)
                                if stats["avg_marks"] is not None
                                else None),
            ))
    return out


def get_assignment_detail(assignment_id: int) -> AssignmentDetail | None:
    init_db()
    a = get_assignment(assignment_id)
    if a is None:
        return None
    subs = list_submissions(assignment_id=assignment_id)
    return AssignmentDetail(assignment=a, submissions=subs)


def update_assignment(assignment_id: int,
                       payload: dict[str, Any]) -> Assignment:
    init_db()
    existing = get_assignment(assignment_id)
    if existing is None:
        raise ValidationError(f"No assignment #{assignment_id}")
    merged = {
        "title":             payload.get("title", existing.title),
        "subject_name":      payload.get("subject_name",
                                          existing.subject_name),
        "course_id":         payload.get("course_id",
                                          existing.course_id),
        "class_group_id":    payload.get("class_group_id",
                                          existing.class_group_id),
        "year_group":        payload.get("year_group",
                                          existing.year_group),
        "assignment_type":   payload.get("assignment_type",
                                          existing.assignment_type),
        "teacher":           payload.get("teacher", existing.teacher),
        "set_date":          payload.get("set_date",
                                          existing.set_date),
        "due_date":          payload.get("due_date",
                                          existing.due_date),
        "max_marks":         payload.get("max_marks",
                                          existing.max_marks),
        "weight_percent":    payload.get("weight_percent",
                                          existing.weight_percent),
        "brief":             payload.get("brief", existing.brief),
        "rubric":            payload.get("rubric", existing.rubric),
        "resources":         payload.get("resources",
                                          existing.resources),
        "submission_method": payload.get("submission_method",
                                          existing.submission_method),
        "status":            payload.get("status", existing.status),
        "notes":             payload.get("notes", existing.notes),
    }
    p = _validate_assignment_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE coursework_assignments SET
                   title = ?, subject_name = ?, course_id = ?,
                   class_group_id = ?, year_group = ?,
                   assignment_type = ?, teacher = ?, set_date = ?,
                   due_date = ?, max_marks = ?, weight_percent = ?,
                   brief = ?, rubric = ?, resources = ?,
                   submission_method = ?, status = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE assignment_id = ?""",
            (p["title"], p["subject_name"], p["course_id"],
             p["class_group_id"], p["year_group"],
             p["assignment_type"], p["teacher"],
             p["set_date"], p["due_date"], p["max_marks"],
             p["weight_percent"], p["brief"], p["rubric"],
             p["resources"], p["submission_method"],
             p["status"], p["notes"], assignment_id),
        )
        conn.commit()
    out = get_assignment(assignment_id)
    assert out is not None
    logger.info("Updated assignment #%d (status=%s)",
                assignment_id, out.status)
    return out


def set_assignment_status(assignment_id: int,
                          status: str) -> Assignment:
    if status not in ASSIGNMENT_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(ASSIGNMENT_STATUSES)}")
    return update_assignment(assignment_id, {"status": status})


def delete_assignment(assignment_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM coursework_assignments WHERE assignment_id = ?",
            (assignment_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted assignment #%d (cascade: submissions)",
                        assignment_id)
            return True
        return False


# ── Submission CRUD ───────────────────────────────────────────────

def add_student(assignment_id: int, student_id: str, *,
                 status: str = DEFAULT_SUBMISSION_STATUS) -> Submission:
    return create_submission({
        "assignment_id": assignment_id,
        "student_id": student_id,
        "status": status,
    })


def add_class_group(assignment_id: int, group_id: int) -> int:
    """Bulk-add every member of a class group as a submission row.
    Returns the number of new rows created."""
    init_db()
    if get_assignment(assignment_id) is None:
        raise ValidationError(f"No assignment #{assignment_id}")
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    if _cg.get_group(group_id) is None:
        raise ValidationError(f"No class group #{group_id}")
    members = _cg.list_members(group_id)
    n = 0
    for sid in members:
        try:
            add_student(assignment_id, sid)
            n += 1
        except ValidationError as e:
            if "already exists" in str(e).lower():
                continue
            # Likely UNIQUE constraint at the DB level
            logger.debug("Skipping %s: %s", sid, e)
    return n


def create_submission(payload: dict[str, Any]) -> Submission:
    init_db()
    p = _validate_submission_payload(payload)
    with _connect() as conn:
        if conn.execute(
                "SELECT 1 FROM coursework_submissions "
                "WHERE assignment_id = ? AND student_id = ?",
                (p["assignment_id"], p["student_id"])).fetchone():
            raise ValidationError(
                f"Student {p['student_id']} already has a "
                f"submission row for assignment "
                f"#{p['assignment_id']}")
        cur = conn.execute(
            """INSERT INTO coursework_submissions
                   (assignment_id, student_id, status, submitted_on,
                    marks, grade, feedback, marked_by, marked_on,
                    notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["assignment_id"], p["student_id"], p["status"],
             p["submitted_on"], p["marks"], p["grade"],
             p["feedback"], p["marked_by"], p["marked_on"],
             p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_submission(new_id)
    assert out is not None
    logger.info("Created submission #%d for student %s on assignment #%d",
                new_id, p["student_id"], p["assignment_id"])
    return out


def get_submission(submission_id: int) -> Submission | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM coursework_submissions "
            "WHERE submission_id = ?",
            (submission_id,)).fetchone()
        return _row_submission(r) if r else None


def list_submissions(
    *,
    assignment_id: int | None = None,
    student_id: str | None = None,
    status: str | None = None,
    done_only: bool = False,
    marked_only: bool = False,
    unmarked_only: bool = False,
) -> list[Submission]:
    init_db()
    clauses, args = [], []
    if assignment_id is not None:
        clauses.append("assignment_id = ?")
        args.append(int(assignment_id))
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if status:
        if status not in SUBMISSION_STATUSES:
            raise ValidationError(
                f"Status must be one of: "
                f"{', '.join(SUBMISSION_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if done_only:
        ph = ",".join("?" * len(DONE_SUBMISSION_STATUSES))
        clauses.append(f"status IN ({ph})")
        args.extend(DONE_SUBMISSION_STATUSES)
    if marked_only:
        clauses.append("marks IS NOT NULL")
    if unmarked_only:
        clauses.append("marks IS NULL")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM coursework_submissions {where} "
           "ORDER BY assignment_id ASC, student_id ASC")
    with _connect() as conn:
        return [_row_submission(r)
                for r in conn.execute(sql, args).fetchall()]


def list_submissions_with_detail(**kwargs) -> list[SubmissionRow]:
    rows = list_submissions(**kwargs)
    if not rows:
        return []
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    names = {s.student_id: s.full_name for s in _students.list_students()}
    return [SubmissionRow(submission=s,
                          student_name=names.get(s.student_id,
                                                   "(unknown)"))
            for s in rows]


def update_submission(submission_id: int,
                       payload: dict[str, Any]) -> Submission:
    init_db()
    existing = get_submission(submission_id)
    if existing is None:
        raise ValidationError(f"No submission #{submission_id}")
    merged = {
        "assignment_id": existing.assignment_id,
        "student_id":    existing.student_id,
        "status":        payload.get("status", existing.status),
        "submitted_on":  payload.get("submitted_on",
                                      existing.submitted_on),
        "marks":         payload.get("marks", existing.marks),
        "grade":         payload.get("grade", existing.grade),
        "feedback":      payload.get("feedback", existing.feedback),
        "marked_by":     payload.get("marked_by", existing.marked_by),
        "marked_on":     payload.get("marked_on", existing.marked_on),
        "notes":         payload.get("notes", existing.notes),
    }
    p = _validate_submission_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE coursework_submissions SET
                   status = ?, submitted_on = ?, marks = ?,
                   grade = ?, feedback = ?, marked_by = ?,
                   marked_on = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE submission_id = ?""",
            (p["status"], p["submitted_on"], p["marks"],
             p["grade"], p["feedback"], p["marked_by"],
             p["marked_on"], p["notes"], submission_id),
        )
        conn.commit()
    out = get_submission(submission_id)
    assert out is not None
    return out


def mark_submission(submission_id: int, *,
                     marks: float | None = None,
                     grade: str | None = None,
                     feedback: str | None = None,
                     marked_by: str | None = None) -> Submission:
    payload: dict[str, Any] = {
        "status": "Returned",
        "marks": marks,
        "grade": grade,
        "feedback": feedback,
        "marked_by": marked_by,
        "marked_on": _dt.date.today().isoformat(),
    }
    return update_submission(submission_id, payload)


def submit(submission_id: int, *,
            late: bool = False,
            submitted_on: str | None = None) -> Submission:
    return update_submission(submission_id, {
        "status": "Late" if late else "Submitted",
        "submitted_on": submitted_on or _dt.date.today().isoformat(),
    })


def set_submission_status(submission_id: int,
                          status: str) -> Submission:
    return update_submission(submission_id, {"status": status})


def delete_submission(submission_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM coursework_submissions "
            "WHERE submission_id = ?",
            (submission_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted submission #%d", submission_id)
            return True
        return False


# ── Summary ───────────────────────────────────────────────────────

def summary(*, upcoming_window_days: int = 14) -> Summary:
    init_db()
    today = _dt.date.today().isoformat()
    horizon = (_dt.date.today()
                + _dt.timedelta(days=upcoming_window_days)).isoformat()
    rows = list_assignments()
    by_status = {s: 0 for s in ASSIGNMENT_STATUSES}
    by_type = {t: 0 for t in ASSIGNMENT_TYPES}
    by_subject: dict[str, int] = {}
    open_count = 0
    overdue = 0
    upcoming = 0
    for a in rows:
        by_status[a.status] = by_status.get(a.status, 0) + 1
        by_type[a.assignment_type] = by_type.get(
            a.assignment_type, 0) + 1
        by_subject[a.subject_name] = by_subject.get(
            a.subject_name, 0) + 1
        if a.is_open:
            open_count += 1
            if a.is_overdue:
                overdue += 1
            elif a.due_date and today <= a.due_date <= horizon:
                upcoming += 1

    with _connect() as conn:
        tot = conn.execute(
            "SELECT COUNT(*) FROM coursework_submissions"
        ).fetchone()[0]
        done = conn.execute(
            f"SELECT COUNT(*) FROM coursework_submissions "
            f"WHERE status IN "
            f"({','.join('?' * len(DONE_SUBMISSION_STATUSES))})",
            DONE_SUBMISSION_STATUSES).fetchone()[0]
        marked = conn.execute(
            "SELECT COUNT(*) FROM coursework_submissions "
            "WHERE marks IS NOT NULL").fetchone()[0]

    return Summary(
        total_assignments=len(rows),
        by_status=by_status,
        by_type=by_type,
        by_subject=dict(sorted(by_subject.items(),
                                key=lambda kv: kv[1],
                                reverse=True)),
        open_count=open_count,
        overdue=overdue,
        upcoming_due=upcoming,
        total_submissions=tot,
        submitted_total=done,
        marked_total=marked,
    )
