"""University-side consumer for college progression events.

Subscribes to ``student.progression.completed`` on the durable
cross-system bus and creates an idempotent university applicant.  The
applicant is deliberately not made an active student here: the admissions
lifecycle performs that conversion only after offer, checks, acceptance,
right-to-study and registration have completed.

Named for the sixth form, which is the route it was written for, but
three systems progress learners here — sixth form, FE college and
apprenticeships — and each has its own declared dataset. The source is
read from the event envelope, not assumed: an apprentice validated
against ``SIXTH_FORM_TO_UNIVERSITY`` fails on every field it does not
carry, and recording their arrival as coming from the sixth form puts a
phase on their journey they were never in.

The payload is read as the boundary's spec — e.g.
``handover.SIXTH_FORM_TO_UNIVERSITY``, assembled on the sixth-form side
by ``progression.university_handover`` — with a fallback to the flat keys
used before that contract existed, so events already queued on the bus
still admit. Identity is read under either name the specs use
(``student_identity`` for the colleges, ``learner_identity`` for
apprenticeships).

Idempotent at the journey, which is the level that actually matters:

* the bus's ``cross_system_event_consumed`` table drops a re-delivery of
  the same event;
* the journey's ``university_student_id`` short-circuits the admit
  entirely — that slot is filled by an admissions conversion or by the
  students GUI's sixth-form import picker, and either way the learner is
  already here as a *student*, so staging an applicant beside them would
  duplicate a person against a row this intake cannot reconcile with;
* **any** existing application carrying this ``journey_id`` is returned
  rather than a second one created. That used to be keyed on
  ``(journey_id, external_reference)``, which meant a college correcting
  a UCAS number — or a handover published before the UCAS record existed
  and again after — produced two applications for one learner, each
  looking canonical.

Admission also records a ``sixth_form -> university`` transition on the
journey, so the applicant is visible in the learner's cross-system
history rather than only in the admissions tables.

Reroutes and deferrals
----------------------
A handover that arrives for a journey which already has an application
does not stop at "already held": the routing it carries — Firm, Insurance,
Clearing, Adjustment or Extra, the course and the entry year — is applied
to that application by ``sixthform_handover_records.apply_routing``, so a
learner who missed their Firm and came in on their Insurance has the one
application *updated* (new course, audit row) rather than a second one
created. ``ucas.handover.rerouted`` (:func:`handle_handover_rerouted`)
carries routing only; when it says the learner has gone elsewhere the
application is marked withdrawn-by-reroute — declined, never deleted. A
deferred entry records its year and is held back from this year's
conversion. Contextual flags are stored on their own, admissions-only
table.

Drained by :func:`drain_intake`, which the launcher calls on university
startup (and which a scheduled job could call too).
"""

from __future__ import annotations

import logging
from datetime import datetime

from education_system.platform.cross_system import handover, identity_service
from education_system.platform.integrations.external import cross_system_bus
from education_system.systems.university.domains.admissions.domain import (
    sixthform_handover_records as handover_records,
)

logger = logging.getLogger(__name__)

CONSUMER_SYSTEM = "university"

#: The route this module was written for, and the fallback for an event
#: that names no source. It is *not* the only one: FE college and
#: apprenticeships arrive over the same bus, and validating their payloads
#: against the sixth form's spec — or writing "from sixth_form" onto their
#: journey — records something that did not happen.
SOURCE_SYSTEM = "sixth_form"

#: Sources this intake accepts. A payload from anywhere else is validated
#: against no spec rather than the wrong one.
SOURCE_SYSTEMS = frozenset({"sixth_form", "fe_college", "apprenticeships"})


