"""Tests for the governor and SLT report.

The report computes no new numbers — every figure comes from the module
that owns it, so the report and the screens cannot disagree.
"""

from __future__ import annotations

import datetime as _dt
import json

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_calendar as calendar,
    attendance_governor_report as governor,
)


def mark_run(attdb, student_id: str, *, attended: int, total: int) -> None:
    monday = _dt.date.fromisoformat(attdb.prev_monday)
    for index in range(total):
        date = (monday - _dt.timedelta(days=index)).isoformat()
        core.save_register(attdb.slot, date,
                           {student_id: {"code": "/" if index < attended
                                         else "O"}}, allow_retro=True)


# ── 1. Building ────────────────────────────────────────────────────

class TestBuild:

    def test_a_report_builds_with_no_data(self, attdb):
        report = governor.build()
        assert report.headline is not None
        assert report.generated_on == _dt.date.today().isoformat()

    def test_the_headline_figure_is_computed(self, attdb):
        mark_run(attdb, attdb.s1, attended=8, total=10)
        report = governor.build(date_from=attdb.prev_monday,
                                date_to=attdb.prev_monday)
        assert report.headline.attendance_pct is not None

    def test_the_period_defaults_to_a_rolling_window(self, attdb):
        report = governor.build()
        assert report.period_label == "Last 90 days"

    def test_a_configured_term_names_the_period(self, attdb):
        today = _dt.date.today()
        calendar.add_term("Autumn",
                          (today - _dt.timedelta(days=30)).isoformat(),
                          (today + _dt.timedelta(days=30)).isoformat())
        report = governor.build()
        assert report.period_label == "Autumn"

    def test_an_explicit_window_is_honoured(self, attdb):
        report = governor.build(date_from=attdb.prev_monday,
                                date_to=attdb.prev_monday,
                                period_label="Week 1")
        assert report.period_label == "Week 1"
        assert report.date_from == attdb.prev_monday

    def test_cohort_lines_cover_the_serious_bands(self, attdb):
        report = governor.build()
        bands = {line.band for line in report.cohorts}
        assert "Persistent absence" in bands
        assert "Severe absence" in bands

    def test_year_groups_are_broken_out(self, attdb):
        mark_run(attdb, attdb.s1, attended=8, total=10)
        report = governor.build(date_from=attdb.prev_monday,
                                date_to=attdb.prev_monday)
        assert report.by_year_group


# ── 2. Narrative and data quality ──────────────────────────────────

class TestNarrative:

    def test_data_quality_is_always_stated(self, attdb):
        # On the same page as the headline, not in an appendix.
        report = governor.build()
        assert report.data_quality

    def test_poor_coverage_is_called_out(self, attdb):
        # Two Monday lessons expected, one marked.
        core.save_register(attdb.slot, attdb.prev_monday,
                           {sid: {"code": "/"} for sid in attdb.students})
        report = governor.build(date_from=attdb.prev_monday,
                                date_to=attdb.prev_monday)
        assert any("coverage" in note.lower()
                   for note in report.data_quality)

    def test_being_below_target_is_a_concern(self, attdb):
        mark_run(attdb, attdb.s1, attended=5, total=10)
        report = governor.build(date_from=attdb.prev_monday,
                                date_to=attdb.prev_monday)
        assert any("below its" in c for c in report.concerns)

    def test_being_above_target_is_a_strength(self, attdb):
        mark_run(attdb, attdb.s1, attended=10, total=10)
        report = governor.build(date_from=attdb.prev_monday,
                                date_to=attdb.prev_monday)
        assert any("above its" in s for s in report.strengths)

    def test_severe_absence_is_named_as_a_concern(self, attdb):
        mark_run(attdb, attdb.s1, attended=1, total=10)
        report = governor.build()
        assert any("severely absent" in c for c in report.concerns)


# ── 3. Rendering ───────────────────────────────────────────────────

class TestRendering:

    def test_the_text_version_has_the_sections(self, attdb):
        report = governor.build()
        text = governor.render_text(report)
        assert "HEADLINE" in text
        assert "COHORTS" in text
        assert "DATA QUALITY" in text

    def test_the_markdown_version_has_tables(self, attdb):
        report = governor.build()
        markdown = governor.render_markdown(report)
        assert markdown.startswith("# ")
        assert "| Measure | Value |" in markdown

    def test_the_json_version_round_trips(self, attdb):
        report = governor.build()
        data = json.loads(report.to_json())
        assert "headline" in data
        assert "cohorts" in data

    def test_a_report_can_be_saved(self, attdb, tmp_path):
        report = governor.build()
        path = governor.save(report, str(tmp_path / "report.md"),
                             fmt="markdown")
        assert path.endswith("report.md")
        assert "# " in (tmp_path / "report.md").read_text()

    def test_an_unknown_format_is_rejected(self, attdb, tmp_path):
        report = governor.build()
        with pytest.raises(core.ValidationError, match="Format must be"):
            governor.save(report, str(tmp_path / "x"), fmt="powerpoint")

    def test_the_termly_series_needs_terms(self, attdb):
        assert governor.termly_series() == []

    def test_the_termly_series_reports_configured_terms(self, attdb):
        today = _dt.date.today()
        calendar.add_term("Autumn",
                          (today - _dt.timedelta(days=60)).isoformat(),
                          today.isoformat())
        mark_run(attdb, attdb.s1, attended=8, total=10)
        series = governor.termly_series()
        assert len(series) == 1
        assert series[0][1] is not None
