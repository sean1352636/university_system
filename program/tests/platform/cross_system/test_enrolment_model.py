"""Enrolment-based journey model: enrolments, transitions, handover, adapters.

Every case runs against an isolated temp auth DB so nothing touches the
running application's data.
"""

from __future__ import annotations

import pytest

from education_system.platform.cross_system import (
    enrolment_schema,
    enrolments,
    handover,
    identity_service,
    progression,
    transitions,
)
from education_system.platform.cross_system.adapters import base, registry
from education_system.platform.integrations.external import cross_system_bus


@pytest.fixture
def db(tmp_path):
    """An isolated auth DB with the enrolment schema in place."""
    path = str(tmp_path / "auth.db")
    enrolment_schema.reset_schema_cache_for_test()
    identity_service._initialised.clear()
    enrolment_schema.ensure_enrolment_schema(path)
    yield path
    enrolment_schema.reset_schema_cache_for_test()
    identity_service._initialised.clear()


@pytest.fixture
def journey(db):
    return identity_service.get_or_create_journey(
        first_name="Ada", last_name="Lovelace", date_of_birth="2010-12-10",
        system="secondary", student_id="S9340", db_path=db)


# ── Schema ──────────────────────────────────────────────────────────

def test_learner_journey_view_reflects_student_journey(db, journey):
    from education_system.platform.identity.auth.db import connect
    conn = connect(db)
    try:
        row = conn.execute(
            "SELECT * FROM learner_journey WHERE journey_id = ?",
            (journey,)).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row["legal_first_name"] == "Ada"
    # The view renames current_system to the enrolment vocabulary.
    assert row["current_phase"] == "secondary"


# ── Enrolments ──────────────────────────────────────────────────────

def test_create_and_close_keeps_the_row(db, journey):
    e = enrolments.create_enrolment(
        journey_id=journey, system="secondary", local_student_id="S9340",
        status="active", db_path=db)
    closed = enrolments.close_enrolment(
        e["enrolment_id"], reason="progressed", status="completed",
        db_path=db)
    assert closed["status"] == "completed"
    assert closed["exit_reason"] == "progressed"
    # Not deleted — still readable.
    assert enrolments.get_enrolment(e["enrolment_id"], db_path=db) is not None


def test_changing_school_within_a_phase_is_two_enrolments(db, journey):
    first = enrolments.create_enrolment(
        journey_id=journey, system="primary", local_student_id="P1",
        institution_id="school-a", status="active", db_path=db)
    enrolments.close_enrolment(first["enrolment_id"], reason="moved house",
                               status="transferred", db_path=db)
    enrolments.create_enrolment(
        journey_id=journey, system="primary", local_student_id="P2",
        institution_id="school-b", status="active", db_path=db)

    rows = enrolments.list_enrolments(journey, system="primary", db_path=db)
    assert len(rows) == 2
    assert {r["institution_id"] for r in rows} == {"school-a", "school-b"}
    # The slot model could only ever have held P2.


def test_leaving_and_returning_reuses_the_local_id_as_a_new_spell(db, journey):
    first = enrolments.link_local_enrolment(
        journey_id=journey, system="primary", local_student_id="P1",
        db_path=db)
    enrolments.close_enrolment(first["enrolment_id"], reason="home educated",
                               status="withdrawn", db_path=db)
    # Same local id, but the previous spell is closed, so this is a new one.
    second = enrolments.link_local_enrolment(
        journey_id=journey, system="primary", local_student_id="P1",
        db_path=db)
    assert second["enrolment_id"] != first["enrolment_id"]
    assert len(enrolments.list_enrolments(journey, system="primary",
                                          db_path=db)) == 2


def test_repeating_a_year_updates_year_group_not_a_new_enrolment(db, journey):
    e = enrolments.create_enrolment(
        journey_id=journey, system="primary", local_student_id="P1",
        status="active", year_group="5", db_path=db)
    # Held back a year: the same spell at the same school, so the year
    # group changes and no second enrolment appears.
    enrolments.set_year_group(e["enrolment_id"], "5", db_path=db)
    rows = enrolments.list_enrolments(journey, system="primary", db_path=db)
    assert len(rows) == 1
    assert rows[0]["year_group"] == "5"


