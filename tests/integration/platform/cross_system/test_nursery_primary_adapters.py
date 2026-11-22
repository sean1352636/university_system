"""The nursery and primary adapters, and the two school routes now built on them.

Nursery→primary and primary→secondary used to import the next school's
pupil table directly. They now run through the platform:

1. the source adapter exports;
2. the boundary's handover spec filters;
3. the destination adapter creates the applicant, then the enrolment;
4. the source adapter closes its record, and keeps it.

These tests run the real adapters and the real transition workflow.
Every database, auth.db included, is under ``tmp_path``.
"""

from __future__ import annotations

import pytest

from education_system.platform.cross_system import (
    enrolment_schema,
    enrolments,
    handover,
    identity_service,
    transitions,
)
from education_system.platform.cross_system.adapters import registry
from education_system.platform.cross_system.adapters.base import HandoverRequest
from education_system.platform.identity.auth import db as auth_db
from education_system.platform.identity.auth.schema import initialise_auth_db
from education_system.platform.integrations.external import cross_system_bus

CHILD = {
    "first_name": "Maya", "last_name": "Okafor", "date_of_birth": "2021-05-04",
    "room": "Preschool Room", "start_date": "2023-09-04",
    "parent_name": "Ngozi Okafor", "parent_phone": "07123 456789",
    "parent_email": "ngozi@example.test", "allergies": "Peanuts",
    "medical_notes": "Carries an inhaler",
}


