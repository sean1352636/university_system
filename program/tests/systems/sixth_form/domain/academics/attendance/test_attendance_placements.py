"""Tests for work-placement attendance.

The load-bearing idea: an expected placement day is *unknown*, not
present, until the employer's supervisor says otherwise — and the
percentage is calculated over the days somebody actually reported on.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_placements as placements,
)
from education_system.systems.sixth_form.domain.progression.work_experience import (
    work_experience,
)


@pytest.fixture
def placement(attdb):
    """One learner on a Monday-to-Friday placement covering this week."""
    employer = work_experience.create_employer({"name": "Hendricks "
                                                        "Engineering"})
    monday = _dt.date.fromisoformat(attdb.monday)
    return work_experience.create_placement({
        "student_id": attdb.s1,
        "employer_id": employer.employer_id,
        "start_date": attdb.monday,
        "end_date": (monday + _dt.timedelta(days=4)).isoformat(),
        "supervisor_name": "R Hendricks",
    })


# ── 1. The working pattern ─────────────────────────────────────────

class TestPattern:

    def test_the_default_is_monday_to_friday(self, attdb, placement):
        pattern = placements.get_pattern(placement.placement_id)
        assert pattern.days == placements.DEFAULT_DAYS

    def test_a_pattern_can_be_narrowed(self, attdb, placement):
        # A Wednesday-only placement generates four false absences a
        # week if the default is left alone.
        pattern = placements.set_pattern(placement.placement_id, days=[3],
                                         hours_per_day=6)
        assert pattern.days == (3,)
        assert pattern.hours_per_day == 6

    def test_a_nonsense_day_is_rejected(self, attdb, placement):
        with pytest.raises(core.ValidationError, match="Days must be"):
            placements.set_pattern(placement.placement_id, days=[9])

    def test_an_unknown_placement_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="No placement"):
            placements.set_pattern(9999, days=[1])

    def test_expected_dates_follow_the_pattern(self, attdb, placement):
        placements.set_pattern(placement.placement_id, days=[1, 3])
        dates = placements.expected_dates(placement.placement_id)
        assert len(dates) == 2
        assert dates[0] == attdb.monday


# ── 2. Generating days ─────────────────────────────────────────────

class TestGenerate:

    def test_days_are_generated_across_the_placement(self, attdb, placement):
        days = placements.generate_days(placement.placement_id)
        assert len(days) == 5
        assert all(d.state == placements.EXPECTED for d in days)

    def test_generating_twice_keeps_confirmations(self, attdb, placement):
        placements.generate_days(placement.placement_id)
        placements.confirm_day(placement.placement_id, attdb.monday,
                               confirmed_by="R Hendricks")
        placements.generate_days(placement.placement_id)
        day = placements.get_day(placement.placement_id, attdb.monday)
        assert day.state == placements.CONFIRMED

    def test_overwrite_resets_them(self, attdb, placement):
        placements.generate_days(placement.placement_id)
        placements.confirm_day(placement.placement_id, attdb.monday,
                               confirmed_by="R Hendricks")
        placements.generate_days(placement.placement_id, overwrite=True)
        day = placements.get_day(placement.placement_id, attdb.monday)
        assert day.state == placements.EXPECTED


# ── 3. Confirmation ────────────────────────────────────────────────

class TestConfirmation:

    def test_a_confirmed_day_records_hours_and_a_source(self, attdb,
                                                        placement):
        placements.generate_days(placement.placement_id)
        day = placements.confirm_day(placement.placement_id, attdb.monday,
                                     hours=7.5,
                                     confirmed_by="R Hendricks")
        assert day.state == placements.CONFIRMED
        assert day.hours == 7.5
        assert day.confirmed_by == "R Hendricks"

    def test_hours_default_to_the_pattern(self, attdb, placement):
        placements.generate_days(placement.placement_id)
        day = placements.confirm_day(placement.placement_id, attdb.monday,
                                     confirmed_by="R Hendricks")
        assert day.hours == placements.DEFAULT_HOURS

    def test_a_confirmation_must_name_its_source(self, attdb, placement):
        # A placement record whose source cannot be named is not evidence.
        placements.generate_days(placement.placement_id)
        with pytest.raises(core.ValidationError, match="who confirmed"):
            placements.confirm_day(placement.placement_id, attdb.monday,
                                   confirmed_by="  ")

    def test_a_missed_day_is_recorded(self, attdb, placement):
        placements.generate_days(placement.placement_id)
        day = placements.report_missed(placement.placement_id, attdb.monday,
                                       confirmed_by="R Hendricks")
        assert day.state == placements.MISSED
        assert day.counts_as_attended is False

    def test_an_employer_cancellation_is_not_the_learners_absence(
            self, attdb, placement):
        placements.generate_days(placement.placement_id)
        day = placements.cancel_day(placement.placement_id, attdb.monday,
                                    reason="Factory closed")
        assert day.state == placements.CANCELLED

    def test_absurd_hours_are_rejected(self, attdb, placement):
        placements.generate_days(placement.placement_id)
        with pytest.raises(core.ValidationError, match="Hours must be"):
            placements.confirm_day(placement.placement_id, attdb.monday,
                                   hours=48, confirmed_by="R Hendricks")

    def test_confirmed_hours_reach_the_placement_record(self, attdb,
                                                        placement):
        placements.generate_days(placement.placement_id)
        placements.confirm_day(placement.placement_id, attdb.monday,
                               hours=7, confirmed_by="R Hendricks")
        updated = work_experience.get_placement(placement.placement_id)
        assert updated.hours_completed == 7

    def test_re_confirming_does_not_inflate_the_total(self, attdb, placement):
        placements.generate_days(placement.placement_id)
        placements.confirm_day(placement.placement_id, attdb.monday, hours=7,
                               confirmed_by="R Hendricks")
        placements.confirm_day(placement.placement_id, attdb.monday, hours=6,
                               confirmed_by="R Hendricks")
        updated = work_experience.get_placement(placement.placement_id)
        assert updated.hours_completed == 6


# ── 4. The college register ────────────────────────────────────────

class TestRegisterSync:

    def test_a_confirmed_day_codes_the_lessons_w(self, attdb, placement):
        placements.generate_days(placement.placement_id)
        placements.confirm_day(placement.placement_id, attdb.monday,
                               confirmed_by="R Hendricks")
        record = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        assert record.code == placements.PRESENT_CODE
        assert record.is_offsite is True

    def test_the_employer_name_lands_as_the_location(self, attdb, placement):
        placements.generate_days(placement.placement_id)
        placements.confirm_day(placement.placement_id, attdb.monday,
                               confirmed_by="R Hendricks")
        record = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        assert record.offsite_location == "Hendricks Engineering"

    def test_a_missed_day_recodes_the_register(self, attdb, placement):
        # The entire reason for collecting the confirmation.
        placements.generate_days(placement.placement_id)
        placements.report_missed(placement.placement_id, attdb.monday,
                                 confirmed_by="R Hendricks")
        record = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        assert record.code == placements.MISSED_CODE

    def test_sync_can_be_declined(self, attdb, placement):
        placements.generate_days(placement.placement_id)
        placements.confirm_day(placement.placement_id, attdb.monday,
                               confirmed_by="R Hendricks",
                               sync_register=False)
        assert core.get_record_for(attdb.slot, attdb.s1, attdb.monday) is None

    def test_a_whole_placement_can_be_synced(self, attdb, placement):
        placements.generate_days(placement.placement_id)
        placements.confirm_day(placement.placement_id, attdb.monday,
                               confirmed_by="R Hendricks",
                               sync_register=False)
        report = placements.sync_placement(placement.placement_id)
        assert report.days == 1
        assert report.marks_written >= 1


# ── 5. Chasing and reporting ───────────────────────────────────────

class TestReporting:

    def test_past_unconfirmed_days_are_chased(self, attdb, placement):
        placements.generate_days(placement.placement_id)
        tomorrow = (_dt.date.today() + _dt.timedelta(days=1)).isoformat()
        outstanding = placements.awaiting_confirmation(as_at=tomorrow)
        assert outstanding

    def test_a_confirmed_day_drops_off_the_chase_list(self, attdb,
                                                      placement):
        placements.generate_days(placement.placement_id)
        placements.confirm_day(placement.placement_id, attdb.monday,
                               confirmed_by="R Hendricks")
        tomorrow = (_dt.date.today() + _dt.timedelta(days=1)).isoformat()
        chased = [d.date for d in
                  placements.awaiting_confirmation(as_at=tomorrow)]
        assert attdb.monday not in chased

    def test_the_percentage_uses_reported_days_only(self, attdb, placement):
        # An unconfirmed day is missing information, not an absence —
        # counting it against the learner punishes the employer's admin.
        placements.generate_days(placement.placement_id)
        placements.confirm_day(placement.placement_id, attdb.monday,
                               confirmed_by="R Hendricks")
        record = placements.attendance_for(placement.placement_id)
        assert record.confirmed == 1
        assert record.percentage == 100.0

    def test_a_missed_day_moves_the_percentage(self, attdb, placement):
        placements.generate_days(placement.placement_id)
        monday = _dt.date.fromisoformat(attdb.monday)
        placements.confirm_day(placement.placement_id, attdb.monday,
                               confirmed_by="R Hendricks")
        placements.report_missed(
            placement.placement_id,
            (monday + _dt.timedelta(days=1)).isoformat(),
            confirmed_by="R Hendricks")
        record = placements.attendance_for(placement.placement_id)
        assert record.percentage == 50.0

    def test_a_learners_placements_add_up(self, attdb, placement):
        placements.generate_days(placement.placement_id)
        placements.confirm_day(placement.placement_id, attdb.monday,
                               hours=7, confirmed_by="R Hendricks")
        record = placements.attendance_for_student(attdb.s1)
        assert record.hours == 7

    def test_a_disagreement_with_the_register_is_reported(self, attdb,
                                                          placement):
        placements.generate_days(placement.placement_id)
        # College says absent; the placement says the learner was there.
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"code": "O"}})
        rows = placements.discrepancies(date_from=attdb.monday,
                                        date_to=attdb.monday)
        assert rows
        assert rows[0].register_code == "O"

    def test_who_is_out_today_is_answerable(self, attdb, placement):
        placements.generate_days(placement.placement_id)
        out = placements.on_placement(attdb.monday)
        assert [d.student_id for d in out] == [attdb.s1]
