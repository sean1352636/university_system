"""Behaviour-log data layer for the Sixth Form System.

One row per pastoral entry, positive or negative. Each entry records:

* what happened (entry_type, category, description),
* how severe it was (severity, points),
* who logged it and where,
* what action was taken,
* whether follow-up is needed and whether parents have been contacted.

Cascade: deleting a student wipes their behaviour entries.

Built on top of the log:

* **Automatic escalation** — configurable thresholds
  (``behaviour_escalation_rules``: negative points within a rolling
  N days -> stage). Saving a negative entry checks the student and
  writes a ``behaviour_escalations`` row; stages set to refer on create
  a disciplinary case linked through ``related_behaviour_id``.
* **Learner agreement** — versioned text with student and parent
  acceptance dates per student.
* **Dress code / ID badge breaches** — each breach logs a negative
  "Uniform" behaviour entry with configurable points, so breaches feed
  the escalation thresholds.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system import paths
from education_system.systems.sixth_form.domain.pastoral import _records

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_BEHAVIOUR_DB

ENTRY_TYPES: tuple[str, ...] = ("Positive", "Negative")

SEVERITIES: tuple[str, ...] = ("Low", "Medium", "High")

POSITIVE_CATEGORIES: tuple[str, ...] = (
    "Excellent Work", "Participation", "Helpfulness", "Leadership",
    "Improvement", "Achievement", "Attendance", "Effort",
    "Community Contribution", "Other",
)

NEGATIVE_CATEGORIES: tuple[str, ...] = (
    "Lateness", "Punctuality", "Uniform", "Disruption", "Bullying",
    "Honesty", "Disrespect", "Missed Detention", "Vandalism",
    "Mobile Phone", "Plagiarism", "Truancy", "Other",
)

# Convenience: union for filter combos.
ALL_CATEGORIES: tuple[str, ...] = tuple(
    sorted(set(POSITIVE_CATEGORIES) | set(NEGATIVE_CATEGORIES)))

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS behaviour_entries (
    entry_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id         TEXT NOT NULL,
    entry_date         TEXT NOT NULL,
    entry_type         TEXT NOT NULL,
    category           TEXT NOT NULL,
    severity           TEXT,
    points             INTEGER NOT NULL DEFAULT 0,
    location           TEXT,
    description        TEXT NOT NULL,
    recorded_by        TEXT,
    action_taken       TEXT,
    follow_up_required INTEGER NOT NULL DEFAULT 0,
    follow_up_date     TEXT,
    parent_contacted   INTEGER NOT NULL DEFAULT 0,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_bh_student  ON behaviour_entries(student_id);
CREATE INDEX IF NOT EXISTS idx_bh_date     ON behaviour_entries(entry_date);
CREATE INDEX IF NOT EXISTS idx_bh_type     ON behaviour_entries(entry_type);
CREATE INDEX IF NOT EXISTS idx_bh_category ON behaviour_entries(category);
"""


@dataclass
class BehaviourEntry:
    entry_id: int
    student_id: str
    entry_date: str
    entry_type: str
    category: str
    severity: str | None
    points: int
    location: str | None
    description: str
    recorded_by: str | None
    action_taken: str | None
    follow_up_required: bool
    follow_up_date: str | None
    parent_contacted: bool
    created_at: str
    updated_at: str


@dataclass
class EntryRow:
    entry: BehaviourEntry
    student_name: str


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
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.executescript(_EXTRA_SCHEMA)
        conn.commit()
    logger.debug("Behaviour schema ready at %s", DB_PATH)

    _DB_READY = True


