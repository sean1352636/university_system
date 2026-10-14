"""Parallel Year 11 applications to Sixth Form, FE and Apprenticeships.

Secondary and every destination are reached through the platform adapter
registry; nothing here imports a system.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from education_system.platform.cross_system import (
    enrolments, handover, route_support, transitions,
)
from education_system.platform.cross_system.adapters.base import HandoverRequest
from education_system.platform.identity.auth.db import connect
from education_system.platform.integrations.external import cross_system_bus

SOURCE = "secondary"
DESTINATIONS = frozenset({"sixth_form", "fe_college", "apprenticeships"})
STAGES = (
    "Planning", "Application submitted", "Interview/assessment",
    "Conditional offer", "Unconditional offer", "Offer accepted",
    "Results pending", "Place confirmed", "Handover approved",
    "Enrolled / On Programme", "Declined", "Withdrawn",
)


class Post16Error(ValueError):
    pass


@dataclass(frozen=True)
class Preview:
    destination: str
    payload: dict[str, Any]
    included: tuple[str, ...]
    withheld_no_consent: tuple[str, ...]
    withheld_restricted: tuple[str, ...]
    missing_required: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return not self.missing_required


def _ensure(db_path: str | None = None) -> None:
    conn = connect(db_path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS post16_destination_application (
                transition_id TEXT PRIMARY KEY,
                journey_id TEXT NOT NULL,
                pupil_id TEXT NOT NULL,
                destination_system TEXT NOT NULL,
                stage TEXT NOT NULL DEFAULT 'Planning',
                destination_label TEXT,
                programme_label TEXT,
                handover_json TEXT NOT NULL,
                consent_reference TEXT,
                interview_details TEXT,
                offer_conditions TEXT,
                confirmed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE UNIQUE INDEX IF NOT EXISTS ux_post16_confirmed_journey
                ON post16_destination_application(journey_id)
                WHERE confirmed = 1;
            CREATE INDEX IF NOT EXISTS ix_post16_pupil
                ON post16_destination_application(pupil_id, created_at);
        """)
        conn.commit()
    finally:
        conn.close()


def _source_adapter():
    """Secondary's adapter, from the platform registry."""
    return route_support.adapter_for(SOURCE)


def _destination_adapter(destination: str):
    """A post-16 destination's adapter, from the platform registry."""
    if destination not in DESTINATIONS:
        raise Post16Error(f"Unknown post-16 destination {destination!r}")
    return route_support.adapter_for(destination)


def preview(pupil_id: str, destination: str, *,
            predicted_grades: Any, prior_attainment: Any,
            consent_record: dict[str, Any],
            achieved_gcse_results: Any | None = None,
            attendance_behaviour: Any | None = None,
            careers_intentions: Any | None = None,
            medical_requirements: Any | None = None,
            support_indicators: Any | None = None,
            subjects: list[str] | None = None,
            course_request: dict[str, Any] | None = None,
            intended_programme: dict[str, Any] | None = None,
            eligibility_evidence: Any | None = None,
            functional_skills: Any | None = None,
            prior_learning: Any | None = None,
            preferred_vacancy: Any | None = None,
            employer_details: Any | None = None,
            personal_statement: str | None = None,
            interview_requirements: Any | None = None,
            consent: bool | set[str] | None = None,
            safeguarding_reference: str | None = None) -> Preview:
    if destination not in DESTINATIONS:
        raise Post16Error(f"Destination must be one of {', '.join(sorted(DESTINATIONS))}")
    if not consent_record:
        raise Post16Error("A learner or parent consent record is required")
    record = dict(_source_adapter().export_handover(
        pupil_id, consent, destination_system=destination).record)
    record.update({
        "predicted_grades": predicted_grades,
        "prior_attainment": prior_attainment,
        "handover_consent": consent_record,
    })
    common = {
        "gcse_results": achieved_gcse_results,
        "attendance_behaviour": attendance_behaviour,
        "careers_intentions": careers_intentions,
        "careers_record": careers_intentions,
        "medical_requirements": medical_requirements,
        "support_indicators": support_indicators,
        "personal_statement": personal_statement,
        "interview_requirements": interview_requirements,
    }
    record.update({k: v for k, v in common.items() if v not in (None, "", [], {})})
    if destination == "sixth_form":
        choices = [s.strip() for s in (subjects or []) if s and s.strip()]
        record["application_details"] = {
            "subjects": choices, "personal_statement": personal_statement,
        }
        record["subject_recommendations"] = choices
    elif destination == "fe_college":
        record["course_request"] = course_request
    else:
        record.update({
            "learner_identity": record.get("student_identity"),
            "intended_programme": intended_programme,
            "eligibility_evidence": eligibility_evidence,
        })
        optional = {
            "functional_skills": functional_skills,
            "prior_learning": prior_learning,
            "preferred_vacancy": preferred_vacancy,
            "employer_details": employer_details,
        }
        record.update({k: v for k, v in optional.items()
                       if v not in (None, "", [], {})})
    released = handover.build_handover(
        SOURCE, destination, record, consent=consent,
        safeguarding_reference=safeguarding_reference)
    return Preview(
        destination=destination, payload=released.payload,
        included=tuple(released.included),
        withheld_no_consent=tuple(released.withheld_no_consent),
        withheld_restricted=tuple(released.withheld_restricted),
        missing_required=tuple(released.missing_required))