def test_concurrent_enrolments_are_supported(db, journey):
    # The fixture already holds an active `secondary` enrolment; add a
    # concurrent college course alongside it.
    enrolments.create_enrolment(journey_id=journey, system="sixth_form",
                                local_student_id="SF1", status="active",
                                db_path=db)
    active = enrolments.active_enrolments(journey, db_path=db)
    assert len(active) == 2
    hist = enrolments.journey_history(journey, db_path=db)
    assert set(hist["current_phases"]) == {"secondary", "sixth_form"}


def test_link_local_enrolment_is_idempotent(db, journey):
    a = enrolments.link_local_enrolment(
        journey_id=journey, system="university", local_student_id="U1",
        db_path=db)
    b = enrolments.link_local_enrolment(
        journey_id=journey, system="university", local_student_id="U1",
        db_path=db)
    assert a["enrolment_id"] == b["enrolment_id"]


def test_link_never_demotes_an_active_enrolment(db, journey):
    active = enrolments.create_enrolment(
        journey_id=journey, system="university", local_student_id="U1",
        status="active", db_path=db)
    again = enrolments.link_local_enrolment(
        journey_id=journey, system="university", local_student_id="U1",
        status="applicant", db_path=db)
    assert again["enrolment_id"] == active["enrolment_id"]
    assert again["status"] == "active"


def test_non_phase_destinations_are_recordable(db, journey):
    # "employment", not "apprenticeship": apprenticeships is a system this
    # platform runs now, with its own slot and adapter. What this still has
    # to prove is that a destination with *no* local system behind it is
    # recordable, so the journey says where someone went rather than
    # simply stopping.
    e = enrolments.create_enrolment(
        journey_id=journey, system="employment",
        institution_id="employer-42", status="active", db_path=db)
    assert e["system"] == "employment"
    assert "employment" in enrolments.journey_history(
        journey, db_path=db)["systems_attended"]


def test_unknown_status_and_field_are_rejected(db, journey):
    with pytest.raises(enrolments.EnrolmentError):
        enrolments.create_enrolment(journey_id=journey, system="primary",
                                    status="enroled", db_path=db)
    e = enrolments.create_enrolment(journey_id=journey, system="primary",
                                    db_path=db)
    with pytest.raises(enrolments.EnrolmentError):
        enrolments.update_enrolment(e["enrolment_id"], systemm="primary",
                                    db_path=db)
    with pytest.raises(enrolments.EnrolmentError):
        enrolments.close_enrolment(e["enrolment_id"], reason="x",
                                   status="active", db_path=db)


# ── Dual-write from the legacy slots ────────────────────────────────

def test_link_system_mirrors_an_enrolment(db, journey):
    identity_service.link_system(journey, "sixth_form",
                                 student_id="SF2208", db_path=db)
    rows = enrolments.list_enrolments(journey, system="sixth_form",
                                      db_path=db)
    assert [r["local_student_id"] for r in rows] == ["SF2208"]


def test_get_or_create_journey_mirrors_on_the_create_path(db, journey):
    # `journey` was created via get_or_create_journey, not link_system.
    rows = enrolments.list_enrolments(journey, system="secondary", db_path=db)
    assert [r["local_student_id"] for r in rows] == ["S9340"]


def test_backfill_derives_enrolments_from_slots(db):
    jid = identity_service.get_or_create_journey(
        first_name="Alan", last_name="Turing", date_of_birth="2008-06-23",
        system="nursery", student_id="N1024", db_path=db)
    identity_service.link_system(jid, "primary", student_id="P4821",
                                 set_current=True, db_path=db)

    # Wipe the mirrored rows so the backfill has real work to do.
    from education_system.platform.identity.auth.db import connect
    conn = connect(db)
    try:
        conn.execute("DELETE FROM learner_enrolment")
        conn.commit()
    finally:
        conn.close()

    summary = enrolment_schema.backfill_enrolments(db_path=db)
    assert summary["created"] == 2
    by_system = {r["system"]: r for r in
                 enrolments.list_enrolments(jid, db_path=db)}
    assert by_system["nursery"]["status"] == "completed"
    assert by_system["nursery"]["exit_reason"] == "progressed"
    assert by_system["primary"]["status"] == "active"

    # Re-running creates nothing further.
    again = enrolment_schema.backfill_enrolments(db_path=db)
    assert again["created"] == 0
    assert again["existing"] == 2


