"""Year 11 pupils arriving from the Secondary School (admissions.secondary_handover).

Uses the admissions ``admdb`` fixture (temp sixth form DB, no auth.db) and
also points the sixth form's SQLite log handler at the temp DB. The
platform board is replaced by a recorder.
"""

from __future__ import annotations

import pytest

from education_system.platform.cross_system.adapters.base import HandoverRequest


@pytest.fixture
def board(admdb, monkeypatch):
    from education_system.systems.sixth_form.domain.admissions import secondary_handover as SH
    from education_system.systems.sixth_form.infrastructure import log_store
    monkeypatch.setattr(log_store, "DB_PATH", admdb["path"])
    monkeypatch.setattr(log_store, "_DB_READY", False)
    calls: list[tuple] = []

    class Board:
        @staticmethod
        def destination_update(journey, destination, stage, **kw):
            calls.append((journey, destination, stage, kw.get("local_student_id")))
            return {"stage": stage}
    monkeypatch.setattr(SH, "_board", lambda: Board)
    return calls


def _handover(journey="J-1", sen=True, **identity):
    ident = {"first_name": "Amelia", "middle_names": "Rose", "last_name": "Turner",
             "full_name": "Amelia Rose Turner", "date_of_birth": "2010-05-02",
             "gender": "Female", "upn": None, **identity}
    payload = {
        "student_identity": ident,
        "gcse_results": [
            {"subject": "Maths", "grade": "7", "qualification": "GCSE",
             "exam_board": "AQA", "year": 2026},
            {"subject": "Biology", "grade": "u", "qualification": "IGCSE",
             "exam_board": None, "year": 2026},
            {"subject": "Bad", "grade": "Z", "qualification": "GCSE", "year": 2026},
        ],
        "application_details": {"subjects": [], "personal_statement": "Keen"},
    }
    if sen:
        payload["access_arrangements"] = {
            "sen_status": "E", "sen_status_label": "EHC plan",
            "primary_need": "ASD", "primary_need_label": "Autistic spectrum disorder",
            "secondary_need": "SEMH", "secondary_need_label": "Social, emotional and mental health",
            "ehcp_reference": "EHC-1", "ehcp_issued_on": "2019-03-01",
            "provision": "1:1 TA", "strategies": "Front seat", "exam_access": "25% extra time"}
    return HandoverRequest(journey_id=journey, source_system="secondary",
                           destination_system="sixth_form", payload=payload)


def _as_staff(sign_in):
    from education_system.systems.sixth_form.domain.governance.user_management import access
    return sign_in("adm1", capabilities={access.ADMISSIONS, access.SEND})


def test_receive_creates_an_incomplete_applicant(admdb, board, sign_in):
    from education_system.systems.sixth_form.domain.admissions import admissions as ADM
    from education_system.systems.sixth_form.domain.admissions import entry_requirements as ER
    from education_system.systems.sixth_form.domain.admissions import secondary_handover as SH
    _as_staff(sign_in)
    aid = SH.receive(_handover())
    a = ADM.get_applicant(aid)
    assert (a.first_name, a.last_name, a.dob) == ("Amelia", "Turner", "2010-05-02")
    assert a.status == "Submitted" and a.application_source == "Transfer"
    assert a.email is None and a.lldd and a.ehcp and a.sex == "female"
    gcses = {g.subject: (g.grade, g.kind, g.source) for g in ER.list_gcses(aid)}
    assert gcses == {"Maths": ("7", "GCSE", "Transfer"),
                     "Biology": ("U", "IGCSE", "Transfer")}


def test_sen_text_and_register_fields(admdb, board, sign_in):
    from education_system.systems.sixth_form.domain.admissions import applicant_details as AD
    from education_system.systems.sixth_form.domain.admissions import secondary_handover as SH
    _as_staff(sign_in)
    aid = SH.receive(_handover())
    text = AD.sensitive_for_conversion(aid)["send"]
    assert "Primary need: ASD - Autistic spectrum disorder" in text
    assert "EHC plan: EHC-1, issued 2019-03-01" in text
    assert "Exam access: 25% extra time" in text
    assert SH.register_fields(text) == {
        "register_status": "EHCP", "primary_need": "Communication & Interaction",
        "secondary_need": "Social, Emotional & Mental Health",
        "ehcp_issued_on": "2019-03-01"}
    assert SH.register_fields("free text from a form") == {}


