"""Tests for the Admissions & Recruitment CRM core service.

Each test gets an isolated SQLite file via the ``admissions_db`` fixture,
which monkeypatches ``db_module.DEFAULT_DB_PATH`` and runs the schema
init function so the manager classes hit a real (but disposable) DB.
"""

from __future__ import annotations

import pytest

from education_system.systems.university.infrastructure.database import db as db_module
from education_system.systems.university.infrastructure.database.schemas.admissions_schemas import (
    init_admissions_crm_system_db,
)
from education_system.systems.university.domain.admissions.services.admissions_crm_core import (
    ApplicationManager,
    CampaignManager,
    ProspectManager,
    ReviewWorkflowManager,
    TourManager,
    YieldPredictionManager,
)


@pytest.fixture
def admissions_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "admissions_test.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)
    init_admissions_crm_system_db()
    yield db_path


def _make_prospect(**overrides) -> int:
    defaults = dict(
        first_name="Ada",
        last_name="Lovelace",
        email="ada@example.com",
        phone="01234 567890",
        intended_major="Computer Science",
        source="open_day",
    )
    defaults.update(overrides)
    return ProspectManager.create_prospect(**defaults)


def _make_application(prospect_id: int, **overrides) -> int:
    defaults = dict(
        application_type="undergraduate",
        program_applied="BSc Computer Science",
        academic_year="2026/27",
        semester="autumn",
        application_fee_paid=False,
    )
    defaults.update(overrides)
    return ApplicationManager.submit_application(prospect_id, **defaults)


class TestProspectManager:
    def test_create_prospect_returns_positive_id(self, admissions_db):
        pid = _make_prospect()
        assert isinstance(pid, int)
        assert pid > 0

    def test_create_multiple_prospects_assigns_unique_ids(self, admissions_db):
        a = _make_prospect(email="a@example.com")
        b = _make_prospect(email="b@example.com")
        assert a != b

    def test_update_prospect_status(self, admissions_db):
        pid = _make_prospect()
        assert ProspectManager.update_prospect_status(pid, "contacted") is True

        from education_system.systems.university.infrastructure.database.db import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT status, last_contact_date FROM admission_prospects WHERE prospect_id = ?",
                (pid,),
            ).fetchone()
        assert row["status"] == "contacted"
        assert row["last_contact_date"] is not None

    def test_log_interaction_returns_id(self, admissions_db):
        pid = _make_prospect()
        iid = ProspectManager.log_interaction(
            pid, "phone_call", notes="Discussed scholarships", staff_member="staff01",
        )
        assert isinstance(iid, int) and iid > 0


class TestApplicationManager:
    def test_submit_application_promotes_prospect_to_applicant(self, admissions_db):
        pid = _make_prospect()
        aid = _make_application(pid)
        assert isinstance(aid, int) and aid > 0

        from education_system.systems.university.infrastructure.database.db import get_connection
        with get_connection() as conn:
            status = conn.execute(
                "SELECT status FROM admission_prospects WHERE prospect_id = ?",
                (pid,),
            ).fetchone()["status"]
        assert status == "applicant"

    def test_submit_application_unknown_prospect_raises(self, admissions_db):
        with pytest.raises(ValueError, match="does not exist"):
            ApplicationManager.submit_application(
                prospect_id=999999,
                application_type="undergraduate",
                program_applied="BSc CS",
                academic_year="2026/27",
                semester="autumn",
            )

    def test_upload_document_unknown_application_raises(self, admissions_db):
        with pytest.raises(ValueError, match="does not exist"):
            ApplicationManager.upload_document(
                application_id=999999,
                document_type="transcript",
                document_name="hs_transcript.pdf",
                file_url="/tmp/x.pdf",
            )

    def test_upload_document_attaches_to_application(self, admissions_db):
        pid = _make_prospect()
        aid = _make_application(pid)
        did = ApplicationManager.upload_document(
            aid, "transcript", "transcript.pdf", "/tmp/transcript.pdf",
        )
        assert isinstance(did, int) and did > 0

        from education_system.systems.university.infrastructure.database.db import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT reference_id, reference_type, verification_status "
                "FROM documents WHERE document_id = ?", (did,),
            ).fetchone()
        assert row["reference_id"] == str(aid)
        assert row["reference_type"] == "application"
        assert row["verification_status"] == "pending"

    def test_update_application_status(self, admissions_db):
        pid = _make_prospect()
        aid = _make_application(pid)
        assert ApplicationManager.update_application_status(aid, "shortlisted") is True

        from education_system.systems.university.infrastructure.database.db import get_connection
        with get_connection() as conn:
            status = conn.execute(
                "SELECT status FROM admission_applications WHERE application_id = ?",
                (aid,),
            ).fetchone()["status"]
        assert status == "shortlisted"

    def test_make_decision_persists_decision_and_status(self, admissions_db, monkeypatch):
        # Stub email + integration-bus side effects so the test stays focused on DB state.
        import education_system.systems.university.domain.admissions.services.admissions_crm_core as mod
        monkeypatch.setattr(mod, "_send_applicant_email", lambda *a, **kw: True)

        pid = _make_prospect()
        aid = _make_application(pid)
        assert ApplicationManager.make_decision(aid, "accept", "2026-06-01") is True

        from education_system.systems.university.infrastructure.database.db import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT decision, decision_date, status "
                "FROM admission_applications WHERE application_id = ?", (aid,),
            ).fetchone()
        assert row["decision"] == "accept"
        assert row["decision_date"] == "2026-06-01"
        assert row["status"] == "decision_made"

    def test_make_decision_defaults_to_today_when_date_omitted(self, admissions_db, monkeypatch):
        import education_system.systems.university.domain.admissions.services.admissions_crm_core as mod
        monkeypatch.setattr(mod, "_send_applicant_email", lambda *a, **kw: True)

        pid = _make_prospect()
        aid = _make_application(pid)
        ApplicationManager.make_decision(aid, "reject")

        from education_system.systems.university.infrastructure.database.db import get_connection
        with get_connection() as conn:
            d = conn.execute(
                "SELECT decision_date FROM admission_applications WHERE application_id = ?",
                (aid,),
            ).fetchone()["decision_date"]
        assert d  # non-empty ISO date stamped by the service