# ── Handover specs ──────────────────────────────────────────────────

def test_every_declared_boundary_has_a_spec():
    for pair in (("nursery", "primary"), ("primary", "secondary"),
                 ("secondary", "sixth_form"), ("sixth_form", "university")):
        assert handover.get_spec(*pair) is not None


def test_sensitive_fields_need_consent():
    result = handover.build_handover(
        "primary", "secondary",
        {"child_identity": {"n": "Ada"}, "guardians": [{"n": "G"}],
         "ks2_results": {"maths": 105}, "send_provision": {"ehcp": True}},
        consent=None)
    assert "ks2_results" in result.included          # routine
    assert "send_provision" in result.withheld_no_consent
    assert "send_provision" not in result.payload


def test_granular_consent_releases_only_named_fields():
    result = handover.build_handover(
        "primary", "secondary",
        {"child_identity": {}, "guardians": [], "send_provision": {"x": 1},
         "support_indicators": {"pp": True}},
        consent={"send_provision"})
    assert "send_provision" in result.payload
    assert "support_indicators" in result.withheld_no_consent


def test_safeguarding_detail_never_crosses_in_the_payload():
    result = handover.build_handover(
        "nursery", "primary",
        {"child_identity": {}, "guardians": [], "emergency_contacts": [],
         "medical_alerts": ["nuts"],
         "safeguarding_reference": "THIS SHOULD NOT CROSS"},
        consent=True, safeguarding_reference="SG-2024-118")
    assert "safeguarding_reference" in result.withheld_restricted
    # Only the reference the caller passed, never the record's own detail.
    assert result.payload["safeguarding_reference"] == "SG-2024-118"


def test_missing_required_field_is_reported():
    result = handover.build_handover(
        "sixth_form", "university",
        {"student_identity": {}, "offer_conditions": {"grades": "AAB"}},
        consent=True)
    assert not result.complete
    assert "ucas_application" in result.missing_required
    assert "handover_consent" in result.missing_required


def test_validate_rejects_restricted_content_in_a_received_payload():
    problems = handover.validate_handover(
        "nursery", "primary",
        {"child_identity": {}, "guardians": [], "medical_alerts": [],
         "safeguarding_reference": {"disclosure": "..."}})
    assert any("restricted" in p for p in problems)


def test_undeclared_boundary_passes_through():
    # sixth_form -> apprenticeships is a *declared* boundary now, so this
    # uses one that genuinely has no national dataset behind it.
    result = handover.build_handover(
        "sixth_form", "employment",
        {"student_identity": {}, "safeguarding_detail": "no"},
        consent=True)
    assert "student_identity" in result.payload
    assert "safeguarding_detail" not in result.payload


# ── Transition workflow ─────────────────────────────────────────────

def test_full_seven_step_workflow(db, journey):
    # The mirrored enrolment the journey fixture already created.
    source = enrolments.current_enrolment(journey, "secondary", db_path=db)
    assert source["local_student_id"] == "S9340"

    t = transitions.start_transition(
        journey_id=journey, source_system="secondary",
        source_enrolment_id=source["enrolment_id"], db_path=db)
    assert t["destination_system"] == "sixth_form"   # recommended default
    assert t["status"] == "expected"

    tid = t["transition_id"]
    assert transitions.record_application(
        tid, application_reference="APP-1", db_path=db)["status"] == "applied"
    assert transitions.offer_place(
        tid, conditions="5 GCSEs", db_path=db)["status"] == "offered"
    assert transitions.accept_place(
        tid, accepted_by="parent", db_path=db)["status"] == "accepted"

    built = handover.build_handover(
        "secondary", "sixth_form",
        {"student_identity": {"n": "Ada"}, "application_details": {"r": 1},
         "gcse_results": {"maths": 8}, "attendance_behaviour": {"pct": 96}},
        consent=True)
    t5 = transitions.approve_handover(tid, built, consent_reference="C-1",
                                      db_path=db)
    assert t5["status"] == "handover_approved"
    assert transitions.get_handover(tid, db_path=db)["gcse_results"] == {
        "maths": 8}

    assert transitions.admit(tid, local_student_id="SF2208",
                             db_path=db)["status"] == "admitted"
    done = transitions.complete(tid, start_date="2026-09-01", db_path=db)
    assert done["status"] == "completed"
    assert done["completed_at"] is not None

    # Destination enrolment active, source closed but retained.
    dest = enrolments.get_enrolment(done["destination_enrolment_id"],
                                    db_path=db)
    assert dest["status"] == "active"
    assert dest["local_student_id"] == "SF2208"
    src = enrolments.get_enrolment(source["enrolment_id"], db_path=db)
    assert src["status"] == "transferred"
    assert src["exit_reason"] == "progressed to sixth_form"

    # Canonical journey kept in step for legacy slot readers.
    j = identity_service.get(journey, db_path=db)
    assert j["college_student_id"] == "SF2208"
    assert j["current_system"] == "sixth_form"


