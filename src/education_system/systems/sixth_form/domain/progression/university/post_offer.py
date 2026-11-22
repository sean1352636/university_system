"""UCAS Extra, Clearing and Adjustment — what happens after the offers.

The UCAS package followed an application up to Firm and Insurance and
then stopped: a learner with no offers, or who missed their grades, fell
off the end of the workflow with nothing to record what the college did
next. This module is that next stage.

Three **routes**, each a row in ``ucas_post_offer_routes`` per
application:

``Extra``       open between February and early July to an applicant who
                used all five choices and holds no offers (none made, or
                every offer declined). One Extra choice at a time.
``Clearing``    from results day (and for anyone applying after 30 June):
                applicants with no confirmed place — no offers held,
                conditions not met at both Firm and Insurance, or a place
                released through "decline my place".
``Adjustment``  results day, for an applicant whose Firm was confirmed
                *and* who exceeded its conditions and wants to look for a
                course with higher requirements. UCAS withdrew the formal
                Adjustment service after the 2021 cycle; the same trade-up
                now happens by releasing the confirmed place into Clearing.
                The route is kept, as the college still advises on it, and
                placing someone through it records the release.

Eligibility is *derived* from the choices and the results-day
confirmation, never typed: :func:`eligibility` explains each route's
answer and :func:`open_route` refuses an ineligible one.

Each route carries its own **choices** (``ucas_post_offer_choices`` — the
Extra choice, the Clearing courses called) and the **contact log**
(``ucas_university_contacts``) records every call to an admissions office.
Recording a route's outcome moves the application's status: Clearing →
``Clearing`` while open and ``Confirmed`` when placed.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from education_system.systems.sixth_form.infrastructure import database as _sql
from dataclasses import dataclass, field
from typing import Any

from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_UCAS_DB

EXTRA = "Extra"
CLEARING = "Clearing"
ADJUSTMENT = "Adjustment"
ROUTES: tuple[str, ...] = (EXTRA, CLEARING, ADJUSTMENT)

ROUTE_STATUSES: tuple[str, ...] = (
    "Active", "Placed", "Closed - not placed", "Withdrawn",
)
OPEN_ROUTE_STATUSES = ("Active",)

CHOICE_STATUSES: tuple[str, ...] = (
    "Considering", "Applied / referred", "Verbal offer", "Offer",
    "Accepted", "Declined", "Unsuccessful",
)

CONTACT_METHODS: tuple[str, ...] = (
    "Phone", "Email", "UCAS Hub", "Online form", "In person", "Other",
)

#: Results-day confirmation outcomes, per application.
CONFIRMATION_OUTCOMES: tuple[str, ...] = (
    "Firm confirmed",
    "Insurance confirmed",
    "Changed course offer",
    "Unsuccessful at Firm and Insurance",
    "Released (decline my place)",
    "Awaiting confirmation",
)

#: Extra runs from late February to early July. Constants because UCAS
#: publishes the exact dates each cycle — check them and adjust here.
EXTRA_OPENS = (2, 26)    # (month, day) in the entry year
EXTRA_CLOSES = (7, 4)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_OFFER = ("Unconditional Offer", "Conditional Offer")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ucas_results_confirmation (
    application_id      INTEGER PRIMARY KEY,
    outcome             TEXT NOT NULL,
    exceeded_conditions INTEGER NOT NULL DEFAULT 0,
    confirmed_on        TEXT,
    notes               TEXT,
    recorded_by         TEXT,
    updated_at          TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (application_id)
        REFERENCES ucas_applications(application_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ucas_post_offer_routes (
    route_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id   INTEGER NOT NULL,
    route            TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'Active',
    eligible_reason  TEXT,
    opened_on        TEXT,
    opened_by        TEXT,
    closed_on        TEXT,
    outcome          TEXT,
    placed_choice_id INTEGER,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    UNIQUE (application_id, route),
    FOREIGN KEY (application_id)
        REFERENCES ucas_applications(application_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ucas_post_offer_choices (
    po_choice_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id           INTEGER NOT NULL,
    university         TEXT NOT NULL,
    course_code        TEXT,
    course_name        TEXT NOT NULL,
    entry_requirements TEXT,
    status             TEXT NOT NULL DEFAULT 'Considering',
    decision_date      TEXT,
    notes              TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (route_id)
        REFERENCES ucas_post_offer_routes(route_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ucas_university_contacts (
    contact_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id  INTEGER NOT NULL,
    route_id        INTEGER,
    university      TEXT NOT NULL,
    contact_date    TEXT NOT NULL,
    method          TEXT NOT NULL DEFAULT 'Phone',
    contact_name    TEXT,
    summary         TEXT NOT NULL,
    outcome         TEXT,
    follow_up_date  TEXT,
    logged_by       TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (application_id)
        REFERENCES ucas_applications(application_id) ON DELETE CASCADE,
    FOREIGN KEY (route_id)
        REFERENCES ucas_post_offer_routes(route_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_po_routes_app    ON ucas_post_offer_routes(application_id);
CREATE INDEX IF NOT EXISTS idx_po_choices_route ON ucas_post_offer_choices(route_id);
CREATE INDEX IF NOT EXISTS idx_uni_contacts_app ON ucas_university_contacts(application_id);
"""


