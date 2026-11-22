"""What the university keeps from a sixth-form handover, beyond the applicant.

``sixthform_intake`` turns a handover into an application. Three things
the handover now carries had nowhere to land on the application itself:

**Routing** (``admission_handover_routing``)
    Which choice placed the learner here — Firm, Insurance (Firm missed),
    Clearing, Adjustment or Extra — with the course, the entry year and
    whether entry is *deferred* (a gap year). One row per application;
    every change is a row in ``admission_handover_route_history`` and a
    line in the application's own ``admission_status_history``.

    When the sixth form re-routes a learner after results day the intake
    **updates** the application it already holds for the journey — the
    new course becomes a choice (and the accepted one, if a choice had been
    accepted), conditions from the superseded offer are marked
    ``superseded`` rather than left to hold the conversion gate shut — and
    when the learner is now going somewhere else the application is marked
    *withdrawn by reroute*: declined, with the reason, never deleted.

    A deferred entry records its year on the application and holds
    conversion closed until that year (:func:`deferred_entry_issue`, read
    by ``admissions_lifecycle.readiness_issues``).

**Contextual flags** (``admission_contextual_flags``)
    Care experienced, free school meals, 16-19 bursary, young carer, first
    generation in HE — only as sent, only when the learner consented to
    that specific purpose at the sixth form, and otherwise a ``withheld``
    row saying so. Readable only through :func:`contextual_flags`, which
    requires the admissions decision permission and writes an access-log
    row (``admission_contextual_access_log``) for every attempt, allowed or
    not.

Schema is created lazily (``CREATE TABLE IF NOT EXISTS``), matching the
admissions CRM tables it hangs off; ``sixthform_intake.ensure_schema``
calls :func:`ensure_tables`.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)

ROUTING_ACTIVE = "active"
ROUTING_WITHDRAWN = "withdrawn_by_reroute"

CONTEXTUAL_RELEASED = "released"
CONTEXTUAL_WITHHELD = "withheld"

#: The capability that gates contextual flags: the university's existing
#: admissions-decision permission. Contextual data informs an admissions
#: decision and nothing else, so whoever may decide applications may see
#: it, and nobody else may.
VIEW_PERMISSION = "approve_applications"
_PRIVILEGED_ROLES = frozenset({"admin", "superadmin"})

#: Readable names, for screens.
FLAG_LABELS: dict[str, str] = {
    "care_experienced": "Care experienced",
    "free_school_meals": "Free school meals",
    "bursary_16_19": "16-19 bursary",
    "young_carer": "Young carer",
    "first_generation_he": "First generation in HE",
    "polar_tundra_band": "POLAR/TUNDRA band",
}

_ACTOR = "sixth_form_handover"

_DDL = """
CREATE TABLE IF NOT EXISTS admission_handover_routing (
    application_id  INTEGER PRIMARY KEY,
    journey_id      TEXT,
    route           TEXT,
    institution     TEXT,
    course_code     TEXT,
    course_name     TEXT,
    entry_year      TEXT,
    deferred        INTEGER NOT NULL DEFAULT 0,
    routing_status  TEXT NOT NULL DEFAULT 'active',
    rerouted_at     TEXT,
    reroute_reason  TEXT,
    source_event_id TEXT,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (application_id)
        REFERENCES admission_applications(application_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_handover_routing_journey
    ON admission_handover_routing(journey_id);

CREATE TABLE IF NOT EXISTS admission_handover_route_history (
    history_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id   INTEGER NOT NULL,
    action           TEXT NOT NULL,
    from_route       TEXT,
    from_course_code TEXT,
    from_course_name TEXT,
    from_entry_year  TEXT,
    to_route         TEXT,
    to_institution   TEXT,
    to_course_code   TEXT,
    to_course_name   TEXT,
    to_entry_year    TEXT,
    deferred         INTEGER NOT NULL DEFAULT 0,
    reason           TEXT,
    source_event_id  TEXT,
    recorded_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (application_id)
        REFERENCES admission_applications(application_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_handover_route_history_app
    ON admission_handover_route_history(application_id);

CREATE TABLE IF NOT EXISTS admission_contextual_flags (
    application_id       INTEGER PRIMARY KEY,
    journey_id           TEXT,
    status               TEXT NOT NULL,
    flags_json           TEXT,
    not_held_json        TEXT,
    consent_reference    TEXT,
    consent_granted_date TEXT,
    withheld_reason      TEXT,
    source_event_id      TEXT,
    received_at          TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (application_id)
        REFERENCES admission_applications(application_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS admission_contextual_access_log (
    log_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL,
    viewer         TEXT,
    allowed        INTEGER NOT NULL,
    viewed_at      TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

_ready = False


def _db():
    from education_system.systems.university.infrastructure.database import db
    return db


def ensure_tables() -> bool:
    """Create the tables if missing. Once per process; never raises."""
    global _ready
    if _ready:
        return True
    try:
        with _db().get_connection() as conn:
            conn.executescript(_DDL)
            conn.commit()
        _ready = True
    except Exception:
        logger.exception("Could not prepare the sixth-form handover tables")
    return _ready


# ── Reading routing out of a payload ────────────────────────────────

def _year(value: Any) -> str:
    return str(value).strip() if value not in (None, "") else ""


def routing_from_payload(payload: dict) -> dict[str, Any] | None:
    """Routing as a progression handover states it, or ``None``."""
    dest = (payload or {}).get("confirmed_destination") or {}
    if not dest:
        return None
    return {
        "route": dest.get("route") or "Firm",
        "institution": dest.get("university") or "",
        "course_code": (dest.get("course_code") or "").strip(),
        "course_name": (dest.get("course_name") or "").strip(),
        "entry_year": _year(dest.get("entry_year")),
        "deferred": bool(dest.get("deferred")),
    }


def routing_from_reroute(payload: dict) -> dict[str, Any]:
    """Routing as a ``ucas.handover.rerouted`` notice states it."""
    payload = payload or {}
    return {
        "route": payload.get("to_route") or "",
        "institution": payload.get("to_institution") or "",
        "course_code": (payload.get("to_course_code") or "").strip(),
        "course_name": (payload.get("to_course_name") or "").strip(),
        "entry_year": _year(payload.get("to_entry_year")),
        "deferred": bool(payload.get("to_deferred")),
    }


def entry_label(routing: dict | None) -> str:
    """"Deferred to 2028" for a deferred entry, else ""."""
    if not routing or not routing.get("deferred"):
        return ""
    year = _year(routing.get("entry_year"))
    return f"Deferred to {year}" if year else "Deferred entry"


def routing_label(routing: dict | None) -> str:
    """One line for a board: route, deferral and withdrawal."""
    if not routing:
        return ""
    if routing.get("routing_status") == ROUTING_WITHDRAWN:
        return f"Withdrawn — rerouted ({routing.get('reroute_reason') or 'destination changed'})"
    parts = []
    route = routing.get("route")
    if route and route != "Firm":
        parts.append(f"Via {route}")
    label = entry_label(routing)
    if label:
        parts.append(label)
    return " · ".join(parts)


# ── Routing reads ───────────────────────────────────────────────────

def get_routing(application_id: int) -> dict | None:
    if not ensure_tables():
        return None
    with _db().get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM admission_handover_routing WHERE application_id = ?",
            (int(application_id),)).fetchone()
    return dict(row) if row else None


def routing_for(application_ids) -> dict[int, dict]:
    """``{application_id: routing}`` in one query."""
    ids = [int(a) for a in application_ids if a is not None]
    if not ids or not ensure_tables():
        return {}
    out: dict[int, dict] = {}
    with _db().get_connection() as conn:
        for start in range(0, len(ids), 500):
            chunk = ids[start:start + 500]
            marks = ",".join("?" * len(chunk))
            # db-audit: ignore[DBW001] - join of placeholders
            for row in conn.execute(
                    f"SELECT * FROM admission_handover_routing "
                    f"WHERE application_id IN ({marks})", chunk):  # nosec B608
                out[int(row["application_id"])] = dict(row)
    return out


def route_history(application_id: int) -> list[dict]:
    if not ensure_tables():
        return []
    with _db().get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM admission_handover_route_history "
            "WHERE application_id = ? ORDER BY history_id",
            (int(application_id),))]


def deferred_entry_issue(application_id: int, *,
                         today: date | None = None) -> str | None:
    """Why a deferred entry may not convert yet, or ``None``.

    A deferred place is confirmed this cycle and taken up in a later one.
    Converting it now would enrol the learner a year early, so the
    conversion gate stays shut until the entry year arrives.
    """
    try:
        routing = get_routing(application_id)
    except Exception:
        logger.exception("Could not read routing for application %s",
                         application_id)
        return None
    if not routing or not routing.get("deferred") \
            or routing.get("routing_status") == ROUTING_WITHDRAWN:
        return None
    try:
        entry = int(str(routing.get("entry_year") or "").strip())
    except ValueError:
        return "deferred entry with no entry year recorded"
    year = (today or date.today()).year
    if entry > year:
        return (f"deferred entry to {entry} — this place converts for the "
                f"{entry} intake, not this year")
    return None


# ── Routing writes ──────────────────────────────────────────────────

def _history(conn, application_id: int, action: str, *, before: dict | None,
             after: dict, reason: str, source_event_id: str | None) -> None:
    before = before or {}
    conn.execute(
        """INSERT INTO admission_handover_route_history
               (application_id, action, from_route, from_course_code,
                from_course_name, from_entry_year, to_route, to_institution,
                to_course_code, to_course_name, to_entry_year, deferred,
                reason, source_event_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (application_id, action, before.get("route"),
         before.get("course_code"), before.get("course_name"),
         before.get("entry_year"), after.get("route"),
         after.get("institution"), after.get("course_code"),
         after.get("course_name"), after.get("entry_year"),
         1 if after.get("deferred") else 0, reason, source_event_id))


def _status_note(conn, application_id: int, status: str, reason: str) -> None:
    """An audit line on the application's own history, status unchanged."""
    conn.execute(
        """INSERT INTO admission_status_history
               (application_id, from_status, to_status, reason, actor_id)
           VALUES (?, ?, ?, ?, ?)""",
        (application_id, status, status, reason, _ACTOR))


def _upsert_routing(conn, application_id: int, journey_id: str | None,
                    routing: dict, *, status: str, reason: str | None,
                    source_event_id: str | None, rerouted: bool) -> None:
    conn.execute(
        """INSERT INTO admission_handover_routing
               (application_id, journey_id, route, institution, course_code,
                course_name, entry_year, deferred, routing_status,
                rerouted_at, reroute_reason, source_event_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(application_id) DO UPDATE SET
               journey_id = COALESCE(excluded.journey_id,
                                     admission_handover_routing.journey_id),
               route = excluded.route, institution = excluded.institution,
               course_code = excluded.course_code,
               course_name = excluded.course_name,
               entry_year = excluded.entry_year,
               deferred = excluded.deferred,
               routing_status = excluded.routing_status,
               rerouted_at = COALESCE(excluded.rerouted_at,
                                      admission_handover_routing.rerouted_at),
               reroute_reason = COALESCE(excluded.reroute_reason,
                                         admission_handover_routing.reroute_reason),
               source_event_id = excluded.source_event_id,
               updated_at = CURRENT_TIMESTAMP""",
        (application_id, journey_id, routing.get("route"),
         routing.get("institution"), routing.get("course_code"),
         routing.get("course_name"), routing.get("entry_year"),
         1 if routing.get("deferred") else 0, status,
         date.today().isoformat() if rerouted else None, reason,
         source_event_id))


def _same_course(a: dict, b: dict) -> bool:
    code_a = (a.get("course_code") or "").strip().upper()
    code_b = (b.get("course_code") or "").strip().upper()
    if code_a or code_b:
        return code_a == code_b
    return (a.get("course_name") or "").strip().lower() == \
        (b.get("course_name") or "").strip().lower()


def _describe(routing: dict) -> str:
    course = routing.get("course_name") or routing.get("course_code") or "course"
    code = routing.get("course_code")
    label = f"{course} ({code})" if code and code != course else course
    return f"{routing.get('route') or 'choice'}: {label}"


def apply_offer_conditions(application_id: int, conditions: dict | None
                           ) -> list[str]:
    """Record an offer's academic conditions, idempotently.

    A description already on the application is left alone — or, when it
    was superseded by an earlier reroute and is now current again, put back
    to ``outstanding``. Returns the descriptions added or restored.
    """
    if not conditions:
        return []
    from education_system.systems.university.domains.admissions.domain.services import (
        admissions_lifecycle,
    )
    deadline = conditions.get("reply_deadline") or ""
    wanted = [d for d in (
        conditions.get("grade_requirement"),
        (f"Alternative offer: {conditions['grade_alternative']}"
         if conditions.get("grade_alternative") else None),
    ) if d]
    if not wanted:
        return []
    with _db().get_connection() as conn:
        held = {r["description"]: r["status"] for r in conn.execute(
            "SELECT description, status FROM admission_conditions "
            "WHERE application_id = ? AND condition_type = 'academic'",
            (application_id,))}
    changed: list[str] = []
    for description in wanted:
        status = held.get(description)
        try:
            if status is None:
                admissions_lifecycle.add_condition(
                    application_id, "academic", description,
                    due_date=deadline)
                changed.append(description)
            elif status == "superseded":
                with _db().transaction() as conn:
                    conn.execute(
                        "UPDATE admission_conditions SET status = 'outstanding' "
                        "WHERE application_id = ? AND condition_type = 'academic' "
                        "AND description = ?", (application_id, description))
                changed.append(description)
        except Exception:
            logger.exception("Could not record offer condition on "
                             "application %s", application_id)
    return changed


def apply_routing(application_id: int, routing: dict | None, *,
                  journey_id: str | None = None,
                  offer_conditions: dict | None = None,
                  reason: str = "",
                  source_event_id: str | None = None) -> str:
    """Bring an application in line with the handover's routing.

    Returns what happened: ``recorded`` (first routing for the
    application), ``unchanged``, ``rerouted`` (course, route or entry year
    moved), ``reinstated`` (was withdrawn by reroute, now coming here
    again), ``enrolled`` (already a student — left alone and noted) or
    ``unavailable``.
    """
    if not routing or not ensure_tables():
        return "unavailable"
    from education_system.systems.university.domains.admissions.domain.services import (
        admissions_lifecycle as lifecycle,
    )
    db = _db()
    with db.get_connection() as conn:
        app = conn.execute(
            """SELECT application_id, status, converted_student_id,
                      program_applied, academic_year, accepted_choice_id
                 FROM admission_applications WHERE application_id = ?""",
            (int(application_id),)).fetchone()
        current = conn.execute(
            "SELECT * FROM admission_handover_routing WHERE application_id = ?",
            (int(application_id),)).fetchone()
    if app is None:
        return "unavailable"
    app = dict(app)
    current = dict(current) if current else None
    status = (app.get("status") or "").strip().lower()

    if current is None:
        with db.transaction() as conn:
            _upsert_routing(conn, application_id, journey_id, routing,
                            status=ROUTING_ACTIVE, reason=None,
                            source_event_id=source_event_id, rerouted=False)
            if routing.get("deferred") and routing.get("entry_year"):
                conn.execute(
                    "UPDATE admission_applications SET academic_year = ? "
                    "WHERE application_id = ?",
                    (routing["entry_year"], application_id))
                _status_note(conn, application_id, status,
                             f"Deferred entry to {routing['entry_year']} "
                             f"recorded from the sixth-form handover")
            _history(conn, application_id, "recorded", before=None,
                     after=routing, reason=reason or "Handover received",
                     source_event_id=source_event_id)
        return "recorded"

    course_changed = not _same_course(current, routing)
    entry_changed = (_year(current.get("entry_year")) != routing.get("entry_year")
                     or bool(current.get("deferred")) != bool(routing.get("deferred")))
    route_changed = (current.get("route") or "") != (routing.get("route") or "")
    withdrawn = current.get("routing_status") == ROUTING_WITHDRAWN

    if app.get("converted_student_id"):
        if course_changed or entry_changed or route_changed:
            with db.transaction() as conn:
                _history(conn, application_id, "ignored_enrolled",
                         before=current, after=routing,
                         reason=("Reroute received after enrolment as "
                                 f"{app['converted_student_id']} — not applied; "
                                 + (reason or "")).strip(),
                         source_event_id=source_event_id)
        return "enrolled"

    if not (course_changed or entry_changed or route_changed or withdrawn):
        return "unchanged"

    if withdrawn:
        lifecycle.transition(
            application_id, lifecycle.DOCUMENTS_PENDING,
            reason=(f"Reinstated: the sixth form rerouted the learner back "
                    f"to this university ({_describe(routing)})"),
            actor_id=_ACTOR, force=True)
        status = lifecycle.DOCUMENTS_PENDING

    new_choice_id = None
    if course_changed:
        code = routing.get("course_code") or ""
        name = routing.get("course_name") or ""
        key = code or name or "UNDECLARED"
        with db.get_connection() as conn:
            existing = conn.execute(
                """SELECT choice_id FROM admission_application_choices
                    WHERE application_id = ? AND programme_code = ?""",
                (application_id, key)).fetchone()
            top_rank = conn.execute(
                "SELECT COALESCE(MAX(rank), 0) FROM admission_application_choices "
                "WHERE application_id = ?", (application_id,)).fetchone()[0]
        new_choice_id = (int(existing["choice_id"]) if existing else
                         lifecycle.add_choice(
                             application_id, key, programme_name=name,
                             entry_year=routing.get("entry_year") or "",
                             rank=int(top_rank or 0) + 1))

    summary = (f"Rerouted by the sixth form from {_describe(current)} to "
               f"{_describe(routing)}"
               + (f" — {entry_label(routing)}" if entry_label(routing) else "")
               + (f". {reason}" if reason else ""))
    with db.transaction() as conn:
        if course_changed:
            conn.execute(
                """UPDATE admission_applications
                      SET program_applied = ?,
                          academic_year = COALESCE(NULLIF(?, ''), academic_year)
                    WHERE application_id = ?""",
                (routing.get("course_name") or routing.get("course_code"),
                 routing.get("entry_year") or "", application_id))
            # The superseded offer's grade conditions no longer apply; they
            # are kept, marked, rather than deleted or left to block.
            conn.execute(
                """UPDATE admission_conditions SET status = 'superseded'
                    WHERE application_id = ? AND condition_type = 'academic'
                      AND status <> 'satisfied'""", (application_id,))
            if app.get("accepted_choice_id") and new_choice_id:
                conn.execute(
                    "UPDATE admission_application_choices SET choice_status = "
                    "CASE WHEN choice_id = ? THEN 'accepted' ELSE 'declined' END "
                    "WHERE application_id = ?", (new_choice_id, application_id))
                conn.execute(
                    "UPDATE admission_applications SET accepted_choice_id = ? "
                    "WHERE application_id = ?", (new_choice_id, application_id))
        elif entry_changed and routing.get("entry_year"):
            conn.execute(
                "UPDATE admission_applications SET academic_year = ? "
                "WHERE application_id = ?",
                (routing["entry_year"], application_id))
        _status_note(conn, application_id, status, summary)
        _upsert_routing(conn, application_id, journey_id, routing,
                        status=ROUTING_ACTIVE, reason=summary,
                        source_event_id=source_event_id, rerouted=True)
        _history(conn, application_id,
                 "reinstated" if withdrawn else "rerouted",
                 before=current, after=routing, reason=summary,
                 source_event_id=source_event_id)
    if course_changed:
        apply_offer_conditions(application_id, offer_conditions)
    logger.info("Application %s: %s", application_id, summary)
    return "reinstated" if withdrawn else "rerouted"


def withdraw_by_reroute(application_id: int, *, reason: str,
                        to_institution: str | None = None,
                        to_route: str | None = None,
                        journey_id: str | None = None,
                        source_event_id: str | None = None) -> str:
    """Mark the application withdrawn because the learner went elsewhere.

    Declined through the lifecycle (so it leaves every active list) with
    the reason on its history, the routing row marked
    ``withdrawn_by_reroute`` — and nothing deleted. A learner already
    enrolled is left alone and the notice recorded against them.
    Returns ``withdrawn``, ``already_withdrawn``, ``enrolled`` or
    ``unavailable``.
    """
    if not ensure_tables():
        return "unavailable"
    from education_system.systems.university.domains.admissions.domain.services import (
        admissions_lifecycle as lifecycle,
    )
    db = _db()
    with db.get_connection() as conn:
        app = conn.execute(
            "SELECT status, converted_student_id FROM admission_applications "
            "WHERE application_id = ?", (int(application_id),)).fetchone()
        current = conn.execute(
            "SELECT * FROM admission_handover_routing WHERE application_id = ?",
            (int(application_id),)).fetchone()
    if app is None:
        return "unavailable"
    current = dict(current) if current else {}
    after = {"route": to_route, "institution": to_institution}
    where = to_institution or "another institution"
    if to_route == "Unplaced":
        text = ("Withdrawn by reroute: the learner no longer holds a place "
                "here" + (f" — {reason}" if reason else ""))
    else:
        text = (f"Withdrawn by reroute: the learner is now going to {where}"
                + (f" ({to_route})" if to_route else "")
                + (f" — {reason}" if reason else ""))
    if app["converted_student_id"]:
        with db.transaction() as conn:
            _history(conn, application_id, "ignored_enrolled",
                     before=current, after=after,
                     reason=f"{text}; not applied — already enrolled as "
                            f"{app['converted_student_id']}",
                     source_event_id=source_event_id)
        return "enrolled"
    if current.get("routing_status") == ROUTING_WITHDRAWN:
        return "already_withdrawn"
    lifecycle.transition(application_id, lifecycle.DECLINED, reason=text,
                         actor_id=_ACTOR, force=True)
    keep = {k: current.get(k) for k in ("route", "institution", "course_code",
                                        "course_name", "entry_year",
                                        "deferred")}
    with db.transaction() as conn:
        _upsert_routing(conn, application_id, journey_id, keep,
                        status=ROUTING_WITHDRAWN, reason=text,
                        source_event_id=source_event_id, rerouted=True)
        _history(conn, application_id, "withdrawn_by_reroute",
                 before=current, after=after, reason=text,
                 source_event_id=source_event_id)
    logger.info("Application %s withdrawn by reroute to %s", application_id,
                where)
    return "withdrawn"


# ── Contextual flags ────────────────────────────────────────────────

def store_contextual(application_id: int, payload: dict, *,
                     journey_id: str | None = None,
                     source_event_id: str | None = None) -> str:
    """Record the contextual section exactly as it arrived.

    Released flags overwrite what was held; a handover without them —
    the learner has not consented, or has withdrawn consent since — clears
    any flags held from an earlier handover and records why. Returns the
    stored status.
    """
    if not ensure_tables():
        return "unavailable"
    section = (payload or {}).get("contextual_flags") or None
    advisories = (payload or {}).get("handover_advisories") or []
    if section and isinstance(section, dict):
        consent = section.get("consent") or {}
        values = (int(application_id), journey_id, CONTEXTUAL_RELEASED,
                  json.dumps(section.get("flags") or {}),
                  json.dumps(section.get("not_held") or []),
                  str(consent.get("consent_id") or "") or None,
                  consent.get("granted_date"), None, source_event_id)
        status = CONTEXTUAL_RELEASED
    else:
        why = next((a.get("note") for a in advisories
                    if isinstance(a, dict) and a.get("key") == "contextual_flags"),
                   "Not received — the sixth form sent no contextual section "
                   "(no consent recorded for it)")
        values = (int(application_id), journey_id, CONTEXTUAL_WITHHELD, None,
                  None, None, None, why, source_event_id)
        status = CONTEXTUAL_WITHHELD
    with _db().transaction() as conn:
        conn.execute(
            """INSERT INTO admission_contextual_flags
                   (application_id, journey_id, status, flags_json,
                    not_held_json, consent_reference, consent_granted_date,
                    withheld_reason, source_event_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(application_id) DO UPDATE SET
                   journey_id = COALESCE(excluded.journey_id,
                                         admission_contextual_flags.journey_id),
                   status = excluded.status,
                   flags_json = excluded.flags_json,
                   not_held_json = excluded.not_held_json,
                   consent_reference = excluded.consent_reference,
                   consent_granted_date = excluded.consent_granted_date,
                   withheld_reason = excluded.withheld_reason,
                   source_event_id = excluded.source_event_id,
                   received_at = CURRENT_TIMESTAMP""", values)
    return status


def contextual_status(application_id: int) -> dict[str, Any]:
    """Whether flags are held, without the flags themselves.

    Safe for any admissions screen: says "released (3 flags)" or
    "withheld — why", never which flags.
    """
    if not ensure_tables():
        return {"status": "unavailable", "count": 0, "reason": None}
    with _db().get_connection() as conn:
        row = conn.execute(
            "SELECT status, flags_json, withheld_reason, received_at "
            "FROM admission_contextual_flags WHERE application_id = ?",
            (int(application_id),)).fetchone()
    if row is None:
        return {"status": "not_received", "count": 0,
                "reason": "No contextual section on record"}
    count = len(json.loads(row["flags_json"] or "{}")) \
        if row["status"] == CONTEXTUAL_RELEASED else 0
    return {"status": row["status"], "count": count,
            "reason": row["withheld_reason"], "received_at": row["received_at"]}


def contextual_statuses(application_ids) -> dict[int, dict[str, Any]]:
    """:func:`contextual_status` for many applications in one query.
    Applications with no row are absent."""
    ids = [int(a) for a in application_ids if a is not None]
    if not ids or not ensure_tables():
        return {}
    out: dict[int, dict[str, Any]] = {}
    with _db().get_connection() as conn:
        for start in range(0, len(ids), 500):
            chunk = ids[start:start + 500]
            marks = ",".join("?" * len(chunk))
            # db-audit: ignore[DBW001] - join of placeholders
            for row in conn.execute(
                    f"SELECT application_id, status, flags_json, "
                    f"withheld_reason, received_at "
                    f"FROM admission_contextual_flags "
                    f"WHERE application_id IN ({marks})", chunk):  # nosec B608
                count = (len(json.loads(row["flags_json"] or "{}"))
                         if row["status"] == CONTEXTUAL_RELEASED else 0)
                out[int(row["application_id"])] = {
                    "status": row["status"], "count": count,
                    "reason": row["withheld_reason"],
                    "received_at": row["received_at"]}
    return out


def _viewer_name(viewer: Any) -> str:
    user = getattr(viewer, "current_user", viewer)
    if isinstance(user, dict):
        return str(user.get("username") or user.get("id") or "unknown")
    return str(getattr(viewer, "username", "") or "unknown")


def can_view_contextual(viewer: Any) -> bool:
    """Admissions staff only: the admissions-decision permission, or admin.

    ``viewer`` is a ``current_user`` dict or an auth object exposing
    ``current_user`` / ``has_permission``. Anything else — including no
    viewer at all — is refused.
    """
    if viewer is None:
        return False
    user = getattr(viewer, "current_user", None) if not isinstance(viewer, dict) \
        else viewer
    if isinstance(user, dict):
        role = str(user.get("role") or "").lower()
        if role in _PRIVILEGED_ROLES:
            return True
        if VIEW_PERMISSION in (user.get("permissions") or []):
            return True
    checker = getattr(viewer, "has_permission", None)
    if callable(checker):
        try:
            return bool(checker(VIEW_PERMISSION))
        except Exception:
            logger.debug("has_permission failed closed", exc_info=True)
    return False


def contextual_flags(application_id: int, *, viewer: Any) -> dict | None:
    """The released flags for an admissions member of staff, or ``None``.

    Every call is logged — who asked, and whether they were allowed — so
    a disclosure of care status is answerable afterwards.
    """
    allowed = can_view_contextual(viewer)
    if not ensure_tables():
        return None
    with _db().transaction() as conn:
        conn.execute(
            "INSERT INTO admission_contextual_access_log "
            "(application_id, viewer, allowed) VALUES (?, ?, ?)",
            (int(application_id), _viewer_name(viewer), 1 if allowed else 0))
    if not allowed:
        return None
    with _db().get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM admission_contextual_flags WHERE application_id = ?",
            (int(application_id),)).fetchone()
    if row is None or row["status"] != CONTEXTUAL_RELEASED:
        return None
    return {
        "flags": json.loads(row["flags_json"] or "{}"),
        "not_held": json.loads(row["not_held_json"] or "[]"),
        "consent_reference": row["consent_reference"],
        "consent_granted_date": row["consent_granted_date"],
        "received_at": row["received_at"],
    }


def describe_flags(section: dict | None) -> list[str]:
    """Readable lines for released flags (for screens)."""
    if not section:
        return []
    lines = []
    for key, flag in (section.get("flags") or {}).items():
        label = FLAG_LABELS.get(key, key.replace("_", " "))
        extra = [str(v) for k, v in (flag or {}).items()
                 if k not in ("value",) and v not in (None, "", True, False)]
        lines.append(label + (f" ({', '.join(extra)})" if extra else ""))
    not_held = [FLAG_LABELS.get(k, k) for k in section.get("not_held") or []]
    if not_held:
        lines.append("Not held by the sixth form: " + ", ".join(not_held))
    return lines


__all__ = [
    "ROUTING_ACTIVE", "ROUTING_WITHDRAWN", "CONTEXTUAL_RELEASED",
    "CONTEXTUAL_WITHHELD", "VIEW_PERMISSION", "FLAG_LABELS",
    "ensure_tables", "routing_from_payload", "routing_from_reroute",
    "entry_label", "routing_label", "get_routing", "routing_for",
    "route_history", "deferred_entry_issue", "apply_offer_conditions",
    "apply_routing", "withdraw_by_reroute", "store_contextual",
    "contextual_status", "contextual_statuses", "can_view_contextual", "contextual_flags",
    "describe_flags",
]