def _read_handover(payload: dict) -> dict:
    """Flatten a progression payload into the fields the CRM needs.

    Reads the ``SIXTH_FORM_TO_UNIVERSITY`` shape, falling back to the flat
    pre-contract keys throughout. The fallback is not decoration: events
    published before the contract existed may still be sitting unconsumed
    on the durable bus, and they should admit on what they carry rather
    than be stranded by a vocabulary change.
    """
    # ``learner_identity`` is not an alternative spelling to be tidied
    # away: it is the key APPRENTICESHIPS_TO_UNIVERSITY declares, and
    # build_handover emits only the keys its spec names. Reading
    # ``student_identity`` alone staged an apprentice with a blank name,
    # date of birth and email.
    identity = (payload.get("student_identity")
                or payload.get("learner_identity") or {})
    ucas = payload.get("ucas_application") or {}
    choices = payload.get("choices") or []
    destination = (payload.get("confirmed_destination")
                   or (choices[0] if isinstance(choices, list) and choices else {})
                   or {})
    entry_year = destination.get("entry_year") or payload.get("entry_year") or ""

    return {
        "ucas_id": ucas.get("ucas_id") or payload.get("ucas_application_id"),
        "sixth_form_student_id": (identity.get("sixth_form_student_id")
                                  or identity.get("college_student_id")
                                  or payload.get("sf_student_id")),
        "first_name": identity.get("first_name") or payload.get("first_name") or "",
        "last_name": identity.get("last_name") or payload.get("last_name") or "",
        "date_of_birth": (identity.get("date_of_birth")
                          or payload.get("date_of_birth") or ""),
        "email": identity.get("email") or payload.get("email") or "",
        "phone": identity.get("phone") or payload.get("phone") or "",
        "sixth_form_name": payload.get("sixth_form_name") or "",
        "programme_code": (destination.get("course_code")
                           or payload.get("programme_code") or "UNDECLARED"),
        "programme_name": (destination.get("course_name")
                           or payload.get("programme_name") or ""),
        "entry_year": str(entry_year) if entry_year else "",
        "semester": payload.get("semester") or "autumn",
        "institution": destination.get("university") or "",
        "offer_conditions": payload.get("offer_conditions") or {},
    }


def _source_of(envelope: dict) -> str:
    """The system a progression event actually came from.

    Falls back to :data:`SOURCE_SYSTEM` for an event that names no source
    or names one that does not send learners here — a wrong-but-known
    value is no worse than the hardcoded one it replaces, and an unknown
    source has no spec to be validated against anyway.
    """
    from education_system.platform.cross_system.progression import normalise_system
    source = normalise_system(envelope.get("source_system")) or ""
    if source in SOURCE_SYSTEMS:
        return source
    if source:
        logger.info(
            "Progression event %s names source %r, which is not a route into "
            "the university; treating it as %s",
            envelope.get("event_id"), source, SOURCE_SYSTEM)
    return SOURCE_SYSTEM


def _age_from_dob(dob: str | None) -> int | None:
    if not dob:
        return None
    try:
        d = datetime.strptime(dob, "%Y-%m-%d")
    except ValueError:
        return None
    now = datetime.now()
    return now.year - d.year - ((now.month, now.day) < (d.month, d.day))


_schema_ready = False

#: Routing columns joined onto an application lookup. Selected only when
#: the routing table exists: a lookup that failed on a missing join would
#: read as "no application" and stage a second one for the same learner.
_ROUTING_COLUMNS = """,
                          r.route AS handover_route,
                          r.deferred AS deferred_entry,
                          r.entry_year AS handover_entry_year,
                          r.routing_status, r.reroute_reason"""
_ROUTING_JOIN = """
                     LEFT JOIN admission_handover_routing r
                       ON r.application_id = a.application_id"""


def _routing_sql() -> tuple[str, str]:
    if handover_records.ensure_tables():
        return _ROUTING_COLUMNS, _ROUTING_JOIN
    return "", ""


def ensure_schema() -> bool:
    """Idempotently add the lifecycle columns this boundary reads.

    ``journey_id``, ``external_reference`` and ``converted_student_id`` are
    ALTERed onto ``admission_applications`` by
    ``init_admissions_crm_system_db``, so a database where the intake has
    never run does not have them and every lookup here fails on a missing
    column. The intake itself always calls that function first; the
    read-only lookups did not, which made them return "no application" on
    an un-migrated database instead of an error — a silent wrong answer
    exactly where a duplicate check depends on it.

    Once per process: the DDL is idempotent but not free, and these are
    called per screen refresh.
    """
    global _schema_ready
    if _schema_ready:
        return True
    try:
        from education_system.systems.university.infrastructure.database.schemas.admissions_schemas import (
            init_admissions_crm_system_db,
        )
        init_admissions_crm_system_db()
        handover_records.ensure_tables()
        _schema_ready = True
    except Exception:
        logger.exception("Could not prepare the admissions CRM schema")
    return _schema_ready


