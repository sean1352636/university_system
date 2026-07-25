"""University-offer tracking for the Sixth Form System.

This module is a *focused view* over the existing ``ucas_choices`` data:
the offer state, terms, and final decision live on the UCAS choice
itself, but staff need a few additional offer-management fields that
don't sit naturally on the choice (reply deadline, scholarship,
accommodation, optional alternative-grade pathway). Those live in a
small companion table here keyed 1:1 to a choice.

Operations:

* List offers (every UCAS choice that has actually had an offer).
* Filter by student / university / decision status / deadline window.
* Edit offer details for a choice (creates the companion row on
  demand).
* Set the final decision on the underlying choice (Firm / Insurance /
  Declined) — this is the workflow staff use during offer week.
* Per-student comparison: every offer side-by-side with predicted
  grades for the relevant subject.

Cascade: deleting a UCAS choice (or its application, or the student)
removes the offer details row.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.systems.sixth_form.infrastructure import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.OFFERS_DB

# Decision statuses that count as "has an offer" for filtering.
OFFER_DECISION_STATUSES: tuple[str, ...] = (
    "Unconditional Offer", "Conditional Offer",
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS offer_details (
    offer_id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    choice_id                 INTEGER NOT NULL UNIQUE,
    grade_requirement         TEXT,
    grade_alternative         TEXT,
    reply_deadline            TEXT,
    expiry_date               TEXT,
    scholarship               TEXT,
    accommodation_guaranteed  INTEGER NOT NULL DEFAULT 0,
    notes                     TEXT,
    created_at                TEXT DEFAULT (datetime('now')),
    updated_at                TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (choice_id) REFERENCES ucas_choices(choice_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_offers_choice   ON offer_details(choice_id);
CREATE INDEX IF NOT EXISTS idx_offers_deadline ON offer_details(reply_deadline);
"""


@dataclass
class OfferDetails:
    offer_id: int
    choice_id: int
    grade_requirement: str | None
    grade_alternative: str | None
    reply_deadline: str | None
    expiry_date: str | None
    scholarship: str | None
    accommodation_guaranteed: bool
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class OfferRow:
    """A UCAS choice joined to its student, application, and (optional)
    offer details — the canonical "one row per offer" record used by
    the directory and per-student comparison views."""
    # From ucas_choices
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
    # From ucas_applications
    cycle_year: int
    application_status: str
    # From students
    student_id: str
    student_name: str
    # From predicted_grades
    predicted_grade: str | None
    # From offer_details (optional — None if no companion row yet)
    details: OfferDetails | None


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
    # FKs target ucas_choices which targets ucas_applications/students.
    from education_system.systems.sixth_form.domain.progression.ucas import ucas as _ucas
    _ucas.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Offers schema ready at %s", DB_PATH)

    _DB_READY = True


