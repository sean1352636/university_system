"""Academic year, terms and breaks (domain.academics.academic_year.academic_year)."""

from __future__ import annotations

import pytest

from education_system.systems.primary.domain.academics.academic_year import academic_year as AY

# 2025-09-01 is a Monday.
SHORT = {"name": "Sept fortnight", "start_date": "2025-09-01", "end_date": "2025-09-14"}


def _year(name="2025/26", start="2025-09-01", end="2026-07-17", **extra):
    return AY.create_year({"name": name, "start_date": start, "end_date": end, **extra})


def _term(year, name="Autumn", start="2025-09-01", end="2025-12-19", **extra):
    return AY.create_term({"year_id": year.year_id, "name": name, "start_date": start,
                           "end_date": end, **extra})


def _break(year, name="Half term", start="2025-10-27", end="2025-10-31", **extra):
    return AY.create_break({"year_id": year.year_id, "name": name, "start_date": start,
                            "end_date": end, **extra})


# ── empty database ──

def test_empty_db():
    assert AY.list_years() == []
    assert AY.current_year() is None
    assert AY.get_year(1) is None
    assert AY.get_year_by_name("2025/26") is None
    assert AY.list_terms() == []
    assert AY.list_breaks() == []
    assert AY.get_term(1) is None
    assert AY.get_break(1) is None
    assert AY.delete_year(1) is False
    assert AY.delete_term(1) is False
    assert AY.delete_break(1) is False


# ── years ──

def test_create_year_stores_fields_and_defaults():
    y = _year(notes=" first ")
    assert (y.name, y.start_date, y.end_date, y.status, y.is_current, y.notes) == (
        "2025/26", "2025-09-01", "2026-07-17", "Planning", False, "first")
    assert AY.get_year(y.year_id) == y
    assert AY.get_year_by_name(" 2025/26 ") == y


def test_day_count_is_inclusive():
    assert _year(**{k: v for k, v in SHORT.items() if k != "name"}, name="x1").day_count == 14


def test_year_name_required_and_shape():
    with pytest.raises(AY.ValidationError, match="Name is required"):
        _year(name=" ")
    with pytest.raises(AY.ValidationError, match="2–32 chars"):
        _year(name="2025*26")


def test_year_dates_required_and_real():
    with pytest.raises(AY.ValidationError, match="Start date is required"):
        _year(start="")
    with pytest.raises(AY.ValidationError, match="End date must be YYYY-MM-DD"):
        _year(end="17/07/2026")
    with pytest.raises(AY.ValidationError, match="not a real date"):
        _year(start="2025-02-30")


def test_year_end_must_be_after_start():
    with pytest.raises(AY.ValidationError, match="End date must be after start date"):
        _year(start="2025-09-01", end="2025-09-01")


def test_year_status_must_be_known():
    with pytest.raises(AY.ValidationError, match="Status must be one of"):
        _year(status="Done")


def test_duplicate_year_name_refused():
    _year()
    with pytest.raises(AY.ValidationError, match="already exists"):
        _year(start="2026-09-01", end="2027-07-16")


def test_only_one_current_year():
    a = _year(is_current=True)
    b = _year("2026/27", "2026-09-01", "2027-07-16", is_current=True)
    assert AY.get_year(a.year_id).is_current is False
    assert AY.current_year() == AY.get_year(b.year_id)
    AY.set_current(a.year_id)
    assert AY.current_year().year_id == a.year_id
    assert AY.get_year(b.year_id).is_current is False
    AY.clear_current()
    assert AY.current_year() is None


def test_set_current_unknown():
    with pytest.raises(AY.ValidationError, match="No academic year #5"):
        AY.set_current(5)


def test_list_years_newest_first_and_status_filter():
    a = _year(status="Archived")
    b = _year("2026/27", "2026-09-01", "2027-07-16", status="Active")
    assert [y.year_id for y in AY.list_years()] == [b.year_id, a.year_id]
    assert [y.year_id for y in AY.list_years(status="Archived")] == [a.year_id]
    with pytest.raises(AY.ValidationError, match="Status must be one of"):
        AY.list_years(status="Old")