def find_application_for_journey(journey_id: str) -> dict | None:
    """The application already staged for ``journey_id``, if any.

    Journey-level, not ``(journey_id, external_reference)``-level: one
    learner arriving over this boundary is one application, whatever
    reference the source happened to quote at the time. Also the question
    the manual import picker asks before it enrols somebody directly —
    an applicant nobody noticed is exactly how one person ends up as two
    records.
    """
    from education_system.systems.university.infrastructure.database.db import (
        get_connection,
    )
    if not journey_id or not ensure_schema():
        return None
    try:
        columns, join = _routing_sql()
        with get_connection() as conn:
            # db-audit: ignore[DBW001] - splices module constants only
            row = conn.execute(
                f"""SELECT a.application_id, a.external_reference, a.status,
                          a.converted_student_id, a.program_applied,
                          a.academic_year{columns}
                     FROM admission_applications a{join}
                    WHERE a.journey_id = ?
                    ORDER BY a.application_id
                    LIMIT 1""",  # nosec B608
                (journey_id,),
            ).fetchone()
        return dict(row) if row else None
    except Exception:
        logger.exception(
            "Could not look up an existing application for journey %s",
            journey_id)
        return None


def find_applications_for_journeys(journey_ids, *,
                                   strict: bool = False) -> dict[str, dict]:
    """:func:`find_application_for_journey` for many journeys, in one query.

    A screen listing a Year 13 cohort asks this about every learner at
    once, and ``get_connection()`` against the university database costs
    roughly a tenth of a second each time it parses the schema — which
    turns a two-hundred-strong list into a twenty-second stall. Journeys
    with no application are absent rather than mapped to ``None``.

    ``strict`` re-raises instead of returning ``{}`` on failure. An empty
    result otherwise means both "nobody has applied" and "the university
    database could not be read", and a caller that wants to tell the user
    which of those it is has no way to find out.
    """
    from education_system.systems.university.infrastructure.database.db import (
        get_connection,
    )
    ids = [str(j) for j in journey_ids if j]
    if not ids:
        return {}
    if not ensure_schema():
        if strict:
            raise RuntimeError(
                "The university's admissions schema is unavailable")
        return {}
    out: dict[str, dict] = {}
    columns, join = _routing_sql()
    try:
        with get_connection() as conn:
            # Chunked below SQLITE_MAX_VARIABLE_NUMBER; ordered so the
            # lowest application_id per journey is the one that survives
            # the dict overwrite, matching the single-journey lookup.
            for start in range(0, len(ids), 500):
                chunk = ids[start:start + 500]
                placeholders = ",".join("?" * len(chunk))
                # db-audit: ignore[DBW001] - join of placeholders
                rows = conn.execute(
                    f"""SELECT a.application_id, a.journey_id,
                               a.external_reference, a.status,
                               a.converted_student_id, a.program_applied,
                               a.academic_year{columns}
                          FROM admission_applications a{join}
                         WHERE a.journey_id IN ({placeholders})
                         ORDER BY a.application_id DESC""",  # nosec B608
                    chunk).fetchall()
                for row in rows:
                    out[str(row["journey_id"])] = dict(row)
    except Exception:
        logger.exception(
            "Could not look up existing applications for %d journey(s)",
            len(ids))
        if strict:
            raise
        return {}
    return out


def _record_handover_details(application_id: int, journey_id: str,
                             payload: dict, *, reason: str = "",
                             source_event_id: str | None = None) -> str:
    """Apply the routing and store the contextual section. Never raises:
    the application exists either way, and admissions can see the gap."""
    action = "unavailable"
    try:
        routing = handover_records.routing_from_payload(payload)
        if routing:
            action = handover_records.apply_routing(
                application_id, routing, journey_id=journey_id,
                offer_conditions=payload.get("offer_conditions") or None,
                reason=reason, source_event_id=source_event_id)
    except Exception:
        logger.exception("Could not apply handover routing to application %s",
                         application_id)
    if payload.get("handover_boundary") or payload.get("contextual_flags"):
        try:
            handover_records.store_contextual(
                application_id, payload, journey_id=journey_id,
                source_event_id=source_event_id)
        except Exception:
            logger.exception("Could not store contextual flags for "
                             "application %s", application_id)
    return action