@pytest.fixture()
def phases(tmp_path, monkeypatch):
    """Auth, nursery, primary and secondary databases, all under tmp_path,
    with the real adapters registered."""
    auth_path = tmp_path / "auth.db"
    # Local record creation registers the journey in the *default* auth
    # database, so the default is redirected as well as passed explicitly.
    monkeypatch.setattr(auth_db, "PLATFORM_AUTH_DB_FILE", auth_path)
    initialise_auth_db(str(auth_path))
    identity_service._initialised.clear()
    enrolment_schema.reset_schema_cache_for_test()

    from education_system.systems.nursery.infrastructure import database as nursery_db
    monkeypatch.setattr(nursery_db, "NURSERY_DB", tmp_path / "nursery.db")
    monkeypatch.setattr(nursery_db, "ensure_nursery_directories", lambda: None)

    from education_system.systems.primary.domain.learners.pupils import pupils as primary
    from education_system.systems.primary.domain.learners.pupils.leavers import leavers
    monkeypatch.setattr(primary, "DB_PATH", tmp_path / "primary.db")
    monkeypatch.setattr(primary, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(primary, "_DB_READY", False)
    if hasattr(leavers, "_DB_READY"):
        monkeypatch.setattr(leavers, "_DB_READY", False)

    from education_system.systems.secondary.domain.admissions import (
        cross_system_adapter as secondary_adapter,
    )
    from education_system.systems.secondary.domain.learners.alumni import alumni
    from education_system.systems.secondary.domain.learners.pupils import pupils as secondary
    monkeypatch.setattr(secondary, "DB_PATH", tmp_path / "secondary.db")
    monkeypatch.setattr(secondary, "_DB_READY", False)
    if hasattr(alumni, "_DB_READY"):
        monkeypatch.setattr(alumni, "_DB_READY", False)
    # The login lives in auth.db; stand in for it so the test says what the
    # route returns without depending on the password policy.
    monkeypatch.setattr(secondary_adapter, "_provision_login",
                        lambda pupil: (7, "first-password"))

    from education_system.systems.nursery.domain.learners.children import (
        cross_system_adapter as nursery_adapter,
    )
    from education_system.systems.primary.domain.learners.pupils import (
        cross_system_adapter as primary_adapter,
    )
    registry.clear_for_test()
    for module in (nursery_adapter, primary_adapter, secondary_adapter):
        module.register()
    cross_system_bus.clear_subscribers_for_test()
    yield str(auth_path)
    registry.clear_for_test()
    cross_system_bus.clear_subscribers_for_test()
    identity_service._initialised.clear()
    enrolment_schema.reset_schema_cache_for_test()


def _child():
    from education_system.systems.nursery.domain.learners.children import children
    return children.create_child(dict(CHILD))


# ── The nursery adapter ─────────────────────────────────────────────

def test_nursery_export_uses_the_spec_keys(phases):
    child = _child()
    exported = registry.require("nursery").export_handover(
        child.pupil_id, destination_system="primary")

    spec_keys = set(handover.NURSERY_TO_PRIMARY.field_keys())
    assert set(exported.record) <= spec_keys
    assert exported.record["child_identity"]["date_of_birth"] == "2021-05-04"
    assert exported.record["medical_alerts"]["allergies"] == "Peanuts"
    assert exported.record["guardians"][0]["name"] == "Ngozi Okafor"


def test_nursery_close_keeps_the_child(phases):
    from education_system.systems.nursery.domain.learners.children import children
    child = _child()

    registry.require("nursery").close_enrolment(child.pupil_id, "Moved to primary")
    registry.require("nursery").close_enrolment(child.pupil_id, "Moved to primary")

    kept = children.get_child(child.pupil_id)
    assert kept is not None
    assert kept.status == "left"


# ── Nursery → primary ───────────────────────────────────────────────

def test_move_is_refused_without_consent_to_share_medical_alerts(phases):
    from education_system.systems.nursery.domain.learners.children import (
        children,
        primary_transfer,
    )
    from education_system.systems.primary.domain.learners.pupils import pupils
    child = _child()

    with pytest.raises(children.ValidationError, match="medical_alerts"):
        primary_transfer.move_to_primary_school(child.pupil_id)

    assert pupils.list_pupils(include_off_roll=True) == []
    assert children.get_child(child.pupil_id).status == "active"


def test_nursery_to_primary_runs_through_the_platform(phases):
    from education_system.systems.nursery.domain.learners.children import (
        children,
        primary_transfer,
    )
    from education_system.systems.primary.domain.learners.pupils import pupils
    child = _child()

    result = primary_transfer.move_to_primary_school(
        child.pupil_id, class_name="Robins",
        consent=primary_transfer.consent_for(medical=True, support=False),
        db_path=phases)

    pupil = pupils.get_pupil(result.primary_pupil_id)
    assert pupil.roll_status == "on_roll"
    assert (pupil.year_group, pupil.class_name) == ("R", "Robins")
    assert "Allergies: Peanuts" in pupil.medical_notes
    assert pupil.journey_id == result.journey_id
    assert children.get_child(child.pupil_id).status == "left"

    transition = transitions.get_transition(result.transition_id, db_path=phases)
    assert transition["status"] == "completed"
    released = transitions.get_handover(result.transition_id, db_path=phases)
    assert "medical_alerts" in released
    assert "send_support" not in released

    open_primary = enrolments.list_enrolments(
        result.journey_id, system="primary", include_closed=False, db_path=phases)
    assert [row["status"] for row in open_primary] == ["active"]


def test_a_move_that_stopped_part_way_resumes(phases, monkeypatch):
    from education_system.systems.nursery.domain.learners.children import (
        children,
        primary_transfer,
    )
    from education_system.systems.primary.domain.learners.pupils import (
        cross_system_adapter as primary_adapter,
    )
    from education_system.systems.primary.domain.learners.pupils import pupils
    child = _child()
    real = primary_adapter.PrimaryAdapter.create_enrolment
    calls = {"n": 0}

    def flaky(self, journey_id, application_id=None, **details):
        calls["n"] += 1
        if calls["n"] == 1:
            raise primary_adapter.AdapterError("primary database busy")
        return real(self, journey_id, application_id, **details)

    monkeypatch.setattr(primary_adapter.PrimaryAdapter, "create_enrolment", flaky)
    consent = primary_transfer.consent_for(medical=True, support=False)

    with pytest.raises(children.ValidationError, match="busy"):
        primary_transfer.move_to_primary_school(child.pupil_id, consent=consent,
                                                db_path=phases)
    assert children.get_child(child.pupil_id).status == "active"

    result = primary_transfer.move_to_primary_school(
        child.pupil_id, consent=consent, db_path=phases)

    assert len(pupils.list_pupils(include_off_roll=True)) == 1
    assert pupils.get_pupil(result.primary_pupil_id).roll_status == "on_roll"
    assert len(transitions.list_transitions(result.journey_id, db_path=phases)) == 1


def test_add_pupil_details_cross_to_primary(phases):
    """The nursery record now asks the schools' Add Pupil questions; those
    answers reach the primary pupil (SEN and EAL only with consent)."""
    from education_system.systems.nursery.domain.learners.children import (
        children,
        primary_transfer,
    )
    from education_system.systems.primary.domain.learners.pupils import pupils
    upn = children.upn_check_letter("201234567890") + "201234567890"
    child = children.create_child({
        **CHILD, "middle_names": "Grace", "preferred_name": "May", "gender": "Female",
        "upn": upn, "address_line1": "1 High Street", "town": "Bath",
        "postcode": "BA1 1AA", "sen_status": "K", "eal": "yes",
        "parent_relationship": "Mother"}, complete=True)

    exported = registry.require("nursery").export_handover(
        child.pupil_id, destination_system="primary").record
    assert set(exported) <= set(handover.NURSERY_TO_PRIMARY.field_keys())
    assert exported["child_identity"]["upn"] == upn
    assert exported["guardians"][0]["relationship"] == "Mother"
    assert exported["send_support"]["sen_status"] == "K"
    assert exported["communication_needs"] == {"eal": True}

    result = primary_transfer.move_to_primary_school(
        child.pupil_id, consent=primary_transfer.consent_for(medical=True, support=True),
        db_path=phases)
    pupil = pupils.get_pupil(result.primary_pupil_id)
    assert (pupil.middle_names, pupil.preferred_name, pupil.gender, pupil.upn) == (
        "Grace", "May", "Female", upn)
    assert (pupil.address_line1, pupil.town, pupil.postcode) == (
        "1 High Street", "Bath", "BA1 1AA")
    assert (pupil.parent_relationship, pupil.parent_email) == (
        "Mother", "ngozi@example.test")
    assert (pupil.sen_status, pupil.send_status, pupil.eal) == ("K", "yes", True)
    left = children.get_child(child.pupil_id)
    assert left.status == "left" and left.left_date


def test_sen_and_eal_stay_behind_without_support_consent(phases):
    from education_system.systems.nursery.domain.learners.children import (
        children,
        primary_transfer,
    )
    from education_system.systems.primary.domain.learners.pupils import pupils
    child = children.create_child({**CHILD, "sen_status": "E", "eal": "yes"})

    result = primary_transfer.move_to_primary_school(
        child.pupil_id, consent=primary_transfer.consent_for(medical=True, support=False),
        db_path=phases)

    pupil = pupils.get_pupil(result.primary_pupil_id)
    assert pupil.sen_status is None and pupil.eal is False
    assert {"send_support", "communication_needs"} <= set(result.withheld)


def test_primary_applicant_is_idempotent_on_the_journey(phases):
    from education_system.systems.primary.domain.learners.pupils import pupils
    request = HandoverRequest(
        journey_id="journey-9", source_system="nursery", destination_system="primary",
        payload={"child_identity": {"first_name": "Ola", "last_name": "Ade",
                                    "date_of_birth": "2021-01-02"}})

    first = registry.require("primary").create_applicant(request)
    second = registry.require("primary").create_applicant(request)

    assert first.local_applicant_id == second.local_applicant_id
    assert pupils.get_pupil(first.local_applicant_id).roll_status == "applicant"
    assert pupils.list_pupils() == []


# ── Primary → secondary ─────────────────────────────────────────────

def test_primary_to_secondary_keeps_the_primary_record(phases):
    from education_system.systems.primary.domain.learners.pupils import pupils
    from education_system.systems.primary.domain.learners.pupils import secondary_transfer
    from education_system.systems.primary.domain.learners.pupils.leavers import leavers
    from education_system.systems.secondary.domain.learners.pupils import (
        pupils as secondary_pupils,
    )
    pupil = pupils.create_pupil({
        "first_name": "Ada", "last_name": "Obi", "year_group": "6",
        "date_of_birth": "2014-09-01", "parent_name": "Grace Obi",
        "parent_phone": "07111 111111", "send_status": "yes",
    })

    result = secondary_transfer.move_to_secondary_school(
        pupil.pupil_id, form_group="7A", db_path=phases)

    assert result.password == "first-password"
    moved = secondary_pupils.get_pupil(result.secondary_pupil_id)
    assert (moved.roll_status, moved.year_group, moved.form_group) == (
        "on_roll", "7", "7A")
    # No consent was given, so the SEND flag stayed with the primary school.
    assert moved.send_status != "yes"
    assert "send_provision" in result.withheld

    kept = pupils.get_pupil(pupil.pupil_id)
    assert kept is not None and kept.roll_status == "left"
    assert leavers.get_leaver(result.leaver_id).current_email == result.secondary_email