def _row(r: sqlite3.Row) -> BehaviourEntry:
    return BehaviourEntry(
        entry_id=r["entry_id"], student_id=r["student_id"],
        entry_date=r["entry_date"], entry_type=r["entry_type"],
        category=r["category"], severity=r["severity"],
        points=r["points"], location=r["location"],
        description=r["description"], recorded_by=r["recorded_by"],
        action_taken=r["action_taken"],
        follow_up_required=bool(r["follow_up_required"]),
        follow_up_date=r["follow_up_date"],
        parent_contacted=bool(r["parent_contacted"]),
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for any invalid behaviour input."""


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
    return s


def _coerce_bool(value: Any) -> int:
    if isinstance(value, str):
        return 1 if value.strip().lower() in ("1", "true", "yes", "y", "on") else 0
    return 1 if bool(value) else 0


def _validate_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    sid = _require(data.get("student_id"), "Student ID").strip()
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    out["student_id"] = sid

    out["entry_date"] = _validate_date(
        _require(data.get("entry_date"), "Entry date"), "Entry date")

    etype = _require(data.get("entry_type"), "Entry type").strip()
    if etype not in ENTRY_TYPES:
        raise ValidationError(
            f"Entry type must be one of: {', '.join(ENTRY_TYPES)}")
    out["entry_type"] = etype

    category = _require(data.get("category"), "Category").strip()
    allowed = (POSITIVE_CATEGORIES if etype == "Positive"
               else NEGATIVE_CATEGORIES)
    if category not in allowed:
        raise ValidationError(
            f"Category for {etype} entries must be one of: "
            f"{', '.join(allowed)}")
    out["category"] = category

    severity = (data.get("severity") or "").strip()
    if etype == "Negative":
        if not severity:
            raise ValidationError(
                "Severity is required for negative entries")
        if severity not in SEVERITIES:
            raise ValidationError(
                f"Severity must be one of: {', '.join(SEVERITIES)}")
        out["severity"] = severity
    else:
        # Positive: severity is optional, but if set must be valid.
        if severity and severity not in SEVERITIES:
            raise ValidationError(
                f"Severity must be one of: {', '.join(SEVERITIES)} (or blank)")
        out["severity"] = severity or None

    points = data.get("points")
    if points in (None, ""):
        # Sensible defaults: +5 positive, -5/-10/-20 by severity.
        if etype == "Positive":
            out["points"] = 5
        else:
            out["points"] = {"Low": -5, "Medium": -10, "High": -20}.get(
                out["severity"], -5)
    else:
        try:
            out["points"] = int(points)
        except (TypeError, ValueError):
            raise ValidationError("Points must be a whole number") from None

    out["description"] = _require(
        data.get("description"), "Description").strip()

    out["follow_up_date"] = _validate_date(
        data.get("follow_up_date"), "Follow-up date")
    out["follow_up_required"] = _coerce_bool(
        data.get("follow_up_required"))
    out["parent_contacted"] = _coerce_bool(data.get("parent_contacted"))

    out["location"]     = (data.get("location") or "").strip() or None
    out["recorded_by"]  = (data.get("recorded_by") or "").strip() or None
    out["action_taken"] = (data.get("action_taken") or "").strip() or None
    return out


# ── CRUD ───────────────────────────────────────────────────────────

def create_entry(data: dict[str, Any]) -> BehaviourEntry:
    init_db()
    try:
        p = _validate_payload(data)
    except ValidationError as e:
        logger.warning("create_entry validation failed: %s", e)
        raise
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO behaviour_entries
                   (student_id, entry_date, entry_type, category, severity,
                    points, location, description, recorded_by,
                    action_taken, follow_up_required, follow_up_date,
                    parent_contacted, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["student_id"], p["entry_date"], p["entry_type"],
             p["category"], p["severity"], p["points"],
             p["location"], p["description"], p["recorded_by"],
             p["action_taken"], p["follow_up_required"],
             p["follow_up_date"], p["parent_contacted"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_entry(new_id)
    assert out is not None
    logger.info(
        "Created behaviour entry #%d for %s "
        "(%s, %s, severity=%s, points=%d)",
        new_id, p["student_id"], p["entry_type"], p["category"],
        p["severity"] or "—", p["points"],
    )
    _escalate_after_save(out)
    return out


def get_entry(entry_id: int) -> BehaviourEntry | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM behaviour_entries WHERE entry_id = ?",
            (entry_id,),
        ).fetchone()
        return _row(r) if r else None


def list_entries(
    *,
    student_id: str | None = None,
    entry_type: str | None = None,
    category: str | None = None,
    severity: str | None = None,
    recorded_by_like: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    follow_up_required: bool | None = None,
) -> list[BehaviourEntry]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if entry_type:
        if entry_type not in ENTRY_TYPES:
            raise ValidationError(
                f"Entry type must be one of: {', '.join(ENTRY_TYPES)}")
        clauses.append("entry_type = ?")
        args.append(entry_type)
    if category:
        clauses.append("category = ?")
        args.append(category)
    if severity:
        if severity not in SEVERITIES:
            raise ValidationError(
                f"Severity must be one of: {', '.join(SEVERITIES)}")
        clauses.append("severity = ?")
        args.append(severity)
    if recorded_by_like:
        clauses.append("recorded_by LIKE ?")
        args.append(f"%{recorded_by_like.strip()}%")
    if date_from:
        clauses.append("entry_date >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("entry_date <= ?")
        args.append(_validate_date(date_to, "date_to"))
    if follow_up_required is not None:
        clauses.append("follow_up_required = ?")
        args.append(1 if follow_up_required else 0)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM behaviour_entries {where} "
           "ORDER BY entry_date DESC, entry_id DESC")
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def entries_for_student(student_id: str) -> list[BehaviourEntry]:
    return list_entries(student_id=student_id)


def list_entries_with_detail(**kwargs) -> list[EntryRow]:
    rows = list_entries(**kwargs)
    if not rows:
        return []
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    names = {s.student_id: s.full_name for s in _students.list_students()}
    return [EntryRow(entry=e,
                      student_name=names.get(e.student_id, "(unknown)"))
            for e in rows]


def update_entry(entry_id: int, data: dict[str, Any]) -> BehaviourEntry:
    init_db()
    existing = get_entry(entry_id)
    if existing is None:
        logger.warning("update_entry: unknown id %d", entry_id)
        raise ValidationError(f"No entry with id {entry_id}")
    p = _validate_payload({
        "student_id":        existing.student_id,
        "entry_date":        data.get("entry_date", existing.entry_date),
        "entry_type":        data.get("entry_type", existing.entry_type),
        "category":          data.get("category", existing.category),
        "severity":          data.get("severity", existing.severity),
        "points":            data.get("points", existing.points),
        "location":          data.get("location", existing.location),
        "description":       data.get("description", existing.description),
        "recorded_by":       data.get("recorded_by", existing.recorded_by),
        "action_taken":      data.get("action_taken", existing.action_taken),
        "follow_up_required": data.get("follow_up_required",
                                        existing.follow_up_required),
        "follow_up_date":    data.get("follow_up_date",
                                       existing.follow_up_date),
        "parent_contacted":  data.get("parent_contacted",
                                       existing.parent_contacted),
    })
    with _connect() as conn:
        conn.execute(
            """UPDATE behaviour_entries SET
                   entry_date = ?, entry_type = ?, category = ?,
                   severity = ?, points = ?, location = ?,
                   description = ?, recorded_by = ?, action_taken = ?,
                   follow_up_required = ?, follow_up_date = ?,
                   parent_contacted = ?, updated_at = datetime('now')
               WHERE entry_id = ?""",
            (p["entry_date"], p["entry_type"], p["category"],
             p["severity"], p["points"], p["location"],
             p["description"], p["recorded_by"], p["action_taken"],
             p["follow_up_required"], p["follow_up_date"],
             p["parent_contacted"], entry_id),
        )
        conn.commit()
    out = get_entry(entry_id)
    assert out is not None
    logger.info("Updated behaviour entry #%d (points=%d, follow_up=%s)",
                entry_id, out.points, out.follow_up_required)
    _escalate_after_save(out)
    return out


def delete_entry(entry_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM behaviour_entries WHERE entry_id = ?",
            (entry_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted behaviour entry #%d", entry_id)
            return True
        logger.warning("delete_entry: unknown id %d", entry_id)
        return False


# ── Summaries ─────────────────────────────────────────────────────

@dataclass
class StudentBehaviourSummary:
    student_id: str
    total_entries: int
    positive_count: int
    negative_count: int
    net_points: int
    open_follow_ups: int


def per_student_summary(student_id: str) -> StudentBehaviourSummary:
    rows = entries_for_student(student_id)
    pos = sum(1 for r in rows if r.entry_type == "Positive")
    neg = sum(1 for r in rows if r.entry_type == "Negative")
    net = sum(r.points for r in rows)
    open_fu = sum(1 for r in rows if r.follow_up_required)
    return StudentBehaviourSummary(
        student_id=student_id, total_entries=len(rows),
        positive_count=pos, negative_count=neg,
        net_points=net, open_follow_ups=open_fu,
    )


@dataclass
class Summary:
    total: int
    by_type: dict[str, int]
    by_category: dict[str, int]
    by_severity: dict[str, int]
    net_points: int
    follow_ups_open: int
    upcoming_follow_ups: int  # follow_up_date within window
    parents_contacted: int
    top_students_by_count: list[tuple[str, int]]  # (student_id, count)


def summary(
    *,
    upcoming_window_days: int = 14,
    top_n: int = 10,
) -> Summary:
    import datetime as _dt
    init_db()
    rows = list_entries()
    today = _dt.date.today().isoformat()
    cutoff = (_dt.date.today() + _dt.timedelta(days=upcoming_window_days)
              ).isoformat()

    by_type = {t: 0 for t in ENTRY_TYPES}
    by_category: dict[str, int] = {}
    by_severity = {s: 0 for s in SEVERITIES}
    net_points = 0
    follow_ups_open = 0
    upcoming = 0
    parents = 0
    per_student_count: dict[str, int] = {}
    for r in rows:
        by_type[r.entry_type] = by_type.get(r.entry_type, 0) + 1
        by_category[r.category] = by_category.get(r.category, 0) + 1
        if r.severity:
            by_severity[r.severity] = by_severity.get(r.severity, 0) + 1
        net_points += r.points
        if r.follow_up_required:
            follow_ups_open += 1
            if r.follow_up_date and today <= r.follow_up_date <= cutoff:
                upcoming += 1
        if r.parent_contacted:
            parents += 1
        per_student_count[r.student_id] = per_student_count.get(
            r.student_id, 0) + 1
    top = sorted(per_student_count.items(),
                 key=lambda kv: -kv[1])[:top_n]
    return Summary(
        total=len(rows), by_type=by_type, by_category=by_category,
        by_severity=by_severity, net_points=net_points,
        follow_ups_open=follow_ups_open,
        upcoming_follow_ups=upcoming,
        parents_contacted=parents,
        top_students_by_count=top,
    )


# ══ Escalation thresholds, learner agreement, dress code ══════════

ESCALATION_STAGES: tuple[str, ...] = (
    "Tutor Conversation",
    "Head of Year Meeting",
    "Parent Meeting",
    "Behaviour Contract",
    "Disciplinary Referral",
)
ESCALATION_STATUSES: tuple[str, ...] = ("Open", "Actioned", "Closed")

#: Disciplinary case type a stage raises when it is set to refer.
STAGE_CASE_TYPES: dict[str, str] = {
    "Tutor Conversation": "Verbal Warning",
    "Head of Year Meeting": "Written Warning",
    "Parent Meeting": "Parent Meeting",
    "Behaviour Contract": "Behaviour Contract",
    "Disciplinary Referral": "Final Written Warning",
}

#: Suggested starting thresholds (negative points in a rolling window).
#: Loaded only when someone asks (install_suggested_rules).
SUGGESTED_RULES: tuple[tuple[str, int, int, bool], ...] = (
    # stage,                 points, window days, raise disciplinary case
    ("Tutor Conversation",     15, 14, False),
    ("Head of Year Meeting",   30, 28, False),
    ("Parent Meeting",         45, 42, True),
    ("Behaviour Contract",     60, 56, True),
    ("Disciplinary Referral",  80, 70, True),
)

AGREEMENT_METHODS: tuple[str, ...] = (
    "Paper", "Online", "In person", "E-mail",
)

BREACH_TYPES: tuple[str, ...] = (
    "ID Badge Forgotten", "ID Badge Not Worn", "Lanyard Missing",
    "Dress Code", "Footwear", "Offensive Clothing", "Other",
)
#: Default negative points per breach (override with set_breach_points).
DEFAULT_BREACH_POINTS: dict[str, int] = {
    "ID Badge Forgotten": -2,
    "ID Badge Not Worn": -2,
    "Lanyard Missing": -1,
    "Dress Code": -3,
    "Footwear": -2,
    "Offensive Clothing": -10,
    "Other": -2,
}

_EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS behaviour_escalation_rules (
    rule_id                INTEGER PRIMARY KEY AUTOINCREMENT,
    stage                  TEXT NOT NULL UNIQUE,
    points_threshold       INTEGER NOT NULL,
    window_days            INTEGER NOT NULL,
    raise_disciplinary     INTEGER NOT NULL DEFAULT 0,
    disciplinary_case_type TEXT,
    active                 INTEGER NOT NULL DEFAULT 1,
    notes                  TEXT,
    created_at             TEXT DEFAULT (datetime('now')),
    updated_at             TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS behaviour_escalations (
    escalation_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id           TEXT NOT NULL,
    rule_id              INTEGER,
    stage                TEXT NOT NULL,
    triggered_on         TEXT NOT NULL,
    window_start         TEXT NOT NULL,
    window_days          INTEGER NOT NULL,
    points_in_window     INTEGER NOT NULL,
    threshold            INTEGER NOT NULL,
    trigger_entry_id     INTEGER,
    status               TEXT NOT NULL DEFAULT 'Open',
    assigned_to          TEXT,
    actioned_on          TEXT,
    outcome              TEXT,
    disciplinary_case_id INTEGER,
    notes                TEXT,
    created_at           TEXT DEFAULT (datetime('now')),
    updated_at           TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (rule_id) REFERENCES behaviour_escalation_rules(rule_id)
        ON DELETE SET NULL,
    FOREIGN KEY (trigger_entry_id) REFERENCES behaviour_entries(entry_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS learner_agreement_versions (
    version_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    version_label   TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    body_text       TEXT NOT NULL,
    effective_from  TEXT NOT NULL,
    is_current      INTEGER NOT NULL DEFAULT 0,
    created_by      TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS learner_agreement_signatures (
    signature_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id          INTEGER NOT NULL,
    student_id          TEXT NOT NULL,
    student_accepted_on TEXT,
    student_method      TEXT,
    parent_name         TEXT,
    parent_accepted_on  TEXT,
    parent_method       TEXT,
    witnessed_by        TEXT,
    notes               TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now')),
    UNIQUE (version_id, student_id),
    FOREIGN KEY (version_id) REFERENCES learner_agreement_versions(version_id)
        ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS dress_code_breaches (
    breach_id               INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id              TEXT NOT NULL,
    breach_date             TEXT NOT NULL,
    breach_type             TEXT NOT NULL,
    description             TEXT,
    recorded_by             TEXT,
    temporary_badge_issued  INTEGER NOT NULL DEFAULT 0,
    behaviour_entry_id      INTEGER,
    notes                   TEXT,
    created_at              TEXT DEFAULT (datetime('now')),
    updated_at              TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (behaviour_entry_id) REFERENCES behaviour_entries(entry_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS dress_code_points (
    breach_type TEXT PRIMARY KEY,
    points      INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bhe_student ON behaviour_escalations(student_id);
CREATE INDEX IF NOT EXISTS idx_bhe_status  ON behaviour_escalations(status);
CREATE INDEX IF NOT EXISTS idx_las_student ON learner_agreement_signatures(student_id);
CREATE INDEX IF NOT EXISTS idx_dcb_student ON dress_code_breaches(student_id);
CREATE INDEX IF NOT EXISTS idx_dcb_date    ON dress_code_breaches(breach_date);
"""


@dataclass
class EscalationRule:
    rule_id: int
    stage: str
    points_threshold: int
    window_days: int
    raise_disciplinary: bool
    disciplinary_case_type: str | None
    active: bool
    notes: str | None
    created_at: str | None
    updated_at: str | None

    @property
    def stage_order(self) -> int:
        return ESCALATION_STAGES.index(self.stage)


@dataclass
class Escalation:
    escalation_id: int
    student_id: str
    rule_id: int | None
    stage: str
    triggered_on: str
    window_start: str
    window_days: int
    points_in_window: int
    threshold: int
    trigger_entry_id: int | None
    status: str
    assigned_to: str | None
    actioned_on: str | None
    outcome: str | None
    disciplinary_case_id: int | None
    notes: str | None
    created_at: str | None
    updated_at: str | None


@dataclass
class AgreementVersion:
    version_id: int
    version_label: str
    title: str
    body_text: str
    effective_from: str
    is_current: bool
    created_by: str | None
    notes: str | None
    created_at: str | None
    updated_at: str | None


@dataclass
class AgreementSignature:
    signature_id: int
    version_id: int
    student_id: str
    student_accepted_on: str | None
    student_method: str | None
    parent_name: str | None
    parent_accepted_on: str | None
    parent_method: str | None
    witnessed_by: str | None
    notes: str | None
    created_at: str | None
    updated_at: str | None


@dataclass
class DressCodeBreach:
    breach_id: int
    student_id: str
    breach_date: str
    breach_type: str
    description: str | None
    recorded_by: str | None
    temporary_badge_issued: bool
    behaviour_entry_id: int | None
    notes: str | None
    created_at: str | None
    updated_at: str | None


def _case_types() -> tuple[str, ...]:
    from education_system.systems.sixth_form.domain.pastoral.disciplinary import (
        disciplinary as _disc,
    )
    return _disc.CASE_TYPES


_C = _records.Col

RULE_SPEC = _records.TableSpec(
    table="behaviour_escalation_rules", id_col="rule_id",
    row_type=EscalationRule, label="Escalation threshold",
    order_by="points_threshold",
    cols=(
        _C("stage", "Stage", "choice", required=True,
           choices=ESCALATION_STAGES),
        _C("points_threshold", "Negative points ≥", "int", required=True,
           min_value=1),
        _C("window_days", "Within rolling days", "int", required=True,
           min_value=1, max_value=365),
        _C("raise_disciplinary", "Open a disciplinary case", "bool"),
        _C("disciplinary_case_type", "Case type (blank = stage default)",
           listed=False),
        _C("active", "Active", "bool", default=True),
        _C("notes", "Notes", "multiline", listed=False),
    ))

ESCALATION_SPEC = _records.TableSpec(
    table="behaviour_escalations", id_col="escalation_id",
    row_type=Escalation, label="Escalation",
    order_by="triggered_on DESC, escalation_id DESC",
    cols=(
        _C("student_id", "Student", "student", required=True, fixed=True),
        _C("stage", "Stage", "choice", choices=ESCALATION_STAGES,
           fixed=True),
        _C("triggered_on", "Triggered", "date", fixed=True),
        _C("points_in_window", "Points", "int", fixed=True),
        _C("window_days", "Window (days)", "int", fixed=True, listed=False),
        _C("status", "Status", "choice", choices=ESCALATION_STATUSES,
           default="Open"),
        _C("assigned_to", "Assigned to"),
        _C("actioned_on", "Actioned on", "date"),
        _C("outcome", "Outcome", "multiline"),
        _C("disciplinary_case_id", "Disciplinary case #", "int",
           fixed=True),
        _C("notes", "Notes", "multiline", listed=False),
    ))

VERSION_SPEC = _records.TableSpec(
    table="learner_agreement_versions", id_col="version_id",
    row_type=AgreementVersion, label="Learner agreement version",
    order_by="effective_from DESC, version_id DESC",
    cols=(
        _C("version_label", "Version (e.g. 2026/27 v1)", required=True),
        _C("title", "Title", required=True,
           default="Sixth Form Learner Agreement"),
        _C("body_text", "Agreement text", "multiline", required=True,
           listed=False),
        _C("effective_from", "Effective from", "date", required=True,
           default=_records.today),
        _C("is_current", "Current version", "bool", fixed=True),
        _C("created_by", "Created by"),
        _C("notes", "Notes", "multiline", listed=False),
    ))

SIGNATURE_SPEC = _records.TableSpec(
    table="learner_agreement_signatures", id_col="signature_id",
    row_type=AgreementSignature, label="Learner agreement acceptance",
    order_by="student_id",
    cols=(
        _C("version_id", "Version #", "int", required=True, fixed=True),
        _C("student_id", "Student", "student", required=True, fixed=True),
        _C("student_accepted_on", "Student accepted on", "date"),
        _C("student_method", "Student method", "choice",
           choices=AGREEMENT_METHODS),
        _C("parent_name", "Parent / carer name"),
        _C("parent_accepted_on", "Parent accepted on", "date"),
        _C("parent_method", "Parent method", "choice",
           choices=AGREEMENT_METHODS),
        _C("witnessed_by", "Witnessed by", listed=False),
        _C("notes", "Notes", "multiline", listed=False),
    ))

BREACH_SPEC = _records.TableSpec(
    table="dress_code_breaches", id_col="breach_id",
    row_type=DressCodeBreach, label="Dress code / ID badge breach",
    order_by="breach_date DESC, breach_id DESC",
    cols=(
        _C("student_id", "Student", "student", required=True, fixed=True),
        _C("breach_date", "Date", "date", required=True,
           default=_records.today),
        _C("breach_type", "Breach", "choice", required=True,
           choices=BREACH_TYPES),
        _C("description", "Details"),
        _C("recorded_by", "Recorded by"),
        _C("temporary_badge_issued", "Temporary badge issued", "bool"),
        _C("behaviour_entry_id", "Behaviour entry #", "int", fixed=True,
           hidden=True),
        _C("notes", "Notes", "multiline", listed=False),
    ))


def _student_ok(sid: str) -> bool:
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    return _students.get_student(sid) is not None


# ── Escalation rules ──────────────────────────────────────────────

def _rule_rules(p: dict[str, Any]) -> None:
    ct = (p.get("disciplinary_case_type") or "").strip() or None
    if ct and ct not in _case_types():
        raise ValidationError(
            f"Case type must be one of: {', '.join(_case_types())}")
    p["disciplinary_case_type"] = ct


def _check_rule_order(conn: sqlite3.Connection) -> None:
    """Later stages must need at least as many points as earlier ones."""
    rules = _records.select(conn, RULE_SPEC, where=["active = 1"])
    rules.sort(key=lambda r: r.stage_order)
    for a, b in zip(rules, rules[1:]):
        if b.points_threshold < a.points_threshold:
            raise ValidationError(
                f"'{b.stage}' needs at least as many points as "
                f"'{a.stage}' ({a.points_threshold})")


def create_rule(data: dict[str, Any]) -> EscalationRule:
    init_db()
    p = _records.validate(RULE_SPEC, data, error=ValidationError)
    _rule_rules(p)
    with _connect() as conn:
        try:
            new_id = _records.insert(conn, RULE_SPEC, p)
        except sqlite3.IntegrityError as e:
            raise ValidationError(
                f"There is already a threshold for {p['stage']}") from e
        _check_rule_order(conn)
        conn.commit()
        return _records.fetch(conn, RULE_SPEC, new_id)


def list_rules(*, active_only: bool = False) -> list[EscalationRule]:
    init_db()
    with _connect() as conn:
        rows = _records.select(conn, RULE_SPEC,
                               where=["active = 1"] if active_only else [])
    return sorted(rows, key=lambda r: r.stage_order)


def update_rule(rule_id: int, data: dict[str, Any]) -> EscalationRule:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, RULE_SPEC, rule_id)
        if existing is None:
            raise ValidationError(f"No threshold #{rule_id}")
        p = _records.validate(RULE_SPEC, data, error=ValidationError,
                              existing=existing)
        _rule_rules(p)
        try:
            _records.update(conn, RULE_SPEC, rule_id, p)
        except sqlite3.IntegrityError as e:
            raise ValidationError(
                f"There is already a threshold for {p['stage']}") from e
        _check_rule_order(conn)
        conn.commit()
        return _records.fetch(conn, RULE_SPEC, rule_id)


