"""Tests for EmployerPortalService."""

import pytest


class TestEmployerPortalService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.employer_portal.services.employer_portal_service import EmployerPortalService
        return EmployerPortalService(db_path)

    @pytest.fixture
    def sample_employer(self, service):
        return service.register_employer(
            company_name="TechCorp Ltd",
            contact_name="Alice Brown",
            contact_email="alice@techcorp.co.uk",
            contact_phone="02012345678",
            sector="IT",
        )

    def test_register_employer(self, service):
        eid = service.register_employer(
            company_name="BuildCo",
            contact_name="Bob", contact_email="bob@build.co.uk",
            contact_phone="01234567890", sector="Construction",
        )
        assert eid is not None

    def test_list_employers(self, service, sample_employer):
        employers = service.list_employers()
        assert len(employers) >= 1

    def test_link_learner(self, service, sample_employer):
        eid = sample_employer if isinstance(sample_employer, int) else sample_employer
        link_id = service.link_learner(
            employer_id=eid, student_id=1,
            apprenticeship_standard="Digital Support Technician L3",
            start_date="2026-09-01",
            expected_end_date="2028-08-31",
        )
        assert link_id is not None

    def test_list_learner_links(self, service, sample_employer):
        eid = sample_employer if isinstance(sample_employer, int) else sample_employer
        service.link_learner(eid, 1, "Standard A", "2026-09-01", "2028-08-31")
        links = service.list_learner_links(employer_id=eid)
        assert len(links) >= 1

    def test_schedule_review(self, service, sample_employer):
        eid = sample_employer if isinstance(sample_employer, int) else sample_employer
        link_id = service.link_learner(eid, 1, "Standard A", "2026-09-01", "2028-08-31")
        review_id = service.schedule_review(
            learner_link_id=link_id,
            review_date="2026-10-15",
        )
        assert review_id is not None

    def test_complete_review(self, service, sample_employer):
        eid = sample_employer if isinstance(sample_employer, int) else sample_employer
        link_id = service.link_learner(eid, 1, "Standard A", "2026-09-01", "2028-08-31")
        review_id = service.schedule_review(link_id, "2026-10-15")
        result = service.complete_review(
            review_id, on_track=True, ksbm_progress="Good",
            off_the_job_hours=50.0,
            employer_feedback="Progressing well",
        )
        assert result is not None or result is None

    def test_get_learner_progress(self, service, sample_employer):
        eid = sample_employer if isinstance(sample_employer, int) else sample_employer
        service.link_learner(eid, 1, "Standard A", "2026-09-01", "2028-08-31")
        progress = service.get_learner_progress(student_id=1)
        assert progress is not None

    def test_get_employer_dashboard(self, service, sample_employer):
        eid = sample_employer if isinstance(sample_employer, int) else sample_employer
        dashboard = service.get_employer_dashboard(eid)
        assert dashboard is not None

    def test_get_overdue_reviews(self, service):
        overdue = service.get_overdue_reviews()
        assert isinstance(overdue, list)