class ValidationError(ValueError):
    """Raised for invalid post-offer input or an ineligible route."""


def _connect() -> _sql.Connection:
    paths.ensure_sixth_form_directories()
    conn = _sql.connect(str(DB_PATH))
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.systems.sixth_form.domain.progression.university import ucas as _ucas
    _ucas.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    _DB_READY = True
    logger.debug("UCAS post-offer schema ready at %s", DB_PATH)


def _date(value: Any, label: str, *, required: bool = False) -> str | None:
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


def _text(value: Any) -> str | None:
    return (str(value).strip() if value is not None else "") or None


def _app(application_id: int):
    from education_system.systems.sixth_form.domain.progression.university import ucas as _ucas
    app = _ucas.get_application(int(application_id))
    if app is None:
        raise ValidationError(f"No application with id {application_id}")
    return app


# ── Results-day confirmation ────────────────────────────────────────

def get_confirmation(application_id: int) -> dict[str, Any] | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM ucas_results_confirmation WHERE application_id=?",
                         (application_id,)).fetchone()
    return dict(r) if r else None


def record_confirmation(application_id: int, outcome: str, *,
                        exceeded_conditions: bool = False,
                        confirmed_on: str | None = None,
                        notes: str | None = None,
                        recorded_by: str | None = None) -> dict[str, Any]:
    """What UCAS said on results day for this application."""
    init_db()
    _app(application_id)
    if outcome not in CONFIRMATION_OUTCOMES:
        raise ValidationError(
            f"Outcome must be one of: {', '.join(CONFIRMATION_OUTCOMES)}")
    if exceeded_conditions and outcome != "Firm confirmed":
        raise ValidationError(
            "'Exceeded conditions' only applies to a confirmed Firm place.")
    with _connect() as conn:
        conn.execute(
            """INSERT INTO ucas_results_confirmation
                   (application_id, outcome, exceeded_conditions, confirmed_on,
                    notes, recorded_by, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(application_id) DO UPDATE SET
                   outcome = excluded.outcome,
                   exceeded_conditions = excluded.exceeded_conditions,
                   confirmed_on = excluded.confirmed_on,
                   notes = excluded.notes, recorded_by = excluded.recorded_by,
                   updated_at = datetime('now')""",
            (application_id, outcome, 1 if exceeded_conditions else 0,
             _date(confirmed_on, "Confirmed on") or _dt.date.today().isoformat(),
             _text(notes), recorded_by))
        conn.commit()
    logger.info("Results confirmation for application #%d: %s", application_id, outcome)
    _reroute_handover(application_id, recorded_by)
    out = get_confirmation(application_id)
    assert out is not None
    return out