def delete_rule(rule_id: int) -> bool:
    init_db()
    with _connect() as conn:
        ok = _records.delete(conn, RULE_SPEC, rule_id)
        conn.commit()
        return ok


def install_suggested_rules() -> list[EscalationRule]:
    """Add SUGGESTED_RULES for any stage that has no threshold yet."""
    init_db()
    have = {r.stage for r in list_rules()}
    for stage, pts, days, refer in SUGGESTED_RULES:
        if stage not in have:
            create_rule({"stage": stage, "points_threshold": pts,
                         "window_days": days, "raise_disciplinary": refer,
                         "active": True})
    return list_rules()


# ── Escalation engine ─────────────────────────────────────────────

def negative_points(student_id: str, *, window_days: int,
                    as_of: str | None = None) -> tuple[int, str]:
    """Total negative points (as a positive number) in the rolling
    window ending *as_of*. Returns (points, window_start)."""
    import datetime as _dt
    end = _records.check_date(as_of, "As of", ValidationError) \
        or _records.today()
    start = (_dt.date.fromisoformat(end)
             - _dt.timedelta(days=int(window_days) - 1)).isoformat()
    with _connect() as conn:
        r = conn.execute(
            "SELECT COALESCE(SUM(-points), 0) FROM behaviour_entries "
            "WHERE student_id = ? AND entry_type = 'Negative' "
            "AND points < 0 AND entry_date BETWEEN ? AND ?",
            (student_id, start, end)).fetchone()
    return int(r[0] or 0), start


