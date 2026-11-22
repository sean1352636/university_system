"""Secondary transfer (domain.learners.pupils.secondary_transfer).

The secondary end is a stand-in adapter registered for ``secondary`` — the
primary school never imports the secondary system, and neither does this test.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from education_system.platform.cross_system import identity_service, person, transitions
from education_system.platform.cross_system.adapters import registry
from education_system.platform.cross_system.adapters.base import (
    AdapterError,
    ApplicantResult,
    EnrolmentResult,
    PhaseAdapter,
)
from education_system.systems.primary.domain.learners.pupils import cross_system_adapter as CA
from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.learners.pupils import secondary_transfer as ST
from education_system.systems.primary.domain.learners.pupils.leavers import leavers as LV


@dataclass
class _Enrolment(EnrolmentResult):
    email: str | None = None
    initial_password: str | None = None
    auth_user_id: int | None = None


class FakeSecondary(PhaseAdapter):
    """Records what crossed; makes Year 7 pupil S100 with a login."""

    system = "secondary"

    def __init__(self, *, fail_applicant: bool = False):
        super().__init__()
        self.handovers = []
        self.enrolment_details = None
        self.fail_applicant = fail_applicant

    def create_applicant(self, handover):
        if self.fail_applicant:
            raise AdapterError("secondary is full")
        self.handovers.append(handover)
        return ApplicantResult(local_applicant_id="S100", year_group="7")

    def create_enrolment(self, journey_id, application_id=None, **details):
        self.enrolment_details = details
        return _Enrolment(local_student_id="S100", year_group="7",
                          email="s100@secondary.example", initial_password="Temp-Pass-1",
                          auth_user_id=42)


@pytest.fixture(autouse=True)
def _isolated_registry(monkeypatch):
    monkeypatch.setitem(person.SYSTEM_DB_PATHS, "primary", P.DB_PATH)
    monkeypatch.setattr(registry, "_adapters", {})
    monkeypatch.setattr(registry, "_declared", {})
    monkeypatch.setattr(registry, "_bootstrapped", True)
    CA.register()


@pytest.fixture
def secondary():
    fake = FakeSecondary()
    registry.register(fake)
    return fake


def _year6(**extra):
    data = {"first_name": "Ben", "last_name": "Ng", "year_group": "6",
            "date_of_birth": "2015-03-03", "parent_name": "Mum",
            "parent_phone": "01234 567890", "medical_notes": "Asthma",
            "send_status": "yes"}
    data.update(extra)
    return P.create_pupil(data)


# ── the move ─────────────────────────────────────────────────────────

def test_move_returns_the_secondary_record_and_login_once(secondary):
    p = _year6()
    r = ST.move_to_secondary_school(p.pupil_id, form_group="7A", notes="Bright")
    assert r.source_pupil_id == p.pupil_id
    assert r.secondary_pupil_id == "S100"
    assert r.secondary_email == "s100@secondary.example"
    assert r.password == "Temp-Pass-1" and r.auth_user_id == 42
    assert r.warnings == ()
    assert r.journey_id and r.transition_id
    assert secondary.enrolment_details["form_group"] == "7A"
    assert secondary.enrolment_details["provision_login"] is True


def test_move_takes_the_pupil_off_roll_and_writes_the_leaver(secondary):
    p = _year6()
    r = ST.move_to_secondary_school(p.pupil_id, notes="Bright")
    got = P.get_pupil(p.pupil_id)
    assert got is not None and got.roll_status == "left"
    assert got.exit_reason == "Moved to secondary school"
    leaver = LV.get_leaver(r.leaver_id)
    assert leaver.pupil_id == p.pupil_id and leaver.year_left == "6"
    assert leaver.destination_school == ST.DEFAULT_DESTINATION
    assert leaver.current_email == "s100@secondary.example" and leaver.notes == "Bright"
    assert P.list_pupils() == []


def test_named_destination_school_is_recorded(secondary):
    p = _year6()
    r = ST.move_to_secondary_school(p.pupil_id, destination_school="Hill Academy")
    assert LV.get_leaver(r.leaver_id).destination_school == "Hill Academy"


def test_move_completes_the_transition_on_the_pupils_journey(secondary):
    p = _year6()
    r = ST.move_to_secondary_school(p.pupil_id)
    assert identity_service.find_by_student("primary", p.pupil_id)["journey_id"] == r.journey_id
    row = transitions.list_transitions(r.journey_id)[-1]
    assert row["transition_id"] == r.transition_id
    assert row["source_system"] == "primary" and row["destination_system"] == "secondary"
    assert row["status"] == "completed"


# ── what crosses ─────────────────────────────────────────────────────

def test_without_consent_send_and_medical_detail_stay_behind(secondary):
    p = _year6()
    r = ST.move_to_secondary_school(p.pupil_id)
    payload = secondary.handovers[0].payload
    assert set(r.withheld) == {"send_provision", "medical_requirements"}
    assert "send_provision" not in payload and "medical_requirements" not in payload
    assert payload["child_identity"]["primary_pupil_id"] == p.pupil_id
    assert payload["guardians"][0]["name"] == "Mum"
    assert secondary.handovers[0].year_group == "7"


def test_consent_to_one_field_releases_only_that_field(secondary):
    p = _year6()
    r = ST.move_to_secondary_school(p.pupil_id, consent={"medical_requirements"})
    payload = secondary.handovers[0].payload
    assert payload["medical_requirements"] == {"notes": "Asthma", "conditions": []}
    assert "send_provision" not in payload
    assert r.withheld == ("send_provision",)


def test_full_consent_releases_send_and_medical(secondary):
    p = _year6()
    r = ST.move_to_secondary_school(p.pupil_id, consent=True)
    payload = secondary.handovers[0].payload
    assert payload["send_provision"]["sen_status"] == "K"
    assert payload["medical_requirements"] == {"notes": "Asthma", "conditions": []}
    assert r.withheld == ()


def test_consent_fields_are_the_sensitive_ones():
    assert ST.CONSENT_FIELDS == ("send_provision", "support_indicators",
                                 "current_interventions", "medical_requirements")


# ── refusals ─────────────────────────────────────────────────────────

def test_blank_or_unknown_pupil_is_refused(secondary):
    with pytest.raises(ST.ValidationError, match="Pupil ID is required"):
        ST.move_to_secondary_school("  ")
    with pytest.raises(ST.ValidationError, match="No pupil with id P0000000"):
        ST.move_to_secondary_school("P0000000")


def test_a_pupil_who_has_left_cannot_move_again(secondary):
    p = _year6()
    ST.move_to_secondary_school(p.pupil_id)
    with pytest.raises(ST.ValidationError, match="already left the school"):
        ST.move_to_secondary_school(p.pupil_id)
    assert len(secondary.handovers) == 1


def test_a_pupil_already_on_the_leavers_register_is_refused(secondary):
    p = _year6()
    lv = LV.create_leaver({"pupil_id": p.pupil_id, "first_name": "Ben", "last_name": "Ng",
                           "year_left": "6"})
    with pytest.raises(ST.ValidationError, match=f"already a leaver \\({lv.leaver_id}\\)"):
        ST.move_to_secondary_school(p.pupil_id)
    assert secondary.handovers == []


def test_missing_guardian_is_refused_before_anything_is_written(secondary):
    p = _year6(parent_name="", parent_phone="")
    with pytest.raises(ST.ValidationError, match="missing required information: guardians"):
        ST.move_to_secondary_school(p.pupil_id)
    assert secondary.handovers == []
    assert P.get_pupil(p.pupil_id).roll_status == "on_roll"


def test_missing_date_of_birth_is_refused(secondary):
    p = _year6(date_of_birth="")
    with pytest.raises(ST.ValidationError, match="date of birth"):
        ST.move_to_secondary_school(p.pupil_id)
    assert P.get_pupil(p.pupil_id).roll_status == "on_roll"


def test_no_secondary_adapter_is_refused():
    p = _year6()
    with pytest.raises(ST.ValidationError, match="No adapter registered for system 'secondary'"):
        ST.move_to_secondary_school(p.pupil_id)
    assert P.get_pupil(p.pupil_id).roll_status == "on_roll"


def test_secondary_refusing_the_applicant_leaves_the_pupil_on_roll():
    registry.register(FakeSecondary(fail_applicant=True))
    p = _year6()
    with pytest.raises(ST.ValidationError, match="secondary is full"):
        ST.move_to_secondary_school(p.pupil_id)
    assert P.get_pupil(p.pupil_id).roll_status == "on_roll"
    assert CA.leaver_id_for(p.pupil_id) is None
