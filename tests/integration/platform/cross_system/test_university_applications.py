from __future__ import annotations

import pytest

from education_system.platform.cross_system import university_applications as apps
from education_system.platform.cross_system.adapters.base import ApplicantResult, ExportResult

#: Distinct people, so a test about two learners is actually about two —
#: the journey registry matches on legal name and date of birth.
PEOPLE = {
    "FE001": ("Sam", "Taylor", "2006-04-02"),
    "FE002": ("Jo", "Patel", "2006-08-11"),
}


class Source:
    def export_handover(self, student_id, consent=None, *, destination_system=None):
        first, last, dob = PEOPLE.get(
            student_id, ("Sam", "Taylor", "2006-04-02"))
        return ExportResult(record={
            "learner_identity": {
                "first_name": first, "last_name": last,
                "date_of_birth": dob, "uln": "1234567890",
            },
            "contact_details": {"email": "sam@example.test", "phone": "07000"},
            "vocational_profile": {"qualification": "T Level Digital", "level": 3},
            "prior_learning": "GCSE English and maths",
            "send_support": "extra time",
        }, local_student_id=student_id)

    def close_enrolment(self, *args, **kwargs):
        pass


class ApprenticeshipSource:
    """An apprenticeship export: no UCAS id, and identity under the key
    APPRENTICESHIPS_TO_UNIVERSITY actually declares."""

    def export_handover(self, student_id, consent=None, *, destination_system=None):
        return ExportResult(record={
            "learner_identity": {
                "first_name": "Alex", "last_name": "Morgan",
                "date_of_birth": "2004-09-15", "uln": "9876543210",
            },
            "contact_details": {"email": "alex@example.test"},
            "standard_completed": {
                "reference": "ST0119", "title": "Software developer",
                "level": 4, "completion_date": "2026-07-31",
            },
            "epa_result": {"grade": "Distinction", "epao": "Example EPAO"},
            "functional_skills": "English and maths level 2",
        }, local_student_id=student_id)

    def close_enrolment(self, *args, **kwargs):
        pass


class University:
    def __init__(self):
        self.requests = []

    def create_applicant(self, request):
        self.requests.append(request)
        return ApplicantResult(local_applicant_id="42")


def fields(ucas_id="1234567890"):
    return {
        "ucas_application": {"ucas_id": ucas_id, "status": "Submitted"},
        "choices": [{"university": "Example University", "course_code": "CS01",
                     "course_name": "Computer Science", "entry_year": "2027"}],
        "handover_consent": {"reference": "CONSENT-1", "recorded_at": "2026-10-01",
                             "recorded_by": "admin1"},
        "predicted_qualifications": "T Level Distinction",
        "academic_reference": "Recommended",
        "consent": True,
    }


def test_fe_preview_normalises_vocational_record(monkeypatch):
    monkeypatch.setattr(apps, "_source_adapter", lambda _system: Source())
    result = apps.preview("fe_college", "FE001", **fields())
    assert result.ready
    assert result.payload["student_identity"]["college_student_id"] == "FE001"
    assert result.payload["qualification_profile"]["qualification"] == "T Level Digital"
    assert result.payload["choices"][0]["course_code"] == "CS01"
    assert "reference" in result.included


def test_submit_creates_applicant_without_enrolling(monkeypatch, tmp_path):
    university = University()
    monkeypatch.setattr(apps, "_source_adapter", lambda _system: Source())
    monkeypatch.setattr(apps, "_university_adapter", lambda: university)
    monkeypatch.setattr(apps, "application_view", lambda row: dict(row))

    result = apps.submit(
        "fe_college", "FE001", db_path=str(tmp_path / "auth.db"), **fields())

    assert result["status"] == "applied"
    assert result["university_application_id"] == "42"
    assert university.requests[0].journey_id
    assert university.requests[0].payload["ucas_application"]["ucas_id"] == "1234567890"


def apprenticeship_fields():
    """An apprentice needs no UCAS id and no choices — that is the point of
    APPRENTICESHIPS_TO_UNIVERSITY."""
    return {
        "handover_consent": {"reference": "CONSENT-2", "recorded_at": "2026-10-01"},
        "consent": True,
    }