def check_escalation(student_id: str, *, as_of: str | None = None,
                     trigger_entry_id: int | None = None
                     ) -> Escalation | None:
    """Escalate *student_id* to the highest stage whose threshold is
    met, unless that stage (or a later one) was already triggered
    inside its window. Returns the new escalation, or None."""
    init_db()
    rules = list_rules(active_only=True)
    if not rules:
        return None
    as_of = _records.check_date(as_of, "As of", ValidationError) \
        or _records.today()
    met: list[tuple[EscalationRule, int, str]] = []
    for rule in rules:
        pts, start = negative_points(student_id, window_days=rule.window_days,
                                     as_of=as_of)
        if pts >= rule.points_threshold:
            met.append((rule, pts, start))
    if not met:
        return None
    rule, pts, start = max(met, key=lambda m: m[0].stage_order)
    later = ESCALATION_STAGES[rule.stage_order:]
    with _connect() as conn:
        dup = conn.execute(
            "SELECT escalation_id FROM behaviour_escalations "
            "WHERE student_id = ? AND triggered_on >= ? AND stage IN (%s)"
            % ",".join("?" * len(later)),
            (student_id, start, *later)).fetchone()
    if dup is not None:
        return None
    values = {
        "student_id": student_id, "rule_id": rule.rule_id,
        "stage": rule.stage, "triggered_on": as_of,
        "window_start": start, "window_days": rule.window_days,
        "points_in_window": pts, "threshold": rule.points_threshold,
        "trigger_entry_id": trigger_entry_id, "status": "Open",
    }
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO behaviour_escalations (student_id, rule_id, stage, "
            "triggered_on, window_start, window_days, points_in_window, "
            "threshold, trigger_entry_id, status, created_at, updated_at) "
            "VALUES (:student_id, :rule_id, :stage, :triggered_on, "
            ":window_start, :window_days, :points_in_window, :threshold, "
            ":trigger_entry_id, :status, datetime('now'), datetime('now'))",
            values)
        esc_id = cur.lastrowid
        conn.commit()
    logger.info("Behaviour escalation #%d: %s reached '%s' (%d points in "
                "%d days, threshold %d)", esc_id, student_id, rule.stage,
                pts, rule.window_days, rule.points_threshold)
    if rule.raise_disciplinary:
        case_id = _open_disciplinary_case(student_id, rule, pts, as_of,
                                          trigger_entry_id)
        with _connect() as conn:
            conn.execute(
                "UPDATE behaviour_escalations SET disciplinary_case_id = ?, "
                "updated_at = datetime('now') WHERE escalation_id = ?",
                (case_id, esc_id))
            conn.commit()
    return get_escalation(esc_id)