def submit(pupil_id: str, destination: str, *, destination_label: str = "",
           programme_label: str = "", actor_user_id: int | None = None,
           db_path: str | None = None, **fields: Any) -> dict:
    """Create one parallel application without closing Secondary."""
    released = preview(pupil_id, destination, **fields)
    if not released.ready:
        raise Post16Error("Handover is incomplete: " + ", ".join(released.missing_required))
    try:
        journey_id = route_support.journey_for(
            route_support.identity_of(released.payload), system=SOURCE,
            student_id=pupil_id, db_path=db_path)
    except route_support.RouteError as exc:
        raise Post16Error(str(exc)) from exc
    existing = [r for r in list_applications(pupil_id=pupil_id, db_path=db_path)
                if r["destination_system"] == destination
                and r["stage"] not in {"Declined", "Withdrawn", "Enrolled / On Programme"}]
    if existing:
        return existing[0]
    source = route_support.source_enrolment(
        journey_id, SOURCE, pupil_id, year_group="11", db_path=db_path)
    # Opened directly rather than through route_support.start: a declined
    # application's transition stays open on this board (the stage lives
    # in post16_destination_application), so reusing the open transition
    # would attach a fresh application to the declined one's row.
    row = transitions.start_transition(
        journey_id=journey_id, source_system=SOURCE,
        source_enrolment_id=source["enrolment_id"],
        destination_system=destination, reason="Post-16 application",
        actor_user_id=actor_user_id, db_path=db_path)
    row = transitions.record_application(row["transition_id"], db_path=db_path)
    applicant = _destination_adapter(destination).create_applicant(HandoverRequest(
        journey_id=journey_id, source_system=SOURCE,
        destination_system=destination, payload=released.payload,
        transition_id=row["transition_id"],
        consent_reference=_consent_reference(fields.get("consent_record"))))
    # Creating the destination's record may already have mirrored an
    # enrolment for it; adopt that row rather than opening a second.
    adopted = route_support.adopt_destination_enrolment(
        journey_id, destination, applicant.local_applicant_id, db_path=db_path)
    if adopted is not None:
        platform_enrolment = enrolments.set_status(
            adopted, "applicant", db_path=db_path)
    else:
        platform_enrolment = enrolments.create_enrolment(
            journey_id=journey_id, system=destination,
            local_student_id=applicant.local_applicant_id, status="applicant",
            notes=f"post-16 application {row['transition_id']}", db_path=db_path)
    conn = connect(db_path)
    try:
        conn.execute(
            "UPDATE learner_transition SET destination_enrolment_id = ? "
            "WHERE transition_id = ?",
            (platform_enrolment["enrolment_id"], row["transition_id"]))
        conn.execute(
            """INSERT INTO post16_destination_application
                 (transition_id, journey_id, pupil_id, destination_system,
                  stage, destination_label, programme_label, handover_json,
                  consent_reference)
               VALUES (?, ?, ?, ?, 'Application submitted', ?, ?, ?, ?)""",
            (row["transition_id"], journey_id, pupil_id, destination,
             destination_label, programme_label,
             json.dumps(released.payload, default=str),
             _consent_reference(fields.get("consent_record"))))
        conn.commit()
    finally:
        conn.close()
    _publish(row, "Application submitted", db_path=db_path)
    return get_application(row["transition_id"], db_path=db_path)


def update_status(transition_id: str, stage: str, *, details: str = "",
                  db_path: str | None = None) -> dict:
    """Record destination-owned interview/offer/status feedback."""
    if stage not in STAGES:
        raise Post16Error(f"Unknown stage {stage!r}")
    app = get_application(transition_id, db_path=db_path)
    if not app:
        raise Post16Error(f"No post-16 application {transition_id}")
    if stage in {"Conditional offer", "Unconditional offer"}:
        transition = transitions.get_transition(transition_id, db_path=db_path)
        if transition and transition["status"] == "applied":
            transitions.offer_place(
                transition_id,
                destination_enrolment_id=transition["destination_enrolment_id"],
                conditions=details or stage, db_path=db_path)
    elif stage == "Offer accepted":
        transition = transitions.get_transition(transition_id, db_path=db_path)
        if transition and transition["status"] == "offered":
            transitions.accept_place(transition_id, accepted_by="learner", db_path=db_path)
    field = ("interview_details" if stage == "Interview/assessment"
             else "offer_conditions" if "offer" in stage.lower() else None)
    conn = connect(db_path)
    try:
        sets = ["stage = ?", "updated_at = datetime('now')"]
        args: list[Any] = [stage]
        if field:
            sets.append(f"{field} = ?")
            args.append(details)
        args.append(transition_id)
        conn.execute(
            f"UPDATE post16_destination_application SET {', '.join(sets)} "
            "WHERE transition_id = ?", args)
        conn.commit()
    finally:
        conn.close()
    _publish(app, stage, details=details, db_path=db_path)
    return get_application(transition_id, db_path=db_path)