def _create_applicant(journey_id: str, payload: dict, *,
                      source_event_id: str | None = None
                      ) -> tuple[int, bool]:
    """Create (or return) the CRM application for a sixth-form handover.

    Returns ``(application_id, created)`` — the caller records a journey
    transition only for a genuinely new applicant, so a redelivered event
    does not append a second identical row to the learner's history.

    An application already held for the journey is *updated* from the
    handover's routing (see the module docstring) rather than duplicated.
    """
    from education_system.systems.university.infrastructure.database.schemas.admissions_schemas import (
        init_admissions_crm_system_db,
    )
    from education_system.systems.university.domains.admissions.domain.services.admissions_crm_core import (
        ApplicationManager,
        ProspectManager,
    )
    from education_system.systems.university.domains.admissions.domain.services import (
        admissions_lifecycle,
    )

    init_admissions_crm_system_db()
    global _schema_ready
    _schema_ready = handover_records.ensure_tables()
    fields = _read_handover(payload)
    external_reference = str(
        fields["ucas_id"]
        or fields["sixth_form_student_id"]
        or journey_id
    )
    from education_system.systems.university.infrastructure.database.db import (
        transaction,
    )
    existing = find_application_for_journey(journey_id)
    if existing:
        held = existing.get("external_reference")
        if held and held != external_reference:
            logger.info(
                "Journey %s already has application %s under reference %s; "
                "this handover quotes %s. Keeping the existing application "
                "rather than staging a second one for the same learner.",
                journey_id, existing["application_id"], held,
                external_reference)
        reroute = payload.get("handover_reroute") or {}
        _record_handover_details(
            int(existing["application_id"]), journey_id, payload,
            reason=reroute.get("reason") or "",
            source_event_id=source_event_id)
        return int(existing["application_id"]), False

    # Nothing under this journey — but the offer route gets here first and
    # does not know the journey exists. ``pipeline_link`` opens an
    # application the moment an offer is recorded, keyed on the UCAS
    # personal id and with ``journey_id`` left NULL, and its own docstring
    # promises "the two routes into this university converge on one
    # application per learner instead of racing to create two". They did
    # not converge: it matches on ``external_reference`` and this matches
    # on ``journey_id``, so neither could see the other's row and the
    # learner ended up with one application per route.
    #
    # Adopting is the convergence. Only an application with no journey on
    # it is eligible — one already bound to a different journey is a
    # different person's, whatever reference it happens to quote.
    adopted = _adopt_application_by_reference(journey_id, external_reference)
    if adopted is not None:
        _record_handover_details(adopted, journey_id, payload,
                                 source_event_id=source_event_id)
        return adopted, False

    journey = identity_service.get(journey_id) or {}
    first = fields["first_name"] or journey.get("legal_first_name") or ""
    last = fields["last_name"] or journey.get("legal_last_name") or ""
    dob = fields["date_of_birth"] or journey.get("date_of_birth") or ""
    prospect_id = ProspectManager.create_prospect(
        first_name=first,
        last_name=last,
        email=fields["email"],
        phone=fields["phone"],
        date_of_birth=dob,
        high_school=fields["sixth_form_name"],
        intended_major=fields["programme_name"] or fields["programme_code"],
        source="college_progression",
    )
    programme_code = fields["programme_code"]
    application_id = ApplicationManager.submit_application(
        prospect_id=prospect_id,
        application_type="undergraduate",
        program_applied=fields["programme_name"] or programme_code,
        academic_year=fields["entry_year"],
        semester=fields["semester"],
    )
    with transaction() as conn:
        conn.execute(
            """UPDATE admission_applications
                  SET journey_id = ?, external_reference = ?,
                      status = 'documents_pending'
                WHERE application_id = ?""",
            (journey_id, external_reference, application_id),
        )
        conn.execute(
            """INSERT INTO admission_status_history
                   (application_id, from_status, to_status, reason)
               VALUES (?, 'submitted', 'documents_pending',
                       'Sixth-form handover received')""",
            (application_id,),
        )
    choices = payload.get("choices") or []
    if not isinstance(choices, list) or not choices:
        choices = [{
            "course_code": programme_code,
            "course_name": fields["programme_name"],
            "entry_year": fields["entry_year"],
            "rank": 1,
        }]
    seen_codes: set[str] = set()
    for rank, choice in enumerate(choices, 1):
        code = str(choice.get("course_code") or choice.get("programme_code")
                   or f"UNDECLARED-{rank}")
        if code in seen_codes:
            continue
        seen_codes.add(code)
        admissions_lifecycle.add_choice(
            application_id, code,
            programme_name=str(choice.get("course_name")
                               or choice.get("programme_name") or ""),
            entry_year=str(choice.get("entry_year") or fields["entry_year"]),
            rank=int(choice.get("rank") or rank),
        )
    for requirement_type, description in (
        ("identity", "Identity and date-of-birth evidence"),
        ("qualifications", "Final qualification results"),
        ("right_to_study", "Right-to-study check"),
    ):
        admissions_lifecycle.add_requirement(
            application_id, requirement_type, description
        )

    # The sixth form's offer conditions become the application's
    # conditions rather than a note nobody reads: admission_conditions is
    # what the readiness check and the conversion gate already consult, so
    # carrying them here is what makes "confirmation against offer
    # conditions promotes an applicant to a student" enforceable at all.
    _apply_offer_conditions(application_id, fields["offer_conditions"])
    _record_handover_details(application_id, journey_id, payload,
                             source_event_id=source_event_id)

    logger.info(
        "Created university application %s for journey %s (%s%s)",
        application_id, journey_id,
        fields["programme_name"] or programme_code,
        f" at {fields['institution']}" if fields["institution"] else "")
    return application_id, True



