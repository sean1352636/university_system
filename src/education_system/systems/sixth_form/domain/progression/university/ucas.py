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

import json
import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_UCAS_DB

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
    #: ``Open`` while the choice is a live application; ``Placed`` once the
    #: university it names has enrolled the learner on it. Set only by
    #: :func:`mark_placed` (from the university's ``university.student.enrolled``
    #: event) — a placed choice is history, never deleted.
    choice_status: str = "Open"
    placed_at: str | None = None
    university_student_id: str | None = None
    #: The university's own record of its decision, as published on the bus
    #: (``ucas.decision.recorded``) and applied by
    #: :func:`apply_university_decision`.
    reply_by: str | None = None
    offer_conditions: str | None = None     # JSON list, or None
    decided_by: str | None = None
    decided_at: str | None = None
    decision_ref: int | None = None

    @property
    def is_placed(self) -> bool:
        return self.choice_status == CHOICE_PLACED

    @property
    def conditions(self) -> list | None:
        if not self.offer_conditions:
            return None
        try:
            value = json.loads(self.offer_conditions)
        except (TypeError, ValueError):
            return None
        return value if isinstance(value, list) else None


#: Lifecycle of a choice as an application, separate from the decision on it.
CHOICE_OPEN = "Open"
CHOICE_PLACED = "Placed"
CHOICE_STATUSES: tuple[str, ...] = (CHOICE_OPEN, CHOICE_PLACED)

