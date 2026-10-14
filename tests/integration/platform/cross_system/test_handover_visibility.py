"""Who sees what of a handover: the gated accessor, consent checks,
structured support fields, safeguarding targeting and DSL redemption.

Every case runs against an isolated temp auth DB, with the central audit
DB beside it.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from education_system.platform.cross_system import (
    enrolment_schema,
    enrolments,
    handover,
    identity_service,
    transitions,
)
from education_system.platform.governance.gdpr.consent_service import (
    CONSENT_TYPES,
    ConsentService,
    transition_handover_reference,
    verify_transition_handover_consent,
)
from education_system.platform.governance.safeguarding import alert_service
from education_system.platform.governance.security import sensitive_access
from education_system.platform.identity.auth.db import connect


@pytest.fixture
def db(tmp_path):
    """An isolated auth DB with the enrolment schema in place (the same
    fixture as test_enrolment_model.py)."""
    path = str(tmp_path / "auth.db")
    enrolment_schema.reset_schema_cache_for_test()
    identity_service._initialised.clear()
    alert_service._initialised.clear()
    enrolment_schema.ensure_enrolment_schema(path)
    yield path
    enrolment_schema.reset_schema_cache_for_test()
    identity_service._initialised.clear()
    alert_service._initialised.clear()


@pytest.fixture
def journey(db):
    return identity_service.get_or_create_journey(
        first_name="Ada", last_name="Lovelace", date_of_birth="2010-12-10",
        system="secondary", student_id="S9340", db_path=db)


RECORD = {
    "student_identity": {"n": "Ada"},
    "application_details": {"r": 1},
    "gcse_results": {"maths": 8},
    "attendance_behaviour": {"pct": 96},
    "access_arrangements": {"extra_time": 25},
    "support_plan": handover.make_support_plan(
        "SEN support: literacy", review_date="2026-11-01", owner="SENCO"),
    "reasonable_adjustments": [handover.make_reasonable_adjustment(
        "25% extra time", context="exams")],
    "key_contacts": [handover.make_key_contact(
        "J Smith", role="SENCO", email="j.smith@school.test")],
}


def _approved(db, journey, **kw):
    t = transitions.start_transition(
        journey_id=journey, source_system="secondary",
        destination_system="sixth_form", db_path=db)
    built = handover.build_handover("secondary", "sixth_form", RECORD,
                                    consent=True,
                                    safeguarding_reference="SG-REF-1")
    transitions.approve_handover(t["transition_id"], built, db_path=db, **kw)
    return t["transition_id"]


def _user(db, username):
    """A users row, for consent_records' foreign key. Fills whatever the
    users table requires rather than hard-coding its columns."""
    conn = connect(db)
    try:
        cols = conn.execute("PRAGMA table_info(users)").fetchall()
        values = {c["name"]: (0 if "INT" in (c["type"] or "").upper()
                              else f"{username}-{c['name']}")
                  for c in cols
                  if c["notnull"] and c["dflt_value"] is None and not c["pk"]}
        values["username"] = username
        cur = conn.execute(
            f"INSERT INTO users ({', '.join(values)}) "
            f"VALUES ({', '.join('?' * len(values))})", list(values.values()))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _view(db, tid, role, system="sixth_form", purpose="transition_planning"):
    return transitions.get_handover_for(
        tid, viewer_role=role, viewer_system=system, purpose=purpose,
        viewer_id=11, db_path=db)


# ── The gated accessor ──────────────────────────────────────────────

def test_routine_fields_reach_any_party_without_a_purpose(db, journey):
    tid = _approved(db, journey)
    view = _view(db, tid, "teacher", purpose=None)
    assert {"student_identity", "gcse_results", "key_contacts"} <= set(
        view["payload"])
    assert "access_arrangements" in view["withheld"]
    assert "support_plan" in view["withheld"]


def test_sensitive_fields_follow_role_and_purpose(db, journey):
    tid = _approved(db, journey)
    teacher = _view(db, tid, "teacher")
    # Day-one classroom needs, not the plan behind them.
    assert "access_arrangements" in teacher["payload"]
    assert "reasonable_adjustments" in teacher["payload"]
    assert "support_plan" in teacher["withheld"]
    assert "attendance_behaviour" in teacher["withheld"]

    senco = _view(db, tid, "senco")
    assert senco["payload"]["support_plan"]["review_date"] == "2026-11-01"
    assert "attendance_behaviour" in senco["withheld"]


def test_restricted_reference_reaches_only_a_designated_lead(db, journey):
    tid = _approved(db, journey)
    for role in ("teacher", "senco", "admin"):
        view = _view(db, tid, role)
        assert "safeguarding_reference" not in view["payload"]
        assert "safeguarding_reference" in view["withheld"]
    dsl = _view(db, tid, "dsl", purpose="safeguarding_casework")
    assert dsl["payload"]["safeguarding_reference"] == "SG-REF-1"
    assert dsl["withheld"] == []
    # A designated lead still needs a purpose.
    assert "safeguarding_reference" in _view(
        db, tid, "dsl", purpose=None)["withheld"]


def test_a_system_that_is_not_a_party_is_refused(db, journey):
    tid = _approved(db, journey)
    with pytest.raises(handover.HandoverAccessError):
        _view(db, tid, "teacher", system="primary")
    # The source that released it may read it back.
    assert _view(db, tid, "admin", system="secondary")["payload"]


def test_every_read_is_audited(db, journey):
    tid = _approved(db, journey)
    _view(db, tid, "teacher")
    conn = connect(db)
    try:
        decisions = {r["decision"] for r in conn.execute(
            "SELECT decision FROM sensitive_access_audit "
            "WHERE domain = 'handover'").fetchall()}
    finally:
        conn.close()
    assert decisions == {"allowed", "denied"}
    audit = sqlite3.connect(Path(db).with_name("audit.db"))
    try:
        actions = [r[0] for r in audit.execute(
            "SELECT action FROM audit_log").fetchall()]
    finally:
        audit.close()
    assert "cross_system.access" in actions


def test_ungated_get_handover_is_unchanged(db, journey):
    tid = _approved(db, journey)
    whole = transitions.get_handover(tid, db_path=db)
    assert whole["safeguarding_reference"] == "SG-REF-1"
    assert "support_plan" in whole


def test_no_handover_reads_as_none(db, journey):
    t = transitions.start_transition(journey_id=journey,
                                     destination_system="sixth_form",
                                     source_system="secondary", db_path=db)
    assert _view(db, t["transition_id"], "dsl") is None


def test_partition_fields_splits_by_role():
    permitted, refused = sensitive_access.partition_fields(
        "handover", "nurse", ["medical_alerts", "send_support"])
    assert permitted == {"medical_alerts"}
    assert refused == {"send_support"}
    assert sensitive_access.partition_fields(
        "handover", "DSL", ["anything"])[1] == frozenset()


# ── Consent ─────────────────────────────────────────────────────────

def test_transition_handover_is_a_consent_type():
    assert "transition_handover" in CONSENT_TYPES


def test_granted_consent_reference_keeps_sensitive_fields(db, journey):
    uid = _user(db, "parent1")
    record = ConsentService(db).grant_consent(uid, "transition_handover")
    ref = transition_handover_reference(record)
    assert verify_transition_handover_consent(ref, db_path=db) is True
    tid = _approved(db, journey, consent_reference=ref)
    assert "support_plan" in transitions.get_handover(tid, db_path=db)
    assert "verified" in transitions.list_transition_events(
        tid, db_path=db)[-1]["note"]


def test_withdrawn_consent_reference_withholds_sensitive_fields(db, journey):
    uid = _user(db, "parent2")
    service = ConsentService(db)
    ref = transition_handover_reference(
        service.grant_consent(uid, "transition_handover"))
    service.withdraw_consent(uid, "transition_handover")
    tid = _approved(db, journey, consent_reference=ref)
    stored = transitions.get_handover(tid, db_path=db)
    assert "support_plan" not in stored
    assert "access_arrangements" not in stored
    assert "gcse_results" in stored
    # The safeguarding pointer does not depend on consent.
    assert stored["safeguarding_reference"] == "SG-REF-1"
    event = transitions.list_transition_events(tid, db_path=db)[-1]
    assert "support_plan" in event["withheld_fields"]


def test_consent_of_another_type_does_not_count(db):
    uid = _user(db, "parent3")
    record = ConsentService(db).grant_consent(uid, "photo_internal")
    assert verify_transition_handover_consent(
        transition_handover_reference(record), db_path=db) is False
    assert verify_transition_handover_consent("consent_records:9999",
                                              db_path=db) is False


def test_a_sending_systems_own_reference_is_left_alone(db, journey):
    assert verify_transition_handover_consent("C-1", db_path=db) is None
    tid = _approved(db, journey, consent_reference="learner-consent:all")
    assert "support_plan" in transitions.get_handover(tid, db_path=db)


# ── Structured support data and checklists ──────────────────────────

def test_structured_fields_are_on_every_spec_with_sensible_levels():
    for spec in handover.HANDOVER_SPECS.values():
        assert spec.get("support_plan").sensitivity is \
            handover.Sensitivity.SENSITIVE
        assert spec.get("reasonable_adjustments").sensitivity is \
            handover.Sensitivity.SENSITIVE
        assert spec.get("key_contacts").sensitivity is \
            handover.Sensitivity.ROUTINE
        assert spec.checklist, spec.boundary
        assert "documents_received" in spec.checklist_keys()


def test_support_plan_needs_a_review_date():
    with pytest.raises(handover.HandoverError):
        handover.make_support_plan("plan", review_date="soon")
    with pytest.raises(handover.HandoverError):
        handover.make_key_contact("A", role="SENCO")
    problems = handover.validate_handover(
        "secondary", "sixth_form",
        {"student_identity": {}, "application_details": {},
         "support_plan": {"summary": "x"},
         "key_contacts": [{"name": "A", "role": "SENCO"}]})
    assert any("review_date" in p for p in problems)
    assert any("key_contacts" in p for p in problems)
    assert handover.validate_handover(
        "secondary", "sixth_form",
        {"student_identity": {}, "application_details": {},
         **{k: RECORD[k] for k in ("support_plan", "reasonable_adjustments",
                                   "key_contacts")}}) == []


def test_unknown_keys_on_undeclared_boundaries_are_treated_as_sensitive():
    assert handover.sensitivity_of("mystery", "sixth_form", "employment") \
        is handover.Sensitivity.SENSITIVE
    assert handover.sensitivity_of("student_identity", "sixth_form",
                                   "employment") is \
        handover.Sensitivity.ROUTINE


# ── Safeguarding ────────────────────────────────────────────────────

def _flag_targets(db):
    conn = connect(db)
    try:
        return sorted(r["target_system"] for r in conn.execute(
            "SELECT target_system FROM cross_system_event_outbox "
            "WHERE event_name = 'safeguarding.flag.raised'").fetchall())
    finally:
        conn.close()


def test_alerts_go_only_to_systems_holding_the_learner(db, journey):
    enrolments.create_enrolment(journey_id=journey, system="primary",
                                status="completed", db_path=db)
    enrolments.create_enrolment(journey_id=journey, system="sixth_form",
                                status="applicant", db_path=db)
    alert_id = alert_service.raise_flag(journey, source_system="secondary",
                                        summary="concern", db_path=db)
    # Sixth form is preparing to receive them; primary finished with them
    # long ago; secondary raised it.
    assert _flag_targets(db) == ["sixth_form"]
    assert alert_service.get_alerts(journey, db_path=db)[0]["alert_id"] == \
        alert_id


def test_alert_with_nobody_else_to_tell_is_still_recorded(db, journey):
    alert_service.raise_flag(journey, source_system="secondary", db_path=db)
    assert _flag_targets(db) == []
    assert len(alert_service.get_alerts(journey, db_path=db)) == 1


def test_dsl_redeems_a_handover_reference(db, journey):
    _approved(db, journey)
    alert_service.raise_flag(journey, source_system="secondary",
                             summary="concern", db_path=db)
    out = alert_service.redeem_safeguarding_reference(
        "SG-REF-1", dsl_user={"id": 40, "role": "dsl", "system": "sixth_form"},
        purpose="safeguarding_casework", db_path=db)
    assert out["resolved"] and out["journey_id"] == journey
    assert len(out["transitions"]) == 1
    assert len(out["alerts"]) == 1
    assert out["issued_by"] == ["secondary"]

    audit = sqlite3.connect(Path(db).with_name("audit.db"))
    try:
        actions = [r[0] for r in audit.execute(
            "SELECT action FROM audit_log").fetchall()]
    finally:
        audit.close()
    assert "safeguarding.view" in actions
    assert "cross_system.access" in actions


def test_redemption_is_refused_to_other_roles_and_other_settings(db, journey):
    _approved(db, journey)
    with pytest.raises(alert_service.SafeguardingAccessError):
        alert_service.redeem_safeguarding_reference(
            "SG-REF-1", dsl_user={"id": 41, "role": "teacher"},
            purpose="safeguarding_casework", db_path=db)
    with pytest.raises(alert_service.SafeguardingAccessError):
        alert_service.redeem_safeguarding_reference(
            "SG-REF-1", dsl_user={"id": 42, "role": "dsl",
                                  "system": "nursery"},
            purpose="safeguarding_casework", db_path=db)
    with pytest.raises(alert_service.SafeguardingAccessError):
        alert_service.redeem_safeguarding_reference(
            "SG-REF-1", dsl_user={"id": 40, "role": "dsl"}, purpose="",
            db_path=db)


def test_unknown_reference_resolves_to_nothing(db):
    out = alert_service.redeem_safeguarding_reference(
        "no-such-ref", dsl_user={"id": 1, "role": "dsl"},
        purpose="safeguarding_casework", db_path=db)
    assert out["resolved"] is False and out["alerts"] == []