def _row_details(r: sqlite3.Row) -> OfferDetails:
    return OfferDetails(
        offer_id=r["offer_id"], choice_id=r["choice_id"],
        grade_requirement=r["grade_requirement"],
        grade_alternative=r["grade_alternative"],
        reply_deadline=r["reply_deadline"],
        expiry_date=r["expiry_date"],
        scholarship=r["scholarship"],
        accommodation_guaranteed=bool(r["accommodation_guaranteed"]),
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for invalid offer-detail input."""


def _validate_date(value: Any, label: str) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _validate_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["grade_requirement"] = (data.get("grade_requirement") or "").strip() or None
    out["grade_alternative"] = (data.get("grade_alternative") or "").strip() or None
    out["reply_deadline"] = _validate_date(
        data.get("reply_deadline"), "Reply deadline")
    out["expiry_date"] = _validate_date(
        data.get("expiry_date"), "Expiry date")
    out["scholarship"] = (data.get("scholarship") or "").strip() or None
    accom = data.get("accommodation_guaranteed")
    if isinstance(accom, str):
        accom = accom.strip().lower() in ("1", "true", "yes", "y", "on")
    out["accommodation_guaranteed"] = 1 if bool(accom) else 0
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


# ── Details CRUD (upsert keyed on choice_id) ───────────────────────

def get_details_for_choice(choice_id: int) -> OfferDetails | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM offer_details WHERE choice_id = ?", (choice_id,),
        ).fetchone()
        return _row_details(r) if r else None


def save_details(choice_id: int, data: dict[str, Any]) -> OfferDetails:
    """Upsert offer details for a UCAS choice."""
    init_db()
    from education_system.systems.sixth_form.domain.progression.ucas import ucas as _ucas
    if _ucas.get_choice(choice_id) is None:
        raise ValidationError(f"No UCAS choice with id {choice_id}")
    try:
        p = _validate_payload(data)
    except ValidationError as e:
        logger.warning("save_details validation failed for choice #%d: %s",
                       choice_id, e)
        raise

    with _connect() as conn:
        conn.execute(
            """INSERT INTO offer_details
                   (choice_id, grade_requirement, grade_alternative,
                    reply_deadline, expiry_date, scholarship,
                    accommodation_guaranteed, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))
               ON CONFLICT(choice_id) DO UPDATE SET
                   grade_requirement = excluded.grade_requirement,
                   grade_alternative = excluded.grade_alternative,
                   reply_deadline    = excluded.reply_deadline,
                   expiry_date       = excluded.expiry_date,
                   scholarship       = excluded.scholarship,
                   accommodation_guaranteed = excluded.accommodation_guaranteed,
                   notes             = excluded.notes,
                   updated_at        = datetime('now')""",
            (choice_id, p["grade_requirement"], p["grade_alternative"],
             p["reply_deadline"], p["expiry_date"], p["scholarship"],
             p["accommodation_guaranteed"], p["notes"]),
        )
        conn.commit()
    out = get_details_for_choice(choice_id)
    assert out is not None
    logger.info(
        "Saved offer details for choice #%d "
        "(deadline=%s, scholarship=%s, accom=%s)",
        choice_id, out.reply_deadline, out.scholarship,
        out.accommodation_guaranteed,
    )
    return out


def delete_details(choice_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM offer_details WHERE choice_id = ?", (choice_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted offer details for choice #%d", choice_id)
            return True
        return False


# ── Final-decision shortcut ───────────────────────────────────────

def set_final_decision(choice_id: int, final: str | None) -> None:
    """Convenience: update the UCAS choice's ``final_decision`` field
    without forcing the caller to import the ucas module. Enforces the
    one-Firm / one-Insurance rule via the UCAS data layer."""
    from education_system.systems.sixth_form.domain.progression.ucas import ucas as _ucas
    _ucas.update_choice(choice_id, {"final_decision": (final or "")})


# ── Joined directory & filters ────────────────────────────────────

def _predicted_grades_map() -> dict[tuple[str, str], str]:
    """Return ``{(student_id, subject): grade}`` from the predicted-grades
    module if it's available; otherwise empty."""
    try:
        from education_system.systems.sixth_form.domain.assessment.predicted_grades import predicted_grades as _pg
        return {(p.student_id, p.subject): p.grade
                for p in _pg.list_predictions()}
    except Exception:
        logger.exception("Could not load predicted grades")
        return {}


def _subject_for_course(course_name: str) -> str:
    """Heuristic: take the first word of the course name as the subject
    key. UCAS course names are messy but most "Mathematics", "Physics
    with Astrophysics", "Computer Science" etc. start with the subject."""
    if not course_name:
        return ""
    first = course_name.split()[0]
    # Normalise a few common variants
    return first.rstrip(",.")


