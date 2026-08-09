"""Tests for statutory attendance returns.

Validation is the point. A return that is merely produced is a
liability; the module refuses to export one with errors in it.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_census as census,
    attendance_codes as codes,
)


def full_register(attdb, date: str, *, code: str = "/") -> None:
    """Mark both Monday lessons for everybody, so coverage is complete."""
    for slot in (attdb.slot, attdb.pm_slot):
        core.save_register(slot, date,
                           {sid: {"code": code} for sid in attdb.students},
                           allow_retro=True)


# ── 1. Code mapping ────────────────────────────────────────────────

class TestMapping:

    def test_every_code_is_classified(self, attdb):
        rows = census.mapping()
        assert len(rows) == len(codes.MARK_CODES)
        assert all(r.national_class in census.NATIONAL_CLASSES
                   for r in rows)

    @pytest.mark.parametrize("code,national", [
        ("/", census.PRESENT),
        ("L", census.PRESENT),
        ("B", census.APPROVED),
        ("W", census.APPROVED),
        ("I", census.AUTHORISED),
        ("O", census.UNAUTHORISED),
        ("U", census.UNAUTHORISED),
        ("X", census.NOT_COUNTED),
        ("Y", census.NOT_COUNTED),
    ])
    def test_codes_map_to_their_class(self, attdb, code, national):
        assert census.classify(code) == national

    def test_an_unknown_code_classifies_unfavourably(self, attdb):
        # A return should never be improved by a gap in the data.
        assert census.classify(None) == census.UNAUTHORISED
        assert census.classify("Q") == census.UNAUTHORISED

    def test_the_mapping_prints_as_a_table(self, attdb):
        table = census.mapping_table()
        assert "Return class" in table
        assert "Illness" in table


# ── 2. Building ────────────────────────────────────────────────────

class TestBuilding:

    def test_a_census_extract_counts_sessions(self, attdb):
        full_register(attdb, attdb.prev_monday)
        built = census.census_extract(date_from=attdb.prev_monday,
                                      date_to=attdb.prev_monday)
        row = next(r for r in built.rows if r.student_id == attdb.s1)
        assert row.sessions_possible == 2
        assert row.sessions_attended == 2
        assert row.attendance_pct == 100.0

    def test_absence_is_split_by_class(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "I"}}, allow_retro=True)
        core.save_register(attdb.pm_slot, attdb.prev_monday,
                           {attdb.s1: {"code": "O"}}, allow_retro=True)
        built = census.census_extract(date_from=attdb.prev_monday,
                                      date_to=attdb.prev_monday)
        row = next(r for r in built.rows if r.student_id == attdb.s1)
        assert row.authorised == 1
        assert row.unauthorised == 1
        assert row.attendance_pct == 0.0

    def test_not_counted_codes_leave_the_denominator(self, attdb):
        full_register(attdb, attdb.prev_monday, code="Y")
        built = census.census_extract(date_from=attdb.prev_monday,
                                      date_to=attdb.prev_monday)
        row = next(r for r in built.rows if r.student_id == attdb.s1)
        assert row.sessions_possible == 0
        assert row.not_counted == 2

    def test_an_ilr_extract_carries_hours(self, attdb):
        full_register(attdb, attdb.prev_monday)
        built = census.ilr_extract(date_from=attdb.prev_monday,
                                   date_to=attdb.prev_monday)
        row = next(r for r in built.rows if r.student_id == attdb.s1)
        assert row.hours_attended > 0
        assert row.hours_possible >= row.hours_attended

    def test_a_backwards_range_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="cannot end before"):
            census.census_extract(date_from=attdb.monday,
                                  date_to=attdb.prev_monday)

    def test_the_summary_reads_sensibly(self, attdb):
        full_register(attdb, attdb.prev_monday)
        built = census.census_extract(date_from=attdb.prev_monday,
                                      date_to=attdb.prev_monday)
        assert "CENSUS" in built.summary


# ── 3. Validation ──────────────────────────────────────────────────

class TestValidation:

    def test_a_complete_return_is_submittable(self, attdb):
        full_register(attdb, attdb.prev_monday)
        built = census.census_extract(date_from=attdb.prev_monday,
                                      date_to=attdb.prev_monday)
        assert built.submittable is True

    def test_missing_registers_are_an_error(self, attdb):
        # Only one of the two Monday lessons is marked.
        core.save_register(attdb.slot, attdb.prev_monday,
                           {sid: {"code": "/"} for sid in attdb.students},
                           allow_retro=True)
        built = census.census_extract(date_from=attdb.prev_monday,
                                      date_to=attdb.prev_monday)
        assert built.submittable is False
        assert any(f.check == "Register coverage" for f in built.errors)

    def test_undecided_absences_are_a_warning(self, attdb):
        # `N` is not a return category, it is an admission nobody chased.
        full_register(attdb, attdb.prev_monday, code="N")
        built = census.census_extract(date_from=attdb.prev_monday,
                                      date_to=attdb.prev_monday)
        assert any(f.check == "Undecided absences" for f in built.warnings)

    def test_a_range_with_no_teaching_days_is_an_error(self, attdb):
        import datetime as _dt
        saturday = attdb.monday
        # Find an actual weekend day.
        day = _dt.date.fromisoformat(attdb.monday)
        while day.weekday() < 5:
            day += _dt.timedelta(days=1)
        saturday = day.isoformat()
        built = census.census_extract(date_from=saturday, date_to=saturday)
        assert any(f.check == "Date range" for f in built.errors)

    def test_the_validation_report_states_the_verdict(self, attdb):
        full_register(attdb, attdb.prev_monday)
        built = census.census_extract(date_from=attdb.prev_monday,
                                      date_to=attdb.prev_monday)
        report = census.validation_report(built)
        assert "SUBMITTABLE" in report

    def test_a_failing_return_says_so_loudly(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "/"}}, allow_retro=True)
        built = census.census_extract(date_from=attdb.prev_monday,
                                      date_to=attdb.prev_monday)
        assert "NOT SUBMITTABLE" in census.validation_report(built)


# ── 4. Export ──────────────────────────────────────────────────────

class TestExport:

    def test_a_clean_return_exports(self, attdb):
        full_register(attdb, attdb.prev_monday)
        built = census.census_extract(date_from=attdb.prev_monday,
                                      date_to=attdb.prev_monday)
        text = census.to_csv(built)
        assert text.startswith("student_id,")
        assert attdb.s1 in text

    def test_a_return_with_errors_refuses_to_export(self, attdb):
        # Producing a file that looks submittable is the one thing this
        # module must not do.
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "/"}}, allow_retro=True)
        built = census.census_extract(date_from=attdb.prev_monday,
                                      date_to=attdb.prev_monday)
        with pytest.raises(core.ValidationError, match="validation error"):
            census.to_csv(built)

    def test_the_ilr_export_uses_its_own_columns(self, attdb):
        full_register(attdb, attdb.prev_monday)
        built = census.ilr_extract(date_from=attdb.prev_monday,
                                   date_to=attdb.prev_monday)
        assert census.to_csv(built).startswith("student_id,student_name,"
                                               "year_group,hours_possible")

    def test_a_return_can_be_saved(self, attdb, tmp_path):
        full_register(attdb, attdb.prev_monday)
        built = census.census_extract(date_from=attdb.prev_monday,
                                      date_to=attdb.prev_monday)
        path = census.save(built, str(tmp_path / "census.csv"))
        assert (tmp_path / "census.csv").read_text().startswith("student_id")
        assert path.endswith("census.csv")

    def test_the_return_aggregates_by_year_group(self, attdb):
        full_register(attdb, attdb.prev_monday)
        built = census.census_extract(date_from=attdb.prev_monday,
                                      date_to=attdb.prev_monday)
        summary = census.summary_by_year_group(built)
        assert summary
        assert all("attendance_pct" in entry for entry in summary.values())

    def test_code_usage_is_countable(self, attdb):
        full_register(attdb, attdb.prev_monday)
        usage = census.code_usage(date_from=attdb.prev_monday,
                                  date_to=attdb.prev_monday)
        assert usage["/"] == 6