def test_apprenticeship_preview_uses_the_learner_identity_key(monkeypatch):
    monkeypatch.setattr(apps, "_source_adapter", lambda _s: ApprenticeshipSource())
    result = apps.preview("apprenticeships", "APP001", **apprenticeship_fields())
    assert result.ready, result.missing_required
    assert "student_identity" not in result.payload
    assert result.payload["learner_identity"]["college_student_id"] == "APP001"
    assert apps.payload_identity(result.payload)["first_name"] == "Alex"


def test_apprenticeship_submit_creates_applicant(monkeypatch, tmp_path):
    university = University()
    monkeypatch.setattr(apps, "_source_adapter", lambda _s: ApprenticeshipSource())
    monkeypatch.setattr(apps, "_university_adapter", lambda: university)
    monkeypatch.setattr(apps, "application_view", lambda row: dict(row))

    result = apps.submit("apprenticeships", "APP001",
                         db_path=str(tmp_path / "auth.db"),
                         **apprenticeship_fields())

    assert result["status"] == "applied"
    assert result["university_application_id"] == "42"
    # The standard, not a UCAS id, is what this route is referenced by.
    assert result["application_reference"] == "ST0119"
    payload = university.requests[0].payload
    assert payload["learner_identity"]["first_name"] == "Alex"
    assert payload["epa_result"]["grade"] == "Distinction"


def test_submit_persists_the_ucas_id_and_choices(monkeypatch, tmp_path):
    """They used to go to the bus only, leaving the row that the university's
    applicant list reads with no course and no reference."""
    from education_system.platform.cross_system import transitions

    monkeypatch.setattr(apps, "_source_adapter", lambda _s: Source())
    monkeypatch.setattr(apps, "_university_adapter", lambda: University())
    monkeypatch.setattr(apps, "application_view", lambda row: dict(row))
    db_path = str(tmp_path / "auth.db")

    result = apps.submit("fe_college", "FE001", db_path=db_path, **fields())

    stored = transitions.get_transition(result["transition_id"], db_path=db_path)
    assert stored["application_reference"] == "1234567890"
    assert stored["choices"][0]["course_code"] == "CS01"
    assert stored["choices"][0]["course_name"] == "Computer Science"


# ---------------------------------------------------------------------------
# The UCAS personal ID
# ---------------------------------------------------------------------------

class TestUcasId:
    @pytest.mark.parametrize("value", ["1234567890", " 1234567890 ",
                                       "12 3456 7890", "123-456-7890"])
    def test_accepts_ten_digits_however_they_are_spaced(self, value):
        assert apps.normalise_ucas_id(value) == "1234567890"

    @pytest.mark.parametrize("value", ["", None, "123", "12345678901",
                                       "12345678AB"])
    def test_rejects_anything_else(self, value):
        with pytest.raises(apps.UniversityApplicationError):
            apps.normalise_ucas_id(value)

    def test_preview_stores_the_normalised_form(self, monkeypatch):
        monkeypatch.setattr(apps, "_source_adapter", lambda _s: Source())
        result = apps.preview("fe_college", "FE001", **fields("12 3456 7890"))
        assert result.payload["ucas_application"]["ucas_id"] == "1234567890"

    def test_one_id_cannot_belong_to_two_learners(self, monkeypatch, tmp_path):
        """The intake tolerates one learner under two references — a college
        correcting a number. Two learners under one is not a correction."""
        monkeypatch.setattr(apps, "_source_adapter", lambda _s: Source())
        monkeypatch.setattr(apps, "_university_adapter", lambda: University())
        monkeypatch.setattr(apps, "application_view",
                            lambda row, app=apps._MISSING: dict(row))
        db_path = str(tmp_path / "auth.db")

        apps.submit("fe_college", "FE001", db_path=db_path, **fields())
        with pytest.raises(apps.UniversityApplicationError, match="different learner"):
            apps.submit("fe_college", "FE002", db_path=db_path, **fields())

    def test_the_same_learner_resubmitting_is_idempotent(self, monkeypatch, tmp_path):
        monkeypatch.setattr(apps, "_source_adapter", lambda _s: Source())
        monkeypatch.setattr(apps, "_university_adapter", lambda: University())
        monkeypatch.setattr(apps, "application_view",
                            lambda row, app=apps._MISSING: dict(row))
        db_path = str(tmp_path / "auth.db")

        first = apps.submit("fe_college", "FE001", db_path=db_path, **fields())
        again = apps.submit("fe_college", "FE001", db_path=db_path, **fields())
        assert again["transition_id"] == first["transition_id"]


