"""Tests for DataExportService."""

import pytest


class TestDataExportService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.data_export.services.data_export_service import DataExportService
        return DataExportService(db_path)

    def test_create_job(self, service):
        job = service.create_job(export_type="student_data")
        assert job is not None
        assert job["export_type"] == "student_data"

    def test_list_jobs(self, service):
        service.create_job(export_type="attendance")
        service.create_job(export_type="grades")
        jobs = service.list_jobs()
        assert len(jobs) >= 2

    def test_list_jobs_filter(self, service):
        service.create_job(export_type="attendance")
        jobs = service.list_jobs(export_type="attendance")
        assert all(j["export_type"] == "attendance" for j in jobs)

    def test_get_job(self, service):
        job = service.create_job(export_type="finance")
        found = service.get_job(job["id"])
        assert found is not None
        assert found["export_type"] == "finance"

    def test_update_job(self, service):
        job = service.create_job(export_type="test")
        updated = service.update_job(job["id"], status="running")
        assert updated["status"] == "running"

    def test_delete_job(self, service):
        job = service.create_job(export_type="temp")
        result = service.delete_job(job["id"])
        assert result is True

    def test_start_job(self, service):
        job = service.create_job(export_type="students")
        started = service.start_job(job["id"])
        assert started["status"] in ("running", "in_progress", "started")

    def test_complete_job(self, service):
        job = service.create_job(export_type="students")
        service.start_job(job["id"])
        completed = service.complete_job(
            job["id"], record_count=100,
            file_path="/tmp/export.csv",
        )
        assert completed["status"] in ("completed", "complete")

    def test_create_template(self, service):
        template = service.create_template(
            template_name="Monthly Attendance",
            export_type="attendance",
        )
        assert template is not None

    def test_list_templates(self, service):
        service.create_template(template_name="T1", export_type="grades")
        templates = service.list_templates()
        assert len(templates) >= 1

    def test_delete_template(self, service):
        template = service.create_template(template_name="Temp", export_type="test")
        result = service.delete_template(template["id"])
        assert result is True

    def test_get_stats(self, service):
        stats = service.get_stats()
        assert stats is not None
