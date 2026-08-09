"""Tests for the Sixth Form Academic Year module.

Covers suggestion items 48-50:

* property-style tests on ``teaching_days_in()``
* JSON round-trip (export → wipe → import) preserves the shape
* ICS round-trip — emit then re-parse — round-trips term ranges
"""

from __future__ import annotations

import datetime as _dt
import json
import random
import pytest

from education_system.systems.sixth_form.domain.academics.academic_year import (
    academic_year_views as views,
)


# ── helpers ──────────────────────────────────────────────────────

def _seed_year(data, *, name="2025/26",
                 start="2025-09-01", end="2026-07-20"):
    return data.create_year({
        "name": name, "start_date": start, "end_date": end,
        "status": "Active", "is_current": True,
    })


def _add_term(data, yid, name, s, e, **kw):
    return data.create_term({
        "year_id": yid, "name": name,
        "start_date": s, "end_date": e, **kw,
    })


def _add_break(data, yid, name, s, e, *, type="Holiday", **kw):
    return data.create_break({
        "year_id": yid, "name": name, "type": type,
        "start_date": s, "end_date": e, **kw,
    })


# ── 48 — property tests on teaching_days_in() ────────────────────

@pytest.mark.parametrize("seed", range(8))
def test_teaching_days_extending_a_break_never_increases(
    fresh_ay_db, seed,
):
    """Property: lengthening a break can only reduce or leave teaching
    days unchanged. It must never increase them."""
    data = fresh_ay_db
    y = _seed_year(data)
    rng = random.Random(seed)

    # Random initial break of 1-5 days within the year.
    base = _dt.date(2025, 9, 1)
    start_off = rng.randint(10, 250)
    length = rng.randint(0, 4)
    s = base + _dt.timedelta(days=start_off)
    e = s + _dt.timedelta(days=length)
    b = _add_break(data, y.year_id, "Test",
                     s.isoformat(), e.isoformat())

    before = data.teaching_days_in(y.year_id)

    # Extend by a random 1..10 days.
    extra = rng.randint(1, 10)
    new_end = (e + _dt.timedelta(days=extra)).isoformat()
    if new_end > y.end_date:
        new_end = y.end_date
    data.update_break(b.break_id, {"end_date": new_end})
    after = data.teaching_days_in(y.year_id)

    assert after <= before, (
        f"seed={seed}: extending {b.start_date}..{e} → {new_end} "
        f"raised teaching days from {before} to {after}"
    )


def test_teaching_days_is_zero_window(fresh_ay_db):
    """Property: teaching days in an empty range is 0."""
    data = fresh_ay_db
    y = _seed_year(data)
    n = data.teaching_days_in(y.year_id,
                                  date_from="2026-01-15",
                                  date_to="2026-01-14")
    assert n == 0


def test_teaching_days_no_breaks_matches_weekday_count(fresh_ay_db):
    """Property: with zero breaks, teaching_days_in equals the count
    of weekdays in the window."""
    data = fresh_ay_db
    y = _seed_year(data)
    td = data.teaching_days_in(y.year_id)
    # Manual weekday count
    s = _dt.date.fromisoformat(y.start_date)
    e = _dt.date.fromisoformat(y.end_date)
    weekdays = sum(
        1 for n in range((e - s).days + 1)
        if (s + _dt.timedelta(days=n)).weekday() < 5)
    assert td == weekdays


def test_teaching_days_inset_subtracts_only_weekdays(fresh_ay_db):
    """Property: an INSET day on a Monday reduces teaching days by 1.
    The same INSET on a Saturday should not change the count."""
    data = fresh_ay_db
    y = _seed_year(data)
    baseline = data.teaching_days_in(y.year_id)
    # Find a Monday and a Saturday inside the year
    base = _dt.date.fromisoformat(y.start_date)
    monday = base + _dt.timedelta(days=(7 - base.weekday()) % 7)
    saturday = monday + _dt.timedelta(days=5)

    _add_break(data, y.year_id, "INSET Mon",
                 monday.isoformat(), monday.isoformat(),
                 type="INSET")
    after_mon = data.teaching_days_in(y.year_id)
    _add_break(data, y.year_id, "INSET Sat",
                 saturday.isoformat(), saturday.isoformat(),
                 type="INSET")
    after_sat = data.teaching_days_in(y.year_id)

    assert after_mon == baseline - 1
    assert after_sat == after_mon  # weekend INSET shouldn't reduce


