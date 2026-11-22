"""Primary cross-system adapter (domain.learners.pupils.cross_system_adapter).

Tested through the platform contract only: learner logins, applicant →
enrolment on the way in, export → close on the way out. No other system is
imported.
"""

from __future__ import annotations

import pytest

from education_system.platform.cross_system import identity_service, person
from education_system.platform.cross_system.adapters import registry
from education_system.platform.cross_system.adapters.base import (
    AdapterError,
    HandoverRequest,
    PhaseAdapter,
)
from education_system.systems.primary.domain.learners.pupils import cross_system_adapter as CA
from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.learners.pupils.leavers import leavers as LV

ADAPTER = CA.PrimaryAdapter()


@pytest.fixture(autouse=True)
def _isolated_registry(monkeypatch):
    monkeypatch.setitem(person.SYSTEM_DB_PATHS, "primary", P.DB_PATH)
    monkeypatch.setattr(registry, "_adapters", {})
    monkeypatch.setattr(registry, "_declared", {})
    monkeypatch.setattr(registry, "_bootstrapped", True)


def _handover(journey="j-1", year=None, **payload):
    base = {"child_identity": {"first_name": "Ada", "last_name": "Lovelace",
                               "date_of_birth": "2021-05-01"},
            "guardians": [{"name": "Anne Lovelace", "phone": "01234 567890"}]}
    base.update(payload)
    return HandoverRequest(journey_id=journey, source_system="nursery",
                           destination_system="primary", payload=base, year_group=year)


def _pupil(**extra):
    data = {"first_name": "Ben", "last_name": "Ng", "year_group": "6"}
    data.update(extra)
    return P.create_pupil(data)


# ── declared interface ───────────────────────────────────────────────

def test_adapter_declares_primary_and_student_logins():
    assert ADAPTER.system == "primary" == CA.SYSTEM_KEY
    assert ADAPTER.learner_login_roles == ("student",)
    assert isinstance(ADAPTER, PhaseAdapter)


def test_register_puts_the_adapter_in_the_registry():
    got = CA.register()
    assert got is CA.ADAPTER
    assert registry.get("primary") is CA.ADAPTER
    assert CA.register() is CA.ADAPTER


# ── learner_ids_for_login ────────────────────────────────────────────

def test_login_named_after_the_pupil_id_or_email_pairs_with_that_pupil():
    p, _other = _pupil(), _pupil(first_name="Other")
    assert ADAPTER.learner_ids_for_login({"username": p.pupil_id}) == [p.pupil_id]
    assert ADAPTER.learner_ids_for_login({"username": p.pupil_id.lower()}) == [p.pupil_id]
    assert ADAPTER.learner_ids_for_login({"username": p.email.upper()}) == [p.pupil_id]
    assert ADAPTER.learner_ids_for_login({"username": f"  {p.pupil_id} "}) == [p.pupil_id]


def test_login_that_is_not_a_pupil_id_or_email_pairs_with_nobody():
    p = _pupil()
    for name in ("Ben Ng", p.pupil_id[:-1], "admin3", "", None):
        assert ADAPTER.learner_ids_for_login({"username": name}) == []
    assert ADAPTER.learner_ids_for_login({}) == []


# ── create_applicant ─────────────────────────────────────────────────

def test_applicant_holds_a_reception_place_off_roll():
    res = ADAPTER.create_applicant(_handover(
        class_name="RA", send_support={"ehcp": True},
        medical_alerts={"allergies": " Peanuts ", "medical_notes": "Inhaler"}))
    assert res.year_group == "R" and res.notes == "applicant created from nursery->primary"
    pupil = P.get_pupil(res.local_applicant_id)
    assert pupil.roll_status == "applicant"
    assert (pupil.full_name, pupil.date_of_birth) == ("Ada Lovelace", "2021-05-01")
    assert pupil.class_name == "RA"
    assert pupil.parent_name == "Anne Lovelace" and pupil.parent_phone == "01234 567890"
    assert pupil.medical_notes == "Allergies: Peanuts\nInhaler"
    assert pupil.send_status == "yes"
    assert P.list_pupils() == []                    # not in class lists yet