def test_no_sen_without_consent(admdb, board, sign_in):
    from education_system.systems.sixth_form.domain.admissions import admissions as ADM
    from education_system.systems.sixth_form.domain.admissions import applicant_details as AD
    from education_system.systems.sixth_form.domain.admissions import secondary_handover as SH
    _as_staff(sign_in)
    aid = SH.receive(_handover(sen=False))
    assert not (AD.sensitive_for_conversion(aid).get("send") or "")
    assert not ADM.get_applicant(aid).lldd


def test_receive_is_idempotent_and_matches_existing(admdb, board, sign_in,
                                                    applicant_payload):
    from education_system.systems.sixth_form.domain.admissions import admissions as ADM
    from education_system.systems.sixth_form.domain.admissions import secondary_handover as SH
    _as_staff(sign_in)
    aid = SH.receive(_handover("J-1"))
    assert SH.receive(_handover("J-1")) == aid
    existing = ADM.create_applicant(applicant_payload(first_name="Bo", last_name="Lee",
                                                      dob="2010-07-02",
                                                      email="bo@example.com"))
    assert SH.receive(_handover("J-2", first_name="Bo", last_name="Lee",
                                date_of_birth="2010-07-02")) == existing.applicant_id


def test_status_changes_reported_to_the_school(admdb, board, sign_in):
    from education_system.systems.sixth_form.domain.admissions import admissions as ADM
    from education_system.systems.sixth_form.domain.admissions import secondary_handover as SH
    _as_staff(sign_in)
    aid = SH.receive(_handover("J-9"))
    ADM.set_status(aid, "Offer Made")
    assert board[-1] == ("J-9", "sixth_form", "Conditional offer", None)
    assert SH.report_enrolled(aid, "C1234567") is True
    assert board[-1] == ("J-9", "sixth_form", "Enrolled / On Programme", "C1234567")


def test_other_applicants_are_not_reported(admdb, board, sign_in, applicant_payload):
    from education_system.systems.sixth_form.domain.admissions import admissions as ADM
    from education_system.systems.sixth_form.domain.admissions import secondary_handover as SH
    _as_staff(sign_in)
    a = ADM.create_applicant(applicant_payload())
    ADM.set_status(a.applicant_id, "Offer Made")
    assert board == []
    assert SH.report_enrolled(a.applicant_id, "C1") is False


def test_adapter_routes_secondary_handovers(admdb, board, sign_in):
    from education_system.systems.sixth_form.infrastructure.adapters.cross_system_adapter import (
        SixthFormAdapter,
    )
    result = SixthFormAdapter().create_applicant(_handover("J-5"))
    assert result.local_applicant_id.startswith("A")
    from education_system.platform.cross_system.adapters.base import AdapterError
    with pytest.raises(AdapterError, match="convert the applicant"):
        SixthFormAdapter().create_enrolment("J-5")


def _results(journey="J-1", results=(), entries=()):
    return HandoverRequest(journey_id=journey, source_system="secondary",
                           destination_system="sixth_form",
                           payload={"gcse_results": list(results),
                                    "gcse_entries": list(entries)})


def test_results_day_updates_the_applicant(admdb, board, sign_in):
    from education_system.systems.sixth_form.domain.admissions import admissions as ADM
    from education_system.systems.sixth_form.domain.admissions import entry_requirements as ER
    from education_system.systems.sixth_form.domain.admissions import secondary_handover as SH
    _as_staff(sign_in)
    aid = SH.receive(_handover(sen=False))  # Maths 7, Biology U
    notes = len(ADM.list_notes(aid))
    later = _results(results=[
        {"subject": "Maths", "grade": "8", "qualification": "GCSE", "year": 2026},
        {"subject": "English Language", "grade": "6", "qualification": "GCSE"}],
        entries=[{"subject": "Physics", "result": "awaited"},
                 {"subject": "English Language", "result": "under review", "grade": "6"}])
    assert SH.receive_results(later) == aid
    gcses = {g.subject: g.grade for g in ER.list_gcses(aid, result_type="Actual")}
    assert gcses == {"Maths": "8", "English Language": "6"}  # Biology no longer sent
    note = ADM.list_notes(aid)
    assert len(note) == notes + 1
    text = "\n".join(n.body for n in note)
    assert "Maths 7 -> 8" in text and "Biology (U)" in text
    assert "Results awaited: Physics" in text and "under review: English Language (6)" in text
    SH.receive_results(later)  # nothing new: no second note
    assert len(ADM.list_notes(aid)) == notes + 1


