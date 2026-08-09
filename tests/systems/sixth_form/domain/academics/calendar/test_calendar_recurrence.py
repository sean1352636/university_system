"""Tests for recurring series: expansion, materialisation,
exceptions and the edit-this / edit-all split."""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.academics.calendar import (
    calendar as core,
    calendar_recurrence as recurrence,
)


@pytest.fixture
def weekly(caldb):
    """Tutor time, Mon+Wed for four weeks."""
    return recurrence.create_series({
        "title": "Tutor Time",
        "frequency": "Weekly",
        "byday": "Mon,Wed",
        "start_date": "2026-09-07",          # a Monday
        "until_date": "2026-09-30",
        "template": {"event_type": "Tutor Time",
                     "start_time": "08:45", "end_time": "09:05",
                     "location": "Tutor bases"},
    }, actor="jsmith")


class TestExpansion:

    def test_weekly_hits_only_the_named_days(self, weekly):
        dates = recurrence.occurrence_dates(weekly)
        assert dates[0] == "2026-09-07"
        assert "2026-09-09" in dates        # the Wednesday
        assert "2026-09-08" not in dates    # not the Tuesday
        assert len(dates) == 8

    def test_byday_defaults_to_the_start_weekday(self, caldb):
        s = recurrence.create_series({
            "title": "Briefing", "frequency": "Weekly",
            "start_date": "2026-09-08",      # a Tuesday
            "until_date": "2026-09-22",
            "template": {},
        })
        assert s.byday == ("Tue",)

    def test_fortnightly_skips_alternate_weeks(self, caldb):
        s = recurrence.create_series({
            "title": "Assembly", "frequency": "Fortnightly",
            "start_date": "2026-09-08", "until_date": "2026-10-10",
            "template": {},
        })
        assert recurrence.occurrence_dates(s) == [
            "2026-09-08", "2026-09-22", "2026-10-06"]

    def test_monthly_skips_short_months(self, caldb):
        s = recurrence.create_series({
            "title": "Governors", "frequency": "Monthly",
            "start_date": "2026-01-31", "until_date": "2026-04-30",
            "template": {},
        })
        # No 31st in February or April: skipped, not slid.
        assert recurrence.occurrence_dates(s) == [
            "2026-01-31", "2026-03-31"]

    def test_max_count_counts_from_the_series_start(self, caldb):
        s = recurrence.create_series({
            "title": "Induction", "frequency": "Daily",
            "start_date": "2026-09-01", "max_count": 3,
            "template": {},
        })
        assert recurrence.occurrence_dates(s) == [
            "2026-09-01", "2026-09-02", "2026-09-03"]

    def test_bad_rules_are_rejected(self, caldb):
        for bad in (
            {"title": "x", "frequency": "Hourly",
             "start_date": "2026-09-01"},
            {"title": "x", "byday": "Funday",
             "start_date": "2026-09-01"},
            {"title": "x", "start_date": "2026-09-01",
             "until_date": "2026-08-01"},
        ):
            with pytest.raises(recurrence.ValidationError):
                recurrence.create_series({**bad, "template": {}})

    def test_a_bad_template_is_caught_at_create(self, caldb):
        with pytest.raises(recurrence.ValidationError):
            recurrence.create_series({
                "title": "x", "start_date": "2026-09-01",
                "template": {"event_type": "NotAType"},
            })


class TestMaterialise:

    def test_occurrences_become_ordinary_events(self, weekly):
        got = recurrence.materialise(weekly.series_id,
                                     date_to="2026-09-30")
        assert got.created == 8
        rows = core.list_events(event_type="Tutor Time")
        assert len(rows) == 8
        assert rows[0].start_time == "08:45:00"
        assert rows[0].created_by == "jsmith"

    def test_materialise_is_idempotent(self, weekly):
        recurrence.materialise(weekly.series_id, date_to="2026-09-30")
        again = recurrence.materialise(weekly.series_id,
                                       date_to="2026-09-30")
        assert again.created == 0
        assert again.skipped == 8


class TestExceptions:

    def test_an_exception_archives_the_occurrence(self, weekly):
        recurrence.materialise(weekly.series_id, date_to="2026-09-30")
        recurrence.add_exception(weekly.series_id, "2026-09-14",
                                 reason="INSET")
        dates = {e.start_date
                 for e in core.list_events(event_type="Tutor Time")}
        assert "2026-09-14" not in dates

    def test_sync_does_not_resurrect_an_exception(self, weekly):
        recurrence.materialise(weekly.series_id, date_to="2026-09-30")
        recurrence.add_exception(weekly.series_id, "2026-09-14")
        recurrence.sync(weekly.series_id, date_to="2026-09-30")
        dates = {e.start_date
                 for e in core.list_events(event_type="Tutor Time")}
        assert "2026-09-14" not in dates


class TestEditThisVsAll:

    def test_detached_occurrence_ignores_template_pushes(self, weekly):
        recurrence.materialise(weekly.series_id, date_to="2026-09-30")
        victim = core.list_events(event_type="Tutor Time")[0]
        recurrence.update_occurrence(victim.event_id,
                                     {"location": "Hall"})
        recurrence.update_series(weekly.series_id,
                                 {"template": {"location": "Room 12"}})
        recurrence.sync(weekly.series_id, date_to="2026-09-30")
        after = {e.event_id: e.location
                 for e in core.list_events(event_type="Tutor Time")}
        assert after.pop(victim.event_id) == "Hall"
        assert set(after.values()) == {"Room 12"}

    def test_series_for_event_links_back(self, weekly):
        recurrence.materialise(weekly.series_id, date_to="2026-09-30")
        event = core.list_events(event_type="Tutor Time")[0]
        occ = recurrence.series_for_event(event.event_id)
        assert occ is not None
        assert occ.series_id == weekly.series_id

    def test_detaching_a_loose_event_is_an_error(self, one_event):
        with pytest.raises(recurrence.ValidationError,
                           match="does not belong"):
            recurrence.detach(one_event.event_id)


class TestDeactivate:

    def test_future_followers_are_archived(self, weekly, monkeypatch):
        recurrence.materialise(weekly.series_id, date_to="2026-09-30")
        # All occurrences are in the future relative to a pinned
        # "today" well before the series.
        import datetime as _dt

        class _FakeDate(_dt.date):
            @classmethod
            def today(cls):
                return cls(2026, 9, 1)
        monkeypatch.setattr(recurrence._dt, "date", _FakeDate)
        archived = recurrence.deactivate_series(weekly.series_id)
        assert archived == 8
        assert core.list_events(event_type="Tutor Time") == []