def test_applicant_is_stamped_with_the_canonical_journey():
    jid = identity_service.get_or_create_journey(
        first_name="Ada", last_name="Lovelace", date_of_birth="2021-05-01",
        system="nursery", student_id="N1")
    res = ADAPTER.create_applicant(_handover(journey=jid))
    assert P.find_by_journey(jid).pupil_id == res.local_applicant_id
    assert identity_service.get(jid)["primary_student_id"] == res.local_applicant_id
    again = ADAPTER.create_applicant(_handover(journey=jid))
    assert again.local_applicant_id == res.local_applicant_id
    assert len(P.list_pupils(include_off_roll=True)) == 1


def test_applicant_is_idempotent_on_journey():
    p = P.create_pupil({"first_name": "Ada", "last_name": "L", "year_group": "R"},
                       roll_status="applicant", journey_id="j-again")
    res = ADAPTER.create_applicant(_handover(journey="j-again"))
    assert res.local_applicant_id == p.pupil_id
    assert res.notes == "existing record, applicant"
    assert len(P.list_pupils(include_off_roll=True)) == 1


def test_applicant_accepts_given_family_names_and_student_identity():
    h = HandoverRequest("j-2", "nursery", "primary", payload={
        "student_identity": {"given_name": "Cy", "family_name": "Day"},
        "guardians": {"name": "Pa", "phone": ""}})
    pupil = P.get_pupil(ADAPTER.create_applicant(h).local_applicant_id)
    assert pupil.full_name == "Cy Day" and pupil.parent_name == "Pa"
    assert pupil.date_of_birth is None


def test_applicant_year_group_from_the_request():
    res = ADAPTER.create_applicant(_handover(year=" 2 "))
    assert res.year_group == "2"
    assert P.get_pupil(res.local_applicant_id).year_group == "2"


def test_applicant_without_a_name_or_with_a_bad_year_is_refused():
    with pytest.raises(AdapterError, match="no usable name"):
        ADAPTER.create_applicant(HandoverRequest("j-3", "nursery", "primary", payload={
            "child_identity": {"first_name": "Ada"}}))
    with pytest.raises(AdapterError, match="Year group must be one of"):
        ADAPTER.create_applicant(_handover(journey="j-4", year="7"))
    with pytest.raises(AdapterError, match="could not create an applicant"):
        ADAPTER.create_applicant(_handover(journey="j-5", guardians=[{"phone": "bad!"}]))
    assert P.list_pupils(include_off_roll=True) == []


@pytest.mark.parametrize("payload,expected", [
    ({"medical_alerts": {}}, "No allergies or medical alerts recorded by the previous setting"),
    ({"medical_alerts": {"allergies": "Eggs"}}, "Allergies: Eggs"),
    ({"medical_alerts": "Epipen in office "}, "Epipen in office"),
    ({"medical_requirements": "Care plan"}, "Care plan"),
    ({}, None),
])
def test_medical_alerts_fold_into_one_notes_field(payload, expected):
    res = ADAPTER.create_applicant(_handover(**payload))
    assert P.get_pupil(res.local_applicant_id).medical_notes == expected


# ── create_enrolment ─────────────────────────────────────────────────

def test_enrolment_puts_the_applicant_on_roll_with_overrides():
    p = P.create_pupil({"first_name": "Ada", "last_name": "L", "year_group": "R",
                        "medical_notes": "Asthma"}, roll_status="applicant", journey_id="j-e")
    res = ADAPTER.create_enrolment("j-e", class_name="RB", start_date="2026-09-03")
    assert isinstance(res, CA.PupilEnrolmentResult)
    assert res.local_student_id == p.pupil_id and res.email == p.email
    assert res.year_group == "R" and res.start_date == "2026-09-03" and res.notes == "on roll"
    got = P.get_pupil(p.pupil_id)
    assert got.roll_status == "on_roll" and got.class_name == "RB"
    assert got.medical_notes == "Asthma"
    assert [x.pupil_id for x in P.list_pupils()] == [p.pupil_id]