def _reroute_handover(application_id: int, actor: str | None) -> None:
    """Re-run the university handover if results day moved the place.

    An Insurance confirmed, a released place or a Clearing placement can
    each change where the learner is going after the university was told
    about their Firm choice. Best-effort: the outcome is recorded either
    way, and a reroute that cannot be sent is logged and can be retried by
    recording the outcome again.
    """
    try:
        from education_system.systems.sixth_form.domain.progression import (
            university_handover,
        )
        result = university_handover.reroute_for_ucas_application(
            application_id, actor=actor)
        if result is not None and result.changed:
            logger.info("Application #%d: university handover %s — %s",
                        application_id, result.action, result.detail)
    except Exception:
        logger.exception("Could not re-check the university handover for "
                         "application #%d", application_id)


# ── Eligibility ─────────────────────────────────────────────────────

@dataclass
class Eligibility:
    route: str
    eligible: bool
    reason: str


def _results_day(cycle_year: int) -> _dt.date:
    from education_system.systems.sixth_form.domain.progression.university import (
        deadlines as _dl,
    )
    return _dl.get_deadline(cycle_year, _dl.RESULTS_DAY).date


def _june_final(cycle_year: int) -> _dt.date:
    from education_system.systems.sixth_form.domain.progression.university import (
        deadlines as _dl,
    )
    return _dl.get_deadline(cycle_year, _dl.JUNE_FINAL).date


def eligibility(application_id: int, *,
                today: _dt.date | None = None) -> list[Eligibility]:
    """Each route's answer for this application, with the reason."""
    init_db()
    from education_system.systems.sixth_form.domain.progression.university import ucas as _ucas
    app = _app(application_id)
    today = today or _dt.date.today()
    choices = _ucas.list_choices(app.application_id)
    offers = [c for c in choices if c.decision_status in _OFFER]
    held = [c for c in offers if c.final_decision in ("Firm", "Insurance")]
    undeclined = [c for c in offers if c.final_decision != "Declined"]
    awaiting = [c for c in choices if c.decision_status == "Awaiting"]
    conf = get_confirmation(app.application_id)
    # An offer accepted through Extra becomes the applicant's Firm choice.
    placed_extra = any(r["route"] == EXTRA and r["status"] == "Placed"
                       for r in list_routes(application_id=app.application_id))
    results_day = _results_day(app.cycle_year)
    submitted = (app.submitted_at or "").strip()
    out: list[Eligibility] = []

    # Extra
    extra_open = _dt.date(app.cycle_year, *EXTRA_OPENS)
    extra_close = _dt.date(app.cycle_year, *EXTRA_CLOSES)
    if not submitted:
        out.append(Eligibility(EXTRA, False, "The application has not been submitted."))
    elif len(choices) < 5:
        out.append(Eligibility(EXTRA, False,
                               f"Only {len(choices)} of 5 choices used — add the "
                               "remaining choices instead of using Extra."))
    elif awaiting:
        out.append(Eligibility(EXTRA, False,
                               f"{len(awaiting)} choice(s) still awaiting a decision."))
    elif undeclined:
        out.append(Eligibility(EXTRA, False,
                               f"Holds {len(undeclined)} offer(s) not declined."))
    elif placed_extra:
        out.append(Eligibility(EXTRA, False, "Already accepted an offer through Extra."))
    elif not (extra_open <= today <= extra_close):
        out.append(Eligibility(EXTRA, False,
                               f"Extra runs {extra_open} to {extra_close}."))
    else:
        out.append(Eligibility(EXTRA, True,
                               "All five choices used and no offers held."))

    # Clearing
    late = submitted and submitted[:10] > _june_final(app.cycle_year).isoformat()
    if today < results_day and not late:
        out.append(Eligibility(CLEARING, False,
                               f"Clearing opens to this applicant on results day "
                               f"({results_day}), or immediately for an application "
                               "made after 30 June."))
    elif late:
        out.append(Eligibility(CLEARING, True, "Applied after 30 June — Clearing only."))
    elif not held and not placed_extra:
        out.append(Eligibility(CLEARING, True, "No Firm or Insurance offer held."))
    elif conf and conf["outcome"] in ("Unsuccessful at Firm and Insurance",
                                      "Released (decline my place)"):
        out.append(Eligibility(CLEARING, True, f"Results day: {conf['outcome']}."))
    elif conf is None or conf["outcome"] == "Awaiting confirmation":
        out.append(Eligibility(CLEARING, False,
                               "Holds a Firm/Insurance (or Extra) offer — record the "
                               "results-day confirmation first."))
    else:
        out.append(Eligibility(CLEARING, False,
                               f"Place confirmed ({conf['outcome']})."))

    # Adjustment
    if today < results_day:
        out.append(Eligibility(ADJUSTMENT, False, f"Only from results day ({results_day})."))
    elif not conf or conf["outcome"] != "Firm confirmed":
        out.append(Eligibility(ADJUSTMENT, False, "Needs a confirmed Firm place."))
    elif not conf["exceeded_conditions"]:
        out.append(Eligibility(ADJUSTMENT, False,
                               "The Firm conditions were met but not exceeded."))
    else:
        out.append(Eligibility(ADJUSTMENT, True,
                               "Firm confirmed with conditions exceeded."))
    return out


