"""Tests for the ClearingAdjustmentService.

Runs against the autouse isolated DB. The service creates its own tables in
``__init__`` via ``transaction()`` which uses the patched DEFAULT_DB_PATH.
"""

import pytest

from education_system.systems.university.domain.admissions.clearing_adjustment.services.clearing_adjustment_service import (
    ClearingAdjustmentService,
)


@pytest.fixture()
def service():
    return ClearingAdjustmentService()


class TestVacancies:
    def test_add_and_list(self, service):
        vid = service.add_vacancy("CS101", "Computer Science", department="CS",
                                  available_places=5, minimum_tariff=96)
        assert vid > 0
        vacancies = service.list_vacancies()
        assert len(vacancies) == 1
        assert vacancies[0]["course_code"] == "CS101"

    def test_list_active_only_hides_full(self, service):
        service.add_vacancy("A", "Course A", available_places=0)
        service.add_vacancy("B", "Course B", available_places=3)
        assert len(service.list_vacancies(active_only=True)) == 1
        assert len(service.list_vacancies(active_only=False)) == 2

    def test_available_courses_respects_tariff(self, service):
        service.add_vacancy("HARD", "Hard", available_places=2, minimum_tariff=144)
        service.add_vacancy("EASY", "Easy", available_places=2, minimum_tariff=80)
        matches = service.get_available_courses(min_tariff=96)
        codes = [m["course_code"] for m in matches]
        assert "EASY" in codes
        assert "HARD" not in codes

    def test_update_vacancy(self, service):
        vid = service.add_vacancy("X", "Course X", available_places=1)
        assert service.update_vacancy(vid, available_places=10) is True
        assert service.list_vacancies()[0]["available_places"] == 10

    def test_update_vacancy_no_kwargs(self, service):
        vid = service.add_vacancy("X", "Course X")
        assert service.update_vacancy(vid) is False


class TestApplications:
    def test_submit_and_get(self, service):
        aid = service.submit_clearing_application("Jane Doe", email="j@x.com",
                                                  tariff_points=120,
                                                  preferred_course="CS101")
        app = service.get_application(aid)
        assert app["applicant_name"] == "Jane Doe"
        assert app["status"] == "pending"

    def test_update_status_decrements_places(self, service):
        service.add_vacancy("CS101", "Computer Science", available_places=2)
        aid = service.submit_clearing_application("Jane", preferred_course="CS101")
        assert service.update_application_status(aid, "accepted", "admin") is True
        assert service.get_application(aid)["status"] == "accepted"
        vac = service.list_vacancies(active_only=False)[0]
        assert vac["available_places"] == 1

    def test_auto_shortlist(self, service):
        service.add_vacancy("CS101", "Computer Science", available_places=5,
                            minimum_tariff=96)
        service.submit_clearing_application("Qualified", tariff_points=120,
                                            preferred_course="CS101")
        service.submit_clearing_application("Underqualified", tariff_points=40,
                                            preferred_course="CS101")
        shortlisted = service.auto_shortlist()
        assert len(shortlisted) == 1
        assert shortlisted[0]["applicant_name"] == "Qualified"

    def test_list_applications_by_status(self, service):
        service.submit_clearing_application("A")
        service.submit_clearing_application("B")
        assert len(service.list_applications(status="pending")) == 2
        assert len(service.list_applications(status="accepted")) == 0


class TestAdjustments:
    def test_submit_and_process(self, service):
        rid = service.submit_adjustment_request("STU1", "CS101", "CS201",
                                                reason="Better grades")
        assert rid > 0
        assert service.process_adjustment(rid, "approved", "admin") is True
        rows = service.list_adjustment_requests(status="approved")
        assert len(rows) == 1


class TestStatistics:
    def test_statistics(self, service):
        service.add_vacancy("CS101", "CS", available_places=4)
        service.submit_clearing_application("A")
        service.submit_clearing_application("B")
        stats = service.get_clearing_statistics()
        assert stats["total_applications"] == 2
        assert stats["by_status"]["pending"] == 2
        assert stats["total_places_remaining"] == 4

    def test_gui_alias_shapes(self, service):
        service.add_vacancy("CS101", "Computer Science", available_places=4)
        gv = service.get_vacancies()
        assert gv[0]["course"] == "Computer Science"
        assert gv[0]["places"] == 4
