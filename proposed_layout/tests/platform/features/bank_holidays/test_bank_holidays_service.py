"""Tests for the shared BankHolidayService."""

import pytest


@pytest.fixture
def svc(tmp_path):
    from education_system.platform.features.bank_holidays.service import BankHolidayService
    return BankHolidayService(db_path=str(tmp_path / "bank_holidays.db"))


class TestSeed:
    def test_seed_populates_2026_easter_monday(self, svc):
        assert svc.is_holiday("2026-04-06") is True

    def test_seed_does_not_mark_random_weekday(self, svc):
        # Tue 7 Apr 2026 is not a holiday.
        assert svc.is_holiday("2026-04-07") is False

    def test_list_for_2026_returns_eight(self, svc):
        rows = svc.list_holidays(year=2026)
        assert len(rows) == 8


class TestRanges:
    def test_holidays_in_easter_window(self, svc):
        rows = svc.holidays_in_range("2026-04-01", "2026-04-30")
        names = {r["name"] for r in rows}
        assert "Good Friday" in names
        assert "Easter Monday" in names

    def test_working_days_excludes_holidays(self, svc):
        # Mon 6 Apr 2026 (Easter Monday) → Fri 10 Apr 2026
        # 5 weekdays minus 1 bank holiday = 4
        assert svc.working_days_in_range("2026-04-06", "2026-04-10") == 4


class TestMutations:
    def test_add_and_remove_custom_holiday(self, svc):
        row = svc.add_holiday("2026-07-04", "Local closure")
        assert row["holiday_date"] == "2026-07-04"
        assert svc.is_holiday("2026-07-04") is True
        ok = svc.remove_holiday(row["id"])
        assert ok is True
        assert svc.is_holiday("2026-07-04") is False

    def test_add_holiday_is_idempotent(self, svc):
        svc.add_holiday("2026-07-04", "Local closure")
        svc.add_holiday("2026-07-04", "Local closure")
        # Still only one row for that (date, region) pair.
        rows = [r for r in svc.list_holidays(year=2026) if r["holiday_date"] == "2026-07-04"]
        assert len(rows) == 1