def _adopt_application_by_reference(journey_id: str,
                                    external_reference: str) -> int | None:
    """Bind an unclaimed application for this UCAS reference to a journey.

    Returns its id, or ``None`` when there is nothing to adopt. Never
    raises: an intake that cannot search still has to admit the learner,
    and creating a second application is a better failure than dropping
    them.
    """
    reference = (external_reference or "").strip()
    if not reference or not ensure_schema():
        return None
    from education_system.systems.university.infrastructure.database.db import (
        get_connection,
    )
    try:
        with get_connection() as conn:
            row = conn.execute(
                """SELECT application_id, status FROM admission_applications
                    WHERE external_reference = ? AND journey_id IS NULL
                    ORDER BY application_id DESC LIMIT 1""",
                (reference,),
            ).fetchone()
            if row is None:
                return None
            application_id = int(row["application_id"])
            conn.execute(
                "UPDATE admission_applications SET journey_id = ? "
                "WHERE application_id = ?", (journey_id, application_id))
            conn.commit()
    except Exception:
        logger.exception(
            "Could not adopt an existing application for reference %s "
            "— a new one will be staged instead", reference)
        return None
    logger.info(
        "Adopted university application %s (reference %s, status %s) onto "
        "journey %s instead of staging a second one",
        application_id, reference, row["status"], journey_id)
    return application_id


def _apply_offer_conditions(application_id: int, conditions: dict) -> None:
    """Record the sixth form's offer terms as admission conditions."""
    if not conditions:
        return
    from education_system.systems.university.domains.admissions.domain.services import (
        admissions_lifecycle,
    )
    deadline = conditions.get("reply_deadline") or ""
    for description in (
        conditions.get("grade_requirement"),
        (f"Alternative offer: {conditions['grade_alternative']}"
         if conditions.get("grade_alternative") else None),
    ):
        if not description:
            continue
        try:
            admissions_lifecycle.add_condition(
                application_id, "academic", description, due_date=deadline)
        except Exception:
            # A condition that would not record must not lose the
            # application that carries it; the offer terms remain on the
            # bus event either way.
            logger.exception(
                "Could not record offer condition on application %s",
                application_id)