def test_update_year_merges_and_checks():
    a = _year()
    _year("2026/27", "2026-09-01", "2027-07-16", is_current=True)
    out = AY.update_year(a.year_id, {"status": "Active", "is_current": True})
    assert (out.name, out.status, out.is_current) == ("2025/26", "Active", True)
    assert [y.year_id for y in AY.list_years() if y.is_current] == [a.year_id]
    with pytest.raises(AY.ValidationError, match="already exists"):
        AY.update_year(a.year_id, {"name": "2026/27"})
    with pytest.raises(AY.ValidationError, match="after start date"):
        AY.update_year(a.year_id, {"end_date": "2025-08-01"})
    with pytest.raises(AY.ValidationError, match="No academic year #99"):
        AY.update_year(99, {})


def test_delete_year_cascades_terms_and_breaks():
    y = _year()
    t = _term(y)
    b = _break(y)
    assert AY.delete_year(y.year_id) is True
    assert AY.get_year(y.year_id) is None
    assert AY.get_term(t.term_id) is None
    assert AY.get_break(b.break_id) is None


# ── terms ──

def test_create_term_and_list_in_date_order():
    y = _year()
    spring = _term(y, "Spring", "2026-01-05", "2026-03-27")
    autumn = _term(y, "Autumn", notes=" busy ")
    assert autumn.notes == "busy"
    assert autumn.day_count == 110
    assert [t.name for t in AY.list_terms(year_id=y.year_id)] == ["Autumn", "Spring"]
    assert AY.get_term(spring.term_id) == spring


def test_list_terms_filtered_by_year():
    a = _year()
    b = _year("2026/27", "2026-09-01", "2027-07-16")
    _term(a)
    _term(b, start="2026-09-01", end="2026-12-18")
    assert len(AY.list_terms()) == 2
    assert [t.year_id for t in AY.list_terms(year_id=b.year_id)] == [b.year_id]


def test_term_custom_name_allowed_up_to_32_chars():
    y = _year()
    assert _term(y, name="Michaelmas").name == "Michaelmas"
    with pytest.raises(AY.ValidationError, match="1–32 chars"):
        _term(y, name="x" * 33)


def test_term_needs_a_real_year():
    with pytest.raises(AY.ValidationError, match="Year is required"):
        AY.create_term({"name": "Autumn", "start_date": "2025-09-01",
                        "end_date": "2025-12-19"})
    with pytest.raises(AY.ValidationError, match="Year id must be a number"):
        AY.create_term({"year_id": "abc", "name": "Autumn",
                        "start_date": "2025-09-01", "end_date": "2025-12-19"})
    with pytest.raises(AY.ValidationError, match="No academic year #8"):
        AY.create_term({"year_id": 8, "name": "Autumn",
                        "start_date": "2025-09-01", "end_date": "2025-12-19"})


def test_term_dates_order_and_within_year():
    y = _year()
    with pytest.raises(AY.ValidationError, match="cannot be before start"):
        _term(y, start="2025-12-19", end="2025-09-01")
    with pytest.raises(AY.ValidationError, match="Term must lie within the year"):
        _term(y, start="2025-08-20", end="2025-12-19")
    with pytest.raises(AY.ValidationError, match="Term must lie within the year"):
        _term(y, name="Summer", start="2026-04-13", end="2026-07-31")


def test_one_day_term_allowed():
    y = _year()
    assert _term(y, start="2025-09-01", end="2025-09-01").day_count == 1


def test_duplicate_term_name_in_year_refused():
    y = _year()
    _term(y)
    with pytest.raises(AY.ValidationError, match="already exists for this year"):
        _term(y, start="2025-09-02", end="2025-09-03")


def test_update_term():
    y = _year()
    t = _term(y)
    s = _term(y, "Spring", "2026-01-05", "2026-03-27")
    out = AY.update_term(t.term_id, {"end_date": "2025-12-17", "notes": "short"})
    assert (out.name, out.end_date, out.notes) == ("Autumn", "2025-12-17", "short")
    with pytest.raises(AY.ValidationError, match="already exists"):
        AY.update_term(s.term_id, {"name": "Autumn"})
    with pytest.raises(AY.ValidationError, match="No term #77"):
        AY.update_term(77, {})


def test_delete_term():
    t = _term(_year())
    assert AY.delete_term(t.term_id) is True
    assert AY.get_term(t.term_id) is None


# ── breaks ──