def _open_disciplinary_case(student_id: str, rule: EscalationRule,
                            points: int, as_of: str,
                            trigger_entry_id: int | None) -> int:
    from education_system.systems.sixth_form.domain.pastoral.disciplinary import (
        disciplinary as _disc,
    )
    case = _disc.create_case({
        "student_id": student_id,
        "incident_date": as_of,
        "reported_on": _records.today(),
        "case_type": (rule.disciplinary_case_type
                      or STAGE_CASE_TYPES[rule.stage]),
        "severity": min(5, rule.stage_order + 1),
        "title": f"Behaviour points escalation: {rule.stage}",
        "description": (f"{points} negative behaviour points in the "
                        f"{rule.window_days} days to {as_of} (threshold "
                        f"{rule.points_threshold})."),
        "related_behaviour_id": trigger_entry_id,
        "status": "Reported",
        "issued_by": "Behaviour escalation",
    })
    return case.case_id


def _escalate_after_save(entry: BehaviourEntry) -> None:
    """Run the escalation check after a negative entry is saved. A
    failure is logged, never allowed to lose the behaviour entry."""
    if entry.entry_type != "Negative" or entry.points >= 0:
        return
    try:
        check_escalation(entry.student_id, as_of=entry.entry_date,
                         trigger_entry_id=entry.entry_id)
    except Exception:
        logger.exception("Behaviour escalation check failed for %s "
                         "(entry #%d)", entry.student_id, entry.entry_id)