# ── 49 — JSON round-trip ─────────────────────────────────────────

def test_export_then_import_round_trip(fresh_ay_db, tmp_path):
    """Export a populated year → wipe DB → import → same shape."""
    data = fresh_ay_db
    y = _seed_year(data)
    _add_term(data, y.year_id, "Autumn",
                "2025-09-01", "2025-12-19")
    _add_term(data, y.year_id, "Spring",
                "2026-01-05", "2026-03-27")
    _add_break(data, y.year_id, "Christmas",
                 "2025-12-22", "2026-01-02")
    _add_break(data, y.year_id, "Bank",
                 "2025-12-25", "2025-12-25", type="Bank Holiday")

    payload = {
        "schema": "sixthform.academic_year/v1",
        "year": {"name": y.name, "start_date": y.start_date,
                   "end_date": y.end_date, "status": "Planning",
                   "is_current": False, "notes": y.notes},
        "terms": [
            {"name": t.name, "start_date": t.start_date,
              "end_date": t.end_date, "notes": t.notes}
            for t in data.list_terms(year_id=y.year_id)
        ],
        "breaks": [
            {"name": b.name, "type": b.type,
              "start_date": b.start_date, "end_date": b.end_date,
              "notes": b.notes}
            for b in data.list_breaks(year_id=y.year_id)
        ],
    }
    path = tmp_path / "exp.json"
    path.write_text(json.dumps(payload))

    # Wipe by hard-deleting the year.
    data.delete_year(y.year_id, hard=True)
    assert data.list_years() == []

    # Re-import.
    loaded = json.loads(path.read_text())
    new_year = data.create_year({**loaded["year"],
                                       "is_current": False,
                                       "status": "Planning"})
    for t in loaded["terms"]:
        data.create_term({**t, "year_id": new_year.year_id})
    for b in loaded["breaks"]:
        data.create_break({**b, "year_id": new_year.year_id})

    assert new_year.name == y.name
    assert new_year.start_date == y.start_date
    new_terms = sorted(
        data.list_terms(year_id=new_year.year_id),
        key=lambda t: t.start_date)
    new_breaks = sorted(
        data.list_breaks(year_id=new_year.year_id),
        key=lambda b: b.start_date)
    assert [t.name for t in new_terms] == ["Autumn", "Spring"]
    assert [(b.name, b.type) for b in new_breaks] == [
        ("Christmas", "Holiday"),
        ("Bank", "Bank Holiday"),
    ]


# ── 50 — ICS golden round-trip ───────────────────────────────────

def test_ics_round_trip_terms(fresh_ay_db):
    """Emit an ICS for the year's terms, parse it back, dates match.

    ICS DTEND is exclusive so emission shifts +1; the parser shifts -1.
    Together they round-trip exactly."""
    data = fresh_ay_db
    y = _seed_year(data)
    _add_term(data, y.year_id, "Autumn",
                "2025-09-01", "2025-12-19")
    _add_term(data, y.year_id, "Spring",
                "2026-01-05", "2026-03-27")

    # Build ICS using the API blueprint helper (no Flask context needed).
    from education_system.systems.sixth_form.interfaces.api.routes.academic_year_routes import (
        _build_ics,
    )
    ics_body = _build_ics(y.year_id)
    assert "BEGIN:VCALENDAR" in ics_body
    assert "END:VCALENDAR" in ics_body

    parsed = views._parse_ics(ics_body)
    # Filter just the term events
    by_name = {p[0].split(" (")[0]: (p[1], p[2]) for p in parsed}
    assert by_name["Autumn"] == ("2025-09-01", "2025-12-19")
    assert by_name["Spring"] == ("2026-01-05", "2026-03-27")


