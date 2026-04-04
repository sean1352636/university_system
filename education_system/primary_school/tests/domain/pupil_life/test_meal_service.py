"""Tests for the MealService in the Primary School system."""

import pytest


class TestRecordMeal:
    """Tests for recording meals."""

    def test_record_meal_returns_dict(self, meal_service, sample_pupil):
        """Recording a meal returns a dict with id, pupil_id, and date."""
        result = meal_service.record_meal(
            pupil_id=sample_pupil["pupil_id"], date="2026-04-04", meal_type="hot",
        )
        assert isinstance(result, dict)
        assert result["id"] > 0
        assert result["pupil_id"] == sample_pupil["pupil_id"]
        assert result["date"] == "2026-04-04"

    def test_record_meal_persists(self, meal_service, sample_pupil):
        """A recorded meal can be retrieved via get_meals."""
        meal_service.record_meal(
            pupil_id=sample_pupil["pupil_id"], date="2026-04-04", meal_type="packed",
        )
        meals = meal_service.get_meals(pupil_id=sample_pupil["pupil_id"])
        assert len(meals) == 1
        assert meals[0]["meal_type"] == "packed"

    def test_record_meal_with_choice_and_entitlement(self, meal_service, sample_pupil):
        """Optional fields meal_choice and entitlement persist."""
        meal_service.record_meal(
            pupil_id=sample_pupil["pupil_id"], date="2026-04-04", meal_type="hot",
            meal_choice="Pasta Bolognese", entitlement="FSM",
        )
        meals = meal_service.get_meals(pupil_id=sample_pupil["pupil_id"])
        assert meals[0]["meal_choice"] == "Pasta Bolognese"
        assert meals[0]["entitlement"] == "FSM"

    def test_record_multiple_meals_same_date(self, meal_service, sample_pupil, sample_pupil_ks1):
        """Multiple pupils can have meals recorded on the same date."""
        meal_service.record_meal(
            pupil_id=sample_pupil["pupil_id"], date="2026-04-04", meal_type="hot",
        )
        meal_service.record_meal(
            pupil_id=sample_pupil_ks1["pupil_id"], date="2026-04-04", meal_type="packed",
        )
        meals = meal_service.get_meals(date="2026-04-04")
        assert len(meals) == 2


class TestGetMeals:
    """Tests for retrieving meals."""

    def test_get_meals_empty_db(self, meal_service):
        """Querying an empty database returns an empty list."""
        assert meal_service.get_meals() == []

    def test_get_meals_filter_by_date(self, meal_service, sample_pupil):
        """Filtering by date returns only meals on that date."""
        meal_service.record_meal(pupil_id=sample_pupil["pupil_id"], date="2026-04-04", meal_type="hot")
        meal_service.record_meal(pupil_id=sample_pupil["pupil_id"], date="2026-04-05", meal_type="packed")
        meals = meal_service.get_meals(date="2026-04-04")
        assert len(meals) == 1
        assert meals[0]["date"] == "2026-04-04"

    def test_get_meals_filter_by_type(self, meal_service, sample_pupil):
        """Filtering by meal_type returns only matching records."""
        meal_service.record_meal(pupil_id=sample_pupil["pupil_id"], date="2026-04-04", meal_type="hot")
        meal_service.record_meal(pupil_id=sample_pupil["pupil_id"], date="2026-04-05", meal_type="packed")
        meals = meal_service.get_meals(meal_type="hot")
        assert len(meals) == 1
        assert meals[0]["meal_type"] == "hot"


class TestUpdateMeal:
    """Tests for updating meals."""

    def test_update_meal_type(self, meal_service, sample_pupil):
        """Updating a meal type persists the change."""
        result = meal_service.record_meal(
            pupil_id=sample_pupil["pupil_id"], date="2026-04-04", meal_type="hot",
        )
        updated = meal_service.update_meal(result["id"], meal_type="packed")
        assert updated["meal_type"] == "packed"

    def test_update_with_no_valid_fields(self, meal_service, sample_pupil):
        """Passing no recognised fields returns None."""
        result = meal_service.record_meal(
            pupil_id=sample_pupil["pupil_id"], date="2026-04-04", meal_type="hot",
        )
        assert meal_service.update_meal(result["id"], bogus="val") is None

    def test_update_entitlement(self, meal_service, sample_pupil):
        """Updating entitlement persists the change."""
        result = meal_service.record_meal(
            pupil_id=sample_pupil["pupil_id"], date="2026-04-04", meal_type="hot",
        )
        updated = meal_service.update_meal(result["id"], entitlement="UIFSM")
        assert updated["entitlement"] == "UIFSM"


class TestGetDailySummary:
    """Tests for daily meal summaries."""

    def test_daily_summary_empty(self, meal_service):
        """A day with no meals returns an empty summary."""
        assert meal_service.get_daily_summary("2026-04-04") == []

    def test_daily_summary_counts(self, meal_service, sample_pupil, sample_pupil_ks1, sample_pupil_ks2):
        """Summary groups by meal_type and entitlement with correct counts."""
        meal_service.record_meal(pupil_id=sample_pupil["pupil_id"], date="2026-04-04", meal_type="hot")
        meal_service.record_meal(pupil_id=sample_pupil_ks1["pupil_id"], date="2026-04-04", meal_type="hot")
        meal_service.record_meal(pupil_id=sample_pupil_ks2["pupil_id"], date="2026-04-04", meal_type="packed")
        summary = meal_service.get_daily_summary("2026-04-04")
        assert len(summary) >= 2
        hot_rows = [s for s in summary if s["meal_type"] == "hot"]
        packed_rows = [s for s in summary if s["meal_type"] == "packed"]
        assert sum(r["count"] for r in hot_rows) == 2
        assert sum(r["count"] for r in packed_rows) == 1