def eligible_routes(application_id: int, *, today: _dt.date | None = None) -> list[str]:
    return [e.route for e in eligibility(application_id, today=today) if e.eligible]


# ── Routes ──────────────────────────────────────────────────────────

def get_route(route_id: int) -> dict[str, Any] | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM ucas_post_offer_routes WHERE route_id=?",
                         (route_id,)).fetchone()
    return dict(r) if r else None


def list_routes(*, application_id: int | None = None, route: str | None = None,
                status: str | None = None, cycle_year: int | None = None) -> list[dict[str, Any]]:
    """Routes joined to their applicant, newest first."""
    init_db()
    clauses, args = [], []
    if application_id is not None:
        clauses.append("r.application_id = ?"); args.append(application_id)
    if route:
        clauses.append("r.route = ?"); args.append(route)
    if status:
        clauses.append("r.status = ?"); args.append(status)
    if cycle_year is not None:
        clauses.append("a.cycle_year = ?"); args.append(cycle_year)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"""SELECT r.*, a.student_id, a.cycle_year,
                       s.first_name || ' ' || s.last_name AS student_name,
                       (SELECT COUNT(*) FROM ucas_post_offer_choices c
                         WHERE c.route_id = r.route_id) AS n_choices
                  FROM ucas_post_offer_routes r
                  JOIN ucas_applications a ON a.application_id = r.application_id
                  LEFT JOIN students s ON s.student_id = a.student_id
                  {where}
                 ORDER BY r.updated_at DESC, r.route_id DESC""", args).fetchall()
    return [dict(r) for r in rows]


