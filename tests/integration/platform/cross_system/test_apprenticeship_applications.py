from __future__ import annotations

from education_system.platform.cross_system import apprenticeship_applications as apps
from education_system.platform.cross_system.adapters.base import (
    ApplicantResult,
    EnrolmentResult,
    ExportResult,
)


class SourceAdapter:
    def __init__(self):
        self.closed = []

    def export_handover(self, student_id, consent=None, *, destination_system=None):
        return ExportResult(record={
            "learner_identity": {
                "first_name": "Alex", "last_name": "Morgan",
                "date_of_birth": "2007-05-10", "uln": "1234567890",
            },
            "contact_details": {"email": "alex@example.test", "phone": "07000"},
            "prior_attainment": "English 5; Maths 5",
            "send_support": "extra time",
        }, local_student_id=student_id)

    def close_enrolment(self, student_id, reason, **details):
        self.closed.append((student_id, reason, details))


class DestinationAdapter:
    def __init__(self):
        self.applicants = []
        self.starts = []

    def create_applicant(self, request):
        self.applicants.append(request)
        return ApplicantResult(local_applicant_id="501")

    def create_enrolment(self, journey_id, **details):
        self.starts.append((journey_id, details))
        return EnrolmentResult(local_student_id="501", start_date="2026-09-01")


def _fields():
    return {
        "intended_programme": {
            "programme_id": 12, "reference": "ST0123",
            "title": "Software developer", "level": 4,
        },
        "eligibility_evidence": "right to work checked",
        "careers_record": "software development",
        "consent": True,
    }


def test_preview_shows_exact_consent_filtered_handover(monkeypatch):
    source, destination = SourceAdapter(), DestinationAdapter()
    monkeypatch.setattr(apps, "_adapters", lambda _system: (source, destination))

    result = apps.preview("sixth_form", "SF001", **_fields())

    assert result.ready
    assert result.payload["intended_programme"]["reference"] == "ST0123"
    assert "send_support" in result.included
    assert "safeguarding_reference" in result.withheld_restricted


def test_submit_accept_and_start_keeps_fe_concurrent(monkeypatch, tmp_path):
    source, destination = SourceAdapter(), DestinationAdapter()
    monkeypatch.setattr(apps, "_adapters", lambda _system: (source, destination))
    db_path = str(tmp_path / "auth.db")

    submitted = apps.submit(
        "fe_college", "FE001", reason="Chosen work-based route",
        db_path=db_path, **_fields())
    assert submitted["application_status"] == "Employer required / Offer"
    assert destination.applicants[0].get("intended_programme")["level"] == 4

    accepted = apps.accept_offer(
        submitted["transition_id"], accepted_by="Alex Morgan",
        db_path=db_path, **_fields())
    assert accepted["application_status"] == "Accepted"

    started = apps.start_programme(
        submitted["transition_id"], programme_id=12, employer_id=20,
        db_path=db_path)
    assert started["application_status"] == "On Programme"
    assert destination.starts[0][1]["programme_id"] == 12
    assert source.closed == []


def test_sixth_form_start_closes_source_by_default(monkeypatch, tmp_path):
    source, destination = SourceAdapter(), DestinationAdapter()
    monkeypatch.setattr(apps, "_adapters", lambda _system: (source, destination))
    db_path = str(tmp_path / "auth.db")
    submitted = apps.submit(
        "sixth_form", "SF001", reason="Higher apprenticeship",
        db_path=db_path, **_fields())
    apps.accept_offer(
        submitted["transition_id"], accepted_by="Alex Morgan",
        db_path=db_path, **_fields())

    apps.start_programme(
        submitted["transition_id"], programme_id=12, employer_id=20,
        db_path=db_path)

    assert source.closed[0][0] == "SF001"