def handle_progression_completed(envelope: dict) -> None:
    """Bus handler: create an applicant; enrolment is a later gated step."""
    # Progression events are explicitly addressed. Ignore any not bound
    # for the university so co-located K-12 intakes (same launcher
    # process) don't get admitted here by mistake.
    target = envelope.get("target_system")
    if target is not None and target != CONSUMER_SYSTEM:
        return
    journey_id = envelope.get("journey_id")
    payload = envelope.get("payload") or {}
    if not journey_id:
        logger.warning("Progression event %s has no journey_id — "
                       "ignoring", envelope.get("event_id"))
        return

    # Already a university student? Then this event is the echo of an
    # admission a human has already completed by hand — the sixth-form
    # import picker in the students GUI creates the student and fills
    # this slot, then calls mark_transferred(), which publishes the very
    # event being handled here. Staging an applicant now would duplicate
    # someone who is already enrolled, against a student row this intake
    # has no way to reconcile with. Mirrors the guard in
    # ``ProgressionIntake.handle``.
    journey = identity_service.get(journey_id) or {}
    _pk_col, id_col = identity_service.SYSTEM_SLOTS[CONSUMER_SYSTEM]
    already_here = journey.get(id_col)
    if already_here:
        logger.info(
            "Journey %s is already university student %s — skipping "
            "applicant intake", journey_id, already_here)
        return

    # Which system the learner is actually coming from. Three send people
    # here and each has its own spec; taking the source from the envelope
    # rather than assuming the sixth form is what stops an apprentice
    # being checked against — and recorded as having come through — a
    # route they never took.
    source_system = _source_of(envelope)

    # Check the payload against the declared boundary, but admit either
    # way. validate_handover() is written for an adapter that can refuse
    # at the door; refusing here would strand a real learner on the bus
    # because their college has not yet recorded, say, a handover consent
    # row. Admissions can chase a missing field — it cannot chase an
    # applicant who never arrived. Only payloads actually built against
    # the spec are checked; a pre-contract event predates the rules and
    # would report every required field as missing.
    if payload.get("handover_boundary"):
        problems = handover.validate_handover(
            source_system, CONSUMER_SYSTEM, payload)
        if problems:
            logger.warning(
                "Handover for journey %s is incomplete — %s. Admitting on "
                "what arrived; the gaps stay for admissions to chase.",
                journey_id, "; ".join(problems))

    application_id, created = _create_applicant(
        journey_id, payload, source_event_id=envelope.get("event_id"))
    if created:
        # Put the applicant on the journey's own timeline. Without this the
        # only record that the learner reached the university was a row in
        # the admissions tables, so the cross-system view of their journey
        # stopped dead at the sixth form — the module claimed to be
        # journey-level and touched the journey nowhere.
        #
        # The university *slot* is deliberately still empty: it names a
        # student, and this is an applicant. Filling it here would tell
        # every other reader the learner is enrolled, and would make the
        # guard above skip the real conversion later on.
        try:
            identity_service.record_transition(
                journey_id, from_system=source_system,
                to_system=CONSUMER_SYSTEM,
                reason=f"Handover from {source_system} staged as university "
                       f"application {application_id}")
        except Exception:
            logger.exception(
                "Could not record the journey transition for application %s "
                "(the applicant itself was created)", application_id)
    logger.info("Journey %s from %s %s application %s",
                journey_id, source_system,
                "staged as" if created else "already held as", application_id)


def handle_handover_rerouted(envelope: dict) -> None:
    """Bus handler for ``ucas.handover.rerouted``.

    Routing only — the dataset, when the learner is still coming here,
    follows as a fresh progression handover and is applied by
    :func:`handle_progression_completed`. Here:

    * going elsewhere → the journey's application is marked withdrawn by
      reroute (declined, reason recorded, not deleted);
    * coming here by another route → the application is moved to the new
      course / route / entry year now, so a route that never sends a
      progression event (the platform's college application board) is
      corrected too.

    Idempotent (both writes compare before they act) and silent for a
    journey with no application here.
    """
    target = envelope.get("target_system")
    if target is not None and target != CONSUMER_SYSTEM:
        return
    journey_id = envelope.get("journey_id")
    payload = envelope.get("payload") or {}
    if not journey_id:
        return
    existing = find_application_for_journey(journey_id)
    if not existing:
        logger.debug("Reroute for journey %s: no application here",
                     journey_id)
        return
    application_id = int(existing["application_id"])
    reason = payload.get("reason") or ""
    event_id = envelope.get("event_id")
    if payload.get("to_home"):
        action = handover_records.apply_routing(
            application_id, handover_records.routing_from_reroute(payload),
            journey_id=journey_id, reason=reason, source_event_id=event_id)
    else:
        action = handover_records.withdraw_by_reroute(
            application_id, reason=reason,
            to_institution=payload.get("to_institution"),
            to_route=payload.get("to_route"), journey_id=journey_id,
            source_event_id=event_id)
    logger.info("Reroute for journey %s applied to application %s: %s",
                journey_id, application_id, action)


_registered = False


def register_intake_consumer() -> None:
    """Idempotently subscribe the intake handlers to the bus."""
    global _registered
    if _registered:
        return
    cross_system_bus.subscribe(
        cross_system_bus.EVENT_STUDENT_PROGRESSION_COMPLETED,
        handle_progression_completed,
        handler_name="university.admissions.sixthform_intake")
    cross_system_bus.subscribe(
        handover.EVENT_UCAS_HANDOVER_REROUTED,
        handle_handover_rerouted,
        handler_name="university.admissions.sixthform_intake.rerouted")
    _registered = True
    logger.debug("Registered sixth-form intake consumer")


def drain_intake(*, db_path: str | None = None) -> int:
    """Process any pending sixth-form progression events. Returns the
    number of (event, handler) dispatches. Safe to call repeatedly."""
    register_intake_consumer()
    return cross_system_bus.poll_and_dispatch(
        CONSUMER_SYSTEM, db_path=db_path)