def run_escalation_check(*, as_of: str | None = None) -> list[Escalation]:
    """Check every student with negative entries (e.g. after changing
    thresholds). Returns the escalations created."""
    init_db()
    with _connect() as conn:
        sids = [r[0] for r in conn.execute(
            "SELECT DISTINCT student_id FROM behaviour_entries "
            "WHERE entry_type = 'Negative'")]
    out = []
    for sid in sids:
        esc = check_escalation(sid, as_of=as_of)
        if esc is not None:
            out.append(esc)
    return out


def get_escalation(escalation_id: int) -> Escalation | None:
    init_db()
    with _connect() as conn:
        return _records.fetch(conn, ESCALATION_SPEC, escalation_id)


def list_escalations(*, student_id: str | None = None,
                     status: str | None = None,
                     stage: str | None = None) -> list[Escalation]:
    init_db()
    with _connect() as conn:
        return _records.select(conn, ESCALATION_SPEC, equals={
            "student_id": student_id, "status": status, "stage": stage})


def update_escalation(escalation_id: int,
                      data: dict[str, Any]) -> Escalation:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, ESCALATION_SPEC, escalation_id)
        if existing is None:
            raise ValidationError(f"No escalation #{escalation_id}")
        p = _records.validate(ESCALATION_SPEC, data, error=ValidationError,
                              existing=existing)
        if p["status"] in ("Actioned", "Closed") and not p["actioned_on"]:
            p["actioned_on"] = _records.today()
        _records.update(conn, ESCALATION_SPEC, escalation_id, p)
        conn.commit()
        return _records.fetch(conn, ESCALATION_SPEC, escalation_id)


def action_escalation(escalation_id: int, *, outcome: str,
                      close: bool = False) -> Escalation:
    if not (outcome or "").strip():
        raise ValidationError("Outcome is required")
    return update_escalation(escalation_id, {
        "outcome": outcome.strip(),
        "status": "Closed" if close else "Actioned",
        "actioned_on": _records.today()})


def delete_escalation(escalation_id: int) -> bool:
    init_db()
    with _connect() as conn:
        ok = _records.delete(conn, ESCALATION_SPEC, escalation_id)
        conn.commit()
        return ok


# ── Learner agreement ─────────────────────────────────────────────