def open_route(application_id: int, route: str, *, opened_by: str | None = None,
               notes: str | None = None, today: _dt.date | None = None) -> dict[str, Any]:
    """Start Extra / Clearing / Adjustment for an eligible application."""
    init_db()
    if route not in ROUTES:
        raise ValidationError(f"Route must be one of: {', '.join(ROUTES)}")
    app = _app(application_id)
    verdict = next(e for e in eligibility(application_id, today=today) if e.route == route)
    if not verdict.eligible:
        raise ValidationError(f"Not eligible for {route}: {verdict.reason}")
    today_iso = (today or _dt.date.today()).isoformat()
    with _connect() as conn:
        existing = conn.execute(
            "SELECT route_id, status FROM ucas_post_offer_routes "
            "WHERE application_id=? AND route=?", (application_id, route)).fetchone()
        if existing and existing["status"] in OPEN_ROUTE_STATUSES:
            raise ValidationError(f"{route} is already open for this application.")
        if existing:
            conn.execute(
                """UPDATE ucas_post_offer_routes SET status='Active',
                       eligible_reason=?, opened_on=?, opened_by=?, closed_on=NULL,
                       outcome=NULL, placed_choice_id=NULL, notes=?,
                       updated_at=datetime('now') WHERE route_id=?""",
                (verdict.reason, today_iso, opened_by, _text(notes), existing["route_id"]))
            route_id = existing["route_id"]
        else:
            cur = conn.execute(
                """INSERT INTO ucas_post_offer_routes
                       (application_id, route, status, eligible_reason,
                        opened_on, opened_by, notes)
                   VALUES (?, ?, 'Active', ?, ?, ?, ?)""",
                (application_id, route, verdict.reason, today_iso, opened_by,
                 _text(notes)))
            route_id = cur.lastrowid
        conn.commit()
    if route in (CLEARING, ADJUSTMENT):
        _set_app_status(app, "Clearing")
    logger.info("Opened %s for application #%d (route #%d)", route, application_id, route_id)
    out = get_route(route_id)
    assert out is not None
    return out


def _set_app_status(app, status: str) -> None:
    from education_system.systems.sixth_form.domain.progression.university import ucas as _ucas
    if app.status != status:
        _ucas.update_application(app.application_id, {"status": status})


def close_route(route_id: int, *, status: str, outcome: str | None = None,
                placed_po_choice_id: int | None = None,
                closed_on: str | None = None) -> dict[str, Any]:
    """Record how the route ended. ``Placed`` needs the accepted choice."""
    init_db()
    r = get_route(route_id)
    if r is None:
        raise ValidationError(f"No route with id {route_id}")
    if status not in ROUTE_STATUSES or status == "Active":
        raise ValidationError("Closing status must be Placed, Closed - not placed "
                              "or Withdrawn.")
    placed = None
    if status == "Placed":
        if not placed_po_choice_id:
            raise ValidationError("Say which choice the student was placed on.")
        placed = get_choice(int(placed_po_choice_id))
        if placed is None or placed["route_id"] != route_id:
            raise ValidationError("That choice does not belong to this route.")
    with _connect() as conn:
        conn.execute(
            """UPDATE ucas_post_offer_routes SET status=?, outcome=?,
                   placed_choice_id=?, closed_on=?, updated_at=datetime('now')
               WHERE route_id=?""",
            (status, _text(outcome) or (
                f"Placed: {placed['university']} — {placed['course_name']}"
                if placed else None),
             placed["po_choice_id"] if placed else None,
             _date(closed_on, "Closed on") or _dt.date.today().isoformat(), route_id))
        if placed:
            conn.execute(
                "UPDATE ucas_post_offer_choices SET status='Accepted', "
                "updated_at=datetime('now') WHERE po_choice_id=?",
                (placed["po_choice_id"],))
        conn.commit()
    app = _app(r["application_id"])
    if status == "Placed":
        _set_app_status(app, "Confirmed" if r["route"] in (CLEARING, ADJUSTMENT)
                        else "Replied")
        _reroute_handover(r["application_id"], None)
    logger.info("Closed %s route #%d: %s", r["route"], route_id, status)
    out = get_route(route_id)
    assert out is not None
    return out


# ── Route choices ───────────────────────────────────────────────────

def get_choice(po_choice_id: int) -> dict[str, Any] | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM ucas_post_offer_choices WHERE po_choice_id=?",
                         (po_choice_id,)).fetchone()
    return dict(r) if r else None


def list_choices(route_id: int) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM ucas_post_offer_choices WHERE route_id=? "
            "ORDER BY po_choice_id", (route_id,))]


