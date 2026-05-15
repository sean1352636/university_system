"""UCAS-application data layer for the Sixth Form System.

Two linked tables:

* ``ucas_applications`` — one row per (student, cycle year). Includes
  the UCAS personal ID, the cycle year, the application's overall
  status (Draft → Submitted → Replied → Confirmed → Clearing), the
  personal statement, and submission date.
* ``ucas_choices``       — up to 5 rows per application, slotted 1-5,
  each pointing at a specific university course with its own offer
  status and a final Firm / Insurance / Declined decision.

The application is keyed UNIQUE on ``(student_id, cycle_year)`` so a
student can have one application per UCAS cycle but staff can record
the previous year's separately if a student is re-applying.

Cascades:
* Deleting a student wipes their applications and choices.
* Deleting an application wipes its choices.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.sixthform_system.core import paths
from education_system.sixthform_system.modules.domain.progression.ucas import ucas as data

logger = logging.getLogger(__name__)

DB_PATH = paths.UCAS_DB

APP_STATUSES: tuple[str, ...] = (
    "Draft", "Submitted", "Replied", "Confirmed", "Clearing",
)
DEFAULT_APP_STATUS: str = "Draft"

DECISION_STATUSES: tuple[str, ...] = (
    "Awaiting", "Unconditional Offer", "Conditional Offer",
    "Rejected", "Withdrawn",
)
DEFAULT_DECISION_STATUS: str = "Awaiting"

FINAL_DECISIONS: tuple[str, ...] = ("Firm", "Insurance", "Declined")

MAX_CHOICES = 5

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_UCAS_ID_RE = re.compile(r"^\d{10}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ucas_applications (
    application_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id         TEXT NOT NULL,
    cycle_year         INTEGER NOT NULL,
    ucas_id            TEXT,
    status             TEXT NOT NULL DEFAULT 'Draft',
    personal_statement TEXT,
    submitted_at       TEXT,
    notes              TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now')),
    UNIQUE(student_id, cycle_year),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ucas_choices (
    choice_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id  INTEGER NOT NULL,
    choice_order    INTEGER NOT NULL,
    university      TEXT NOT NULL,
    course_code     TEXT,
    course_name     TEXT NOT NULL,
    entry_year      INTEGER,
    decision_status TEXT NOT NULL DEFAULT 'Awaiting',
    offer_terms     TEXT,
    final_decision  TEXT,
    notes           TEXT,
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(application_id, choice_order),
    FOREIGN KEY (application_id)
        REFERENCES ucas_applications(application_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_apps_student  ON ucas_applications(student_id);
CREATE INDEX IF NOT EXISTS idx_apps_status   ON ucas_applications(status);
CREATE INDEX IF NOT EXISTS idx_choices_app   ON ucas_choices(application_id);
CREATE INDEX IF NOT EXISTS idx_choices_uni   ON ucas_choices(university);
CREATE INDEX IF NOT EXISTS idx_choices_dec   ON ucas_choices(decision_status);
"""


@dataclass
class Application:
    application_id: int
    student_id: str
    cycle_year: int
    ucas_id: str | None
    status: str
    personal_statement: str | None
    submitted_at: str | None
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class Choice:
    choice_id: int
    application_id: int
    choice_order: int
    university: str
    course_code: str | None
    course_name: str
    entry_year: int | None
    decision_status: str
    offer_terms: str | None
    final_decision: str | None
    notes: str | None
    updated_at: str


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
    from education_system.sixthform_system.modules.domain.students.students import students as _students
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("UCAS schema ready at %s", DB_PATH)

    _DB_READY = True