def test_workflow_only_moves_forward(db, journey):
    t = transitions.start_transition(journey_id=journey,
                                     destination_system="primary", db_path=db)
    tid = t["transition_id"]
    transitions.offer_place(tid, db_path=db)
    with pytest.raises(transitions.TransitionError):
        transitions.record_application(tid, db_path=db)


def test_external_arrival_may_jump_straight_to_admitted(db, journey):
    t = transitions.start_transition(
        journey_id=journey, source_system="external",
        destination_system="secondary",
        reason="joined mid-year from another school", db_path=db)
    tid = t["transition_id"]
    transitions.admit(tid, local_student_id="S777", db_path=db)
    done = transitions.complete(tid, db_path=db)
    assert done["status"] == "completed"
    assert enrolments.get_enrolment(
        done["destination_enrolment_id"], db_path=db)["status"] == "active"


def test_cancelled_transition_is_kept_and_closes_the_applicant(db, journey):
    t = transitions.start_transition(journey_id=journey,
                                     destination_system="university",
                                     db_path=db)
    tid = t["transition_id"]
    transitions.offer_place(tid, local_student_id="U1", db_path=db)
    cancelled = transitions.cancel(tid, reason="chose insurance offer",
                                   db_path=db)
    assert cancelled["status"] == "cancelled"
    assert cancelled["cancelled_reason"] == "chose insurance offer"
    dest = enrolments.get_enrolment(cancelled["destination_enrolment_id"],
                                    db_path=db)
    assert dest["status"] == "cancelled"
    # Kept in history.
    assert len(transitions.list_transitions(journey, db_path=db)) == 1
    with pytest.raises(transitions.TransitionError):
        transitions.accept_place(tid, db_path=db)


def test_concurrent_enrolment_leaves_the_source_open(db, journey):
    source = enrolments.current_enrolment(journey, "secondary", db_path=db)
    t = transitions.start_transition(
        journey_id=journey, source_system="secondary",
        source_enrolment_id=source["enrolment_id"],
        destination_system="sixth_form", db_path=db)
    tid = t["transition_id"]
    transitions.admit(tid, local_student_id="SF1", db_path=db)
    transitions.complete(tid, close_source=False, db_path=db)
    assert enrolments.get_enrolment(
        source["enrolment_id"], db_path=db)["status"] == "active"
    assert len(enrolments.active_enrolments(journey, db_path=db)) == 2


def test_destination_to_a_non_phase_still_records_the_journey(db, journey):
    t = transitions.start_transition(
        journey_id=journey, source_system="sixth_form",
        destination_system="employment", reason="left for full-time work",
        db_path=db)
    tid = t["transition_id"]
    transitions.admit(tid, local_student_id="EMP-9", db_path=db)
    done = transitions.complete(tid, db_path=db)
    assert done["status"] == "completed"
    # No slot exists for employment, but the transition is still audited.
    j = identity_service.get(journey, db_path=db)
    assert j["current_system"] == "employment"