def _validate_choice(data: dict[str, Any]) -> dict[str, Any]:
    uni = _text(data.get("university"))
    course = _text(data.get("course_name"))
    if not uni:
        raise ValidationError("University is required")
    if not course:
        raise ValidationError("Course name is required")
    status = _text(data.get("status")) or "Considering"
    if status not in CHOICE_STATUSES:
        raise ValidationError(f"Status must be one of: {', '.join(CHOICE_STATUSES)}")
    return {
        "university": uni, "course_name": course,
        "course_code": _text(data.get("course_code")),
        "entry_requirements": _text(data.get("entry_requirements")),
        "status": status,
        "decision_date": _date(data.get("decision_date"), "Decision date"),
        "notes": _text(data.get("notes")),
    }


def add_choice(route_id: int, data: dict[str, Any]) -> dict[str, Any]:
    init_db()
    r = get_route(route_id)
    if r is None:
        raise ValidationError(f"No route with id {route_id}")
    if r["status"] not in OPEN_ROUTE_STATUSES:
        raise ValidationError(f"This {r['route']} route is closed.")
    p = _validate_choice(data)
    if r["route"] == EXTRA:
        # UCAS allows one Extra choice at a time: a new one only once the
        # last was declined, unsuccessful, or withdrawn.
        live = [c for c in list_choices(route_id)
                if c["status"] not in ("Declined", "Unsuccessful")]
        if live:
            raise ValidationError(
                "Extra allows one choice at a time — record the outcome of "
                f"{live[0]['university']} first.")
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO ucas_post_offer_choices
                   (route_id, university, course_code, course_name,
                    entry_requirements, status, decision_date, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (route_id, p["university"], p["course_code"], p["course_name"],
             p["entry_requirements"], p["status"], p["decision_date"], p["notes"]))
        conn.execute("UPDATE ucas_post_offer_routes SET updated_at=datetime('now') "
                     "WHERE route_id=?", (route_id,))
        conn.commit()
        new_id = cur.lastrowid
    out = get_choice(new_id)
    assert out is not None
    return out


def update_choice(po_choice_id: int, data: dict[str, Any]) -> dict[str, Any]:
    init_db()
    existing = get_choice(po_choice_id)
    if existing is None:
        raise ValidationError(f"No choice with id {po_choice_id}")
    p = _validate_choice({k: data.get(k, existing.get(k)) for k in (
        "university", "course_name", "course_code", "entry_requirements",
        "status", "decision_date", "notes")})
    with _connect() as conn:
        conn.execute(
            """UPDATE ucas_post_offer_choices SET university=?, course_code=?,
                   course_name=?, entry_requirements=?, status=?, decision_date=?,
                   notes=?, updated_at=datetime('now') WHERE po_choice_id=?""",
            (p["university"], p["course_code"], p["course_name"],
             p["entry_requirements"], p["status"], p["decision_date"], p["notes"],
             po_choice_id))
        conn.commit()
    out = get_choice(po_choice_id)
    assert out is not None
    return out


def delete_choice(po_choice_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM ucas_post_offer_choices WHERE po_choice_id=?",
                           (po_choice_id,))
        conn.commit()
    return bool(cur.rowcount)


# ── Contact log ─────────────────────────────────────────────────────

def log_contact(application_id: int, data: dict[str, Any], *,
                logged_by: str | None = None) -> dict[str, Any]:
    init_db()
    _app(application_id)
    uni = _text(data.get("university"))
    summary = _text(data.get("summary"))
    if not uni:
        raise ValidationError("University is required")
    if not summary:
        raise ValidationError("Summary of the contact is required")
    method = _text(data.get("method")) or "Phone"
    if method not in CONTACT_METHODS:
        raise ValidationError(f"Method must be one of: {', '.join(CONTACT_METHODS)}")
    route_id = data.get("route_id")
    route_id = int(route_id) if route_id not in (None, "") else None
    if route_id is not None:
        r = get_route(route_id)
        if r is None or r["application_id"] != int(application_id):
            raise ValidationError("That route does not belong to this application.")
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO ucas_university_contacts
                   (application_id, route_id, university, contact_date, method,
                    contact_name, summary, outcome, follow_up_date, logged_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (application_id, route_id, uni,
             _date(data.get("contact_date"), "Contact date") or _dt.date.today().isoformat(),
             method, _text(data.get("contact_name")), summary,
             _text(data.get("outcome")),
             _date(data.get("follow_up_date"), "Follow-up date"), logged_by))
        conn.commit()
        new_id = cur.lastrowid
    with _connect() as conn:
        return dict(conn.execute("SELECT * FROM ucas_university_contacts WHERE contact_id=?",
                                 (new_id,)).fetchone())


