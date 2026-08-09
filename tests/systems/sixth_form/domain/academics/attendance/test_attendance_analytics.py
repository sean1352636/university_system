"""Tests for attendance analytics.

The correlation half is deliberately cautious: with no grade source
configured it reports "not enough data" rather than a coefficient
somebody could put on a slide.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_analytics as analytics,
)


def mark_run(attdb, student_id: str, *, attended: int, total: int,
             slot: int | None = None) -> None:
    monday = _dt.date.fromisoformat(attdb.prev_monday)
    for index in range(total):
        date = (monday - _dt.timedelta(days=index)).isoformat()
        core.save_register(slot or attdb.slot, date,
                           {student_id: {"code": "/" if index < attended
                                         else "O"}}, allow_retro=True)


# ── 1. Maths ───────────────────────────────────────────────────────

class TestMaths:

    def test_a_perfect_relationship_reads_as_one(self, attdb):
        assert analytics._pearson([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]) == 1.0

    def test_an_inverse_relationship_reads_as_minus_one(self, attdb):
        assert analytics._pearson([1.0, 2.0, 3.0], [6.0, 4.0, 2.0]) == -1.0

    def test_no_variation_has_no_correlation(self, attdb):
        assert analytics._pearson([1.0, 1.0, 1.0], [2.0, 4.0, 6.0]) is None

    def test_a_single_point_has_no_correlation(self, attdb):
        assert analytics._pearson([1.0], [2.0]) is None

    @pytest.mark.parametrize("grade,points", [
        ("A*", 6.0), ("a", 5.0), ("C", 3.0), ("U", 0.0),
    ])
    def test_grades_convert_to_points(self, attdb, grade, points):
        assert analytics.grade_points(grade) == points

    def test_an_unknown_grade_converts_to_nothing(self, attdb):
        assert analytics.grade_points("Excellent") is None
        assert analytics.grade_points(None) is None


# ── 2. Correlation ─────────────────────────────────────────────────

class TestCorrelation:

    def test_no_grade_data_is_reported_honestly(self, attdb):
        mark_run(attdb, attdb.s1, attended=8, total=10)
        result = analytics.attainment_correlation(
            date_from=attdb.prev_monday, date_to=attdb.prev_monday)
        assert result.reliable is False
        assert result.strength == analytics.INSUFFICIENT
        assert "not enough data" in result.label

    def test_a_small_sample_is_never_called_reliable(self, attdb):
        result = analytics.Correlation(sample=5, coefficient=0.9)
        assert result.reliable is False
        assert result.strength == analytics.INSUFFICIENT

    @pytest.mark.parametrize("coefficient,strength", [
        (0.7, analytics.STRONG),
        (0.4, analytics.MODERATE),
        (0.2, analytics.WEAK),
        (0.05, analytics.NEGLIGIBLE),
        (-0.7, analytics.STRONG),
    ])
    def test_strength_bands_are_applied(self, attdb, coefficient, strength):
        result = analytics.Correlation(sample=analytics.MIN_SAMPLE,
                                       coefficient=coefficient)
        assert result.strength == strength


# ── 3. Subject comparison ──────────────────────────────────────────

class TestSubjects:

    def test_attendance_is_broken_down_by_subject(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "/"}})
        core.save_register(attdb.pm_slot, attdb.prev_monday,
                           {attdb.s1: {"code": "O"}})
        rows = analytics.subject_comparison(attdb.s1)
        assert rows
        assert sum(r.sessions for r in rows) == 2

    def test_the_gap_against_their_own_average_is_computed(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "O"}})
        core.save_register(attdb.pm_slot, attdb.prev_monday,
                           {attdb.s1: {"code": "/"}})
        rows = analytics.subject_comparison(attdb.s1)
        assert any(r.gap is not None for r in rows)

    def test_the_worst_subject_comes_first(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "O"}})
        core.save_register(attdb.pm_slot, attdb.prev_monday,
                           {attdb.s1: {"code": "/"}})
        rows = analytics.subject_comparison(attdb.s1)
        assert rows[0].percentage <= rows[-1].percentage

    def test_not_counted_codes_leave_the_denominator(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "Y"}})
        rows = analytics.subject_comparison(attdb.s1)
        assert all(r.sessions == 0 for r in rows) or rows == []

    def test_a_learner_with_no_marks_has_no_subjects(self, attdb):
        assert analytics.subject_comparison(attdb.s1) == []


# ── 4. Forecast ────────────────────────────────────────────────────

class TestForecast:

    def test_a_learner_with_no_marks_forecasts_nothing(self, attdb):
        projection = analytics.forecast(attdb.s1)
        assert projection.current_pct is None
        assert projection.projected_pct is None

    def test_the_current_figure_is_reported(self, attdb):
        mark_run(attdb, attdb.s1, attended=8, total=10)
        projection = analytics.forecast(attdb.s1,
                                        date_from=attdb.prev_monday)
        assert projection.current_pct is not None

    def test_a_projection_carries_a_target(self, attdb):
        mark_run(attdb, attdb.s1, attended=8, total=10)
        projection = analytics.forecast(attdb.s1, target_pct=90.0)
        assert projection.target_pct == 90.0
        assert projection.will_meet_target in (True, False)

    def test_headroom_is_never_negative(self, attdb):
        mark_run(attdb, attdb.s1, attended=0, total=10)
        assert analytics.forecast(attdb.s1).headroom_sessions >= 0

    def test_a_cohort_forecast_lists_those_at_risk(self, attdb):
        mark_run(attdb, attdb.s1, attended=2, total=10)
        rows = analytics.forecast_cohort(target_pct=90.0)
        assert attdb.s1 in [f.student_id for f in rows]

    def test_a_healthy_learner_is_not_at_risk(self, attdb):
        mark_run(attdb, attdb.s1, attended=10, total=10)
        rows = analytics.forecast_cohort(target_pct=50.0)
        assert attdb.s1 not in [f.student_id for f in rows]


# ── 5. Benchmark and heatmap ───────────────────────────────────────

class TestBenchmark:

    def test_the_current_figure_is_computed(self, attdb):
        mark_run(attdb, attdb.s1, attended=8, total=10)
        result = analytics.benchmark(date_from=attdb.prev_monday,
                                     date_to=attdb.prev_monday)
        assert result.current_pct is not None
        assert result.learners >= 1

    def test_no_previous_year_means_no_change(self, attdb):
        mark_run(attdb, attdb.s1, attended=8, total=10)
        result = analytics.benchmark(date_from=attdb.prev_monday,
                                     date_to=attdb.prev_monday)
        assert result.change is None

    def test_the_target_gap_is_computed(self, attdb):
        mark_run(attdb, attdb.s1, attended=10, total=10)
        result = analytics.benchmark(date_from=attdb.prev_monday,
                                     date_to=attdb.prev_monday)
        assert result.against_target is not None

    def test_groups_can_be_benchmarked(self, attdb):
        mark_run(attdb, attdb.s1, attended=8, total=10)
        rows = analytics.benchmark_by_group()
        assert any(b.scope == "12A" for b in rows)


class TestHeatmap:

    def test_cells_are_keyed_by_day_and_period(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "/"}})
        grid = analytics.heatmap()
        assert grid.cell(1, 1) is not None
        assert grid.cell(1, 1).percentage == 100.0

    def test_an_absence_moves_the_cell(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "/"},
                            attdb.s2: {"code": "O"}})
        assert analytics.heatmap().cell(1, 1).percentage == 50.0

    def test_the_grid_prints_as_rows(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "/"}})
        rows = analytics.heatmap().rows()
        assert rows and rows[0][0] == 1

    def test_weekday_and_period_profiles_are_derived(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "/"}})
        assert analytics.weekday_profile()[1] == 100.0
        assert analytics.period_profile()[1] == 100.0

    def test_an_empty_window_produces_an_empty_grid(self, attdb):
        assert analytics.heatmap().cells == {}


# ── 6. One-call summary ────────────────────────────────────────────

class TestInsight:

    def test_the_learner_insight_pulls_it_together(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "O"}})
        core.save_register(attdb.pm_slot, attdb.prev_monday,
                           {attdb.s1: {"code": "/"}})
        insight = analytics.learner_insight(attdb.s1)
        assert insight["student_id"] == attdb.s1
        assert insight["forecast"] is not None
        assert insight["subjects"]
        assert "headroom" in insight
