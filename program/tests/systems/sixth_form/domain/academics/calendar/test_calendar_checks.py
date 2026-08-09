"""Tests for the save-time checks: clash detection and the term
calendar's warnings. Both must warn, never veto — and never crash a
save when their data sources are absent."""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.academics.calendar import (
    calendar as core,
    calendar_clashes as clashes,
    calendar_terms as terms,
)


@pytest.fixture
def hall_event(caldb):
    return core.create_event({
        "title": "Awards Evening", "event_type": "Social",
        "start_date": "2026-09-24", "start_time": "18:00",
        "end_time": "20:00", "location": "Main Hall",
        "organiser": "P Jones",
    })


class TestLocationClashes:

    def test_overlap_at_the_same_location_is_flagged(self, hall_event):
        report = clashes.check({
            "title": "Band", "start_date": "2026-09-24",
            "start_time": "19:00", "end_time": "21:00",
            "location": "main hall"})       # case-insensitive
        assert not report.clean
        assert report.clashes[0].kind == "location"

    def test_touching_windows_do_not_clash(self, hall_event):
        report = clashes.check({
            "title": "Setup", "start_date": "2026-09-24",
            "start_time": "16:00", "end_time": "18:00",
            "location": "Main Hall"})
        assert report.clean

    def test_all_day_blocks_the_whole_day(self, caldb):
        core.create_event({"title": "Exams", "event_type": "Exam",
                           "start_date": "2026-09-25",
                           "all_day": True, "location": "Gym"})
        report = clashes.check({
            "title": "PE", "start_date": "2026-09-25",
            "start_time": "10:00", "end_time": "11:00",
            "location": "Gym"})
        assert not report.clean

    def test_cancelled_events_do_not_clash(self, caldb):
        core.create_event({"title": "Was cancelled",
                           "start_date": "2026-09-26",
                           "start_time": "09:00",
                           "end_time": "17:00",
                           "location": "Hall",
                           "status": "Cancelled"})
        assert clashes.check({
            "title": "New", "start_date": "2026-09-26",
            "start_time": "10:00", "end_time": "11:00",
            "location": "Hall"}).clean

    def test_deadlines_never_clash(self, hall_event):
        assert clashes.check({
            "title": "Coursework due", "event_type": "Deadline",
            "start_date": "2026-09-24",
            "location": "Main Hall"}).clean

    def test_an_edit_does_not_clash_with_itself(self, hall_event):
        report = clashes.check(
            {"title": "Awards Evening", "start_date": "2026-09-24",
             "start_time": "18:00", "end_time": "21:00",
             "location": "Main Hall"},
            exclude_event_id=hall_event.event_id)
        assert report.clean


class TestOrganiserClashes:

    def test_double_commitment_is_flagged(self, hall_event):
        report = clashes.check({
            "title": "Talk", "start_date": "2026-09-24",
            "start_time": "18:30", "end_time": "19:00",
            "location": "Room 5", "organiser": "p jones"})
        assert any(c.kind == "organiser" for c in report.clashes)


class TestSuggestSlots:

    def test_suggestions_avoid_the_blocked_day_and_weekends(
            self, caldb):
        import datetime as _dt
        core.create_event({"title": "Exams", "event_type": "Exam",
                           "start_date": "2026-09-25",   # a Friday
                           "all_day": True, "location": "Gym"})
        slots = clashes.suggest_slots(
            duration_minutes=60, location="Gym",
            date_from="2026-09-25", days_to_search=5,
            max_suggestions=3)
        assert slots
        assert all(s.date != "2026-09-25" for s in slots)
        assert all(_dt.date.fromisoformat(s.date).weekday() < 5
                   for s in slots)

    def test_zero_duration_is_rejected(self, caldb):
        with pytest.raises(clashes.ValidationError):
            clashes.suggest_slots(duration_minutes=0)


class TestTermChecks:

    @pytest.fixture
    def term(self, caldb, tmp_path, monkeypatch):
        """A configured Autumn term with one INSET day."""
        from education_system.systems.sixth_form.domain.academics.attendance import (  # noqa: E501
            attendance as att_core,
            attendance_calendar as att_cal,
        )
        db = str(tmp_path / "att.db")
        for mod in (att_core, att_cal):
            monkeypatch.setattr(mod, "DB_PATH", db, raising=False)
            monkeypatch.setattr(mod, "_DB_READY", False,
                                raising=False)
        att_cal.init_db()
        att_cal.add_term("Autumn Term", "2026-09-07", "2026-12-18",
                         academic_year="2026/27")
        att_cal.add_day("2026-10-02", kind="INSET",
                        name="Staff training")
        return att_cal

    def test_week_label_speaks_the_college_dialect(self, term):
        assert terms.week_label("2026-09-09") == \
            "Week 1 of Autumn Term"
        assert terms.week_label("2026-10-14") == \
            "Week 6 of Autumn Term"
        assert terms.week_label("2026-08-15") is None

    def test_weekends_and_inset_warn(self, term):
        r = terms.check({"title": "Trip", "event_type": "Trip",
                         "start_date": "2026-09-12"},   # Saturday
                        today="2026-06-01")
        assert any(w.kind == "closed" for w in r.warnings)
        r = terms.check({"title": "Rehearsal",
                         "start_date": "2026-10-02"},
                        today="2026-06-01")
        assert any(w.kind == "closed" for w in r.warnings)

    def test_training_on_the_inset_day_is_fine(self, term):
        r = terms.check({"title": "CPD", "event_type": "Training",
                         "start_date": "2026-10-02"},
                        today="2026-06-01")
        assert not any(w.kind == "closed" for w in r.warnings)

    def test_exam_window_warns_socials_but_not_exams(self, term):
        core.create_event({"title": "Mocks",
                           "event_type": "Mock Exam",
                           "start_date": "2026-11-16",
                           "end_date": "2026-11-20",
                           "all_day": True})
        r = terms.check({"title": "Concert", "event_type": "Social",
                         "start_date": "2026-11-18"},
                        today="2026-09-01")
        assert any(w.kind == "exam-window" for w in r.warnings)
        r = terms.check({"title": "More mocks",
                         "event_type": "Mock Exam",
                         "start_date": "2026-11-18"},
                        today="2026-09-01")
        assert not any(w.kind == "exam-window" for w in r.warnings)

    def test_lead_time_uses_the_table(self, term):
        r = terms.check({"title": "Trip", "event_type": "Trip",
                         "start_date": "2026-09-16"},
                        today="2026-09-10")
        lead = [w for w in r.warnings if w.kind == "lead-time"]
        assert lead and "14 days" in lead[0].detail

    def test_unconfigured_calendar_never_warns_closed(self, caldb):
        # No terms set up at all — a weekday must come back clean
        # rather than every event being "outside term".
        r = terms.check({"title": "Meeting",
                         "start_date": "2026-09-16"},
                        today="2026-09-01")
        assert not any(w.kind == "closed" for w in r.warnings)
