"""Tests for RecruitmentService."""

import pytest


class TestRecruitmentService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.recruitment.services.recruitment_service import RecruitmentService
        return RecruitmentService(db_path)

    @pytest.fixture
    def sample_vacancy(self, service):
        return service.create_vacancy(
            job_title="Maths Teacher",
            department="Mathematics",
            contract_type="permanent",
            salary_range="30000-40000",
            closing_date="2026-05-31",
        )

    def test_create_vacancy(self, service):
        vacancy = service.create_vacancy(
            job_title="English Teacher",
            department="English", hours="full-time",
        )
        assert vacancy is not None

    def test_list_vacancies(self, service):
        service.create_vacancy(job_title="Science Teacher")
        service.create_vacancy(job_title="Art Teacher")
        vacancies = service.list_vacancies()
        assert len(vacancies) >= 2

    def test_get_vacancy(self, service, sample_vacancy):
        vid = sample_vacancy if isinstance(sample_vacancy, int) else sample_vacancy.get("id", sample_vacancy)
        found = service.get_vacancy(vid)
        assert found is not None

    def test_update_vacancy(self, service, sample_vacancy):
        vid = sample_vacancy if isinstance(sample_vacancy, int) else sample_vacancy.get("id", sample_vacancy)
        result = service.update_vacancy(vid, salary_range="32000-42000")
        assert result is not None

    def test_delete_vacancy(self, service, sample_vacancy):
        vid = sample_vacancy if isinstance(sample_vacancy, int) else sample_vacancy.get("id", sample_vacancy)
        result = service.delete_vacancy(vid)
        assert result is True or result is None

    def test_publish_vacancy(self, service, sample_vacancy):
        vid = sample_vacancy if isinstance(sample_vacancy, int) else sample_vacancy.get("id", sample_vacancy)
        result = service.publish_vacancy(vid)
        assert result is not None

    def test_create_application(self, service, sample_vacancy):
        vid = sample_vacancy if isinstance(sample_vacancy, int) else sample_vacancy.get("id", sample_vacancy)
        app = service.create_application(
            vacancy_id=vid,
            applicant_name="Jane Smith",
            email="jane@example.com",
        )
        assert app is not None

    def test_list_applications(self, service, sample_vacancy):
        vid = sample_vacancy if isinstance(sample_vacancy, int) else sample_vacancy.get("id", sample_vacancy)
        service.create_application(vid, "Applicant A")
        apps = service.list_applications(vacancy_id=vid)
        assert len(apps) >= 1

    def test_shortlist_application(self, service, sample_vacancy):
        vid = sample_vacancy if isinstance(sample_vacancy, int) else sample_vacancy.get("id", sample_vacancy)
        app = service.create_application(vid, "Shortlist Me")
        aid = app if isinstance(app, int) else app.get("id", app)
        result = service.shortlist_application(aid)
        assert result is not None

    def test_schedule_interview(self, service, sample_vacancy):
        vid = sample_vacancy if isinstance(sample_vacancy, int) else sample_vacancy.get("id", sample_vacancy)
        app = service.create_application(vid, "Interview Me")
        aid = app if isinstance(app, int) else app.get("id", app)
        result = service.schedule_interview(aid, interview_date="2026-06-10")
        assert result is not None

    def test_make_offer(self, service, sample_vacancy):
        vid = sample_vacancy if isinstance(sample_vacancy, int) else sample_vacancy.get("id", sample_vacancy)
        app = service.create_application(vid, "Offer Me")
        aid = app if isinstance(app, int) else app.get("id", app)
        result = service.make_offer(aid)
        assert result is not None

    def test_get_stats(self, service):
        stats = service.get_stats()
        assert stats is not None