def create_agreement_version(data: dict[str, Any]) -> AgreementVersion:
    init_db()
    p = _records.validate(VERSION_SPEC, data, error=ValidationError)
    p["is_current"] = 0
    with _connect() as conn:
        try:
            new_id = _records.insert(conn, VERSION_SPEC, p)
        except sqlite3.IntegrityError as e:
            raise ValidationError(
                f"Version '{p['version_label']}' already exists") from e
        first = conn.execute("SELECT COUNT(*) FROM learner_agreement_versions"
                             ).fetchone()[0] == 1
        if first:
            conn.execute("UPDATE learner_agreement_versions "
                         "SET is_current = 1 WHERE version_id = ?", (new_id,))
        conn.commit()
        return _records.fetch(conn, VERSION_SPEC, new_id)


def list_agreement_versions() -> list[AgreementVersion]:
    init_db()
    with _connect() as conn:
        return _records.select(conn, VERSION_SPEC)


def get_agreement_version(version_id: int) -> AgreementVersion | None:
    init_db()
    with _connect() as conn:
        return _records.fetch(conn, VERSION_SPEC, version_id)


def current_agreement_version() -> AgreementVersion | None:
    init_db()
    with _connect() as conn:
        rows = _records.select(conn, VERSION_SPEC, where=["is_current = 1"],
                               limit=1)
    return rows[0] if rows else None


def update_agreement_version(version_id: int,
                             data: dict[str, Any]) -> AgreementVersion:
    """Edit a version. Once anyone has accepted it, its text is frozen:
    publish a new version instead."""
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, VERSION_SPEC, version_id)
        if existing is None:
            raise ValidationError(f"No agreement version #{version_id}")
        p = _records.validate(VERSION_SPEC, data, error=ValidationError,
                              existing=existing)
        signed = conn.execute(
            "SELECT COUNT(*) FROM learner_agreement_signatures "
            "WHERE version_id = ?", (version_id,)).fetchone()[0]
        if signed and (p["body_text"] != existing.body_text
                       or p["title"] != existing.title):
            raise ValidationError(
                f"{signed} acceptance(s) recorded against this version — "
                "its text cannot change. Create a new version.")
        try:
            _records.update(conn, VERSION_SPEC, version_id, p)
        except sqlite3.IntegrityError as e:
            raise ValidationError(
                f"Version '{p['version_label']}' already exists") from e
        conn.commit()
        return _records.fetch(conn, VERSION_SPEC, version_id)


def set_current_agreement_version(version_id: int) -> AgreementVersion:
    init_db()
    with _connect() as conn:
        if _records.fetch(conn, VERSION_SPEC, version_id) is None:
            raise ValidationError(f"No agreement version #{version_id}")
        conn.execute("UPDATE learner_agreement_versions SET is_current = 0 "
                     "WHERE is_current = 1")
        conn.execute("UPDATE learner_agreement_versions SET is_current = 1, "
                     "updated_at = datetime('now') WHERE version_id = ?",
                     (version_id,))
        conn.commit()
        return _records.fetch(conn, VERSION_SPEC, version_id)


def delete_agreement_version(version_id: int) -> bool:
    init_db()
    with _connect() as conn:
        signed = conn.execute(
            "SELECT COUNT(*) FROM learner_agreement_signatures "
            "WHERE version_id = ?", (version_id,)).fetchone()[0]
        if signed:
            raise ValidationError(
                f"{signed} acceptance(s) recorded — a signed version "
                "cannot be deleted")
        ok = _records.delete(conn, VERSION_SPEC, version_id)
        conn.commit()
        return ok


def _signature_rules(p: dict[str, Any]) -> None:
    if not p["student_accepted_on"] and not p["parent_accepted_on"]:
        raise ValidationError(
            "Record a student and/or parent acceptance date")
    if p["parent_accepted_on"] and not p["parent_name"]:
        raise ValidationError("Give the parent / carer's name")


def record_agreement_acceptance(data: dict[str, Any]) -> AgreementSignature:
    """Record (or add to) a student's acceptance of a version. Fields
    left blank keep any value already recorded, so the student and the
    parent can sign on different days."""
    init_db()
    vid = data.get("version_id")
    if vid in (None, ""):
        cur_v = current_agreement_version()
        if cur_v is None:
            raise ValidationError("No learner agreement version exists yet")
        data = {**data, "version_id": cur_v.version_id}
    with _connect() as conn:
        try:
            ver = int(data["version_id"])
        except (TypeError, ValueError):
            raise ValidationError("Version must be a number") from None
        if _records.fetch(conn, VERSION_SPEC, ver) is None:
            raise ValidationError(f"No agreement version #{ver}")
        sid = str(data.get("student_id") or "").strip()
        r = conn.execute(
            "SELECT * FROM learner_agreement_signatures "
            "WHERE version_id = ? AND student_id = ?", (ver, sid)).fetchone()
        existing = _records.to_row(SIGNATURE_SPEC, r) if r else None
    if existing is not None:
        keep = {k: v for k, v in data.items() if v not in (None, "")}
        p = _records.validate(SIGNATURE_SPEC, keep, error=ValidationError,
                              existing=existing)
    else:
        p = _records.validate(SIGNATURE_SPEC, data, error=ValidationError,
                              student_exists=_student_ok)
    _signature_rules(p)
    with _connect() as conn:
        if existing is not None:
            _records.update(conn, SIGNATURE_SPEC, existing.signature_id, p)
            sig_id = existing.signature_id
        else:
            sig_id = _records.insert(conn, SIGNATURE_SPEC, p)
        conn.commit()
        return _records.fetch(conn, SIGNATURE_SPEC, sig_id)


def list_agreement_acceptances(*, version_id: int | None = None,
                               student_id: str | None = None
                               ) -> list[AgreementSignature]:
    init_db()
    with _connect() as conn:
        return _records.select(conn, SIGNATURE_SPEC, equals={
            "version_id": version_id, "student_id": student_id})