def test_enrolment_is_idempotent_and_does_not_reapply_overrides():
    p = P.create_pupil({"first_name": "Ada", "last_name": "L", "year_group": "R",
                        "class_name": "RA"}, roll_status="applicant", journey_id="j-i")
    ADAPTER.create_enrolment("j-i")
    res = ADAPTER.create_enrolment("j-i", class_name="RZ")
    assert res.local_student_id == p.pupil_id
    assert P.get_pupil(p.pupil_id).class_name == "RA"


def test_enrolment_finds_the_applicant_by_application_id():
    p = P.create_pupil({"first_name": "Ada", "last_name": "L", "year_group": "R"},
                       roll_status="applicant")
    assert ADAPTER.create_enrolment("j-none", p.pupil_id).local_student_id == p.pupil_id
    assert P.get_pupil(p.pupil_id).roll_status == "on_roll"


def test_enrolment_refusals():
    with pytest.raises(AdapterError, match="create_applicant must run"):
        ADAPTER.create_enrolment("j-missing")
    p = P.create_pupil({"first_name": "Ada", "last_name": "L", "year_group": "R"},
                       roll_status="applicant", journey_id="j-bad")
    with pytest.raises(AdapterError, match="Year group must be one of"):
        ADAPTER.create_enrolment("j-bad", year_group="7")
    assert P.get_pupil(p.pupil_id).roll_status == "applicant"
    P.set_roll_status(p.pupil_id, "left")
    with pytest.raises(AdapterError, match="has left"):
        ADAPTER.create_enrolment("j-bad")


# ── export_handover ──────────────────────────────────────────────────

def test_export_gathers_identity_guardian_send_and_medical():
    p = _pupil(date_of_birth="2014-03-03", parent_name="Mum", parent_phone="01234 567890",
               send_status="yes", medical_notes="Asthma")
    out = ADAPTER.export_handover(p.pupil_id, destination_system="secondary")
    assert out.local_student_id == p.pupil_id
    rec = out.record
    ident = rec["child_identity"]
    assert (ident["first_name"], ident["last_name"], ident["date_of_birth"]) == (
        "Ben", "Ng", "2014-03-03")
    assert ident["primary_pupil_id"] == p.pupil_id and ident["year_group"] == "6"
    assert ident["school_name"]
    for key in ("middle_names", "preferred_name", "gender", "upn", "class_name",
                "address_line1", "address_line2", "town", "postcode"):
        assert key in ident
    assert rec["guardians"] == [{"name": "Mum", "relationship": "Parent/Carer",
                                 "phone": "01234 567890", "email": None,
                                 "parental_responsibility": True}]
    assert rec["send_provision"]["sen_status"] == "K"
    assert rec["send_provision"]["ehcp"] is False
    assert rec["medical_requirements"] == {"notes": "Asthma", "conditions": []}


def test_export_leaves_empty_sections_as_none():
    p = _pupil(send_status="no")
    rec = ADAPTER.export_handover(p.pupil_id).record
    for key in ("guardians", "send_provision", "medical_requirements", "ks2_results",
                "core_assessments", "attendance_summary", "support_indicators",
                "current_interventions", "transition_report"):
        assert rec[key] is None, key


def test_export_carries_every_spec_key_but_safeguarding():
    from education_system.platform.cross_system import handover
    p = _pupil(date_of_birth="2014-03-03", parent_name="Mum", parent_phone="01234 567890")
    rec = ADAPTER.export_handover(p.pupil_id).record
    wanted = {"child_identity", "guardians", "ks2_results", "core_assessments",
              "attendance_summary", "support_indicators", "send_provision",
              "current_interventions", "medical_requirements", "transition_report"}
    assert set(rec) == wanted
    assert wanted <= set(handover.PRIMARY_TO_SECONDARY.field_keys())