def test_results_for_an_unknown_learner_are_refused(admdb, board, sign_in):
    from education_system.systems.sixth_form.domain.admissions import admissions as ADM
    from education_system.systems.sixth_form.domain.admissions import secondary_handover as SH
    _as_staff(sign_in)
    with pytest.raises(ADM.ValidationError):
        SH.receive_results(_results("J-nobody"))


def test_adapter_takes_results_from_the_school_only(admdb, board, sign_in):
    from education_system.platform.cross_system.adapters.base import AdapterNotImplemented
    from education_system.systems.sixth_form.domain.admissions import secondary_handover as SH
    from education_system.systems.sixth_form.infrastructure.adapters.cross_system_adapter import (
        SixthFormAdapter,
    )
    SH.receive(_handover("J-6", sen=False))
    SixthFormAdapter().update_applicant_results(_results("J-6", results=[
        {"subject": "Maths", "grade": "9", "qualification": "GCSE"}]))
    other = HandoverRequest(journey_id="J-6", source_system="fe_college",
                            destination_system="sixth_form", payload={})
    with pytest.raises(AdapterNotImplemented):
        SixthFormAdapter().update_applicant_results(other)


def test_course_eligibility_uses_the_entry_requirements(admdb, board, sign_in):
    from education_system.systems.sixth_form.domain.admissions import entry_requirements as ER
    _as_staff(sign_in)
    ER.set_requirement(ER.GENERAL_PROGRAMME, min_gcse_count=5, min_gcse_grade=4)
    ER.set_requirement("Mathematics", subject_minimums={"Mathematics": 7})
    ER.set_requirement("Physics", subject_minimums={"Mathematics": 6, "Physics": 6})
    results = [{"subject": s, "grade": g, "qualification": "GCSE"} for s, g in (
        ("Mathematics", "6"), ("English Language", "5"), ("Physics", "4"),
        ("History", "6"), ("Biology", "5"))]
    out = {o["course"]: o for o in ER.course_eligibility(
        results, ["Mathematics", "Physics", "History"])}
    assert out["Mathematics"]["outcome"] == "Near miss"  # 6, needed 7
    assert out["Physics"]["outcome"] == "Not met"  # Physics 4, needed 6
    assert out["History"]["outcome"] == "Met"  # only the general minimum
    assert "5 GCSEs at grade 4 or above" in out["History"]["requirements"]
    pending = ER.course_eligibility([], ["History"])[0]
    assert pending["outcome"] == "Pending"
    ER.delete_requirement(ER.GENERAL_PROGRAMME)
    assert ER.course_eligibility([], ["History"])[0] == {
        "course": "History", "outcome": "Met", "requirements": [], "checks": []}


def test_changed_choices_from_the_school(admdb, board, sign_in):
    from education_system.systems.sixth_form.domain.admissions import admissions as ADM
    from education_system.systems.sixth_form.domain.admissions import secondary_handover as SH
    from education_system.systems.sixth_form.infrastructure.adapters.cross_system_adapter import (
        SixthFormAdapter,
    )
    _as_staff(sign_in)
    h = _handover("J-7", sen=False)
    h.payload["application_details"]["subjects"] = ["Mathematics", "Physics", "Chemistry"]
    aid = SH.receive(h)
    assert ADM.get_applicant(aid).subjects[:3] == ["Mathematics", "Physics", "Chemistry"]
    notes = len(ADM.list_notes(aid))
    new = HandoverRequest(journey_id="J-7", source_system="secondary",
                          destination_system="sixth_form", payload={"application_details": {
                              "subjects": ["Biology", "History", "Chemistry"]}})
    SixthFormAdapter().update_applicant_choices(new)
    assert ADM.get_applicant(aid).subjects[:3] == ["Biology", "History", "Chemistry"]
    assert len(ADM.list_notes(aid)) == notes + 1
    assert any("(were Mathematics, Physics, Chemistry)" in n.body
               for n in ADM.list_notes(aid))
    SH.receive_choices(new)  # the same again: no second note
    assert len(ADM.list_notes(aid)) == notes + 1
    options = {o["course"]: o["outcome"] for o in SixthFormAdapter().course_options([])}
    assert "Biology" in options