def update_agreement_acceptance(signature_id: int,
                                data: dict[str, Any]) -> AgreementSignature:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, SIGNATURE_SPEC, signature_id)
        if existing is None:
            raise ValidationError(f"No acceptance #{signature_id}")
        p = _records.validate(SIGNATURE_SPEC, data, error=ValidationError,
                              existing=existing)
        _signature_rules(p)
        _records.update(conn, SIGNATURE_SPEC, signature_id, p)
        conn.commit()
        return _records.fetch(conn, SIGNATURE_SPEC, signature_id)


def delete_agreement_acceptance(signature_id: int) -> bool:
    init_db()
    with _connect() as conn:
        ok = _records.delete(conn, SIGNATURE_SPEC, signature_id)
        conn.commit()
        return ok


@dataclass
class OutstandingAgreement:
    student_id: str
    student_name: str
    student_signed: bool
    parent_needed: bool
    parent_signed: bool


def _is_adult(dob: str | None) -> bool:
    import datetime as _dt
    if not dob:
        return False
    try:
        d = _dt.date.fromisoformat(str(dob)[:10])
    except ValueError:
        return False
    t = _dt.date.today()
    return (t.year - d.year - ((t.month, t.day) < (d.month, d.day))) >= 18


def outstanding_agreements(version_id: int | None = None
                           ) -> list[OutstandingAgreement]:
    """Students who have not fully accepted a version (default: the
    current one). Parent acceptance is not needed once a student is 18."""
    ver = (get_agreement_version(version_id) if version_id
           else current_agreement_version())
    if ver is None:
        return []
    sigs = {s.student_id: s for s in
            list_agreement_acceptances(version_id=ver.version_id)}
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    out = []
    for st in _students.list_students():
        if getattr(st, "status", "Active") in ("Inactive", "Left"):
            continue
        s = sigs.get(st.student_id)
        parent_needed = not _is_adult(getattr(st, "date_of_birth", None))
        student_ok = bool(s and s.student_accepted_on)
        parent_ok = bool(s and s.parent_accepted_on)
        if student_ok and (parent_ok or not parent_needed):
            continue
        out.append(OutstandingAgreement(st.student_id, st.full_name,
                                        student_ok, parent_needed,
                                        parent_ok))
    return out


# ── Dress code / ID badge breaches ────────────────────────────────

def breach_points() -> dict[str, int]:
    init_db()
    out = dict(DEFAULT_BREACH_POINTS)
    with _connect() as conn:
        for r in conn.execute("SELECT breach_type, points "
                              "FROM dress_code_points"):
            out[r["breach_type"]] = int(r["points"])
    return out


def set_breach_points(breach_type: str, points: int) -> dict[str, int]:
    if breach_type not in BREACH_TYPES:
        raise ValidationError(
            f"Breach must be one of: {', '.join(BREACH_TYPES)}")
    try:
        pts = int(points)
    except (TypeError, ValueError):
        raise ValidationError("Points must be a whole number") from None
    if pts > 0:
        pts = -pts          # breaches always cost points
    init_db()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO dress_code_points (breach_type, points) "
            "VALUES (?, ?) ON CONFLICT(breach_type) DO UPDATE SET "
            "points = excluded.points", (breach_type, pts))
        conn.commit()
    return breach_points()


def record_breach(data: dict[str, Any]) -> DressCodeBreach:
    """Log a breach and the matching negative "Uniform" behaviour entry
    (which in turn runs the escalation check)."""
    init_db()
    p = _records.validate(BREACH_SPEC, data, error=ValidationError,
                          student_exists=_student_ok)
    p["recorded_by"] = p["recorded_by"] or _records.current_username()
    pts = breach_points()[p["breach_type"]]
    if pts:
        desc = p["breach_type"] + (f": {p['description']}"
                                   if p["description"] else "")
        entry = create_entry({
            "student_id": p["student_id"],
            "entry_date": p["breach_date"],
            "entry_type": "Negative",
            "category": "Uniform",
            "severity": "Low" if pts > -5 else "Medium",
            "points": pts,
            "description": desc,
            "recorded_by": p["recorded_by"],
            "action_taken": ("Temporary badge issued"
                             if p["temporary_badge_issued"] else None),
        })
        p["behaviour_entry_id"] = entry.entry_id
    with _connect() as conn:
        new_id = _records.insert(conn, BREACH_SPEC, p)
        conn.commit()
        out = _records.fetch(conn, BREACH_SPEC, new_id)
    logger.info("Recorded %s for %s (%d points)", p["breach_type"],
                p["student_id"], pts)
    return out


def list_breaches(*, student_id: str | None = None,
                  breach_type: str | None = None,
                  date_from: str | None = None,
                  date_to: str | None = None) -> list[DressCodeBreach]:
    init_db()
    where, args = [], []
    if date_from:
        where.append("breach_date >= ?")
        args.append(_records.check_date(date_from, "From", ValidationError))
    if date_to:
        where.append("breach_date <= ?")
        args.append(_records.check_date(date_to, "To", ValidationError))
    with _connect() as conn:
        return _records.select(conn, BREACH_SPEC, equals={
            "student_id": student_id, "breach_type": breach_type},
            where=where, args=args)


def update_breach(breach_id: int, data: dict[str, Any]) -> DressCodeBreach:
    """Edit breach details. The linked behaviour entry keeps its points;
    edit it in the Behaviour Log if they need changing."""
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, BREACH_SPEC, breach_id)
        if existing is None:
            raise ValidationError(f"No breach #{breach_id}")
        p = _records.validate(BREACH_SPEC, data, error=ValidationError,
                              existing=existing)
        _records.update(conn, BREACH_SPEC, breach_id, p)
        conn.commit()
        return _records.fetch(conn, BREACH_SPEC, breach_id)


def delete_breach(breach_id: int, *, delete_points: bool = True) -> bool:
    """Delete a breach logged in error, with its behaviour entry."""
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, BREACH_SPEC, breach_id)
        if existing is None:
            return False
        ok = _records.delete(conn, BREACH_SPEC, breach_id)
        conn.commit()
    if ok and delete_points and existing.behaviour_entry_id:
        delete_entry(existing.behaviour_entry_id)
    return ok