def test_legacy_apprenticeship_spelling_folds_onto_the_real_system(db, journey):
    """A journey recorded against the pre-registry label must reach the
    same slot as one recorded against the system key, or one learner ends
    up with two parallel histories."""
    t = transitions.start_transition(
        journey_id=journey, source_system="sixth_form",
        destination_system="apprenticeship",     # the old, singular label
        db_path=db)
    assert t["destination_system"] == "apprenticeships"

    tid = t["transition_id"]
    transitions.admit(tid, local_student_id="APP-9", db_path=db)
    transitions.complete(tid, db_path=db)

    j = identity_service.get(journey, db_path=db)
    assert j["current_system"] == "apprenticeships"
    # Unlike a non-phase destination, this one has a slot to land in.
    assert j["apprenticeships_learner_id"] == "APP-9"


def test_a_degree_apprenticeship_leaves_both_enrolments_open(db, journey):
    """University and apprenticeships run concurrently for a degree
    apprentice; closing the source would say they had left a course they
    are still on."""
    uni = enrolments.create_enrolment(
        journey_id=journey, system="university", local_student_id="U-77",
        status="active", db_path=db)
    t = transitions.start_transition(
        journey_id=journey, source_system="university",
        destination_system="apprenticeships",
        source_enrolment_id=uni["enrolment_id"],
        reason="degree apprenticeship", db_path=db)
    transitions.admit(t["transition_id"], local_student_id="APP-12", db_path=db)
    transitions.complete(t["transition_id"], close_source=False, db_path=db)

    live = {e["system"] for e in enrolments.active_enrolments(journey, db_path=db)}
    assert {"university", "apprenticeships"} <= live


def test_start_transition_requires_a_destination_at_the_end_of_the_chain(db,
                                                                        journey):
    with pytest.raises(transitions.TransitionError):
        transitions.start_transition(journey_id=journey,
                                     source_system="university", db_path=db)


def test_pending_transitions_is_the_destination_work_queue(db, journey):
    t = transitions.start_transition(journey_id=journey,
                                     destination_system="university",
                                     db_path=db)
    assert len(transitions.pending_transitions("university", db_path=db)) == 1
    transitions.admit(t["transition_id"], local_student_id="U1", db_path=db)
    transitions.complete(t["transition_id"], db_path=db)
    assert transitions.pending_transitions("university", db_path=db) == []


# ── Events ──────────────────────────────────────────────────────────

def _event_names(db_path):
    from education_system.platform.identity.auth.db import connect
    conn = connect(db_path)
    try:
        return [r["event_name"] for r in conn.execute(
            "SELECT event_name FROM cross_system_event_outbox "
            "ORDER BY rowid").fetchall()]
    finally:
        conn.close()


def test_each_step_publishes_its_event(db, journey):
    t = transitions.start_transition(journey_id=journey,
                                     destination_system="university",
                                     db_path=db)
    tid = t["transition_id"]
    transitions.record_application(tid, db_path=db)
    transitions.offer_place(tid, db_path=db)
    transitions.accept_place(tid, db_path=db)
    transitions.approve_handover(tid, {"a": 1}, db_path=db)
    transitions.admit(tid, local_student_id="U1", db_path=db)
    transitions.complete(tid, db_path=db)

    names = _event_names(db)
    for expected in ("progression.expected", "application.submitted",
                     "place.offered", "place.accepted", "handover.approved",
                     "enrolment.created", "progression.completed"):
        assert expected in names, f"{expected} not published"


def test_legacy_twins_keep_existing_consumers_working(db, journey):
    t = transitions.start_transition(journey_id=journey,
                                     destination_system="university",
                                     db_path=db)
    tid = t["transition_id"]
    transitions.offer_place(tid, db_path=db)
    transitions.accept_place(tid, db_path=db)
    transitions.admit(tid, local_student_id="U1", db_path=db)
    transitions.complete(tid, db_path=db)

    names = _event_names(db)
    # ProgressionIntake subscribes to this one.
    assert "student.progression.completed" in names
    assert "student.progression.offered" in names
    assert "student.progression.accepted" in names


def test_handover_payload_is_not_put_on_the_bus(db, journey):
    from education_system.platform.identity.auth.db import connect
    t = transitions.start_transition(journey_id=journey,
                                     destination_system="university",
                                     db_path=db)
    transitions.approve_handover(
        t["transition_id"], {"reference": "confidential text"}, db_path=db)
    conn = connect(db)
    try:
        blobs = " ".join(r["payload_json"] for r in conn.execute(
            "SELECT payload_json FROM cross_system_event_outbox").fetchall())
    finally:
        conn.close()
    assert "confidential text" not in blobs


