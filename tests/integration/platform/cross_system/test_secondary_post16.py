from __future__ import annotations

import pytest

from education_system.platform.cross_system import secondary_post16 as post16
from education_system.platform.cross_system.adapters.base import ApplicantResult, ExportResult


class Source:
    def __init__(self):
        self.closed = []

    def export_handover(self, pupil_id, consent=None, *, destination_system=None):
        identity = {"first_name": "Jamie", "last_name": "Singh",
                    "date_of_birth": "2010-03-02", "upn": "UPN1", "uln": "ULN1"}
        return ExportResult(record={
            "student_identity": identity, "learner_identity": identity,
            "contact_details": {"email": "jamie@example.test",
                                "parent_phone": "07000"},
            "send_support": "exam access",
        }, local_student_id=pupil_id)

    def close_enrolment(self, pupil_id, reason, **details):
        self.closed.append((pupil_id, reason))


class Destination:
    def __init__(self, prefix):
        self.prefix = prefix
        self.requests = []

    def create_applicant(self, request):
        self.requests.append(request)
        return ApplicantResult(local_applicant_id=f"{self.prefix}-APP")


def common():
    return {
        "predicted_grades": "English 6; Maths 6",
        "achieved_gcse_results": "English 6; Maths 6",
        "prior_attainment": "English and maths grade 6",
        "careers_intentions": "Digital technology",
        "consent_record": {"reference": "CONSENT-1"},
        "consent": True,
    }


def test_all_three_handover_previews_are_complete(monkeypatch):
    monkeypatch.setattr(post16, "_source_adapter", lambda: Source())
    sixth = post16.preview(
        "Y1", "sixth_form", subjects=["Maths", "Physics", "Computing"], **common())
    college = post16.preview(
        "Y1", "fe_college",
        course_request={"course": "Digital T Level", "level": 3}, **common())
    apprentice = post16.preview(
        "Y1", "apprenticeships",
        intended_programme={"title": "Software Developer", "level": 4},
        eligibility_evidence="right to work checked", **common())

    assert sixth.ready and college.ready and apprentice.ready
    assert sixth.payload["application_details"]["subjects"] == [
        "Maths", "Physics", "Computing"]
    assert college.payload["course_request"]["course"] == "Digital T Level"
    assert apprentice.payload["intended_programme"]["level"] == 4


def test_parallel_applications_do_not_close_secondary(monkeypatch, tmp_path):
    source = Source()
    destinations = {key: Destination(key) for key in post16.DESTINATIONS}
    monkeypatch.setattr(post16, "_source_adapter", lambda: source)
    monkeypatch.setattr(post16, "_destination_adapter", lambda key: destinations[key])
    db_path = str(tmp_path / "auth.db")

    sixth = post16.submit(
        "Y1", "sixth_form", subjects=["Maths", "Physics", "Computing"],
        db_path=db_path, **common())
    college = post16.submit(
        "Y1", "fe_college", course_request={"course": "Digital T Level", "level": 3},
        db_path=db_path, **common())
    apprentice = post16.submit(
        "Y1", "apprenticeships",
        intended_programme={"title": "Software Developer", "level": 4},
        eligibility_evidence="checked", db_path=db_path, **common())

    assert {sixth["destination_system"], college["destination_system"],
            apprentice["destination_system"]} == post16.DESTINATIONS
    assert all(row["stage"] == "Application submitted"
               for row in (sixth, college, apprentice))
    assert source.closed == []


def test_only_one_destination_can_be_confirmed(monkeypatch, tmp_path):
    monkeypatch.setattr(post16, "_source_adapter", lambda: Source())
    monkeypatch.setattr(post16, "_destination_adapter", lambda key: Destination(key))
    db_path = str(tmp_path / "auth.db")
    sixth = post16.submit(
        "Y1", "sixth_form", subjects=["Maths", "Physics", "Computing"],
        db_path=db_path, **common())
    college = post16.submit(
        "Y1", "fe_college", course_request={"course": "Digital T Level", "level": 3},
        db_path=db_path, **common())
    for row in (sixth, college):
        post16.update_status(row["transition_id"], "Conditional offer", db_path=db_path)
        post16.update_status(row["transition_id"], "Offer accepted", db_path=db_path)

    confirmed = post16.confirm_destination(sixth["transition_id"], db_path=db_path)
    assert confirmed["confirmed"] == 1
    with pytest.raises(post16.Post16Error, match="already has a confirmed"):
        post16.confirm_destination(college["transition_id"], db_path=db_path)