def test_create_break_defaults_to_holiday():
    y = _year()
    b = _break(y, notes=" ")
    assert (b.name, b.type, b.notes, b.day_count) == ("Half term", "Holiday", None, 5)
    assert AY.get_break(b.break_id) == b


def test_break_validation():
    y = _year()
    with pytest.raises(AY.ValidationError, match="Name is required"):
        _break(y, name="")
    with pytest.raises(AY.ValidationError, match="Type must be one of"):
        _break(y, type="Snow day")
    with pytest.raises(AY.ValidationError, match="cannot be before start"):
        _break(y, start="2025-10-31", end="2025-10-27")
    with pytest.raises(AY.ValidationError, match="Break must lie within the year"):
        _break(y, start="2026-07-20", end="2026-08-31")
    with pytest.raises(AY.ValidationError, match="No academic year #3"):
        AY.create_break({"year_id": 3, "name": "x", "start_date": "2025-10-27",
                         "end_date": "2025-10-31"})


def test_list_breaks_order_and_type_filter():
    y = _year()
    xmas = _break(y, "Christmas", "2025-12-22", "2026-01-02")
    inset = _break(y, "INSET", "2025-09-01", "2025-09-01", type="INSET")
    assert [b.break_id for b in AY.list_breaks(year_id=y.year_id)] == [
        inset.break_id, xmas.break_id]
    assert [b.break_id for b in AY.list_breaks(type="INSET")] == [inset.break_id]
    with pytest.raises(AY.ValidationError, match="Type must be one of"):
        AY.list_breaks(type="Strike")


def test_update_and_delete_break():
    y = _year()
    b = _break(y)
    out = AY.update_break(b.break_id, {"type": "Half-Term", "name": "Oct half term"})
    assert (out.type, out.name, out.start_date) == ("Half-Term", "Oct half term",
                                                    "2025-10-27")
    with pytest.raises(AY.ValidationError, match="Type must be one of"):
        AY.update_break(b.break_id, {"type": "nope"})
    with pytest.raises(AY.ValidationError, match="No break #50"):
        AY.update_break(50, {})
    assert AY.delete_break(b.break_id) is True
    assert AY.list_breaks() == []


# ── lookups ──

def test_find_term_on_and_is_break():
    y = _year()
    autumn = _term(y)
    half = _break(y)
    assert AY.find_term_on(y.year_id, "2025-10-01") == autumn
    assert AY.find_term_on(y.year_id, "2025-12-19") == autumn       # inclusive end
    assert AY.find_term_on(y.year_id, "2025-12-25") is None
    assert AY.is_break(y.year_id, "2025-10-27") == half
    assert AY.is_break(y.year_id, "2025-11-03") is None
    with pytest.raises(AY.ValidationError, match="Date must be YYYY-MM-DD"):
        AY.find_term_on(y.year_id, "1 Oct")


def test_teaching_days_counts_weekdays_outside_breaks():
    y = AY.create_year(SHORT)                       # Mon 1 → Sun 14 Sept: 10 weekdays
    assert AY.teaching_days_in(y.year_id) == 10
    _break(y, "Closure", "2025-09-03", "2025-09-06")    # Wed–Sat: 3 weekdays lost
    assert AY.teaching_days_in(y.year_id) == 7
    assert AY.teaching_days_in(y.year_id, date_from="2025-09-08") == 5
    assert AY.teaching_days_in(y.year_id, date_from="2025-09-01",
                               date_to="2025-09-02") == 2
    assert AY.teaching_days_in(y.year_id, date_from="2025-09-10",
                               date_to="2025-09-09") == 0


def test_teaching_days_unknown_year():
    with pytest.raises(AY.ValidationError, match="No academic year #4"):
        AY.teaching_days_in(4)


def test_year_summary_figures():
    y = AY.create_year(SHORT)
    _break(y, "Closure", "2025-09-03", "2025-09-06")
    _term(y, "Autumn 1", "2025-09-01", "2025-09-12")
    s = AY.year_summary(y.year_id)
    assert s.year == y
    assert [t.name for t in s.terms] == ["Autumn 1"]
    assert [b.name for b in s.breaks] == ["Closure"]
    assert (s.teaching_days, s.non_teaching_days, s.weekend_days) == (7, 3, 4)
    with pytest.raises(AY.ValidationError, match="No academic year #9"):
        AY.year_summary(9)