def test_export_assessment_sections_follow_the_contract():
    from education_system.systems.primary.domain.assessment import assessment
    from education_system.systems.primary.domain.assessment.ks2_sats import ks2_sats
    from education_system.systems.primary.domain.assessment.mtc import mtc
    from education_system.systems.primary.domain.assessment.phonics_screening import (
        phonics_screening,
    )
    p = _pupil(date_of_birth="2015-03-03")
    for subject, score, outcome in (("Reading", 108, "EXS"), ("Maths", 112, "GDS"),
                                    ("EGPS", 99, "WTS")):
        ks2_sats.create({"pupil_id": p.pupil_id, "academic_year": "2026-27",
                         "subject": subject, "scaled_score": score, "outcome": outcome})
    ks2_sats.create({"pupil_id": p.pupil_id, "academic_year": "2026-27",
                     "subject": "Science", "outcome": "EXS"})
    mtc.create({"pupil_id": p.pupil_id, "academic_year": "2024-25", "score": 23})
    phonics_screening.create({"pupil_id": p.pupil_id, "academic_year": "2020-21",
                              "attempt": 1, "score": 30})
    assessment.create({"pupil_id": p.pupil_id, "academic_year": "2026-27", "term": "Autumn",
                       "subject": "Writing", "grade": "WTS"})
    assessment.create({"pupil_id": p.pupil_id, "academic_year": "2026-27", "term": "Spring",
                       "subject": "Writing", "grade": "EXS"})
    rec = ADAPTER.export_handover(p.pupil_id).record
    ks2 = rec["ks2_results"]
    assert (ks2["academic_year"], ks2["reading_scaled"], ks2["maths_scaled"],
            ks2["gps_scaled"]) == ("2026-27", 108, 112, 99)
    assert (ks2["reading_outcome"], ks2["maths_outcome"], ks2["gps_outcome"]) == (
        "EXS", "GDS", "WTS")
    assert ks2["writing_ta"] == "EXS" and ks2["science_ta"] == "EXS"
    assert ks2["mtc_score"] == 23 and ks2["phonics_passed"] is False
    latest = rec["core_assessments"]["latest"]
    assert [(r["subject"], r["grade"]) for r in latest] == [("Writing", "EXS")]


def test_export_support_send_interventions_medical_and_contacts():
    from education_system.systems.primary.domain.assessment.intervention_tracking import (
        intervention_tracking,
    )
    from education_system.systems.primary.domain.finance.pupil_premium import pupil_premium
    from education_system.systems.primary.domain.learners.pupils import year6_transition
    from education_system.systems.primary.domain.operations.communications.parent_contacts import (
        parent_contacts,
    )
    from education_system.systems.primary.domain.pastoral.health.medical_records import (
        medical_records,
    )
    from education_system.systems.primary.domain.pastoral.send import send
    p = _pupil(date_of_birth="2015-03-03", parent_name="Mum", parent_phone="01234 567890")
    slash = year6_transition._slash_year(year6_transition.current_academic_year())
    pupil_premium.upsert({"pupil_id": p.pupil_id, "academic_year": slash,
                          "category": "LAC (Looked-after child)", "status": "Eligible",
                          "start_date": "2026-09-01"})
    send.upsert({"pupil_id": p.pupil_id, "academic_year": slash,
                 "provision_stage": "EHCP (Education, Health, Care Plan)",
                 "primary_need": "Communication and interaction", "status": "Active",
                 "start_date": "2026-09-01", "next_review_date": "2027-01-10"})
    intervention_tracking.create({"pupil_id": p.pupil_id, "intervention_type": "Small group",
                                  "goal": "Fractions", "start_date": "2026-09-10",
                                  "status": "Active"})
    intervention_tracking.create({"pupil_id": p.pupil_id, "intervention_type": "Tutoring",
                                  "start_date": "2026-01-10", "status": "Complete"})
    medical_records.create({"pupil_id": p.pupil_id, "record_type": "allergy",
                            "title": "Peanuts", "severity": "critical",
                            "action_plan": "Epipen in office"})
    parent_contacts.create_contact({"student_id": p.pupil_id, "relationship": "Mother",
                                    "first_name": "Ann", "last_name": "Ng",
                                    "email": "ann@example.com", "primary_phone": "01234 567890",
                                    "has_parental_responsibility": True})
    parent_contacts.create_contact({"student_id": p.pupil_id, "relationship": "Social Worker",
                                    "first_name": "Sam", "last_name": "Case",
                                    "primary_phone": "01234 000000"})
    rec = ADAPTER.export_handover(p.pupil_id).record
    assert rec["support_indicators"]["pupil_premium"] is True
    assert rec["support_indicators"]["lac"] is True
    send_out = rec["send_provision"]
    assert send_out["sen_status"] == "E" and send_out["ehcp"] is True
    assert send_out["primary_need"] == "Communication and interaction"
    assert send_out["plan_review_date"] == "2027-01-10"
    assert [i["name"] for i in rec["current_interventions"]] == ["Small group: Fractions"]
    assert rec["medical_requirements"]["conditions"] == [
        {"type": "allergy", "name": "Peanuts", "severity": "critical",
         "care_plan": "Epipen in office"}]
    # Family only: a social worker never travels as a guardian.
    assert [g["name"] for g in rec["guardians"]] == ["Ann Ng"]
    assert rec["guardians"][0]["parental_responsibility"] is True