def _row_app(r: sqlite3.Row) -> Application:
    return Application(
        application_id=r["application_id"], student_id=r["student_id"],
        cycle_year=r["cycle_year"], ucas_id=r["ucas_id"],
        status=r["status"], personal_statement=r["personal_statement"],
        submitted_at=r["submitted_at"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_choice(r: sqlite3.Row) -> Choice:
    return Choice(
        choice_id=r["choice_id"], application_id=r["application_id"],
        choice_order=r["choice_order"], university=r["university"],
        course_code=r["course_code"], course_name=r["course_name"],
        entry_year=r["entry_year"],
        decision_status=r["decision_status"],
        offer_terms=r["offer_terms"], final_decision=r["final_decision"],
        notes=r["notes"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for invalid application / choice input."""


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_year(value, label: str, *, lo: int = 2020, hi: int = 2099) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a 4-digit year") from None
    if n < lo or n > hi:
        raise ValidationError(f"{label} must be between {lo} and {hi}")
    return n


def _validate_app_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    sid = _require(data.get("student_id"), "Student ID").strip()
    from education_system.sixthform_system.modules.domain.students.students import students as _students
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    out["student_id"] = sid

    out["cycle_year"] = _validate_year(
        _require(data.get("cycle_year"), "Cycle year"), "Cycle year")

    ucas_id = (data.get("ucas_id") or "").strip()
    if ucas_id:
        if not _UCAS_ID_RE.match(ucas_id):
            raise ValidationError("UCAS personal ID must be 10 digits")
    out["ucas_id"] = ucas_id or None

    status = (data.get("status") or DEFAULT_APP_STATUS).strip()
    if status not in APP_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(APP_STATUSES)}")
    out["status"] = status

    sub = (data.get("submitted_at") or "").strip()
    if sub and not _DATE_RE.match(sub):
        raise ValidationError("Submitted at must be YYYY-MM-DD")
    out["submitted_at"] = sub or None

    out["personal_statement"] = (
        data.get("personal_statement") or "").strip() or None
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def _validate_choice_payload(
    data: dict[str, Any], *, application_id: int,
) -> dict[str, Any]:
    out: dict[str, Any] = {"application_id": application_id}

    order_raw = _require(data.get("choice_order"), "Choice slot")
    try:
        order = int(order_raw)
    except (TypeError, ValueError):
        raise ValidationError("Choice slot must be 1-5") from None
    if not (1 <= order <= MAX_CHOICES):
        raise ValidationError(f"Choice slot must be 1-{MAX_CHOICES}")
    out["choice_order"] = order

    out["university"] = _require(data.get("university"), "University").strip()
    out["course_name"] = _require(data.get("course_name"), "Course name").strip()
    out["course_code"] = (data.get("course_code") or "").strip() or None

    entry = data.get("entry_year")
    if entry in (None, ""):
        out["entry_year"] = None
    else:
        out["entry_year"] = _validate_year(entry, "Entry year")

    decision = (data.get("decision_status") or
                DEFAULT_DECISION_STATUS).strip()
    if decision not in DECISION_STATUSES:
        raise ValidationError(
            f"Decision status must be one of: {', '.join(DECISION_STATUSES)}")
    out["decision_status"] = decision

    final = (data.get("final_decision") or "").strip()
    if final and final not in FINAL_DECISIONS:
        raise ValidationError(
            f"Final decision must be blank or one of: "
            f"{', '.join(FINAL_DECISIONS)}")
    out["final_decision"] = final or None

    out["offer_terms"] = (data.get("offer_terms") or "").strip() or None
    out["notes"]       = (data.get("notes") or "").strip() or None
    return out


# ── Application CRUD ──────────────────────────────────────────────

def create_application(data: dict[str, Any]) -> Application:
    init_db()
    try:
        p = _validate_app_payload(data)
    except ValidationError as e:
        logger.warning("create_application validation failed: %s", e)
        raise
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO ucas_applications
                       (student_id, cycle_year, ucas_id, status,
                        personal_statement, submitted_at, notes,
                        created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?,
                           datetime('now'), datetime('now'))""",
                (p["student_id"], p["cycle_year"], p["ucas_id"], p["status"],
                 p["personal_statement"], p["submitted_at"], p["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e):
            logger.warning(
                "create_application: duplicate (%s, %d)",
                p["student_id"], p["cycle_year"],
            )
            raise ValidationError(
                f"{p['student_id']} already has an application for "
                f"cycle {p['cycle_year']}"
            ) from e
        logger.exception("create_application DB error")
        raise ValidationError(f"Database error: {e}") from e
    out = get_application(new_id)
    assert out is not None
    logger.info(
        "Created UCAS application #%d for %s (cycle %d, status=%s)",
        new_id, p["student_id"], p["cycle_year"], p["status"],
    )
    return out


def get_application(application_id: int) -> Application | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM ucas_applications WHERE application_id = ?",
            (application_id,),
        ).fetchone()
        return _row_app(r) if r else None


def get_application_for_student(
    student_id: str, *, cycle_year: int | None = None,
) -> Application | None:
    """Return the application (most recent if no cycle_year given)."""
    init_db()
    with _connect() as conn:
        if cycle_year is None:
            r = conn.execute(
                "SELECT * FROM ucas_applications WHERE student_id = ? "
                "ORDER BY cycle_year DESC LIMIT 1",
                (student_id.strip(),),
            ).fetchone()
        else:
            r = conn.execute(
                "SELECT * FROM ucas_applications "
                "WHERE student_id = ? AND cycle_year = ?",
                (student_id.strip(), cycle_year),
            ).fetchone()
        return _row_app(r) if r else None


def list_applications(
    *,
    student_id: str | None = None,
    cycle_year: int | None = None,
    status: str | None = None,
) -> list[Application]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if cycle_year is not None:
        clauses.append("cycle_year = ?")
        args.append(cycle_year)
    if status:
        if status not in APP_STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(APP_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        f"SELECT * FROM ucas_applications {where} "
        "ORDER BY cycle_year DESC, student_id"
    )
    with _connect() as conn:
        return [_row_app(r) for r in conn.execute(sql, args).fetchall()]


def update_application(application_id: int, data: dict[str, Any]) -> Application:
    init_db()
    existing = get_application(application_id)
    if existing is None:
        logger.warning("update_application: unknown id %d", application_id)
        raise ValidationError(f"No application with id {application_id}")
    p = _validate_app_payload({
        "student_id":         existing.student_id,
        "cycle_year":         data.get("cycle_year", existing.cycle_year),
        "ucas_id":            data.get("ucas_id", existing.ucas_id),
        "status":             data.get("status", existing.status),
        "personal_statement": data.get("personal_statement",
                                       existing.personal_statement),
        "submitted_at":       data.get("submitted_at", existing.submitted_at),
        "notes":              data.get("notes", existing.notes),
    })
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE ucas_applications SET
                       cycle_year = ?, ucas_id = ?, status = ?,
                       personal_statement = ?, submitted_at = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE application_id = ?""",
                (p["cycle_year"], p["ucas_id"], p["status"],
                 p["personal_statement"], p["submitted_at"], p["notes"],
                 application_id),
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e):
            raise ValidationError(
                f"Another application already exists for "
                f"{existing.student_id} in cycle {p['cycle_year']}"
            ) from e
        logger.exception("update_application DB error")
        raise ValidationError(f"Database error: {e}") from e
    out = get_application(application_id)
    assert out is not None
    logger.info("Updated UCAS application #%d (status=%s)",
                application_id, out.status)
    return out


def delete_application(application_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM ucas_applications WHERE application_id = ?",
            (application_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted UCAS application #%d", application_id)
            return True
        logger.warning("delete_application: unknown id %d", application_id)
        return False


# ── Choice CRUD ───────────────────────────────────────────────────

def list_choices(application_id: int) -> list[Choice]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM ucas_choices WHERE application_id = ? "
            "ORDER BY choice_order",
            (application_id,),
        ).fetchall()
        return [_row_choice(r) for r in rows]


def get_choice(choice_id: int) -> Choice | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM ucas_choices WHERE choice_id = ?", (choice_id,),
        ).fetchone()
        return _row_choice(r) if r else None


def create_choice(application_id: int, data: dict[str, Any]) -> Choice:
    init_db()
    if get_application(application_id) is None:
        raise ValidationError(f"No application with id {application_id}")
    if len(list_choices(application_id)) >= MAX_CHOICES:
        raise ValidationError(
            f"This application already has {MAX_CHOICES} choices")
    try:
        p = _validate_choice_payload(data, application_id=application_id)
    except ValidationError as e:
        logger.warning("create_choice validation failed: %s", e)
        raise
    # Enforce one Firm + one Insurance at most.
    _check_final_decision_uniqueness(
        application_id, p["final_decision"], excluding_choice_id=None)
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO ucas_choices
                       (application_id, choice_order, university, course_code,
                        course_name, entry_year, decision_status, offer_terms,
                        final_decision, notes, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           datetime('now'))""",
                (application_id, p["choice_order"], p["university"],
                 p["course_code"], p["course_name"], p["entry_year"],
                 p["decision_status"], p["offer_terms"],
                 p["final_decision"], p["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e):
            raise ValidationError(
                f"Choice slot {p['choice_order']} is already filled"
            ) from e
        logger.exception("create_choice DB error")
        raise ValidationError(f"Database error: {e}") from e
    out = get_choice(new_id)
    assert out is not None
    logger.info(
        "Created UCAS choice #%d for application #%d: slot %d, %s — %s (%s)",
        new_id, application_id, p["choice_order"],
        p["university"], p["course_name"], p["decision_status"],
    )
    return out


def update_choice(choice_id: int, data: dict[str, Any]) -> Choice:
    init_db()
    existing = get_choice(choice_id)
    if existing is None:
        logger.warning("update_choice: unknown id %d", choice_id)
        raise ValidationError(f"No choice with id {choice_id}")
    p = _validate_choice_payload(
        {
            "choice_order":    data.get("choice_order", existing.choice_order),
            "university":      data.get("university", existing.university),
            "course_code":     data.get("course_code", existing.course_code),
            "course_name":     data.get("course_name", existing.course_name),
            "entry_year":      data.get("entry_year", existing.entry_year),
            "decision_status": data.get("decision_status",
                                         existing.decision_status),
            "offer_terms":     data.get("offer_terms", existing.offer_terms),
            "final_decision":  data.get("final_decision",
                                         existing.final_decision),
            "notes":           data.get("notes", existing.notes),
        },
        application_id=existing.application_id,
    )
    _check_final_decision_uniqueness(
        existing.application_id, p["final_decision"],
        excluding_choice_id=choice_id,
    )
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE ucas_choices SET
                       choice_order = ?, university = ?, course_code = ?,
                       course_name = ?, entry_year = ?, decision_status = ?,
                       offer_terms = ?, final_decision = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE choice_id = ?""",
                (p["choice_order"], p["university"], p["course_code"],
                 p["course_name"], p["entry_year"], p["decision_status"],
                 p["offer_terms"], p["final_decision"], p["notes"],
                 choice_id),
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e):
            raise ValidationError(
                f"Choice slot {p['choice_order']} is already filled "
                "by another row"
            ) from e
        logger.exception("update_choice DB error")
        raise ValidationError(f"Database error: {e}") from e
    out = get_choice(choice_id)
    assert out is not None
    logger.info(
        "Updated UCAS choice #%d (slot %d, %s — %s, decision=%s, final=%s)",
        choice_id, out.choice_order, out.university, out.course_name,
        out.decision_status, out.final_decision,
    )
    return out


def delete_choice(choice_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM ucas_choices WHERE choice_id = ?", (choice_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted UCAS choice #%d", choice_id)
            return True
        logger.warning("delete_choice: unknown id %d", choice_id)
        return False


def _check_final_decision_uniqueness(
    application_id: int,
    new_final: str | None,
    *,
    excluding_choice_id: int | None,
) -> None:
    """Enforce at most one Firm and one Insurance choice per application."""
    if new_final not in ("Firm", "Insurance"):
        return
    existing = [c for c in list_choices(application_id)
                if c.final_decision == new_final
                and c.choice_id != excluding_choice_id]
    if existing:
        c = existing[0]
        raise ValidationError(
            f"Choice slot {c.choice_order} is already marked {new_final}; "
            f"only one {new_final} choice allowed per application"
        )


# ── Reads with joined detail ──────────────────────────────────────

@dataclass
class ApplicationRow:
    application: Application
    student_name: str
    n_choices: int
    has_firm: bool
    has_insurance: bool


def list_applications_with_detail(
    *,
    student_id: str | None = None,
    cycle_year: int | None = None,
    status: str | None = None,
) -> list[ApplicationRow]:
    apps = list_applications(
        student_id=student_id, cycle_year=cycle_year, status=status)
    if not apps:
        return []
        from education_system.sixthform_system.modules.domain.students.students import students as _students
    name_index = {s.student_id: s.full_name for s in _students.list_students()}
    out: list[ApplicationRow] = []
    for a in apps:
        cs = list_choices(a.application_id)
        out.append(ApplicationRow(
            application=a,
            student_name=name_index.get(a.student_id, "(unknown)"),
            n_choices=len(cs),
            has_firm=any(c.final_decision == "Firm" for c in cs),
            has_insurance=any(c.final_decision == "Insurance" for c in cs),
        ))
    return out


# ── Summaries ─────────────────────────────────────────────────────

@dataclass
class CycleSummary:
    total_applications: int
    by_status: dict[str, int]
    total_choices: int
    by_decision_status: dict[str, int]
    by_final_decision: dict[str, int]


def cycle_summary(cycle_year: int | None = None) -> CycleSummary:
    init_db()
    by_status: dict[str, int] = {s: 0 for s in APP_STATUSES}
    by_decision: dict[str, int] = {s: 0 for s in DECISION_STATUSES}
    by_final: dict[str, int] = {f: 0 for f in FINAL_DECISIONS}
    by_final[""] = 0  # bucket for not yet decided

    apps = list_applications(cycle_year=cycle_year)
    for a in apps:
        by_status[a.status] = by_status.get(a.status, 0) + 1

    total_choices = 0
    for a in apps:
        for c in list_choices(a.application_id):
            total_choices += 1
            by_decision[c.decision_status] = by_decision.get(c.decision_status, 0) + 1
            key = c.final_decision or ""
            by_final[key] = by_final.get(key, 0) + 1

    # Drop the empty bucket if no final decisions; keep otherwise so callers
    # can show "Not decided".
    if by_final.get("") == 0:
        del by_final[""]
    return CycleSummary(
        total_applications=len(apps),
        by_status=by_status,
        total_choices=total_choices,
        by_decision_status=by_decision,
        by_final_decision=by_final,
    )