def test_new_events_are_registered_on_the_bus():
    for name in ("progression.expected", "application.submitted",
                 "place.offered", "place.accepted", "handover.approved",
                 "enrolment.created", "progression.completed",
                 "progression.cancelled"):
        assert name in cross_system_bus.KNOWN_EVENTS


# ── next_phase is a recommendation, not a gate ──────────────────────

def test_next_phase_still_recommends():
    assert progression.next_phase("secondary") == "sixth_form"
    assert progression.recommended_destination("university") is None


def test_any_named_destination_is_permitted():
    assert progression.is_permitted_destination("secondary", "university")
    assert progression.is_permitted_destination("sixth_form",
                                                "apprenticeship")
    assert progression.is_permitted_destination("university", "employment")
    assert not progression.is_permitted_destination("secondary", "")


def test_known_destinations_lead_with_the_recommendation():
    dests = progression.known_destinations("secondary")
    assert dests[0] == "sixth_form"
    assert "university" in dests              # skipping sixth form
    assert "apprenticeships" in dests         # a real system, post-16
    assert "fe_college" in dests
    assert "home_education" in dests
    assert "secondary" not in dests
    # Systems the platform runs come before leaving it, so recording a
    # real destination is the easy default.
    assert dests.index("apprenticeships") < dests.index("external")


def test_parallel_systems_are_offered_but_stay_off_the_phase_chain():
    # Both are destinations everywhere...
    assert set(progression.PARALLEL_SYSTEMS) <= set(
        progression.known_destinations("sixth_form"))
    # ...but neither is a step, so the recommendation is unaffected.
    assert "apprenticeships" not in progression.PHASE_ORDER
    assert "fe_college" not in progression.PHASE_ORDER
    assert progression.next_phase("sixth_form") == "university"


def test_legacy_destination_labels_normalise():
    assert progression.normalise_system("apprenticeship") == "apprenticeships"
    assert progression.normalise_system("college") == "sixth_form"
    assert progression.normalise_system("school") == "secondary"
    # A destination the platform does not run passes through untouched.
    assert progression.normalise_system("employment") == "employment"
    assert progression.normalise_system(None) is None


# ── Adapters ────────────────────────────────────────────────────────

class _Receiving(base.PhaseAdapter):
    system = "primary"

    def create_applicant(self, handover_request):
        return base.ApplicantResult(local_applicant_id="APP-1")

    def create_enrolment(self, journey_id, application_id=None, **details):
        return base.EnrolmentResult(local_student_id="P4821")


@pytest.fixture(autouse=True)
def _clean_registry():
    registry.clear_for_test()
    yield
    registry.clear_for_test()


def test_register_and_look_up():
    a = registry.register(_Receiving())
    assert registry.get("primary") is a
    assert registry.registered_systems() == ["primary"]


def test_missing_adapter_is_not_an_error_for_get():
    # "employment" has no adapter and never will — there is no system to
    # call. That is an expected answer from get(), not a failure.
    assert registry.get("employment") is None
    with pytest.raises(base.AdapterError):
        registry.require("employment")


def test_duplicate_registration_is_rejected():
    registry.register(_Receiving())

    class Other(base.PhaseAdapter):
        system = "primary"

    with pytest.raises(base.AdapterError):
        registry.register(Other())
    registry.register(Other(), replace=True)
    assert isinstance(registry.get("primary"), Other)


def test_unimplemented_side_raises_rather_than_returning_none():
    a = _Receiving()
    with pytest.raises(base.AdapterNotImplemented):
        a.export_handover("P4821")
    with pytest.raises(base.AdapterNotImplemented):
        a.close_enrolment("P4821", reason="left")


def test_capabilities_report_what_is_wired():
    caps = _Receiving().capabilities()
    assert caps["create_applicant"] is True
    assert caps["create_enrolment"] is True
    assert caps["export_handover"] is False
    assert caps["close_enrolment"] is False


def test_adapter_without_a_system_key_is_rejected():
    class Nameless(base.PhaseAdapter):
        pass

    with pytest.raises(base.AdapterError):
        Nameless()
