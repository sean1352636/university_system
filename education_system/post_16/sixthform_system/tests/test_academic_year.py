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

from education_system.post_16.sixthform_system.modules.domain.academics.academic_year import (
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
    from education_system.shared.api.sixthform.routes.academic_year_routes import (
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