def confirm_destination(transition_id: str, *, db_path: str | None = None) -> dict:
    """Choose the one destination that may eventually close Secondary."""
    app = get_application(transition_id, db_path=db_path)
    if not app:
        raise Post16Error(f"No post-16 application {transition_id}")
    if app["stage"] not in {"Offer accepted", "Results pending", "Place confirmed"}:
        raise Post16Error("An offer must be accepted before it can be confirmed")
    conn = connect(db_path)
    try:
        other = conn.execute(
            "SELECT transition_id FROM post16_destination_application "
            "WHERE journey_id = ? AND confirmed = 1 AND transition_id <> ?",
            (app["journey_id"], transition_id)).fetchone()
        if other:
            raise Post16Error("This learner already has a confirmed destination")
        conn.execute(
            "UPDATE post16_destination_application SET confirmed = 1, "
            "stage = 'Place confirmed', updated_at = datetime('now') "
            "WHERE transition_id = ?", (transition_id,))
        conn.commit()
    finally:
        conn.close()
    return get_application(transition_id, db_path=db_path)


def approve_handover(transition_id: str, *, db_path: str | None = None) -> dict:
    app = get_application(transition_id, db_path=db_path)
    if not app or not app["confirmed"]:
        raise Post16Error("Confirm the destination before approving handover")
    row = transitions.get_transition(transition_id, db_path=db_path)
    if row and row["status"] == "offered":
        transitions.accept_place(transition_id, accepted_by="learner", db_path=db_path)
    transitions.approve_handover(
        transition_id, json.loads(app["handover_json"]),
        consent_reference=app.get("consent_reference"), db_path=db_path)
    return update_status(transition_id, "Handover approved", db_path=db_path)


def enrol_confirmed(transition_id: str, *, start_date: str | None = None,
                    db_path: str | None = None, **destination_details: Any) -> dict:
    app = get_application(transition_id, db_path=db_path)
    if not app or not app["confirmed"] or app["stage"] != "Handover approved":
        raise Post16Error("The confirmed handover must be approved before enrolment")
    result = _destination_adapter(app["destination_system"]).create_enrolment(
        app["journey_id"], start_date=start_date, **destination_details)
    transitions.admit(
        transition_id, local_student_id=result.local_student_id,
        year_group="12" if app["destination_system"] == "sixth_form" else None,
        start_date=result.start_date or start_date, db_path=db_path)
    transitions.complete(
        transition_id, start_date=result.start_date or start_date,
        close_source=True, source_exit_reason=(
            f"Confirmed post-16 destination: {app['destination_system']}"),
        db_path=db_path)
    _source_adapter().close_enrolment(
        app["pupil_id"], f"Progressed to {app['destination_system']}",
        end_date=result.start_date or start_date)
    return update_status(transition_id, "Enrolled / On Programme", db_path=db_path)


def get_application(transition_id: str, *, db_path: str | None = None) -> dict | None:
    _ensure(db_path)
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM post16_destination_application WHERE transition_id = ?",
            (transition_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_applications(*, pupil_id: str | None = None,
                      destination: str | None = None,
                      db_path: str | None = None) -> list[dict]:
    _ensure(db_path)
    sql = ["SELECT * FROM post16_destination_application WHERE 1=1"]
    args: list[Any] = []
    if pupil_id:
        sql.append("AND pupil_id = ?")
        args.append(pupil_id)
    if destination:
        sql.append("AND destination_system = ?")
        args.append(destination)
    sql.append("ORDER BY created_at DESC")
    conn = connect(db_path)
    try:
        return [dict(r) for r in conn.execute(" ".join(sql), args).fetchall()]
    finally:
        conn.close()


def _publish(app: dict, stage: str, *, details: str = "",
             db_path: str | None = None) -> None:
    try:
        cross_system_bus.publish_cross_system(
            "post16.application.status_changed", source_system=SOURCE,
            source_module="platform.cross_system.secondary_post16",
            journey_id=app["journey_id"], target_system=app["destination_system"],
            db_path=db_path, transition_id=app["transition_id"],
            stage=stage, details=details)
    except Exception:
        pass


def _consent_reference(record: dict | None) -> str | None:
    if not record:
        return None
    return str(record.get("reference") or record.get("consent_id") or "post16-consent")


__all__ = [
    "Post16Error", "Preview", "DESTINATIONS", "STAGES", "preview", "submit",
    "update_status", "confirm_destination", "approve_handover",
    "enrol_confirmed", "get_application", "list_applications",
]