def list_contacts(*, application_id: int | None = None,
                  follow_ups_due_by: str | None = None) -> list[dict[str, Any]]:
    init_db()
    clauses, args = [], []
    if application_id is not None:
        clauses.append("c.application_id = ?"); args.append(application_id)
    if follow_ups_due_by:
        clauses.append("c.follow_up_date IS NOT NULL AND c.follow_up_date <= ?")
        args.append(follow_ups_due_by)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        return [dict(r) for r in conn.execute(
            f"""SELECT c.*, a.student_id, r.route
                  FROM ucas_university_contacts c
                  JOIN ucas_applications a ON a.application_id = c.application_id
                  LEFT JOIN ucas_post_offer_routes r ON r.route_id = c.route_id
                  {where}
                 ORDER BY c.contact_date DESC, c.contact_id DESC""", args)]


def delete_contact(contact_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM ucas_university_contacts WHERE contact_id=?",
                           (contact_id,))
        conn.commit()
    return bool(cur.rowcount)


# ── Cohort view ─────────────────────────────────────────────────────

@dataclass
class CohortRow:
    application_id: int
    student_id: str
    student_name: str
    status: str
    eligible: list[str] = field(default_factory=list)
    open_routes: list[str] = field(default_factory=list)
    confirmation: str | None = None

    def as_row(self) -> dict[str, Any]:
        return {"application_id": self.application_id,
                "student_id": self.student_id, "student_name": self.student_name,
                "status": self.status, "eligible": ", ".join(self.eligible) or "—",
                "open_routes": ", ".join(self.open_routes) or "—",
                "confirmation": self.confirmation or "—"}


def cohort(cycle_year: int, *, today: _dt.date | None = None,
           only_actionable: bool = False) -> list[CohortRow]:
    """Each application with the routes it can open and those already open."""
    init_db()
    from education_system.systems.sixth_form.domain.progression.university import ucas as _ucas
    rows = []
    open_by_app: dict[int, list[str]] = {}
    for r in list_routes(cycle_year=cycle_year, status="Active"):
        open_by_app.setdefault(r["application_id"], []).append(r["route"])
    for detail in _ucas.list_applications_with_detail(cycle_year=cycle_year):
        app = detail.application
        elig = [e.route for e in eligibility(app.application_id, today=today) if e.eligible]
        conf = get_confirmation(app.application_id)
        row = CohortRow(app.application_id, app.student_id, detail.student_name,
                        app.status, elig, open_by_app.get(app.application_id, []),
                        conf["outcome"] if conf else None)
        if only_actionable and not (row.eligible or row.open_routes):
            continue
        rows.append(row)
    return rows


__all__ = [
    "EXTRA", "CLEARING", "ADJUSTMENT", "ROUTES", "ROUTE_STATUSES",
    "CHOICE_STATUSES", "CONTACT_METHODS", "CONFIRMATION_OUTCOMES",
    "ValidationError", "Eligibility", "CohortRow",
    "get_confirmation", "record_confirmation", "eligibility", "eligible_routes",
    "get_route", "list_routes", "open_route", "close_route",
    "get_choice", "list_choices", "add_choice", "update_choice", "delete_choice",
    "log_contact", "list_contacts", "delete_contact", "cohort",
]