#: Columns added to ``ucas_choices`` after it first shipped, applied with a
#: guarded ``ALTER TABLE`` by :func:`init_db`.
_CHOICE_LINK_COLUMNS: tuple[tuple[str, str], ...] = (
    ("choice_status", "TEXT NOT NULL DEFAULT 'Open'"),
    ("placed_at", "TEXT"),
    ("university_student_id", "TEXT"),
    ("reply_by", "TEXT"),
    ("offer_conditions", "TEXT"),
    ("decided_by", "TEXT"),
    ("decided_at", "TEXT"),
    ("decision_ref", "INTEGER"),
)


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
        have = {r["name"] for r in conn.execute(
            "PRAGMA table_info(ucas_choices)")}
        for name, decl in _CHOICE_LINK_COLUMNS:
            if name not in have:
                # db-audit: ignore[DBW001] - names/decls from a module constant
                conn.execute(
                    f"ALTER TABLE ucas_choices ADD COLUMN {name} {decl}")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_choices_status "
                     "ON ucas_choices(choice_status)")
        conn.commit()
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
        **{name: r[name] for name, _decl in _CHOICE_LINK_COLUMNS
           if name in r.keys() and r[name] is not None},
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for invalid application / choice input."""


class UniversityOwnedFieldError(ValidationError):
    """Raised when the sixth form tries to author a decision that is the
    university's to make.

    A subclass of :class:`ValidationError` so every existing caller still
    catches it and shows the message; distinct so the API can answer 403
    rather than 400 — this is not malformed input, it is input the sixth
    form is not entitled to send.
    """


#: Fields on a UCAS choice that the *institution* fills in, not the school.
#: The school records what it is told for the four choices at universities
#: this platform does not run. For the one that is ours, the answer is
#: written by ``university...admissions.domain.ucas.record_decision`` and
#: read here — a sixth form that could type "Unconditional Offer" into its
#: own copy could admit its students to us without us ever deciding.
UNIVERSITY_OWNED_FIELDS: tuple[str, ...] = ("decision_status", "offer_terms")


def _is_home_university(institution: str | None) -> bool:
    """Does *institution* name this platform's own university?

    Lazily imported and guarded: a sixth form running standalone cannot
    establish who "we" are, gets ``False``, and keeps every field editable
    exactly as it did before this rule existed.
    """
    try:
        from education_system.systems.sixth_form.domain.progression import (
            university_handover,
        )
        return university_handover.is_home_university(institution)
    except Exception:
        logger.debug("Could not resolve the home university", exc_info=True)
        return False


def _reject_university_owned_writes(
    payload: dict[str, Any],
    existing: "Choice | None",
    *,
    issued_by_university: bool,
) -> None:
    """Refuse a decision written by anyone but the university that made it.

    Judged on the *resulting* institution, and on whether the choice was
    already ours, because those are two different situations:

    * **Still ours.** Only a *change* is refused. The GUI and CLI both
      submit the whole choice on every save, so comparing against what is
      stored is what keeps editing a course name from tripping a rule
      about offers.
    * **Newly ours** — a choice created at this university, or an existing
      one switched onto it. Here it must arrive undecided. Comparing
      against the stored value would be exactly wrong: the stored value is
      the decision some *other* university made, and letting it through
      unchanged converts a conditional offer from Elsewhere into a
      conditional offer from us that nobody here ever agreed to.
    * **No longer ours.** Allowed outright — a choice corrected onto the
      university that really sent the offer takes those fields with it.
    """
    if issued_by_university:
        return
    institution = payload.get("university")
    if not _is_home_university(institution):
        return

    was_ours = (existing is not None
                and _is_home_university(existing.university))
    if was_ours:
        current = {"decision_status": existing.decision_status,
                   "offer_terms": existing.offer_terms}
        changed = [f for f in UNIVERSITY_OWNED_FIELDS
                   if payload.get(f) != current[f]]
        if not changed:
            return
        verb, pronoun = ("is", "It") if len(changed) == 1 else ("are", "They")
        raise UniversityOwnedFieldError(
            f"{', '.join(changed)} on a choice at {institution} {verb} "
            "recorded by that university's admissions team, not here. "
            f"{pronoun} will appear on this choice once they publish it."
        )

    # Newly ours: it starts undecided, whatever it carried before.
    undecided = {"decision_status": DEFAULT_DECISION_STATUS,
                 "offer_terms": None}
    carried = [f for f in UNIVERSITY_OWNED_FIELDS
               if payload.get(f) != undecided[f]]
    if not carried:
        return
    raise UniversityOwnedFieldError(
        f"A choice at {institution} starts with no decision on it — "
        f"{', '.join(carried)} cannot be set here. That university's "
        "admissions team records its own decision, and it will appear on "
        "this choice once they do."
    )


#: The two statuses that are a *function* of the form rather than a
#: judgement about it: an application is a Draft until a submission date
#: is on it, and Submitted once one is. Everything after that —  Replied,
#: Confirmed, Clearing — describes what the universities have since done,
#: which no amount of looking at the form can tell you.
DERIVED_STATUSES: tuple[str, ...] = ("Draft", "Submitted")


def derive_status(current_status: str | None,
                  submitted_at: str | None) -> str:
    """The status an application should carry, given its submission date.

    Screens no longer ask anyone to pick between "Draft" and "Submitted"
    while separately typing the date that decides which of the two it is;
    they set the date and call this. A blank date means Draft, a date
    means Submitted.

    A status further along the cycle is returned unchanged. Deriving it
    would be a downgrade: an application the universities have already
    replied to is still an application with a submission date on it, and
    re-deriving would silently walk "Replied" back to "Submitted" every
    time somebody edited the notes field.
    """
    current = (current_status or DEFAULT_APP_STATUS).strip()
    if current not in DERIVED_STATUSES:
        return current
    return "Submitted" if (submitted_at or "").strip() else "Draft"


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
    from education_system.systems.sixth_form.domain.learners.students import students as _students
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


def create_choice(application_id: int, data: dict[str, Any],
                   *, issued_by_university: bool = False) -> Choice:
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
    # A new choice at our university starts undecided, whoever adds it.
    _reject_university_owned_writes(
        p, None, issued_by_university=issued_by_university)
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


def update_choice(choice_id: int, data: dict[str, Any],
                   *, issued_by_university: bool = False) -> Choice:
    """Update a UCAS choice.

    ``issued_by_university`` marks the write as coming from the university
    that owns the decision — it is set by
    ``university...admissions.domain.ucas.record_decision`` and by nothing
    else. Without it, the decision fields on a choice naming this
    platform's university are read-only here; see
    :data:`UNIVERSITY_OWNED_FIELDS`.
    """
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
    _reject_university_owned_writes(
        p, existing, issued_by_university=issued_by_university)
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
    from education_system.systems.sixth_form.domain.learners.students import students as _students
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


# ── The university link ───────────────────────────────────────────
#
# A university on this platform reaches these rows only through the sixth
# form's adapter (reads) and the cross-system bus (its decisions and its
# enrolments). Nothing below is called by university code directly.

def _students_has_journey(conn: sqlite3.Connection) -> bool:
    return "journey_id" in {r["name"] for r in conn.execute(
        "PRAGMA table_info(students)")}


def _choice_dict(r: sqlite3.Row, *, journey: bool) -> dict[str, Any]:
    """One choice as the adapter hands it over: plain data, no dataclass."""
    keys = r.keys()
    full = " ".join(p for p in (r["first_name"], r["middle_name"],
                                r["last_name"]) if p).strip()
    entry_year = r["entry_year"]
    cycle_year = r["cycle_year"]
    final = r["final_decision"] or None
    conditions = None
    if "offer_conditions" in keys and r["offer_conditions"]:
        try:
            conditions = json.loads(r["offer_conditions"])
        except (TypeError, ValueError):
            conditions = None

    def col(name: str, default: Any = None) -> Any:
        return r[name] if name in keys and r[name] is not None else default

    return {
        "choice_id": r["choice_id"],
        "application_id": r["application_id"],
        "student_id": r["student_id"],
        "student_name": full,
        "ucas_personal_id": r["ucas_id"],
        "university": r["university"],
        "course_name": r["course_name"],
        "course_code": r["course_code"],
        "decision_status": r["decision_status"],
        "reply_status": final if final in ("Firm", "Insurance") else None,
        "entry_year": entry_year,
        # No separate deferral flag is held: an entry year later than the
        # cycle the application was made in *is* a deferred entry.
        "deferred": bool(entry_year and cycle_year
                         and int(entry_year) > int(cycle_year)),
        "choice_status": col("choice_status", CHOICE_OPEN),
        "application_status": r["app_status"],
        # Beyond the contract minimum — what the admissions screens show.
        "choice_order": r["choice_order"],
        "offer_terms": r["offer_terms"],
        "offer_conditions": conditions,
        "final_decision": final,
        "choice_notes": r["notes"],
        "reply_by": col("reply_by"),
        "decided_by": col("decided_by"),
        "decided_at": col("decided_at"),
        "placed_at": col("placed_at"),
        "university_student_id": col("university_student_id"),
        "cycle_year": cycle_year,
        "submitted_at": r["submitted_at"],
        "app_notes": r["app_notes"],
        "personal_statement": r["personal_statement"],
        "student_email": r["email"],
        "student_dob": r["date_of_birth"],
        "student_status": r["student_status"] or "Active",
        "journey_id": r["journey_id"] if journey else None,
    }


def _choice_select(conn: sqlite3.Connection, where: str,
                   args: list[Any]) -> list[dict[str, Any]]:
    journey = _students_has_journey(conn)
    journey_col = ", s.journey_id" if journey else ""
    # db-audit: ignore[DBW001] - where is built from literals by the callers
    rows = conn.execute(
        f"""SELECT c.*, a.cycle_year, a.status AS app_status, a.ucas_id,
                   a.submitted_at, a.notes AS app_notes,
                   a.personal_statement,
                   s.student_id, s.first_name, s.middle_name, s.last_name,
                   s.email, s.date_of_birth,
                   s.status AS student_status{journey_col}
              FROM ucas_choices AS c
              JOIN ucas_applications AS a
                   ON a.application_id = c.application_id
              JOIN students AS s ON s.student_id = a.student_id
             WHERE {where}
             ORDER BY a.submitted_at DESC NULLS LAST,
                      s.last_name, s.first_name, c.choice_order""",
        args,
    ).fetchall()
    return [_choice_dict(r, journey=journey) for r in rows]


def choices_for_institution(institution_names: set[str] | None = None, *,
                            include_placed: bool = False
                            ) -> list[dict[str, Any]]:
    """Every choice naming one of *institution_names* (case-insensitive).

    ``None`` means every institution. Placed choices — learners the
    university has already enrolled — are left out unless asked for: they
    are history, not applicants.
    """
    init_db()
    clauses = ["1 = 1"]
    args: list[Any] = []
    if institution_names is not None:
        names = sorted({n.strip().lower() for n in institution_names
                        if n and n.strip()})
        if not names:
            return []
        clauses.append("LOWER(TRIM(c.university)) IN ("
                       + ",".join("?" * len(names)) + ")")
        args.extend(names)
    if not include_placed:
        clauses.append("COALESCE(c.choice_status, 'Open') <> 'Placed'")
    with _connect() as conn:
        return _choice_select(conn, " AND ".join(clauses), args)


def choice_detail(choice_id: int) -> dict[str, Any] | None:
    """One choice in the adapter shape, placed or not."""
    init_db()
    with _connect() as conn:
        rows = _choice_select(conn, "c.choice_id = ?", [int(choice_id)])
    return rows[0] if rows else None


def application_detail(application_id: int) -> dict[str, Any] | None:
    """The application, its learner and every choice on it, as plain data."""
    init_db()
    app = get_application(int(application_id))
    if app is None:
        return None
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    student = _students.get_student(app.student_id)
    with _connect() as conn:
        choices = _choice_select(conn, "c.application_id = ?",
                                 [int(application_id)])
    return {
        "application_id": app.application_id,
        "student_id": app.student_id,
        "student_name": student.full_name if student else "",
        "student_email": student.email if student else None,
        "student_dob": student.date_of_birth if student else None,
        "student_known": student is not None,
        "subjects": list(student.subjects) if student else [],
        "cycle_year": app.cycle_year,
        "ucas_personal_id": app.ucas_id,
        "application_status": app.status,
        "submitted_at": app.submitted_at,
        "personal_statement": app.personal_statement,
        "app_notes": app.notes,
        "choices": sorted(choices, key=lambda c: c["choice_order"]),
    }


def promote_to_replied(application_id: int) -> bool:
    """Move a Submitted application to Replied once nothing is awaited.

    Only from Submitted, and only when no choice is still ``Awaiting``.
    Never walks a settled (Confirmed / Clearing) application back.
    """
    application = get_application(int(application_id))
    if application is None or application.status != "Submitted":
        return False
    choices = list_choices(application.application_id)
    if not choices or any(c.decision_status == "Awaiting" for c in choices):
        return False
    update_application(application.application_id, {"status": "Replied"})
    logger.info("UCAS application #%d -> Replied (all %d choice(s) decided)",
                application.application_id, len(choices))
    return True


def apply_university_decision(payload: dict[str, Any]
                              ) -> tuple[Choice | None, bool]:
    """Apply a ``ucas.decision.recorded`` payload to our own choice row.

    Returns ``(choice, changed)``. Idempotent: the university's decision id
    (``decision_id``) is stored as ``decision_ref``, and a payload whose id
    is not newer than the one already applied is a redelivery (or an older
    decision arriving late) and changes nothing. Without an id the
    ``decided_at`` timestamps are compared instead. An unknown choice is
    logged and skipped — it may have been deleted here since.
    """
    init_db()
    try:
        choice_id = int(payload.get("choice_id"))
    except (TypeError, ValueError):
        logger.warning("UCAS decision event without a usable choice_id: %r",
                       payload.get("choice_id"))
        return None, False
    existing = get_choice(choice_id)
    if existing is None:
        logger.info("UCAS decision for unknown choice #%d skipped", choice_id)
        return None, False

    decision = (payload.get("decision_status") or "").strip()
    if decision not in DECISION_STATUSES:
        logger.warning("UCAS decision event for choice #%d has unknown "
                       "status %r; skipped", choice_id, decision)
        return existing, False

    ref = payload.get("decision_id")
    try:
        ref = int(ref) if ref not in (None, "") else None
    except (TypeError, ValueError):
        ref = None
    decided_at = (payload.get("decided_at") or "").strip() or None
    if ref is not None and existing.decision_ref is not None:
        if ref <= existing.decision_ref:
            return existing, False
    elif (ref is None and decided_at and existing.decided_at
          and decided_at <= existing.decided_at):
        return existing, False

    update: dict[str, Any] = {"decision_status": decision}
    if payload.get("offer_summary") is not None:
        update["offer_terms"] = payload.get("offer_summary")
    if payload.get("notes") is not None:
        update["notes"] = payload.get("notes")
    # The university made this decision; this is its write landing here.
    update_choice(choice_id, update, issued_by_university=True)

    conditions = payload.get("conditions")
    with _connect() as conn:
        conn.execute(
            """UPDATE ucas_choices SET reply_by = ?, offer_conditions = ?,
                      decided_by = ?, decided_at = ?, decision_ref = ?,
                      updated_at = datetime('now')
                WHERE choice_id = ?""",
            ((payload.get("reply_by") or None),
             json.dumps(conditions) if isinstance(conditions, list) else None,
             (payload.get("decided_by") or None), decided_at, ref,
             choice_id))
        conn.commit()
    out = get_choice(choice_id)
    logger.info("Applied university decision #%s to UCAS choice #%d: %s",
                ref, choice_id, decision)
    try:
        promote_to_replied(existing.application_id)
    except Exception:
        logger.exception("Could not re-evaluate application #%d after "
                         "decision on choice #%d", existing.application_id,
                         choice_id)
    return out, True


def mark_placed(choice_id: int, *, university_student_id: str | None,
                placed_at: str | None = None) -> tuple[Choice | None, bool]:
    """Record that the university named on this choice enrolled the learner.

    Replaces the old clear-down, which deleted the choice (and sometimes
    the application) on enrolment and so erased the record of where the
    learner went. Idempotent: re-marking with the same student id changes
    nothing. Returns ``(choice, changed)``; ``(None, False)`` when the
    choice does not exist.
    """
    init_db()
    existing = get_choice(int(choice_id))
    if existing is None:
        return None, False
    uni_id = (str(university_student_id).strip()
              if university_student_id else None)
    if existing.is_placed and (existing.university_student_id or None) == uni_id:
        return existing, False
    with _connect() as conn:
        conn.execute(
            """UPDATE ucas_choices
                  SET choice_status = ?, university_student_id = ?,
                      placed_at = COALESCE(placed_at, ?, datetime('now')),
                      updated_at = datetime('now')
                WHERE choice_id = ?""",
            (CHOICE_PLACED, uni_id, placed_at, int(choice_id)))
        conn.commit()
    logger.info("UCAS choice #%d placed (university student %s)",
                choice_id, uni_id or "unknown")
    return get_choice(int(choice_id)), True


def record_reply(choice_id: int, final_decision: str | None) -> Choice:
    """Set (or clear) the Firm / Insurance / Declined reply on a choice.

    The reply is recorded by the university that made the offer; the
    uniqueness of Firm / Insurance across the application is enforced by
    :func:`update_choice` as for every other write.
    """
    return update_choice(int(choice_id),
                         {"final_decision": (final_decision or "")},
                         issued_by_university=True)


def set_application_status(application_id: int, status: str) -> Application:
    """Set the application's status (the university's Confirmed / Clearing)."""
    if status not in APP_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(APP_STATUSES)}")
    return update_application(int(application_id), {"status": status})