# ---------------------------------------------------------------------------
# Consent
# ---------------------------------------------------------------------------

class TestConsentRecord:
    def test_names_who_took_it_and_when(self):
        record = apps.consent_record(recorded_by="admin1", scope=("reference",),
                                     ucas_id="1234567890",
                                     recorded_at="2026-10-01")
        assert record["recorded_by"] == "admin1"
        assert record["recorded_at"] == "2026-10-01"
        assert record["scope"] == ["reference"]
        assert "1234567890" in record["reference"]

    def test_refuses_to_invent_a_recorder(self):
        with pytest.raises(apps.UniversityApplicationError):
            apps.consent_record(recorded_by="")

    def test_preview_rejects_an_undated_consent_record(self, monkeypatch):
        """A reference derived from a UCAS number documents nothing."""
        monkeypatch.setattr(apps, "_source_adapter", lambda _s: Source())
        payload = fields()
        payload["handover_consent"] = {"reference": "UCAS-1234567890"}
        with pytest.raises(apps.UniversityApplicationError, match="when consent"):
            apps.preview("fe_college", "FE001", **payload)

    def test_preview_accepts_a_gdpr_register_record(self, monkeypatch):
        """The sixth form's own consents are dated ``granted_date`` and
        referenced by ``consent_id`` — a real record, another spelling."""
        monkeypatch.setattr(apps, "_source_adapter", lambda _s: Source())
        payload = fields()
        payload["handover_consent"] = {
            "consent_id": "C-9", "purpose": "university_handover",
            "granted_date": "2026-06-01", "source": "gdpr",
        }
        result = apps.preview("fe_college", "FE001", **payload)
        assert result.ready
        assert apps.consent_reference(payload["handover_consent"]) == "C-9"


def test_more_than_five_choices_is_refused(monkeypatch):
    monkeypatch.setattr(apps, "_source_adapter", lambda _s: Source())
    payload = fields()
    payload["choices"] = [{"course_code": f"C{i}"} for i in range(6)]
    with pytest.raises(apps.UniversityApplicationError, match="allows 5 choices"):
        apps.preview("fe_college", "FE001", **payload)


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------

def test_list_batches_the_university_lookup(monkeypatch, tmp_path):
    """One query for the list, not one connection per row — a fresh
    university connection costs about a tenth of a second each."""
    monkeypatch.setattr(apps, "_source_adapter", lambda _s: Source())
    monkeypatch.setattr(apps, "_university_adapter", lambda: University())
    monkeypatch.setattr(apps, "application_view",
                        lambda row, app=apps._MISSING: dict(row))
    db_path = str(tmp_path / "auth.db")
    calls = []
    monkeypatch.setattr(
        apps, "_university_applications",
        lambda journey_ids: (calls.append(list(journey_ids)) or ({}, True)))

    apps.submit("fe_college", "FE001", db_path=db_path, **fields())
    apps.submit("fe_college", "FE002", db_path=db_path,
                **fields("1234567891"))
    rows = apps.list_applications(source_system="fe_college", db_path=db_path)

    assert len(rows) == 2
    # The two submits view their own row; the list views both in one call.
    assert len(calls[-1]) == 2


def test_an_unreadable_university_is_not_reported_as_no_application(
        monkeypatch, tmp_path):
    monkeypatch.setattr(apps, "_source_adapter", lambda _s: Source())
    monkeypatch.setattr(apps, "_university_adapter", lambda: University())
    monkeypatch.setattr(apps, "application_view",
                        lambda row, app=apps._MISSING: dict(row))
    db_path = str(tmp_path / "auth.db")
    monkeypatch.setattr(apps, "_university_applications",
                        lambda journey_ids: ({}, True))
    apps.submit("fe_college", "FE001", db_path=db_path, **fields())

    monkeypatch.setattr(apps, "_university_applications",
                        lambda journey_ids: ({}, False))
    rows = apps.list_applications(db_path=db_path)

    assert rows[0].get("university_status") is None
    assert rows[0]["university_lookup_failed"] is True
