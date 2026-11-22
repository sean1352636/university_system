"""Report cards for the Sixth Form System.

Until now "publishing a report card" meant a bare ``(student, period)``
flag in ``report_card_publications`` (written by
:func:`bulk_operations.bulk_publish_report_cards`) with no report behind
it and nothing that read it. This module supplies the report:

* **Report periods** — "2025/26 Autumn" etc. The period *label* is the
  same string ``report_card_publications.period`` holds, so the existing
  bulk publish keeps working and is what this module publishes through.
* **Templates** — which sections a report carries: attendance %, a line
  per learning aim (current / target / predicted grade), effort and
  attitude on configurable scales, a teacher comment per subject, the
  tutor's comment and the head of sixth form's comment.
* **Cards** — one per learner per period, generated from their active
  learning aims, class groups, targets and predictions.
* **Comment entry** — each teacher fills in the lines for the classes
  they teach; tutors write the tutor comment; the head of sixth form
  writes theirs.
* **Completion tracking**, **review / approve**, **publish** (via the
  bulk operation, which gates on approval) and **render** to text, HTML
  and — when ``reportlab`` is installed — PDF under the sixth form data
  directory.
* **Portal reads** — :func:`published_cards_for_student` and
  :func:`published_card` are the only functions the student and parent
  portals call. A card is visible there only while it is Published *and*
  its ``report_card_publications`` row exists, so undoing the bulk job
  hides it again.

All tables live in the shared ``sixthform.db``.
"""

from __future__ import annotations

import datetime as _dt
import html
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from education_system import paths
from education_system.systems.sixth_form.infrastructure import database as db

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_STUDENTS_DB

#: Rendered report files, one folder per period.
OUTPUT_DIR: Path = paths.SIXTH_FORM_DATA_DIR / "report_cards"

PERIOD_OPEN = "Open"
PERIOD_CLOSED = "Closed"
PERIOD_PUBLISHED = "Published"
PERIOD_STATUSES: tuple[str, ...] = (PERIOD_OPEN, PERIOD_CLOSED, PERIOD_PUBLISHED)

CARD_DRAFT = "Draft"
CARD_REVIEW = "In Review"
CARD_APPROVED = "Approved"
CARD_PUBLISHED = "Published"
CARD_STATUSES: tuple[str, ...] = (CARD_DRAFT, CARD_REVIEW, CARD_APPROVED,
                                  CARD_PUBLISHED)
#: Once approved, nobody edits the content — reopen it first.
LOCKED_STATUSES: tuple[str, ...] = (CARD_APPROVED, CARD_PUBLISHED)

DEFAULT_EFFORT_SCALE: tuple[str, ...] = (
    "1 - Excellent", "2 - Good", "3 - Inconsistent", "4 - Cause for concern")
DEFAULT_ATTITUDE_SCALE: tuple[str, ...] = (
    "Outstanding", "Good", "Requires improvement", "Cause for concern")
DEFAULT_TEMPLATE_NAME = "Standard sixth form report"
DEFAULT_COMMENT_MAX = 1200

