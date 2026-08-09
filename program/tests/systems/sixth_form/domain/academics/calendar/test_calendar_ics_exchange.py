"""Tests for the file surfaces: ICS round-trip, CSV dry-run import
and the printable sheets."""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.academics.calendar import (
    calendar as core,
    calendar_exchange as exchange,
    calendar_ics as ics,
)


class TestIcsExport:

    def test_escaping_and_structure(self, caldb):
        core.create_event({
            "title": "Parents' Evening; Year 12, Autumn",
            "start_date": "2026-10-08", "start_time": "16:30",
            "end_time": "19:00", "location": "Main Hall, Block A",
        })
        text = ics.export_filtered()
        assert text.startswith("BEGIN:VCALENDAR\r\n")
        assert "SUMMARY:Parents' Evening\\; Year 12\\, Autumn" in text
        assert "LOCATION:Main Hall\\, Block A" in text
        assert "DTSTART:20261008T163000" in text

    def test_all_day_uses_exclusive_date_dtend(self, caldb):
        core.create_event({"title": "Half term",
                           "event_type": "Holiday",
                           "start_date": "2026-10-26",
                           "end_date": "2026-10-30",
                           "all_day": True})
        text = ics.export_filtered()
        assert "DTSTART;VALUE=DATE:20261026" in text
        assert "DTEND;VALUE=DATE:20261031" in text

    def test_no_line_exceeds_75_octets(self, caldb):
        core.create_event({"title": "T" * 200,
                           "start_date": "2026-11-02"})
        for line in ics.export_filtered().split("\r\n"):
            assert len(line) <= 75


class TestIcsImport:

    def test_round_trip_recreates_faithfully(self, one_event):
        exported = ics.export_filtered()
        core.purge_event(one_event.event_id)
        result = ics.import_ics(exported)
        assert result.created == 1
        back = core.list_events()[0]
        assert back.title == one_event.title
        assert back.start_time == "16:30:00"
        assert back.event_type == "Parents' Evening"

    def test_reimport_updates_by_uid(self, one_event):
        exported = ics.export_filtered()
        result = ics.import_ics(exported)
        # Same UID: the existing event updates, no duplicate.
        assert result.created == 0
        assert result.updated == 1
        assert len(core.list_events()) == 1

    def test_utc_stamps_keep_their_clock_time(self, caldb):
        foreign = (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
            "BEGIN:VEVENT\r\nUID:x@board\r\n"
            "DTSTART:20270517T090000Z\r\n"
            "DTEND:20270517T110000Z\r\n"
            "SUMMARY:Paper 1\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")
        result = ics.import_ics(foreign, default_event_type="Exam")
        assert result.created == 1
        exam = core.list_events()[0]
        assert exam.start_date == "2027-05-17"
        assert exam.start_time == "09:00:00"

    def test_a_dateless_vevent_is_dropped_not_fatal(self, caldb):
        bad = ("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\n"
               "SUMMARY:No date\r\nEND:VEVENT\r\n"
               "BEGIN:VEVENT\r\nSUMMARY:Fine\r\n"
               "DTSTART;VALUE=DATE:20270601\r\nEND:VEVENT\r\n"
               "END:VCALENDAR\r\n")
        assert ics.import_ics(bad).created == 1


class TestCsv:

    def test_export_import_round_trip(self, caldb):
        core.create_event({"title": 'Awards, "Gala" Night',
                           "start_date": "2026-12-11",
                           "cost": 7.5})
        text = exchange.export_filtered_csv()
        report = exchange.import_csv(text, dry_run=False)
        assert report.created == 1
        assert len(core.list_events()) == 2

    def test_dry_run_reports_rows_and_writes_nothing(self, caldb):
        bad = ("title,start_date\n"
               "Good,2026-09-10\n"
               ",2026-09-11\n"
               "Bad date,2026-02-30\n")
        report = exchange.import_csv(bad, dry_run=True)
        assert report.valid == 1
        assert len(report.errors) == 2
        assert {e.row for e in report.errors} == {3, 4}
        assert core.list_events() == []

    def test_a_dirty_file_imports_none_of_its_rows(self, caldb):
        bad = ("title,start_date\nGood,2026-09-10\nBad,2026-02-30\n")
        report = exchange.import_csv(bad, dry_run=False)
        assert report.created == 0
        assert core.list_events() == []

    def test_unknown_columns_are_flagged(self, caldb):
        report = exchange.import_csv(
            "title,start_date,colour\nX,2026-09-10,red\n")
        assert any("Unknown column" in e.message
                   for e in report.errors)


class TestSheets:

    def test_day_sheet_lists_the_day(self, one_event):
        sheet = exchange.day_sheet("2026-10-08")
        assert "Parents' Evening" in sheet
        assert "16:30–19:00" in sheet

    def test_day_sheet_hides_cancelled(self, one_event):
        core.cancel_event(one_event.event_id)
        assert "Parents' Evening" not in \
            exchange.day_sheet("2026-10-08")

    def test_term_sheet_groups_by_date(self, one_event):
        core.create_event({"title": "Mocks",
                           "event_type": "Mock Exam",
                           "start_date": "2026-10-12",
                           "end_date": "2026-10-16",
                           "all_day": True})
        sheet = exchange.term_sheet("2026-10-01", "2026-10-31")
        assert "Thursday 08 October" in sheet
        assert "(until 2026-10-16)" in sheet
