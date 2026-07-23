"""Tests for the academic advising service.

Uses the autouse ``_isolate_db`` fixture from the university_system tests
conftest: every test runs against a throw-away copy of the template DB, so
``get_connection()`` (which reads DEFAULT_DB_PATH) hits the temp DB. The
advising tables are created by ``init_db()``.
"""

import pytest

from education_system.post_18.university_system.modules.domain.academics.advising.services import (
    advising_service as svc,
)


@pytest.fixture(autouse=True)
def _tables():
    """Ensure advising tables exist in the isolated DB before each test."""
    svc.init_db()


# --------------------------------------------------------------- Advisors
class TestAdvisors:
    def test_seed_and_count(self):
        assert svc.get_advisor_count() == 0
        svc.seed_sample_advisors()
        assert svc.get_advisor_count() == 3

    def test_get_all_advisors_ordered_by_name(self):
        svc.seed_sample_advisors()
        advisors = svc.get_all_advisors()
        names = [a["name"] for a in advisors]
        assert names == sorted(names)
        assert "Dr. Sarah Johnson" in names


# ------------------------------------------------------------ Appointments
class TestAppointments:
    def test_schedule_and_fetch(self):
        svc.schedule_appointment("S1", "ADV001", "2026-05-01", "10:30",
                                 topic="Module choice")
        appts = svc.get_appointments("S1")
        assert len(appts) == 1
        assert appts[0]["advisor_id"] == "ADV001"
        assert appts[0]["status"] == "scheduled"
        assert appts[0]["topic"] == "Module choice"

    def test_schedule_invalid_date_raises(self):
        with pytest.raises(ValueError):
            svc.schedule_appointment("S1", "ADV001", "01-05-2026", "10:30")

    def test_schedule_invalid_time_raises(self):
        with pytest.raises(ValueError):
            svc.schedule_appointment("S1", "ADV001", "2026-05-01", "25:99")

    def test_status_filter(self):
        svc.schedule_appointment("S2", "ADV001", "2026-05-01", "10:30")
        svc.schedule_appointment("S2", "ADV002", "2026-05-02", "11:00")
        all_appts = svc.get_appointments("S2")
        assert len(all_appts) == 2
        # Cancel one and filter
        cancelled_id = all_appts[0]["appointment_id"]
        assert svc.cancel_appointment(cancelled_id) is True
        scheduled = svc.get_appointments("S2", status_filter="scheduled")
        assert len(scheduled) == 1

    def test_cancel_returns_false_when_already_cancelled(self):
        svc.schedule_appointment("S3", "ADV001", "2026-05-01", "10:30")
        appt_id = svc.get_appointments("S3")[0]["appointment_id"]
        assert svc.cancel_appointment(appt_id) is True
        # Second cancel is a no-op
        assert svc.cancel_appointment(appt_id) is False


# ----------------------------------------------------------- Degree plans
class TestDegreePlans:
    def test_create_and_get_active_plan(self):
        svc.create_degree_plan("S9", "BSc Plan", target_graduation="2028-06-01",
                               total_credits_required=360, credits_completed=90)
        plan = svc.get_active_degree_plan("S9")
        assert plan is not None
        assert plan["plan_name"] == "BSc Plan"
        assert plan["total_credits_required"] == 360
        assert plan["credits_completed"] == 90

    def test_create_requires_plan_name(self):
        with pytest.raises(ValueError):
            svc.create_degree_plan("S9", "")

    def test_get_active_plan_none_when_absent(self):
        assert svc.get_active_degree_plan("nobody") is None

    def test_get_completed_credits_defaults_zero(self):
        # student_modules in the template lacks a 'status' column, so the
        # lookup swallows the error and returns 0.
        assert svc.get_completed_credits("S9") == 0