#: Job roles that review, approve and publish reports and write the
#: head of sixth form comment.
APPROVER_JOB_ROLES: frozenset[str] = frozenset({
    "Head of Sixth Form", "Principal", "Vice Principal"})

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS report_templates (
    template_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name                     TEXT NOT NULL UNIQUE,
    intro_text               TEXT,
    include_attendance       INTEGER NOT NULL DEFAULT 1,
    include_current_grade    INTEGER NOT NULL DEFAULT 1,
    include_target_grade     INTEGER NOT NULL DEFAULT 1,
    include_predicted_grade  INTEGER NOT NULL DEFAULT 1,
    include_effort           INTEGER NOT NULL DEFAULT 1,
    include_attitude         INTEGER NOT NULL DEFAULT 1,
    include_subject_comments INTEGER NOT NULL DEFAULT 1,
    include_tutor_comment    INTEGER NOT NULL DEFAULT 1,
    include_hosf_comment     INTEGER NOT NULL DEFAULT 1,
    effort_scale             TEXT NOT NULL,
    attitude_scale           TEXT NOT NULL,
    comment_max_chars        INTEGER NOT NULL DEFAULT 1200,
    created_at               TEXT DEFAULT (datetime('now')),
    updated_at               TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS report_periods (
    period_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    label          TEXT NOT NULL UNIQUE,
    academic_year  TEXT,
    start_date     TEXT NOT NULL,
    end_date       TEXT NOT NULL,
    comments_due   TEXT,
    template_id    INTEGER NOT NULL,
    status         TEXT NOT NULL DEFAULT 'Open',
    created_by     TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (template_id) REFERENCES report_templates(template_id)
);

CREATE TABLE IF NOT EXISTS report_cards (
    card_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    period_id       INTEGER NOT NULL,
    student_id      TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'Draft',
    attendance_pct  REAL,
    tutor_comment   TEXT,
    tutor_by        TEXT,
    tutor_at        TEXT,
    hosf_comment    TEXT,
    hosf_by         TEXT,
    hosf_at         TEXT,
    submitted_by    TEXT,
    submitted_at    TEXT,
    review_note     TEXT,
    approved_by     TEXT,
    approved_at     TEXT,
    published_by    TEXT,
    published_at    TEXT,
    file_path       TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE (period_id, student_id),
    FOREIGN KEY (period_id)  REFERENCES report_periods(period_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id)      ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS report_card_subjects (
    line_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id             INTEGER NOT NULL,
    subject             TEXT NOT NULL,
    qualification_type  TEXT,
    group_id            INTEGER,
    teacher             TEXT,
    staff_id            TEXT,
    current_grade       TEXT,
    target_grade        TEXT,
    predicted_grade     TEXT,
    effort              TEXT,
    attitude            TEXT,
    comment             TEXT,
    entered_by          TEXT,
    entered_at          TEXT,
    display_order       INTEGER NOT NULL DEFAULT 0,
    UNIQUE (card_id, subject),
    FOREIGN KEY (card_id) REFERENCES report_cards(card_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_rc_period   ON report_cards(period_id);
CREATE INDEX IF NOT EXISTS idx_rc_student  ON report_cards(student_id);
CREATE INDEX IF NOT EXISTS idx_rc_status   ON report_cards(status);
CREATE INDEX IF NOT EXISTS idx_rcs_card    ON report_card_subjects(card_id);
CREATE INDEX IF NOT EXISTS idx_rcs_teacher ON report_card_subjects(teacher);
CREATE INDEX IF NOT EXISTS idx_rcs_staff   ON report_card_subjects(staff_id);
"""


class ValidationError(ValueError):
    """Raised for invalid report-card input or a refused action."""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class ReportTemplate:
    template_id: int
    name: str
    intro_text: str | None
    include_attendance: bool
    include_current_grade: bool
    include_target_grade: bool
    include_predicted_grade: bool
    include_effort: bool
    include_attitude: bool
    include_subject_comments: bool
    include_tutor_comment: bool
    include_hosf_comment: bool
    effort_scale: tuple[str, ...]
    attitude_scale: tuple[str, ...]
    comment_max_chars: int


@dataclass
class ReportPeriod:
    period_id: int
    label: str
    academic_year: str | None
    start_date: str
    end_date: str
    comments_due: str | None
    template_id: int
    status: str
    created_by: str | None
    created_at: str | None


@dataclass
class SubjectLine:
    line_id: int
    card_id: int
    subject: str
    qualification_type: str | None
    group_id: int | None
    teacher: str | None
    staff_id: str | None
    current_grade: str | None
    target_grade: str | None
    predicted_grade: str | None
    effort: str | None
    attitude: str | None
    comment: str | None
    entered_by: str | None
    entered_at: str | None
    display_order: int = 0


@dataclass
class ReportCard:
    card_id: int
    period_id: int
    student_id: str
    status: str
    attendance_pct: float | None
    tutor_comment: str | None
    tutor_by: str | None
    tutor_at: str | None
    hosf_comment: str | None
    hosf_by: str | None
    hosf_at: str | None
    submitted_by: str | None
    submitted_at: str | None
    review_note: str | None
    approved_by: str | None
    approved_at: str | None
    published_by: str | None
    published_at: str | None
    file_path: str | None
    student_name: str | None = None
    subjects: list[SubjectLine] = field(default_factory=list)

    @property
    def is_locked(self) -> bool:
        return self.status in LOCKED_STATUSES


@dataclass
class Completion:
    """How far one card has got."""
    card_id: int
    student_id: str
    student_name: str | None
    status: str
    subjects_total: int
    subjects_done: int
    tutor_done: bool
    hosf_done: bool
    missing: list[str]

    @property
    def complete(self) -> bool:
        return not self.missing

    @property
    def label(self) -> str:
        return (f"{self.subjects_done}/{self.subjects_total} subjects"
                f"{'' if self.tutor_done else ', tutor outstanding'}"
                f"{'' if self.hosf_done else ', HoSF outstanding'}")


@dataclass
class TeacherProgress:
    teacher: str
    lines_total: int
    lines_done: int

    @property
    def outstanding(self) -> int:
        return self.lines_total - self.lines_done


# ── DB plumbing ─────────────────────────────────────────────────────

def _connect() -> db.Connection:
    paths.ensure_sixth_form_directories()
    conn = db.connect(str(DB_PATH))
    conn.row_factory = db.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY = False


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
    _DB_READY = True
    logger.debug("Report-card schema ready at %s", DB_PATH)


def _now() -> str:
    return _dt.datetime.now().isoformat(sep=" ", timespec="seconds")


def _split_scale(raw: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    items = tuple(s.strip() for s in (raw or "").split("|") if s.strip())
    return items or default


def _row_template(r: db.Row) -> ReportTemplate:
    return ReportTemplate(
        template_id=r["template_id"], name=r["name"], intro_text=r["intro_text"],
        include_attendance=bool(r["include_attendance"]),
        include_current_grade=bool(r["include_current_grade"]),
        include_target_grade=bool(r["include_target_grade"]),
        include_predicted_grade=bool(r["include_predicted_grade"]),
        include_effort=bool(r["include_effort"]),
        include_attitude=bool(r["include_attitude"]),
        include_subject_comments=bool(r["include_subject_comments"]),
        include_tutor_comment=bool(r["include_tutor_comment"]),
        include_hosf_comment=bool(r["include_hosf_comment"]),
        effort_scale=_split_scale(r["effort_scale"], DEFAULT_EFFORT_SCALE),
        attitude_scale=_split_scale(r["attitude_scale"], DEFAULT_ATTITUDE_SCALE),
        comment_max_chars=int(r["comment_max_chars"] or DEFAULT_COMMENT_MAX),
    )


def _row_period(r: db.Row) -> ReportPeriod:
    return ReportPeriod(
        period_id=r["period_id"], label=r["label"],
        academic_year=r["academic_year"], start_date=r["start_date"],
        end_date=r["end_date"], comments_due=r["comments_due"],
        template_id=r["template_id"], status=r["status"],
        created_by=r["created_by"], created_at=r["created_at"])


def _row_line(r: db.Row) -> SubjectLine:
    return SubjectLine(
        line_id=r["line_id"], card_id=r["card_id"], subject=r["subject"],
        qualification_type=r["qualification_type"], group_id=r["group_id"],
        teacher=r["teacher"], staff_id=r["staff_id"],
        current_grade=r["current_grade"], target_grade=r["target_grade"],
        predicted_grade=r["predicted_grade"], effort=r["effort"],
        attitude=r["attitude"], comment=r["comment"],
        entered_by=r["entered_by"], entered_at=r["entered_at"],
        display_order=r["display_order"] or 0)


def _row_card(r: db.Row) -> ReportCard:
    keys = r.keys()
    return ReportCard(
        card_id=r["card_id"], period_id=r["period_id"],
        student_id=r["student_id"], status=r["status"],
        attendance_pct=r["attendance_pct"],
        tutor_comment=r["tutor_comment"], tutor_by=r["tutor_by"],
        tutor_at=r["tutor_at"], hosf_comment=r["hosf_comment"],
        hosf_by=r["hosf_by"], hosf_at=r["hosf_at"],
        submitted_by=r["submitted_by"], submitted_at=r["submitted_at"],
        review_note=r["review_note"], approved_by=r["approved_by"],
        approved_at=r["approved_at"], published_by=r["published_by"],
        published_at=r["published_at"], file_path=r["file_path"],
        student_name=(f"{r['first_name']} {r['last_name']}".strip()
                      if "first_name" in keys and r["first_name"] else None))


def _validate_date(value: Any, label: str, *, required: bool = True) -> str | None:
    s = (str(value).strip() if value is not None else "")
    if not s:
        if required:
            raise ValidationError(f"{label} is required")
        return None
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


# ── Who may do what ─────────────────────────────────────────────────

def _principal(by: Any = None) -> Any:
    if by is not None:
        return by
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return access.current()


def _who(by: Any) -> str:
    return (getattr(by, "username", None) or getattr(by, "staff_id", None)
            or "system")


def _staff_values(by: Any) -> set[str]:
    """Every string a class/tutor group might name this member of staff by."""
    vals = {getattr(by, "staff_id", None), getattr(by, "staff_name", None),
            getattr(by, "username", None)}
    return {v.strip().lower() for v in vals if v}


def can_approve(by: Any = None) -> bool:
    """Head of sixth form, principal / vice principal, or an admin."""
    p = _principal(by)
    return bool(getattr(p, "is_admin", False)
                or getattr(p, "job_role", None) in APPROVER_JOB_ROLES)


def can_manage(by: Any = None) -> bool:
    """Set up periods and templates, generate cards, chase completion."""
    p = _principal(by)
    if can_approve(p):
        return True
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    try:
        return bool(p.is_staff and p.can(access.REPORTS))
    except Exception:
        return False


def _require_manage(by: Any) -> Any:
    p = _principal(by)
    if not can_manage(p):
        raise ValidationError(
            "Only report leads (head of sixth form, senior leaders or staff "
            "with the reports permission) can do that")
    return p


def _require_approve(by: Any) -> Any:
    p = _principal(by)
    if not can_approve(p):
        raise ValidationError(
            "Only the head of sixth form or a senior leader can review, "
            "approve or publish reports")
    return p


def is_tutor_of(student_id: str, by: Any = None) -> bool:
    p = _principal(by)
    vals = _staff_values(p)
    if not vals:
        return False
    with _connect() as conn:
        try:
            r = conn.execute(
                """SELECT g.tutor, g.co_tutor FROM tutor_group_students s
                     JOIN tutor_groups g ON g.tutor_group_id = s.tutor_group_id
                    WHERE s.student_id = ?""", (student_id,)).fetchone()
        except db.OperationalError:
            return False
    if not r:
        return False
    return any((v or "").strip().lower() in vals for v in (r["tutor"], r["co_tutor"]))


def teaches_line(line: SubjectLine, by: Any = None) -> bool:
    p = _principal(by)
    vals = _staff_values(p)
    return bool(vals) and any(
        (v or "").strip().lower() in vals for v in (line.teacher, line.staff_id))


# ── Templates ───────────────────────────────────────────────────────

_TEMPLATE_FLAGS: tuple[str, ...] = (
    "include_attendance", "include_current_grade", "include_target_grade",
    "include_predicted_grade", "include_effort", "include_attitude",
    "include_subject_comments", "include_tutor_comment", "include_hosf_comment",
)


def _scale_text(value: Any, default: tuple[str, ...], label: str) -> str:
    if value is None:
        items = list(default)
    elif isinstance(value, (list, tuple)):
        items = [str(v).strip() for v in value if str(v).strip()]
    else:
        items = [s.strip() for s in re.split(r"[|\n]", str(value)) if s.strip()]
    if len(items) < 2:
        raise ValidationError(f"{label} needs at least two points")
    if len(set(items)) != len(items):
        raise ValidationError(f"{label} has a repeated point")
    return "|".join(items)


def _template_payload(d: dict[str, Any], existing: ReportTemplate | None = None
                      ) -> dict[str, Any]:
    out: dict[str, Any] = {}
    name = d.get("name", existing.name if existing else None)
    out["name"] = (name or "").strip()
    if not out["name"]:
        raise ValidationError("Template name is required")
    out["intro_text"] = (d.get("intro_text", existing.intro_text if existing else "")
                         or "").strip() or None
    for flag in _TEMPLATE_FLAGS:
        default = getattr(existing, flag) if existing else True
        out[flag] = 1 if bool(d.get(flag, default)) else 0
    if not any(out[f] for f in _TEMPLATE_FLAGS):
        raise ValidationError("A template must include at least one section")
    out["effort_scale"] = _scale_text(
        d.get("effort_scale", existing.effort_scale if existing else None),
        DEFAULT_EFFORT_SCALE, "Effort scale")
    out["attitude_scale"] = _scale_text(
        d.get("attitude_scale", existing.attitude_scale if existing else None),
        DEFAULT_ATTITUDE_SCALE, "Attitude scale")
    cmax = d.get("comment_max_chars",
                 existing.comment_max_chars if existing else DEFAULT_COMMENT_MAX)
    try:
        cmax = int(cmax)
    except (TypeError, ValueError):
        raise ValidationError("Comment length limit must be a whole number") from None
    if not 100 <= cmax <= 5000:
        raise ValidationError("Comment length limit must be between 100 and 5000")
    out["comment_max_chars"] = cmax
    return out


def create_template(d: dict[str, Any], *, by: Any = None) -> ReportTemplate:
    init_db()
    _require_manage(by)
    p = _template_payload(d)
    cols = ["name", "intro_text", *_TEMPLATE_FLAGS, "effort_scale",
            "attitude_scale", "comment_max_chars"]
    try:
        with _connect() as conn:
            cur = conn.execute(
                f"INSERT INTO report_templates ({', '.join(cols)}) "
                f"VALUES ({', '.join('?' * len(cols))})",
                [p[c] for c in cols])
            conn.commit()
            tid = cur.lastrowid
    except db.IntegrityError:
        raise ValidationError(f"A template called '{p['name']}' already exists") from None
    logger.info("Created report template #%s %s", tid, p["name"])
    out = get_template(tid)
    assert out is not None
    return out


def update_template(template_id: int, d: dict[str, Any], *, by: Any = None
                    ) -> ReportTemplate:
    init_db()
    _require_manage(by)
    existing = get_template(template_id)
    if existing is None:
        raise ValidationError(f"No template #{template_id}")
    p = _template_payload(d, existing)
    cols = ["name", "intro_text", *_TEMPLATE_FLAGS, "effort_scale",
            "attitude_scale", "comment_max_chars"]
    try:
        with _connect() as conn:
            conn.execute(
                f"UPDATE report_templates SET {', '.join(c + '=?' for c in cols)}, "
                "updated_at=datetime('now') WHERE template_id=?",
                [p[c] for c in cols] + [template_id])
            conn.commit()
    except db.IntegrityError:
        raise ValidationError(f"A template called '{p['name']}' already exists") from None
    out = get_template(template_id)
    assert out is not None
    return out


def get_template(template_id: int) -> ReportTemplate | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM report_templates WHERE template_id=?",
                         (int(template_id),)).fetchone()
    return _row_template(r) if r else None


def list_templates() -> list[ReportTemplate]:
    init_db()
    with _connect() as conn:
        return [_row_template(r) for r in conn.execute(
            "SELECT * FROM report_templates ORDER BY name")]


def ensure_default_template() -> ReportTemplate:
    """The college's standard template, created the first time it is needed.

    Configuration rather than data: a period cannot exist without a
    template, and a lead setting up their first period should not have
    to design one before they can start.
    """
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM report_templates WHERE name=?",
                         (DEFAULT_TEMPLATE_NAME,)).fetchone()
        if r:
            return _row_template(r)
        cur = conn.execute(
            "INSERT INTO report_templates (name, intro_text, effort_scale, "
            "attitude_scale, comment_max_chars) VALUES (?,?,?,?,?)",
            (DEFAULT_TEMPLATE_NAME,
             "This report summarises progress in each subject this period.",
             "|".join(DEFAULT_EFFORT_SCALE), "|".join(DEFAULT_ATTITUDE_SCALE),
             DEFAULT_COMMENT_MAX))
        conn.commit()
        tid = cur.lastrowid
    out = get_template(tid)
    assert out is not None
    return out


# ── Periods ─────────────────────────────────────────────────────────

def create_period(d: dict[str, Any], *, by: Any = None) -> ReportPeriod:
    init_db()
    p = _require_manage(by)
    label = (d.get("label") or "").strip()
    if not label:
        raise ValidationError("Period label is required (e.g. '2025/26 Autumn')")
    start = _validate_date(d.get("start_date"), "Start date")
    end = _validate_date(d.get("end_date"), "End date")
    if end < start:
        raise ValidationError("End date must be on or after the start date")
    due = _validate_date(d.get("comments_due"), "Comments due", required=False)
    tid = d.get("template_id")
    if tid in (None, ""):
        tid = ensure_default_template().template_id
    elif get_template(int(tid)) is None:
        raise ValidationError(f"No template #{tid}")
    try:
        with _connect() as conn:
            cur = conn.execute(
                "INSERT INTO report_periods (label, academic_year, start_date, "
                "end_date, comments_due, template_id, status, created_by) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (label, (d.get("academic_year") or "").strip() or None, start,
                 end, due, int(tid), PERIOD_OPEN, _who(p)))
            conn.commit()
            pid = cur.lastrowid
    except db.IntegrityError:
        raise ValidationError(f"A report period called '{label}' already exists") from None
    logger.info("Created report period #%s %s", pid, label)
    out = get_period(pid)
    assert out is not None
    return out


def update_period(period_id: int, d: dict[str, Any], *, by: Any = None) -> ReportPeriod:
    init_db()
    _require_manage(by)
    cur = get_period(period_id)
    if cur is None:
        raise ValidationError(f"No report period #{period_id}")
    if cur.status == PERIOD_PUBLISHED and "label" in d and d["label"] != cur.label:
        raise ValidationError("A published period's label cannot change — "
                              "it is the key its publications are held under")
    label = (d.get("label", cur.label) or "").strip()
    start = _validate_date(d.get("start_date", cur.start_date), "Start date")
    end = _validate_date(d.get("end_date", cur.end_date), "End date")
    if end < start:
        raise ValidationError("End date must be on or after the start date")
    due = _validate_date(d.get("comments_due", cur.comments_due), "Comments due",
                         required=False)
    tid = int(d.get("template_id", cur.template_id))
    if get_template(tid) is None:
        raise ValidationError(f"No template #{tid}")
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE report_periods SET label=?, academic_year=?, start_date=?, "
                "end_date=?, comments_due=?, template_id=?, updated_at=datetime('now') "
                "WHERE period_id=?",
                (label, (d.get("academic_year", cur.academic_year) or "").strip() or None,
                 start, end, due, tid, period_id))
            conn.commit()
    except db.IntegrityError:
        raise ValidationError(f"A report period called '{label}' already exists") from None
    out = get_period(period_id)
    assert out is not None
    return out


def set_period_status(period_id: int, status: str, *, by: Any = None) -> ReportPeriod:
    init_db()
    _require_manage(by)
    if status not in PERIOD_STATUSES:
        raise ValidationError(f"Status must be one of: {', '.join(PERIOD_STATUSES)}")
    if get_period(period_id) is None:
        raise ValidationError(f"No report period #{period_id}")
    with _connect() as conn:
        conn.execute("UPDATE report_periods SET status=?, updated_at=datetime('now') "
                     "WHERE period_id=?", (status, period_id))
        conn.commit()
    out = get_period(period_id)
    assert out is not None
    return out


def get_period(period_id: int) -> ReportPeriod | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM report_periods WHERE period_id=?",
                         (int(period_id),)).fetchone()
    return _row_period(r) if r else None


def get_period_by_label(label: str) -> ReportPeriod | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM report_periods WHERE label=?",
                         ((label or "").strip(),)).fetchone()
    return _row_period(r) if r else None


def list_periods(*, status: str | None = None) -> list[ReportPeriod]:
    init_db()
    sql = "SELECT * FROM report_periods"
    args: list[Any] = []
    if status:
        sql += " WHERE status=?"
        args.append(status)
    sql += " ORDER BY start_date DESC, period_id DESC"
    with _connect() as conn:
        return [_row_period(r) for r in conn.execute(sql, args)]


def delete_period(period_id: int, *, by: Any = None) -> bool:
    """Remove a period that has never been published (its cards go too)."""
    init_db()
    _require_manage(by)
    period = get_period(period_id)
    if period is None:
        return False
    if _published_students(period.label):
        raise ValidationError("Reports in this period have been published — "
                              "unpublish them before deleting the period")
    with _connect() as conn:
        conn.execute("DELETE FROM report_periods WHERE period_id=?", (period_id,))
        conn.commit()
    logger.info("Deleted report period #%s %s", period_id, period.label)
    return True


# ── Generating cards ────────────────────────────────────────────────

def _attendance_pct(student_id: str, period: ReportPeriod) -> float | None:
    try:
        from education_system.systems.sixth_form.domain.academics.attendance import (
            attendance as _att,
        )
        return _att.summary_for_student(
            student_id, date_from=period.start_date,
            date_to=period.end_date).percentage
    except Exception:
        logger.debug("Attendance unavailable for %s", student_id, exc_info=True)
        return None


def _subjects_for(student_id: str) -> list[tuple[str, str | None]]:
    """(subject, qualification type) for each active learning aim."""
    out: list[tuple[str, str | None]] = []
    try:
        from education_system.systems.sixth_form.domain.academics.qualifications import (
            learning_aims as _aims,
        )
        for aim in _aims.active_aims(student_id):
            out.append((aim.subject, aim.qualification_type))
    except Exception:
        logger.debug("Learning aims unavailable for %s", student_id, exc_info=True)
    if not out:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        s = _students.get_student(student_id)
        if s is not None:
            out = [(subj, None) for subj in s.subjects]
    seen: set[str] = set()
    uniq = []
    for subj, q in out:
        if subj and subj not in seen:
            seen.add(subj)
            uniq.append((subj, q))
    return uniq


def _groups_by_subject(conn: db.Connection, student_id: str
                       ) -> dict[str, tuple[int, str | None]]:
    try:
        rows = conn.execute(
            """SELECT g.group_id, COALESCE(NULLIF(g.teacher, ''), c.teacher) AS teacher,
                      c.subject
                 FROM class_group_students s
                 JOIN class_groups g ON g.group_id = s.group_id
                 LEFT JOIN courses c ON c.course_id = g.course_id
                WHERE s.student_id = ?""", (student_id,)).fetchall()
    except db.OperationalError:
        return {}
    out: dict[str, tuple[int, str | None]] = {}
    for r in rows:
        if r["subject"]:
            out.setdefault(r["subject"].strip().lower(), (r["group_id"], r["teacher"]))
    return out


def _resolve_staff_id(conn: db.Connection, teacher: str | None) -> str | None:
    if not teacher:
        return None
    try:
        r = conn.execute(
            "SELECT staff_id FROM staff WHERE UPPER(staff_id)=UPPER(?) "
            "OR LOWER(TRIM(first_name || ' ' || last_name))=LOWER(TRIM(?)) "
            "OR LOWER(email)=LOWER(TRIM(?)) LIMIT 1",
            (teacher.strip(), teacher, teacher)).fetchone()
    except db.OperationalError:
        return None
    return r["staff_id"] if r else None


def _target_and_prediction(student_id: str, subject: str
                           ) -> tuple[str | None, str | None, str | None]:
    """(current, target, predicted) as the college currently holds them."""
    current = target = predicted = None
    try:
        from education_system.systems.sixth_form.domain.assessment.target_setting import (
            target_setting as _ts,
        )
        t = _ts.get_target_for(student_id, subject)
        if t is not None:
            target, current = t.mte_grade, t.current_grade
    except Exception:
        logger.debug("Target unavailable for %s/%s", student_id, subject, exc_info=True)
    try:
        from education_system.systems.sixth_form.domain.assessment.predicted_grades import (
            predicted_grades as _pg,
        )
        p = _pg.get_for_student_subject(student_id, subject)
        if p is not None:
            predicted = p.grade
    except Exception:
        logger.debug("Prediction unavailable for %s/%s", student_id, subject, exc_info=True)
    return current, target, predicted


def generate_cards(period_id: int, student_ids: list[str] | None = None, *,
                   by: Any = None) -> dict[str, int]:
    """Create a card per learner (default: every Active student).

    Existing cards are left alone except that subject lines are added for
    any new learning aim, so re-running after a timetable change is safe.
    Returns ``{"created": n, "lines_added": n, "skipped": n}``.
    """
    init_db()
    _require_manage(by)
    period = get_period(period_id)
    if period is None:
        raise ValidationError(f"No report period #{period_id}")
    if period.status == PERIOD_PUBLISHED:
        raise ValidationError("This period has been published")
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    if student_ids is None:
        targets = [s.student_id for s in _students.list_students()
                   if (s.status or "Active") == "Active"]
    else:
        targets = [str(s).strip() for s in student_ids if str(s).strip()]
    created = added = skipped = 0
    for sid in targets:
        if _students.get_student(sid) is None:
            skipped += 1
            continue
        subjects = _subjects_for(sid)
        att = _attendance_pct(sid, period)
        with _connect() as conn:
            r = conn.execute("SELECT card_id, status FROM report_cards "
                             "WHERE period_id=? AND student_id=?",
                             (period_id, sid)).fetchone()
            if r is None:
                cur = conn.execute(
                    "INSERT INTO report_cards (period_id, student_id, status, "
                    "attendance_pct) VALUES (?,?,?,?)",
                    (period_id, sid, CARD_DRAFT, att))
                card_id = cur.lastrowid
                created += 1
            else:
                card_id = r["card_id"]
                if r["status"] in LOCKED_STATUSES:
                    skipped += 1
                    conn.commit()
                    continue
            groups = _groups_by_subject(conn, sid)
            have = {row["subject"] for row in conn.execute(
                "SELECT subject FROM report_card_subjects WHERE card_id=?", (card_id,))}
            for order, (subject, qtype) in enumerate(subjects):
                if subject in have:
                    continue
                gid, teacher = groups.get(subject.strip().lower(), (None, None))
                current, target, predicted = _target_and_prediction(sid, subject)
                conn.execute(
                    "INSERT INTO report_card_subjects (card_id, subject, "
                    "qualification_type, group_id, teacher, staff_id, current_grade, "
                    "target_grade, predicted_grade, display_order) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (card_id, subject, qtype, gid, teacher,
                     _resolve_staff_id(conn, teacher), current, target, predicted,
                     order))
                added += 1
            conn.commit()
    logger.info("Report cards for %s: %d created, %d lines added, %d skipped",
                period.label, created, added, skipped)
    return {"created": created, "lines_added": added, "skipped": skipped}


def refresh_card_data(card_id: int, *, by: Any = None) -> ReportCard:
    """Re-pull attendance, targets and predictions into a card not yet approved.

    Teacher-entered current grades are kept; only blank ones are filled.
    """
    init_db()
    _require_manage(by)
    card = get_card(card_id)
    if card is None:
        raise ValidationError(f"No report card #{card_id}")
    if card.is_locked:
        raise ValidationError("This report is approved — reopen it first")
    period = get_period(card.period_id)
    assert period is not None
    att = _attendance_pct(card.student_id, period)
    with _connect() as conn:
        conn.execute("UPDATE report_cards SET attendance_pct=?, updated_at=datetime('now') "
                     "WHERE card_id=?", (att, card_id))
        for line in card.subjects:
            current, target, predicted = _target_and_prediction(card.student_id,
                                                                line.subject)
            conn.execute(
                "UPDATE report_card_subjects SET target_grade=?, predicted_grade=?, "
                "current_grade=COALESCE(current_grade, ?) WHERE line_id=?",
                (target, predicted, current, line.line_id))
        conn.commit()
    out = get_card(card_id)
    assert out is not None
    return out


# ── Reading cards ───────────────────────────────────────────────────

_CARD_SELECT = ("SELECT rc.*, s.first_name, s.last_name FROM report_cards rc "
                "LEFT JOIN students s ON s.student_id = rc.student_id")


def get_card(card_id: int) -> ReportCard | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(f"{_CARD_SELECT} WHERE rc.card_id=?", (int(card_id),)).fetchone()
        if not r:
            return None
        card = _row_card(r)
        card.subjects = [_row_line(x) for x in conn.execute(
            "SELECT * FROM report_card_subjects WHERE card_id=? "
            "ORDER BY display_order, subject", (card.card_id,))]
    return card


def get_card_for(period_id: int, student_id: str) -> ReportCard | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT card_id FROM report_cards WHERE period_id=? "
                         "AND student_id=?", (period_id, student_id)).fetchone()
    return get_card(r["card_id"]) if r else None


def list_cards(period_id: int, *, status: str | None = None) -> list[ReportCard]:
    init_db()
    sql = f"{_CARD_SELECT} WHERE rc.period_id=?"
    args: list[Any] = [period_id]
    if status:
        sql += " AND rc.status=?"
        args.append(status)
    sql += " ORDER BY s.last_name, s.first_name, rc.student_id"
    with _connect() as conn:
        cards = [_row_card(r) for r in conn.execute(sql, args)]
        lines: dict[int, list[SubjectLine]] = {}
        for r in conn.execute(
                "SELECT l.* FROM report_card_subjects l JOIN report_cards c "
                "ON c.card_id = l.card_id WHERE c.period_id=? "
                "ORDER BY l.display_order, l.subject", (period_id,)):
            lines.setdefault(r["card_id"], []).append(_row_line(r))
    for c in cards:
        c.subjects = lines.get(c.card_id, [])
    return cards


def get_line(line_id: int) -> SubjectLine | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM report_card_subjects WHERE line_id=?",
                         (int(line_id),)).fetchone()
    return _row_line(r) if r else None


@dataclass
class TeacherLine:
    """A subject line as a teacher's comment-entry list shows it."""
    line: SubjectLine
    student_id: str
    student_name: str
    card_status: str


def lines_for_teacher(period_id: int, *, by: Any = None,
                      all_lines: bool = False) -> list[TeacherLine]:
    """The lines this member of staff writes for (their classes).

    ``all_lines`` (report leads only) returns every line, for chasing and
    for covering an absent colleague.
    """
    init_db()
    p = _principal(by)
    if all_lines:
        _require_manage(p)
    vals = _staff_values(p)
    with _connect() as conn:
        rows = conn.execute(
            """SELECT l.*, c.student_id, c.status AS card_status,
                      s.first_name, s.last_name
                 FROM report_card_subjects l
                 JOIN report_cards c ON c.card_id = l.card_id
                 LEFT JOIN students s ON s.student_id = c.student_id
                WHERE c.period_id = ?
                ORDER BY l.subject, s.last_name, s.first_name""",
            (period_id,)).fetchall()
    out = []
    for r in rows:
        line = _row_line(r)
        if not all_lines and not any(
                (v or "").strip().lower() in vals for v in (line.teacher, line.staff_id)):
            continue
        out.append(TeacherLine(
            line=line, student_id=r["student_id"],
            student_name=f"{r['first_name'] or ''} {r['last_name'] or ''}".strip()
            or r["student_id"], card_status=r["card_status"]))
    return out


def cards_for_tutor(period_id: int, *, by: Any = None) -> list[ReportCard]:
    """Cards for this tutor's tutees."""
    p = _principal(by)
    return [c for c in list_cards(period_id) if is_tutor_of(c.student_id, p)]


# ── Comment entry ───────────────────────────────────────────────────

def _check_open(card: ReportCard) -> ReportPeriod:
    if card.is_locked:
        raise ValidationError(f"This report is {card.status.lower()} — "
                              "ask the head of sixth form to reopen it")
    period = get_period(card.period_id)
    assert period is not None
    if period.status != PERIOD_OPEN:
        raise ValidationError(f"The {period.label} period is {period.status.lower()} "
                              "for comment entry")
    return period


def _clean_comment(text: Any, tmpl: ReportTemplate, label: str) -> str | None:
    s = (str(text) if text is not None else "").strip()
    if len(s) > tmpl.comment_max_chars:
        raise ValidationError(f"{label} is {len(s)} characters — the limit is "
                              f"{tmpl.comment_max_chars}")
    return s or None


def save_subject_entry(line_id: int, *, current_grade: str | None = None,
                       effort: str | None = None, attitude: str | None = None,
                       comment: str | None = None, by: Any = None) -> SubjectLine:
    """A teacher's entry for one learner in one subject.

    Only the line's teacher or a report lead may write it. The grade is
    validated against the learner's qualification scale; effort and
    attitude against the period template's scales.
    """
    init_db()
    p = _principal(by)
    line = get_line(line_id)
    if line is None:
        raise ValidationError(f"No report line #{line_id}")
    card = get_card(line.card_id)
    assert card is not None
    if not (teaches_line(line, p) or can_manage(p)):
        raise ValidationError(f"You are not the {line.subject} teacher for this learner")
    period = _check_open(card)
    tmpl = get_template(period.template_id)
    assert tmpl is not None

    grade = (current_grade or "").strip() or None
    if grade:
        from education_system.systems.sixth_form.domain.academics.qualifications import (
            grade_scales as _gs,
        )
        try:
            grade = _gs.validate_grade(grade, line.qualification_type)
        except ValueError as e:
            raise ValidationError(str(e)) from None
    eff = (effort or "").strip() or None
    if eff and eff not in tmpl.effort_scale:
        raise ValidationError(f"Effort must be one of: {', '.join(tmpl.effort_scale)}")
    att = (attitude or "").strip() or None
    if att and att not in tmpl.attitude_scale:
        raise ValidationError(f"Attitude must be one of: {', '.join(tmpl.attitude_scale)}")
    text = _clean_comment(comment, tmpl, f"The {line.subject} comment")
    with _connect() as conn:
        conn.execute(
            "UPDATE report_card_subjects SET current_grade=?, effort=?, attitude=?, "
            "comment=?, entered_by=?, entered_at=? WHERE line_id=?",
            (grade, eff, att, text, _who(p), _now(), line_id))
        conn.execute("UPDATE report_cards SET updated_at=datetime('now') WHERE card_id=?",
                     (card.card_id,))
        conn.commit()
    out = get_line(line_id)
    assert out is not None
    return out


def save_tutor_comment(card_id: int, text: str, *, by: Any = None) -> ReportCard:
    init_db()
    p = _principal(by)
    card = get_card(card_id)
    if card is None:
        raise ValidationError(f"No report card #{card_id}")
    if not (is_tutor_of(card.student_id, p) or can_manage(p)):
        raise ValidationError("Only this learner's tutor can write the tutor comment")
    period = _check_open(card)
    tmpl = get_template(period.template_id)
    assert tmpl is not None
    clean = _clean_comment(text, tmpl, "The tutor comment")
    with _connect() as conn:
        conn.execute("UPDATE report_cards SET tutor_comment=?, tutor_by=?, tutor_at=?, "
                     "updated_at=datetime('now') WHERE card_id=?",
                     (clean, _who(p), _now(), card_id))
        conn.commit()
    out = get_card(card_id)
    assert out is not None
    return out


def save_hosf_comment(card_id: int, text: str, *, by: Any = None) -> ReportCard:
    init_db()
    p = _require_approve(by)
    card = get_card(card_id)
    if card is None:
        raise ValidationError(f"No report card #{card_id}")
    if card.is_locked:
        raise ValidationError("This report is approved — reopen it first")
    period = get_period(card.period_id)
    assert period is not None
    if period.status == PERIOD_PUBLISHED:
        raise ValidationError("This period has been published")
    tmpl = get_template(period.template_id)
    assert tmpl is not None
    clean = _clean_comment(text, tmpl, "The head of sixth form comment")
    with _connect() as conn:
        conn.execute("UPDATE report_cards SET hosf_comment=?, hosf_by=?, hosf_at=?, "
                     "updated_at=datetime('now') WHERE card_id=?",
                     (clean, _who(p), _now(), card_id))
        conn.commit()
    out = get_card(card_id)
    assert out is not None
    return out


# ── Completion ──────────────────────────────────────────────────────

def _line_done(line: SubjectLine, tmpl: ReportTemplate) -> bool:
    if tmpl.include_subject_comments and not line.comment:
        return False
    if tmpl.include_effort and not line.effort:
        return False
    if tmpl.include_attitude and not line.attitude:
        return False
    return True


def card_completion(card: ReportCard, tmpl: ReportTemplate | None = None) -> Completion:
    if tmpl is None:
        period = get_period(card.period_id)
        assert period is not None
        tmpl = get_template(period.template_id)
        assert tmpl is not None
    done = [ln for ln in card.subjects if _line_done(ln, tmpl)]
    missing = [f"{ln.subject} ({ln.teacher or 'no teacher'})"
               for ln in card.subjects if not _line_done(ln, tmpl)]
    tutor_done = (not tmpl.include_tutor_comment) or bool(card.tutor_comment)
    hosf_done = (not tmpl.include_hosf_comment) or bool(card.hosf_comment)
    if not tutor_done:
        missing.append("tutor comment")
    if not hosf_done:
        missing.append("head of sixth form comment")
    if not card.subjects:
        missing.append("no subjects on the report")
    return Completion(
        card_id=card.card_id, student_id=card.student_id,
        student_name=card.student_name, status=card.status,
        subjects_total=len(card.subjects), subjects_done=len(done),
        tutor_done=tutor_done, hosf_done=hosf_done, missing=missing)


def completion(period_id: int) -> list[Completion]:
    period = get_period(period_id)
    if period is None:
        raise ValidationError(f"No report period #{period_id}")
    tmpl = get_template(period.template_id)
    assert tmpl is not None
    return [card_completion(c, tmpl) for c in list_cards(period_id)]


def teacher_progress(period_id: int) -> list[TeacherProgress]:
    """Lines written vs lines owed, per teacher — for chasing."""
    period = get_period(period_id)
    if period is None:
        raise ValidationError(f"No report period #{period_id}")
    tmpl = get_template(period.template_id)
    assert tmpl is not None
    tally: dict[str, list[int]] = {}
    for card in list_cards(period_id):
        for ln in card.subjects:
            t = tally.setdefault(ln.teacher or "(no teacher)", [0, 0])
            t[0] += 1
            t[1] += 1 if _line_done(ln, tmpl) else 0
    return sorted((TeacherProgress(k, v[0], v[1]) for k, v in tally.items()),
                  key=lambda t: (-t.outstanding, t.teacher))


def period_summary(period_id: int) -> dict[str, int]:
    comp = completion(period_id)
    by_status = {s: 0 for s in CARD_STATUSES}
    for c in comp:
        by_status[c.status] = by_status.get(c.status, 0) + 1
    return {"cards": len(comp), "complete": sum(1 for c in comp if c.complete),
            **{k.lower().replace(" ", "_"): v for k, v in by_status.items()}}


# ── Review and approval ─────────────────────────────────────────────

def submit_for_review(card_id: int, *, by: Any = None) -> ReportCard:
    """Hand a complete card to the head of sixth form."""
    init_db()
    p = _principal(by)
    card = get_card(card_id)
    if card is None:
        raise ValidationError(f"No report card #{card_id}")
    if not (can_manage(p) or is_tutor_of(card.student_id, p)):
        raise ValidationError("Only the tutor or a report lead can submit a report")
    if card.status != CARD_DRAFT:
        raise ValidationError(f"This report is already {card.status.lower()}")
    comp = card_completion(card)
    # The HoSF comment is written during review, so it is not required here.
    outstanding = [m for m in comp.missing if m != "head of sixth form comment"]
    if outstanding:
        raise ValidationError("Not complete yet: " + "; ".join(outstanding))
    with _connect() as conn:
        conn.execute("UPDATE report_cards SET status=?, submitted_by=?, submitted_at=?, "
                     "updated_at=datetime('now') WHERE card_id=?",
                     (CARD_REVIEW, _who(p), _now(), card_id))
        conn.commit()
    out = get_card(card_id)
    assert out is not None
    return out


def return_for_changes(card_id: int, note: str, *, by: Any = None) -> ReportCard:
    init_db()
    p = _require_approve(by)
    card = get_card(card_id)
    if card is None:
        raise ValidationError(f"No report card #{card_id}")
    if card.status == CARD_PUBLISHED:
        raise ValidationError("This report is published — unpublish it first")
    note = (note or "").strip()
    if not note:
        raise ValidationError("Say what needs changing")
    with _connect() as conn:
        conn.execute("UPDATE report_cards SET status=?, review_note=?, approved_by=NULL, "
                     "approved_at=NULL, updated_at=datetime('now') WHERE card_id=?",
                     (CARD_DRAFT, f"{note} — {_who(p)}, {_now()}", card_id))
        conn.commit()
    out = get_card(card_id)
    assert out is not None
    return out


def approve(card_id: int, *, by: Any = None) -> ReportCard:
    init_db()
    p = _require_approve(by)
    card = get_card(card_id)
    if card is None:
        raise ValidationError(f"No report card #{card_id}")
    if card.status in LOCKED_STATUSES:
        raise ValidationError(f"This report is already {card.status.lower()}")
    comp = card_completion(card)
    if comp.missing:
        raise ValidationError("Not complete yet: " + "; ".join(comp.missing))
    with _connect() as conn:
        conn.execute("UPDATE report_cards SET status=?, approved_by=?, approved_at=?, "
                     "review_note=NULL, updated_at=datetime('now') WHERE card_id=?",
                     (CARD_APPROVED, _who(p), _now(), card_id))
        conn.commit()
    out = get_card(card_id)
    assert out is not None
    return out


def approve_all_complete(period_id: int, *, by: Any = None) -> tuple[int, list[str]]:
    """Approve every complete, unapproved card. Returns (count, problems)."""
    p = _require_approve(by)
    n, problems = 0, []
    for c in completion(period_id):
        if c.status in LOCKED_STATUSES:
            continue
        if not c.complete:
            problems.append(f"{c.student_name or c.student_id}: {'; '.join(c.missing)}")
            continue
        try:
            approve(c.card_id, by=p)
            n += 1
        except ValidationError as e:
            problems.append(f"{c.student_name or c.student_id}: {e}")
    return n, problems


def reopen(card_id: int, *, by: Any = None) -> ReportCard:
    """Take an approved (not published) card back to Draft for edits."""
    init_db()
    p = _require_approve(by)
    card = get_card(card_id)
    if card is None:
        raise ValidationError(f"No report card #{card_id}")
    if card.status == CARD_PUBLISHED:
        raise ValidationError("This report is published — unpublish it first")
    with _connect() as conn:
        conn.execute("UPDATE report_cards SET status=?, approved_by=NULL, approved_at=NULL, "
                     "updated_at=datetime('now') WHERE card_id=?", (CARD_DRAFT, card_id))
        conn.commit()
    logger.info("Report card #%s reopened by %s", card_id, _who(p))
    out = get_card(card_id)
    assert out is not None
    return out


# ── Publishing (through bulk_operations) ────────────────────────────

def _published_students(period_label: str) -> set[str]:
    from education_system.systems.sixth_form.domain.learners.bulk_operations import (
        base as bulk_base,
    )
    bulk_base.init_db()
    with _connect() as conn:
        return {r["student_id"] for r in conn.execute(
            "SELECT student_id FROM report_card_publications WHERE period=?",
            (period_label,))}


def unapproved_for_publication(student_ids: list[str], period_label: str
                               ) -> dict[str, str]:
    """Learners the bulk publish must refuse, with the reason.

    Called by :func:`bulk_operations.bulk_publish_report_cards`. When no
    report period carries ``period_label`` the bulk operation predates
    this module's content and nothing is refused.
    """
    period = get_period_by_label(period_label)
    if period is None:
        return {}
    with _connect() as conn:
        status = {r["student_id"]: r["status"] for r in conn.execute(
            "SELECT student_id, status FROM report_cards WHERE period_id=?",
            (period.period_id,))}
    out = {}
    for sid in student_ids:
        st = status.get(sid)
        if st is None:
            out[sid] = f"no report card for {period_label}"
        elif st not in LOCKED_STATUSES:
            out[sid] = f"report card is {st.lower()}, not approved"
    return out


def on_publications_changed(student_ids: list[str], period_label: str, *,
                            publish: bool, by: str | None = None) -> int:
    """Keep card status (and rendered files) in step with the bulk publish.

    Called by :func:`bulk_operations.bulk_publish_report_cards` after it
    has written ``report_card_publications``. Returns cards updated.
    """
    period = get_period_by_label(period_label)
    if period is None or not student_ids:
        return 0
    n = 0
    for sid in student_ids:
        card = get_card_for(period.period_id, sid)
        if card is None:
            continue
        if publish and card.status in LOCKED_STATUSES:
            with _connect() as conn:
                conn.execute("UPDATE report_cards SET status=?, published_by=?, "
                             "published_at=?, updated_at=datetime('now') WHERE card_id=?",
                             (CARD_PUBLISHED, by, _now(), card.card_id))
                conn.commit()
            try:
                render(card.card_id, fmt="html")
            except Exception:
                logger.exception("Could not render report card #%s", card.card_id)
            n += 1
        elif not publish and card.status == CARD_PUBLISHED:
            with _connect() as conn:
                conn.execute("UPDATE report_cards SET status=?, published_by=NULL, "
                             "published_at=NULL, updated_at=datetime('now') "
                             "WHERE card_id=?", (CARD_APPROVED, card.card_id))
                conn.commit()
            n += 1
    with _connect() as conn:
        remaining = conn.execute(
            "SELECT COUNT(*) FROM report_cards WHERE period_id=? AND status<>?",
            (period.period_id, CARD_PUBLISHED)).fetchone()[0]
        any_pub = conn.execute(
            "SELECT COUNT(*) FROM report_cards WHERE period_id=? AND status=?",
            (period.period_id, CARD_PUBLISHED)).fetchone()[0]
        new_status = (PERIOD_PUBLISHED if any_pub and not remaining
                      else (PERIOD_CLOSED if period.status == PERIOD_PUBLISHED
                            else period.status))
        conn.execute("UPDATE report_periods SET status=?, updated_at=datetime('now') "
                     "WHERE period_id=?", (new_status, period.period_id))
        conn.commit()
    return n


def publish(period_id: int, *, student_ids: list[str] | None = None,
            by: Any = None):
    """Publish approved cards to learners and their parents.

    Goes through :func:`bulk_operations.bulk_publish_report_cards` so the
    job is logged (and undoable) like every other bulk operation. Returns
    its ``BulkResult``.
    """
    p = _require_approve(by)
    period = get_period(period_id)
    if period is None:
        raise ValidationError(f"No report period #{period_id}")
    if student_ids is None:
        student_ids = [c.student_id for c in list_cards(period_id)
                       if c.status == CARD_APPROVED]
    if not student_ids:
        raise ValidationError("No approved reports to publish")
    from education_system.systems.sixth_form.domain.learners.bulk_operations import (
        ops_academic as bulk_ops_academic,
    )
    return bulk_ops_academic.bulk_publish_report_cards(
        student_ids, period=period.label, publish=True,
        published_by=_who(p), ran_by=_who(p))


def unpublish(period_id: int, *, student_ids: list[str] | None = None,
              by: Any = None):
    p = _require_approve(by)
    period = get_period(period_id)
    if period is None:
        raise ValidationError(f"No report period #{period_id}")
    if student_ids is None:
        student_ids = sorted(_published_students(period.label))
    if not student_ids:
        raise ValidationError("Nothing is published for this period")
    from education_system.systems.sixth_form.domain.learners.bulk_operations import (
        ops_academic as bulk_ops_academic,
    )
    return bulk_ops_academic.bulk_publish_report_cards(
        student_ids, period=period.label, publish=False,
        published_by=_who(p), ran_by=_who(p))


# ── Portal reads (students and parents) ─────────────────────────────

def published_cards_for_student(student_id: str) -> list[dict[str, Any]]:
    """Published report cards for one learner, newest period first.

    The *only* list the portals show. A card appears while it is
    Published and its publication row exists; caller scopes the student.
    """
    init_db()
    sid = (student_id or "").strip()
    if not sid:
        return []
    from education_system.systems.sixth_form.domain.learners.bulk_operations import (
        base as bulk_base,
    )
    bulk_base.init_db()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT rc.card_id, rc.published_at, p.label, p.period_id,
                      p.start_date, p.end_date
                 FROM report_cards rc
                 JOIN report_periods p ON p.period_id = rc.period_id
                 JOIN report_card_publications pub
                   ON pub.student_id = rc.student_id AND pub.period = p.label
                WHERE rc.student_id = ? AND rc.status = ?
                ORDER BY p.start_date DESC""", (sid, CARD_PUBLISHED)).fetchall()
    out = []
    for r in rows:
        out.append({"card_id": r["card_id"], "period": r["label"],
                    "period_id": r["period_id"], "start_date": r["start_date"],
                    "end_date": r["end_date"], "published_at": r["published_at"]})
    return out


def published_card(student_id: str, card_id: int) -> ReportCard:
    """One published card, provided it is this learner's and still published."""
    sid = (student_id or "").strip()
    allowed = {c["card_id"] for c in published_cards_for_student(sid)}
    if int(card_id) not in allowed:
        raise ValidationError("That report is not available.")
    card = get_card(int(card_id))
    assert card is not None
    return card


def published_text(student_id: str, card_id: int) -> str:
    return render_text(published_card(student_id, card_id))


def published_predictions(student_id: str) -> dict[str, str]:
    """Predicted grades as shared on the learner's latest published report.

    Predicted grades have no "shareable" flag of their own, so the only
    predictions a learner or parent sees are ones a published (approved)
    report carried.
    """
    cards = published_cards_for_student(student_id)
    if not cards:
        return {}
    card = get_card(cards[0]["card_id"])
    if card is None:
        return {}
    period = get_period(card.period_id)
    tmpl = get_template(period.template_id) if period else None
    if tmpl is None or not tmpl.include_predicted_grade:
        return {}
    return {ln.subject: ln.predicted_grade for ln in card.subjects if ln.predicted_grade}


# ── Rendering ───────────────────────────────────────────────────────

def _context(card: ReportCard) -> tuple[ReportPeriod, ReportTemplate, str]:
    period = get_period(card.period_id)
    assert period is not None
    tmpl = get_template(period.template_id)
    assert tmpl is not None
    from education_system.systems.sixth_form import SYSTEM_NAME
    return period, tmpl, SYSTEM_NAME


def render_text(card: ReportCard) -> str:
    period, tmpl, system = _context(card)
    rule = "─" * 70
    out = [system, f"Report — {period.label}", rule,
           f"Learner: {card.student_name or card.student_id} ({card.student_id})",
           f"Period:  {period.start_date} to {period.end_date}"]
    if tmpl.include_attendance:
        out.append("Attendance: " + ("—" if card.attendance_pct is None
                                     else f"{card.attendance_pct:.1f}%"))
    if tmpl.intro_text:
        out += ["", tmpl.intro_text]
    for ln in card.subjects:
        out += ["", rule, f"{ln.subject}"
                + (f"  ({ln.qualification_type})" if ln.qualification_type else "")
                + (f"  — {ln.teacher}" if ln.teacher else "")]
        bits = []
        if tmpl.include_current_grade:
            bits.append(f"Current: {ln.current_grade or '—'}")
        if tmpl.include_target_grade:
            bits.append(f"Target: {ln.target_grade or '—'}")
        if tmpl.include_predicted_grade:
            bits.append(f"Predicted: {ln.predicted_grade or '—'}")
        if tmpl.include_effort:
            bits.append(f"Effort: {ln.effort or '—'}")
        if tmpl.include_attitude:
            bits.append(f"Attitude: {ln.attitude or '—'}")
        if bits:
            out.append("   ".join(bits))
        if tmpl.include_subject_comments and ln.comment:
            out += ["", ln.comment]
    if tmpl.include_tutor_comment:
        out += ["", rule, "Tutor's comment", card.tutor_comment or "—"]
    if tmpl.include_hosf_comment:
        out += ["", rule, "Head of Sixth Form's comment", card.hosf_comment or "—"]
    out += ["", rule, f"Approved: {card.approved_at or '—'}   "
            f"Published: {card.published_at or '—'}"]
    return "\n".join(out) + "\n"


def render_html(card: ReportCard) -> str:
    period, tmpl, system = _context(card)
    e = html.escape
    rows = []
    for ln in card.subjects:
        cells = [f"<td><strong>{e(ln.subject)}</strong><br><small>"
                 f"{e(ln.qualification_type or '')} {e(ln.teacher or '')}</small></td>"]
        for flag, val in (("include_current_grade", ln.current_grade),
                          ("include_target_grade", ln.target_grade),
                          ("include_predicted_grade", ln.predicted_grade),
                          ("include_effort", ln.effort),
                          ("include_attitude", ln.attitude)):
            if getattr(tmpl, flag):
                cells.append(f"<td>{e(val or '—')}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
        if tmpl.include_subject_comments and ln.comment:
            span = 1 + sum(1 for f in ("include_current_grade", "include_target_grade",
                                       "include_predicted_grade", "include_effort",
                                       "include_attitude") if getattr(tmpl, f))
            rows.append(f'<tr><td colspan="{span}" class="c">{e(ln.comment)}</td></tr>')
    heads = ["Subject"] + [h for f, h in (
        ("include_current_grade", "Current"), ("include_target_grade", "Target"),
        ("include_predicted_grade", "Predicted"), ("include_effort", "Effort"),
        ("include_attitude", "Attitude")) if getattr(tmpl, f)]
    parts = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        f"<title>{e(card.student_name or card.student_id)} — {e(period.label)}</title>",
        "<style>body{font-family:sans-serif;max-width:860px;margin:2em auto;color:#222}"
        "table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;"
        "padding:6px;text-align:left;vertical-align:top}td.c{white-space:pre-wrap;"
        "background:#fafafa}h1{margin-bottom:0}</style></head><body>",
        f"<h1>{e(system)}</h1><h2>Report — {e(period.label)}</h2>",
        f"<p><strong>{e(card.student_name or card.student_id)}</strong> "
        f"({e(card.student_id)})<br>{e(period.start_date)} to {e(period.end_date)}</p>",
    ]
    if tmpl.include_attendance:
        parts.append("<p>Attendance: <strong>" + (
            "—" if card.attendance_pct is None else f"{card.attendance_pct:.1f}%")
            + "</strong></p>")
    if tmpl.intro_text:
        parts.append(f"<p>{e(tmpl.intro_text)}</p>")
    parts.append("<table><tr>" + "".join(f"<th>{e(h)}</th>" for h in heads)
                 + "</tr>" + "".join(rows) + "</table>")
    if tmpl.include_tutor_comment:
        parts.append(f"<h3>Tutor's comment</h3><p style='white-space:pre-wrap'>"
                     f"{e(card.tutor_comment or '—')}</p>")
    if tmpl.include_hosf_comment:
        parts.append(f"<h3>Head of Sixth Form's comment</h3>"
                     f"<p style='white-space:pre-wrap'>{e(card.hosf_comment or '—')}</p>")
    parts.append(f"<p><small>Approved {e(card.approved_at or '—')} · "
                 f"Published {e(card.published_at or '—')}</small></p></body></html>")
    return "".join(parts)


def pdf_available() -> bool:
    try:
        import reportlab  # noqa: F401
    except ImportError:
        return False
    return True


def _write_pdf(card: ReportCard, target: Path) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    styles = getSampleStyleSheet()
    story = []
    for i, line in enumerate(render_text(card).splitlines()):
        if not line.strip() or set(line) == {"─"}:
            story.append(Spacer(1, 6))
            continue
        style = styles["Title"] if i == 0 else styles["BodyText"]
        story.append(Paragraph(html.escape(line), style))
    SimpleDocTemplate(str(target), pagesize=A4).build(story)


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_") or "report"


def render(card_id: int, *, fmt: str = "html", output_dir: Path | str | None = None
           ) -> Path:
    """Write one card to a file and return its path.

    ``fmt`` is ``txt``, ``html`` or ``pdf`` (PDF needs ``reportlab``).
    Files land in ``OUTPUT_DIR/<period>/`` unless ``output_dir`` is given.
    """
    card = get_card(card_id)
    if card is None:
        raise ValidationError(f"No report card #{card_id}")
    fmt = (fmt or "html").lower().lstrip(".")
    if fmt not in ("txt", "html", "pdf"):
        raise ValidationError("Format must be txt, html or pdf")
    if fmt == "pdf" and not pdf_available():
        raise ValidationError("PDF output needs the reportlab package — "
                              "choose html or txt instead")
    period = get_period(card.period_id)
    assert period is not None
    folder = Path(output_dir) if output_dir else OUTPUT_DIR / _slug(period.label)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{_slug(card.student_id)}_{_slug(period.label)}.{fmt}"
    if fmt == "txt":
        target.write_text(render_text(card), encoding="utf-8")
    elif fmt == "html":
        target.write_text(render_html(card), encoding="utf-8")
    else:
        _write_pdf(card, target)
    with _connect() as conn:
        conn.execute("UPDATE report_cards SET file_path=? WHERE card_id=?",
                     (str(target), card_id))
        conn.commit()
    logger.info("Rendered report card #%s to %s", card_id, target)
    return target


def render_period(period_id: int, *, fmt: str = "html", by: Any = None,
                  approved_only: bool = True) -> list[Path]:
    """Render every (approved or published) card in a period."""
    _require_manage(by)
    out = []
    for c in list_cards(period_id):
        if approved_only and c.status not in LOCKED_STATUSES:
            continue
        out.append(render(c.card_id, fmt=fmt))
    return out