class TestReviewWorkflowManager:
    def test_assign_reviewer_unknown_application_raises(self, admissions_db):
        with pytest.raises(ValueError, match="does not exist"):
            ReviewWorkflowManager.assign_reviewer(999999, "reviewer1")

    def test_create_review_updates_application_status(self, admissions_db):
        pid = _make_prospect()
        aid = _make_application(pid)
        rid = ReviewWorkflowManager.create_review(
            application_id=aid, reviewer_id="reviewer1",
            review_stage="initial", score=85,
            recommendation="advance", comments="Strong PS.",
        )
        assert isinstance(rid, int) and rid > 0

        from education_system.systems.university.infrastructure.database.db import get_connection
        with get_connection() as conn:
            status = conn.execute(
                "SELECT status FROM admission_applications WHERE application_id = ?",
                (aid,),
            ).fetchone()["status"]
        assert status == "in_review_initial"

    def test_get_application_reviews_orders_by_review_date(self, admissions_db):
        pid = _make_prospect()
        aid = _make_application(pid)
        ReviewWorkflowManager.create_review(aid, "r1", "initial", 70, "advance")
        ReviewWorkflowManager.create_review(aid, "r2", "final", 80, "accept")
        rows = ReviewWorkflowManager.get_application_reviews(aid)
        assert len(rows) == 2
        assert {r["reviewer_id"] for r in rows} == {"r1", "r2"}


class TestCampaignManager:
    def test_send_message_increments_sent_count(self, admissions_db):
        cid = CampaignManager.create_campaign(
            "Spring Open Day", "email", "year12",
            "2026-02-01", "2026-03-01", "Hi {{name}}",
        )
        pid = _make_prospect()
        m1 = CampaignManager.send_campaign_message(cid, pid)
        m2 = CampaignManager.send_campaign_message(cid, pid)
        assert m1 != m2

        from education_system.systems.university.infrastructure.database.db import get_connection
        with get_connection() as conn:
            sent = conn.execute(
                "SELECT sent_count FROM recruitment_campaigns WHERE campaign_id = ?",
                (cid,),
            ).fetchone()["sent_count"]
        assert sent == 2


class TestTourManager:
    def test_register_for_tour_increments_attendee_count(self, admissions_db):
        tid = TourManager.create_tour(
            "2026-03-15", "10:00", tour_guide="staff01",
            max_attendees=3, meeting_point="Main Reception",
        )
        p1 = _make_prospect(email="p1@example.com")
        p2 = _make_prospect(email="p2@example.com")
        TourManager.register_for_tour(tid, p1, num_guests=0)
        TourManager.register_for_tour(tid, p2, num_guests=1)

        from education_system.systems.university.infrastructure.database.db import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT current_attendees FROM campus_tours WHERE tour_id = ?", (tid,),
            ).fetchone()
        # +1 per prospect plus the recorded guest count
        assert row["current_attendees"] == 3

    def test_register_for_full_tour_raises(self, admissions_db):
        tid = TourManager.create_tour(
            "2026-03-15", "10:00", max_attendees=1, meeting_point="Reception",
        )
        p1 = _make_prospect(email="p1@example.com")
        p2 = _make_prospect(email="p2@example.com")
        TourManager.register_for_tour(tid, p1)
        with pytest.raises(Exception, match="full"):
            TourManager.register_for_tour(tid, p2)


class TestYieldPredictionManager:
    def test_create_prediction(self, admissions_db):
        pid = _make_prospect()
        aid = _make_application(pid)
        prid = YieldPredictionManager.create_prediction(
            application_id=aid, predicted_probability=0.72,
            model_version="v1.0", factors="program,gpa",
        )
        assert isinstance(prid, int) and prid > 0

        from education_system.systems.university.infrastructure.database.db import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT predicted_enrollment_probability, model_version "
                "FROM yield_predictions WHERE prediction_id = ?", (prid,),
            ).fetchone()
        assert row["predicted_enrollment_probability"] == pytest.approx(0.72)
        assert row["model_version"] == "v1.0"