def test_parse_ics_handles_line_folding(fresh_ay_db):
    """RFC-5545 line folding: continuation lines start with space/tab."""
    body = (
        "BEGIN:VCALENDAR\r\n"
        "BEGIN:VEVENT\r\n"
        "SUMMARY:Long event\r\n"
        " name that wraps\r\n"
        "DTSTART;VALUE=DATE:20250901\r\n"
        "DTEND;VALUE=DATE:20250906\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    out = views._parse_ics(body)
    assert len(out) == 1
    name, s, e = out[0]
    assert "Long event" in name
    # DTEND is exclusive in iCal; our parser shifts back by 1
    assert s == "2025-09-01"
    assert e == "2025-09-05"


# ═══════════════════════════════════════════════════════════════════
# Data-model additions (suggestion items 1-10)
# ═══════════════════════════════════════════════════════════════════

# ── 1 — Week A/B timetable cycle ─────────────────────────────────

def test_cycle_week_alternates_weekly_and_is_stable_within_a_week(
    fresh_ay_db,
):
    data = fresh_ay_db
    y = data.create_year({
        "name": "2025/26", "start_date": "2025-09-01",
        "end_date": "2026-07-20", "cycle_weeks": 2,
    })
    # 2025-09-01 is a Monday, so it anchors Week A.
    assert data.cycle_week_label(y.year_id, "2025-09-01") == "A"
    assert data.cycle_week_label(y.year_id, "2025-09-05") == "A"  # Fri
    assert data.cycle_week_label(y.year_id, "2025-09-08") == "B"
    assert data.cycle_week_label(y.year_id, "2025-09-15") == "A"


def test_cycle_week_is_one_for_a_weekly_timetable(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)          # cycle_weeks defaults to 1
    assert y.cycle_weeks == 1
    for iso in ("2025-09-01", "2025-09-08", "2026-03-02"):
        assert data.cycle_week_on(y.year_id, iso) == 1


def test_cycle_week_is_none_outside_the_year(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    assert data.cycle_week_on(y.year_id, "2025-08-01") is None
    assert data.cycle_week_label(y.year_id, "2027-01-01") is None


def test_cycle_anchor_must_be_a_monday(fresh_ay_db):
    data = fresh_ay_db
    with pytest.raises(data.ValidationError, match="Monday"):
        data.create_year({
            "name": "2025/26", "start_date": "2025-09-01",
            "end_date": "2026-07-20", "cycle_weeks": 2,
            "cycle_anchor": "2025-09-03",   # a Wednesday
        })


def test_cycle_anchor_shifts_which_week_is_a(fresh_ay_db):
    data = fresh_ay_db
    y = data.create_year({
        "name": "2025/26", "start_date": "2025-09-01",
        "end_date": "2026-07-20", "cycle_weeks": 2,
        "cycle_anchor": "2025-09-08",
    })
    assert data.cycle_week_label(y.year_id, "2025-09-08") == "A"
    assert data.cycle_week_label(y.year_id, "2025-09-01") == "B"


@pytest.mark.parametrize("bad", [0, -1, 99])
def test_cycle_weeks_out_of_range_rejected(fresh_ay_db, bad):
    data = fresh_ay_db
    with pytest.raises(data.ValidationError):
        data.create_year({
            "name": f"bad{bad}", "start_date": "2025-09-01",
            "end_date": "2026-07-20", "cycle_weeks": bad,
        })


# ── 2 — Teaching-week numbering ──────────────────────────────────

def test_week_number_counts_teaching_weeks_and_resets_per_term(
    fresh_ay_db,
):
    data = fresh_ay_db
    y = _seed_year(data)
    _add_term(data, y.year_id, "Autumn", "2025-09-01", "2025-12-19")
    _add_term(data, y.year_id, "Spring", "2026-01-05", "2026-03-27")

    wk = data.week_number_on(y.year_id, "2025-09-01")
    assert wk["year_week"] == 1
    assert wk["term_week"] == 1
    assert wk["term"] == "Autumn"

    wk = data.week_number_on(y.year_id, "2025-09-10")   # 2nd week
    assert wk["year_week"] == 2 and wk["term_week"] == 2

    # Spring restarts term numbering but not year numbering.
    wk = data.week_number_on(y.year_id, "2026-01-05")
    assert wk["term"] == "Spring"
    assert wk["term_week"] == 1
    assert wk["year_week"] > 2


def test_week_number_skips_a_fully_closed_week(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    _add_term(data, y.year_id, "Autumn", "2025-09-01", "2025-12-19")
    before = data.week_number_on(y.year_id, "2025-09-15")["term_week"]
    # Close the whole of week 2 (8th-12th Sept).
    _add_break(data, y.year_id, "Closure",
                 "2025-09-08", "2025-09-12", type="Holiday")
    after = data.week_number_on(y.year_id, "2025-09-15")["term_week"]
    assert after == before - 1


def test_week_number_is_none_outside_the_year(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    assert data.week_number_on(y.year_id, "2024-01-01") is None


# ── 3 — Periods (day shape) ──────────────────────────────────────

def _add_period(data, yid, name, wd, s, e, **kw):
    return data.create_period({
        "year_id": yid, "name": name, "weekday": wd,
        "start_time": s, "end_time": e, **kw,
    })


def test_periods_round_trip_and_report_duration(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    p = _add_period(data, y.year_id, "P1", 0, "09:00", "10:00")
    assert p.minutes == 60
    assert p.weekday_name == "Monday"
    assert [x.name for x in data.list_periods(year_id=y.year_id)] == ["P1"]


def test_overlapping_periods_on_the_same_day_rejected(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    _add_period(data, y.year_id, "P1", 0, "09:00", "10:00")
    with pytest.raises(data.ValidationError, match="Clashes"):
        _add_period(data, y.year_id, "P2", 0, "09:30", "10:30")
    # Abutting is fine — one ends exactly as the next starts.
    _add_period(data, y.year_id, "P2", 0, "10:00", "11:00")
    # A different weekday never clashes.
    _add_period(data, y.year_id, "P1", 1, "09:00", "10:00")


def test_periods_pinned_to_a_cycle_week_dont_clash_across_weeks(
    fresh_ay_db,
):
    data = fresh_ay_db
    y = data.create_year({
        "name": "2025/26", "start_date": "2025-09-01",
        "end_date": "2026-07-20", "cycle_weeks": 2,
    })
    _add_period(data, y.year_id, "Maths", 0, "09:00", "10:00",
                  cycle_week=1)
    _add_period(data, y.year_id, "Physics", 0, "09:00", "10:00",
                  cycle_week=2)
    # Week A (Mon 1 Sep) sees Maths; Week B (Mon 8 Sep) sees Physics.
    assert [p.name for p in data.periods_on(y.year_id, "2025-09-01")] \
        == ["Maths"]
    assert [p.name for p in data.periods_on(y.year_id, "2025-09-08")] \
        == ["Physics"]


def test_period_cycle_week_beyond_the_years_cycle_rejected(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)          # cycle_weeks == 1
    with pytest.raises(data.ValidationError, match="Cycle week"):
        _add_period(data, y.year_id, "P1", 0, "09:00", "10:00",
                      cycle_week=2)


@pytest.mark.parametrize("s,e", [("10:00", "09:00"), ("09:00", "09:00")])
def test_period_end_must_be_after_start(fresh_ay_db, s, e):
    data = fresh_ay_db
    y = _seed_year(data)
    with pytest.raises(data.ValidationError, match="after start"):
        _add_period(data, y.year_id, "P1", 0, s, e)


@pytest.mark.parametrize("bad", ["9:00", "25:00", "09:60", "morning"])
def test_period_time_format_enforced(fresh_ay_db, bad):
    data = fresh_ay_db
    y = _seed_year(data)
    with pytest.raises(data.ValidationError, match="HH:MM"):
        _add_period(data, y.year_id, "P1", 0, bad, "23:00")


def test_day_shape_trims_periods_on_a_half_day(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    _add_term(data, y.year_id, "Autumn", "2025-09-01", "2025-12-19")
    _add_period(data, y.year_id, "Morning", 0, "09:00", "11:00")
    _add_period(data, y.year_id, "Afternoon", 0, "13:00", "15:00")
    # A PM-only closure leaves the morning running.
    _add_break(data, y.year_id, "Staff training",
                 "2025-09-08", "2025-09-08", type="INSET", am_pm="PM")

    shape = data.day_shape(y.year_id, "2025-09-08")
    assert [p.name for p in shape["periods"]] == ["Morning"]
    assert shape["is_teaching_day"] is True
    assert shape["term"] == "Autumn"


def test_day_shape_has_no_periods_on_a_full_closure(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    _add_period(data, y.year_id, "Morning", 0, "09:00", "11:00")
    _add_break(data, y.year_id, "Bank Holiday",
                 "2025-09-08", "2025-09-08", type="Bank Holiday")
    shape = data.day_shape(y.year_id, "2025-09-08")
    assert shape["periods"] == []
    assert shape["is_teaching_day"] is False


# ── 4 — Per-year-group calendars ─────────────────────────────────

def _with_groups(data, yid):
    data.create_year_group(yid, "Y12")
    data.create_year_group(yid, "Y13")


def test_group_scoped_break_leaves_the_college_denominator_alone(
    fresh_ay_db,
):
    data = fresh_ay_db
    y = _seed_year(data)
    _with_groups(data, y.year_id)
    college = data.teaching_days_in(y.year_id)
    y12 = data.teaching_days_in(y.year_id, group_label="Y12")

    _add_break(data, y.year_id, "Y13 study leave",
                 "2026-05-04", "2026-05-15", type="Other",
                 group_label="Y13")

    # Y13 loses ten weekdays; Y12 and the college as a whole don't.
    assert data.teaching_days_in(y.year_id) == college
    assert data.teaching_days_in(y.year_id, group_label="Y12") == y12
    assert data.teaching_days_in(y.year_id, group_label="Y13") \
        == college - 10


def test_shared_breaks_apply_to_every_group(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    _with_groups(data, y.year_id)
    before = data.teaching_days_in(y.year_id, group_label="Y13")
    _add_break(data, y.year_id, "Christmas",
                 "2025-12-22", "2025-12-26")     # no group_label
    assert data.teaching_days_in(y.year_id, group_label="Y13") \
        == before - 5


def test_unknown_group_label_rejected(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    _with_groups(data, y.year_id)
    with pytest.raises(data.ValidationError, match="Unknown year group"):
        _add_break(data, y.year_id, "Oops", "2025-10-01", "2025-10-02",
                     group_label="Y14")


def test_group_label_needs_groups_to_exist_first(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    with pytest.raises(data.ValidationError, match="No year groups"):
        _add_break(data, y.year_id, "Oops", "2025-10-01", "2025-10-02",
                     group_label="Y13")


def test_group_specific_term_wins_over_the_college_wide_one(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    _with_groups(data, y.year_id)
    _add_term(data, y.year_id, "Summer", "2026-04-13", "2026-07-17")
    _add_term(data, y.year_id, "Summer (Y13)",
                "2026-04-13", "2026-05-29", group_label="Y13")

    assert data.find_term_on(y.year_id, "2026-05-01").name == "Summer"
    assert data.find_term_on(y.year_id, "2026-05-01",
                              group_label="Y13").name == "Summer (Y13)"


# ── 5 — Term overlap validation ──────────────────────────────────

def test_overlapping_terms_of_the_same_kind_rejected(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    _add_term(data, y.year_id, "Autumn", "2025-09-01", "2025-12-19")
    with pytest.raises(data.ValidationError, match="Overlaps"):
        _add_term(data, y.year_id, "Autumn extra",
                    "2025-12-15", "2026-01-30")


def test_abutting_terms_are_allowed(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    _add_term(data, y.year_id, "Autumn", "2025-09-01", "2025-12-19")
    _add_term(data, y.year_id, "Spring", "2025-12-20", "2026-03-27")


def test_a_different_kind_may_nest_inside_a_term(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    _add_term(data, y.year_id, "Autumn", "2025-09-01", "2025-12-19")
    # Mock exams sit inside the Autumn term — that's not a clash.
    _add_term(data, y.year_id, "Mocks", "2025-11-10", "2025-11-21",
                kind="Mock-Exam Week")


def test_different_year_groups_may_overlap(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    _with_groups(data, y.year_id)
    _add_term(data, y.year_id, "Summer Y12", "2026-04-13", "2026-07-17",
                group_label="Y12")
    _add_term(data, y.year_id, "Summer Y13", "2026-04-13", "2026-05-29",
                group_label="Y13")


def test_editing_a_term_doesnt_clash_with_itself(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    t = _add_term(data, y.year_id, "Autumn", "2025-09-01", "2025-12-19")
    out = data.update_term(t.term_id, {"end_date": "2025-12-18"})
    assert out.end_date == "2025-12-18"


def test_editing_a_term_into_another_is_rejected(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    _add_term(data, y.year_id, "Autumn", "2025-09-01", "2025-12-19")
    t2 = _add_term(data, y.year_id, "Spring", "2026-01-05", "2026-03-27")
    with pytest.raises(data.ValidationError, match="Overlaps"):
        data.update_term(t2.term_id, {"start_date": "2025-12-01"})


# ── 6 — Coverage gap detection ───────────────────────────────────

def test_gap_between_terms_not_covered_by_a_break_is_reported(
    fresh_ay_db,
):
    data = fresh_ay_db
    y = data.create_year({
        "name": "2025/26", "start_date": "2025-09-01",
        "end_date": "2025-10-31",
    })
    _add_term(data, y.year_id, "Autumn 1", "2025-09-01", "2025-10-17")
    # 20-31 Oct left uncovered, and no break declared for it.
    gaps = data.find_calendar_gaps(y.year_id)
    assert len(gaps) == 1
    assert gaps[0].start_date == "2025-10-20"
    assert gaps[0].end_date == "2025-10-31"
    assert gaps[0].weekdays == 10


def test_a_gap_explained_by_a_break_is_not_reported(fresh_ay_db):
    data = fresh_ay_db
    y = data.create_year({
        "name": "2025/26", "start_date": "2025-09-01",
        "end_date": "2025-10-31",
    })
    _add_term(data, y.year_id, "Autumn 1", "2025-09-01", "2025-10-17")
    _add_break(data, y.year_id, "Half-Term",
                 "2025-10-20", "2025-10-31", type="Half-Term")
    assert data.find_calendar_gaps(y.year_id) == []
    # …but it is still an uncovered stretch if you ask for the raw view.
    assert len(data.find_calendar_gaps(y.year_id,
                                        ignore_breaks=True)) == 1


def test_a_fully_covered_year_has_no_gaps(fresh_ay_db):
    data = fresh_ay_db
    y = data.create_year({
        "name": "2025/26", "start_date": "2025-09-01",
        "end_date": "2025-10-31",
    })
    _add_term(data, y.year_id, "Autumn", "2025-09-01", "2025-10-31")
    assert data.find_calendar_gaps(y.year_id) == []


def test_weekends_are_never_reported_as_gaps(fresh_ay_db):
    data = fresh_ay_db
    y = data.create_year({
        "name": "2025/26", "start_date": "2025-09-06",   # a Saturday
        "end_date": "2025-09-07",
    })
    assert data.find_calendar_gaps(y.year_id) == []


# ── 7 — Sixth-form event kinds ───────────────────────────────────

@pytest.mark.parametrize("kind", [
    "Interview", "Work Experience", "Enrichment", "Mock Results", "UCAS"])
def test_new_event_kinds_accepted(fresh_ay_db, kind):
    data = fresh_ay_db
    y = _seed_year(data)
    ev = data.create_event({
        "year_id": y.year_id, "name": f"{kind} day",
        "kind": kind, "date": "2025-10-01"})
    assert ev.kind == kind
    assert data.list_events(year_id=y.year_id, kind=kind) == [ev]


def test_unknown_event_kind_still_rejected(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    with pytest.raises(data.ValidationError, match="Event kind"):
        data.create_event({"year_id": y.year_id, "name": "x",
                            "kind": "Pizza Party", "date": "2025-10-01"})


# ── 8 — Recurring events ─────────────────────────────────────────

def test_weekly_event_expands_to_one_occurrence_per_week(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    ev = data.create_event({
        "year_id": y.year_id, "name": "Enrichment", "kind": "Enrichment",
        "date": "2025-09-03", "repeat_rule": "WEEKLY",
        "repeat_until": "2025-10-01"})
    occ = data.expand_event_occurrences(ev)
    assert [o.date for o in occ] == [
        "2025-09-03", "2025-09-10", "2025-09-17",
        "2025-09-24", "2025-10-01"]
    assert ev.is_recurring


def test_repeat_interval_skips_weeks(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    ev = data.create_event({
        "year_id": y.year_id, "name": "Fortnightly review",
        "date": "2025-09-03", "repeat_rule": "WEEKLY",
        "repeat_interval": 2, "repeat_until": "2025-10-01"})
    assert [o.date for o in data.expand_event_occurrences(ev)] == [
        "2025-09-03", "2025-09-17", "2025-10-01"]


def test_monthly_repeat_clamps_to_short_months(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    ev = data.create_event({
        "year_id": y.year_id, "name": "Month end",
        "date": "2025-12-31", "repeat_rule": "MONTHLY",
        "repeat_until": "2026-03-31"})
    assert [o.date for o in data.expand_event_occurrences(ev)] == [
        "2025-12-31", "2026-01-31", "2026-02-28", "2026-03-31"]


def test_occurrences_preserve_a_multi_day_events_length(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    ev = data.create_event({
        "year_id": y.year_id, "name": "Trip", "kind": "Trip",
        "date": "2025-09-03", "end_date": "2025-09-05",
        "repeat_rule": "WEEKLY", "repeat_until": "2025-09-17"})
    occ = data.expand_event_occurrences(ev)
    assert [(o.date, o.end_date) for o in occ] == [
        ("2025-09-03", "2025-09-05"),
        ("2025-09-10", "2025-09-12"),
        ("2025-09-17", "2025-09-19")]


def test_a_non_recurring_event_yields_exactly_itself(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    ev = data.create_event({
        "year_id": y.year_id, "name": "Results Day",
        "kind": "Results Day", "date": "2026-07-16"})
    occ = data.expand_event_occurrences(ev)
    assert len(occ) == 1 and occ[0].date == "2026-07-16"
    assert not ev.is_recurring


def test_open_ended_series_stops_at_the_end_of_the_year(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    ev = data.create_event({
        "year_id": y.year_id, "name": "Assembly",
        "date": "2025-09-01", "repeat_rule": "WEEKLY"})
    assert ev.repeat_until == y.end_date
    assert data.expand_event_occurrences(ev)[-1].date <= y.end_date


def test_repeat_until_outside_the_year_rejected(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    with pytest.raises(data.ValidationError, match="Repeat until"):
        data.create_event({
            "year_id": y.year_id, "name": "Assembly",
            "date": "2025-09-01", "repeat_rule": "WEEKLY",
            "repeat_until": "2030-01-01"})


def test_repeat_until_without_a_rule_rejected(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    with pytest.raises(data.ValidationError, match="needs a repeat rule"):
        data.create_event({
            "year_id": y.year_id, "name": "One-off",
            "date": "2025-09-01", "repeat_until": "2025-10-01"})


def test_events_on_finds_a_recurring_occurrence(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    data.create_event({
        "year_id": y.year_id, "name": "Enrichment",
        "date": "2025-09-03", "repeat_rule": "WEEKLY",
        "repeat_until": "2025-12-17"})
    assert [o.name for o in data.events_on(y.year_id, "2025-11-05")] \
        == ["Enrichment"]
    assert data.events_on(y.year_id, "2025-11-06") == []


def test_events_between_spans_a_window(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    data.create_event({
        "year_id": y.year_id, "name": "Enrichment",
        "date": "2025-09-03", "repeat_rule": "WEEKLY",
        "repeat_until": "2025-12-17"})
    out = data.events_between(y.year_id, "2025-10-01", "2025-10-31")
    assert len(out) == 5


# ── 9/10 — Event owner, department, location, capacity ───────────

def test_event_detail_round_trips(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    ev = data.create_event({
        "year_id": y.year_id, "name": "Open Evening",
        "kind": "Open Evening", "date": "2025-10-09",
        "owner": "J. Patel", "department": "Admissions",
        "location": "Main Hall", "capacity": 300})
    got = data.get_event(ev.event_id)
    assert (got.owner, got.department, got.location, got.capacity) == (
        "J. Patel", "Admissions", "Main Hall", 300)


def test_events_filter_by_owner_and_department(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    data.create_event({"year_id": y.year_id, "name": "A",
                        "date": "2025-10-01", "owner": "J. Patel",
                        "department": "Admissions"})
    data.create_event({"year_id": y.year_id, "name": "B",
                        "date": "2025-10-02", "owner": "R. Osei",
                        "department": "Science"})
    assert [e.name for e in data.list_events(year_id=y.year_id,
                                              owner="J. Patel")] == ["A"]
    assert [e.name for e in data.list_events(
        year_id=y.year_id, department="Science")] == ["B"]


def test_negative_capacity_rejected(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    with pytest.raises(data.ValidationError, match="Capacity"):
        data.create_event({"year_id": y.year_id, "name": "x",
                            "date": "2025-10-01", "capacity": -5})


def test_update_event_changes_detail_and_keeps_the_year(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    ev = data.create_event({
        "year_id": y.year_id, "name": "Open Evening",
        "kind": "Open Evening", "date": "2025-10-09", "capacity": 300})
    out = data.update_event(ev.event_id,
                              {"capacity": 350, "location": "Sports Hall"})
    assert out.capacity == 350
    assert out.location == "Sports Hall"
    assert out.year_id == y.year_id
    assert out.name == "Open Evening"       # untouched fields survive


def test_event_end_date_outside_the_year_rejected(fresh_ay_db):
    data = fresh_ay_db
    y = _seed_year(data)
    with pytest.raises(data.ValidationError, match="end inside the year"):
        data.create_event({
            "year_id": y.year_id, "name": "Long trip",
            "date": "2026-07-19", "end_date": "2026-08-30"})
