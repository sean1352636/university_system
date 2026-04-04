"""Tests for StaffAbsenceService."""

import pytest


class TestStaffAbsenceService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.staff_absence.services.staff_absence_service import StaffAbsenceService
        return StaffAbsenceService(db_path)

    def test_create_absence(self, service):
        absence = service.create_absence(
            staff_id=1, start_date="2026-04-10",
            absence_type="sick", reason="Flu",
        )
        assert absence is not None

    def test_list_absences(self, service):
        service.create_absence(staff_id=1, start_date="2026-04-10")
        service.create_absence(staff_id=2, start_date="2026-04-11")
        absences = service.list_absences()
        assert len(absences) >= 2

    def test_get_absence(self, service):
        absence = service.create_absence(staff_id=1, start_date="2026-04-10")
        aid = absence if isinstance(absence, int) else absence.get("id", absence)
        found = service.get_absence(aid)
        assert found is not None

    def test_update_absence(self, service):
        absence = service.create_absence(staff_id=1, start_date="2026-04-10")
        aid = absence if isinstance(absence, int) else absence.get("id", absence)
        updated = service.update_absence(aid, reason="COVID")
        assert updated is not None

    def test_delete_absence(self, service):
        absence = service.create_absence(staff_id=1, start_date="2026-04-10")
        aid = absence if isinstance(absence, int) else absence.get("id", absence)
        result = service.delete_absence(aid)
        assert result is True or result is None

    def test_close_absence(self, service):
        absence = service.create_absence(staff_id=1, start_date="2026-04-10")
        aid = absence if isinstance(absence, int) else absence.get("id", absence)
        result = service.close_absence(
            aid, end_date="2026-04-14", days_lost=3,
            rtw_notes="Fit to return",
        )
        assert result is not None

    def test_create_trigger(self, service):
        trigger = service.create_trigger(
            trigger_name="Bradford Factor",
            threshold=200,
        )
        assert trigger is not None

    def test_list_triggers(self, service):
        service.create_trigger("Trigger A", 100)
        triggers = service.list_triggers()
        assert len(triggers) >= 1

    def test_check_triggers(self, service):
        result = service.check_triggers(staff_id=1)
        assert isinstance(result, list)

    def test_get_stats(self, service):
        stats = service.get_stats()
        assert stats is not None