def test_export_unknown_pupil_is_refused():
    with pytest.raises(AdapterError, match="No primary pupil P0000000"):
        ADAPTER.export_handover("P0000000")


# ── close_enrolment / leaver_id_for ──────────────────────────────────

def test_close_writes_the_leaver_and_keeps_the_pupil_off_roll():
    p = _pupil(date_of_birth="2014-03-03", parent_phone="01234 567890")
    assert CA.leaver_id_for(p.pupil_id) is None
    ADAPTER.close_enrolment(p.pupil_id, "Moved to secondary school", end_date="2027-07-21",
                            destination="Hill Academy", current_email="ben@hill.example",
                            notes="Good luck")
    lid = CA.leaver_id_for(p.pupil_id)
    rec = LV.get_leaver(lid)
    assert rec.pupil_id == p.pupil_id and rec.year_left == "6"
    assert rec.leaving_date == "2027-07-21" and rec.destination_school == "Hill Academy"
    assert rec.current_email == "ben@hill.example" and rec.notes == "Good luck"
    assert rec.reason == "Moved to secondary school" and rec.status == "active"
    assert rec.parent_phone == "01234 567890"
    got = P.get_pupil(p.pupil_id)
    assert got.roll_status == "left" and got.left_date == "2027-07-21"
    assert got.exit_reason == "Moved to secondary school"


def test_close_twice_writes_one_leaver():
    p = _pupil()
    ADAPTER.close_enrolment(p.pupil_id, "Moved", end_date="2027-07-21")
    ADAPTER.close_enrolment(p.pupil_id, "Again", end_date="2027-08-01")
    assert len(LV.list_leavers()) == 1
    assert P.get_pupil(p.pupil_id).exit_reason == "Moved"


def test_close_reuses_an_existing_leaver_entry():
    p = _pupil()
    existing = LV.create_leaver({"pupil_id": p.pupil_id, "first_name": "Ben",
                                 "last_name": "Ng", "year_left": "6"})
    ADAPTER.close_enrolment(p.pupil_id, "Moved", end_date="2027-07-21")
    assert [r.leaver_id for r in LV.list_leavers()] == [existing.leaver_id]
    assert P.get_pupil(p.pupil_id).roll_status == "left"


def test_close_unknown_pupil_is_a_quiet_no_op():
    ADAPTER.close_enrolment("P0000000", "Moved")
    assert LV.list_leavers() == []