def list_offer_rows(
    *,
    student_id: str | None = None,
    university_like: str | None = None,
    decision_status: str | None = None,
    final_decision: str | None = None,
    offers_only: bool = False,
    deadline_before: str | None = None,
) -> list[OfferRow]:
    """Joined view of UCAS choices + applications + students + offer
    details. ``offers_only=True`` restricts to choices with a decision
    status that indicates an offer (Unconditional / Conditional).
    """
    init_db()
    from education_system.systems.sixth_form.domain.progression.ucas import ucas
    from education_system.systems.sixth_form.domain.learners.students import students as _ucas
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("a.student_id = ?")
        args.append(student_id.strip())
    if university_like:
        clauses.append("c.university LIKE ?")
        args.append(f"%{university_like.strip()}%")
    if decision_status:
        clauses.append("c.decision_status = ?")
        args.append(decision_status)
    if final_decision:
        clauses.append("c.final_decision = ?")
        args.append(final_decision)
    if offers_only:
        placeholders = ",".join("?" * len(OFFER_DECISION_STATUSES))
        clauses.append(f"c.decision_status IN ({placeholders})")
        args.extend(OFFER_DECISION_STATUSES)
    if deadline_before:
        deadline_before_s = _validate_date(deadline_before, "Deadline before")
        clauses.append("od.reply_deadline IS NOT NULL "
                       "AND od.reply_deadline <= ?")
        args.append(deadline_before_s)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        "SELECT "
        "  c.choice_id, c.application_id, c.choice_order, "
        "  c.university, c.course_code, c.course_name, c.entry_year, "
        "  c.decision_status, c.offer_terms, c.final_decision, "
        "  a.cycle_year, a.status AS app_status, a.student_id, "
        "  od.* "
        "FROM ucas_choices c "
        "JOIN ucas_applications a ON a.application_id = c.application_id "
        "LEFT JOIN offer_details od ON od.choice_id = c.choice_id "
        f"{where} "
        "ORDER BY a.student_id, c.choice_order"
    )
    with _connect() as conn:
        rows = conn.execute(sql, args).fetchall()

    name_index = {s.student_id: s.full_name for s in _students.list_students()}
    grade_map = _predicted_grades_map()
    out: list[OfferRow] = []
    for r in rows:
        details = None
        if r["offer_id"] is not None:
            details = OfferDetails(
                offer_id=r["offer_id"], choice_id=r["choice_id"],
                grade_requirement=r["grade_requirement"],
                grade_alternative=r["grade_alternative"],
                reply_deadline=r["reply_deadline"],
                expiry_date=r["expiry_date"],
                scholarship=r["scholarship"],
                accommodation_guaranteed=bool(r["accommodation_guaranteed"]),
                notes=r["notes"],
                created_at=r["created_at"], updated_at=r["updated_at"],
            )
        subj_key = _subject_for_course(r["course_name"])
        pred = grade_map.get((r["student_id"], subj_key))
        out.append(OfferRow(
            choice_id=r["choice_id"],
            application_id=r["application_id"],
            choice_order=r["choice_order"],
            university=r["university"],
            course_code=r["course_code"],
            course_name=r["course_name"],
            entry_year=r["entry_year"],
            decision_status=r["decision_status"],
            offer_terms=r["offer_terms"],
            final_decision=r["final_decision"],
            cycle_year=r["cycle_year"],
            application_status=r["app_status"],
            student_id=r["student_id"],
            student_name=name_index.get(r["student_id"], "(unknown)"),
            predicted_grade=pred,
            details=details,
        ))
    return out


def get_offer_row(choice_id: int) -> OfferRow | None:
    """Single joined row for one UCAS choice."""
    for r in list_offer_rows():
        if r.choice_id == choice_id:
            return r
    return None


def offers_for_student(student_id: str) -> list[OfferRow]:
    return list_offer_rows(student_id=student_id)


# ── Summary ───────────────────────────────────────────────────────

@dataclass
class OfferSummary:
    total_choices: int
    total_offers: int
    by_decision: dict[str, int]
    by_final: dict[str, int]
    with_scholarship: int
    with_accommodation: int
    upcoming_deadlines: int  # within 30 days


def summary(*, deadline_window_days: int = 30) -> OfferSummary:
    """Counts across all offer rows. ``upcoming_deadlines`` counts
    rows whose reply_deadline is within ``deadline_window_days`` of
    today and hasn't been actioned yet (final_decision is null)."""
    import datetime as _dt
    rows = list_offer_rows()
    today = _dt.date.today()
    cutoff = today + _dt.timedelta(days=deadline_window_days)
    by_decision: dict[str, int] = {}
    by_final: dict[str, int] = {}
    n_offers = 0
    n_scholarship = 0
    n_accom = 0
    upcoming = 0
    for r in rows:
        by_decision[r.decision_status] = by_decision.get(
            r.decision_status, 0) + 1
        if r.decision_status in OFFER_DECISION_STATUSES:
            n_offers += 1
        key = r.final_decision or "(none)"
        by_final[key] = by_final.get(key, 0) + 1
        if r.details and r.details.scholarship:
            n_scholarship += 1
        if r.details and r.details.accommodation_guaranteed:
            n_accom += 1
        if (r.details and r.details.reply_deadline
                and r.final_decision is None):
            try:
                d = _dt.date.fromisoformat(r.details.reply_deadline)
            except ValueError:
                continue
            if today <= d <= cutoff:
                upcoming += 1
    return OfferSummary(
        total_choices=len(rows), total_offers=n_offers,
        by_decision=by_decision, by_final=by_final,
        with_scholarship=n_scholarship,
        with_accommodation=n_accom,
        upcoming_deadlines=upcoming,
    )
