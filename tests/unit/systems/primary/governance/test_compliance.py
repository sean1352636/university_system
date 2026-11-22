"""Compliance register (domain.governance.compliance.compliance)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.governance.compliance import compliance as C

TODAY = dt.date.today()


def _iso(days: int) -> str:
    return (TODAY + dt.timedelta(days=days)).isoformat()


def _item(title="Safeguarding policy review", category="Policy", **extra):
    return C.create_item({"title": title, "category": category, **extra})


# ── create / read ──

def test_create_item_defaults():
    i = _item("  Fire drill log ", "Health & Safety")
    assert i.title == "Fire drill log" and i.category == "Health & Safety"
    assert i.status == C.DEFAULT_STATUS == "Action required"
    assert i.frequency == C.DEFAULT_FREQUENCY == "Annual"
    assert i.owner is None and i.due_date is None and i.next_review is None
    assert C.get_item(i.item_id) == i


def test_create_item_stores_fields():
    i = _item(owner=" Head ", status="In progress", frequency="Termly",
              due_date="2026-12-01", notes=" check ")
    assert (i.owner, i.status, i.frequency) == ("Head", "In progress", "Termly")
    assert (i.due_date, i.notes) == ("2026-12-01", "check")


@pytest.mark.parametrize("frequency, expected", [
    ("Monthly", "2026-01-31"), ("Termly", "2026-05-01"),
    ("Annual", "2027-01-01"), ("Biennial", "2028-01-01"), ("Once", None),
])
def test_create_derives_next_review_from_last_review(frequency, expected):
    i = _item(frequency=frequency, last_review="2026-01-01")
    assert i.next_review == expected


def test_explicit_next_review_wins_over_derived():
    i = _item(last_review="2026-01-01", next_review="2026-03-01")
    assert i.next_review == "2026-03-01"


def test_get_missing_item_is_none():
    assert C.get_item(123) is None


# ── validation ──

def test_category_required_and_known():
    with pytest.raises(C.ValidationError, match="Category must be one of"):
        C.create_item({"title": "x"})
    with pytest.raises(C.ValidationError, match="Category must be one of"):
        _item(category="Catering")


def test_title_required_and_length():
    with pytest.raises(C.ValidationError, match="Title is required"):
        _item(title="  ")
    with pytest.raises(C.ValidationError, match="200 chars"):
        _item(title="t" * 201)


def test_owner_and_notes_lengths():
    with pytest.raises(C.ValidationError, match="Owner must be 100"):
        _item(owner="o" * 101)
    with pytest.raises(C.ValidationError, match="Notes must be 1000"):
        _item(notes="n" * 1001)


def test_status_and_frequency_must_be_known():
    with pytest.raises(C.ValidationError, match="Status must be one of"):
        _item(status="Overdue")      # derived only, never stored
    with pytest.raises(C.ValidationError, match="Frequency must be one of"):
        _item(frequency="Weekly")


def test_dates_must_be_iso():
    with pytest.raises(C.ValidationError, match="Due date must be YYYY-MM-DD"):
        _item(due_date="tomorrow")
    with pytest.raises(C.ValidationError, match="Last review must be YYYY-MM-DD"):
        _item(last_review="1/1/2026")
    with pytest.raises(C.ValidationError, match="Next review must be YYYY-MM-DD"):
        _item(next_review="2026/01/01")


# ── list / filter ──

def test_list_items_empty():
    assert C.list_items() == []


def test_list_items_sorted_by_next_review_then_due_then_undated_last():
    a = _item("A", next_review="2026-06-01")
    b = _item("B", due_date="2026-03-01")
    c = _item("C")
    d = _item("D", next_review="2026-01-01")
    assert [i.item_id for i in C.list_items()] == [d.item_id, b.item_id, a.item_id, c.item_id]


def test_list_items_filters():
    _item("Data retention", "Data", owner="DPO Smith", notes="annual purge")
    _item("Fire training", "Training", status="Compliant", owner="Site manager")
    assert [i.title for i in C.list_items(category="Data")] == ["Data retention"]
    assert [i.title for i in C.list_items(status="Compliant")] == ["Fire training"]
    assert [i.title for i in C.list_items(owner="smith")] == ["Data retention"]
    assert [i.title for i in C.list_items(query="purge")] == ["Data retention"]
    assert [i.title for i in C.list_items(query="Site")] == ["Fire training"]


def test_list_items_rejects_unknown_filter_values():
    with pytest.raises(C.ValidationError):
        C.list_items(category="Nope")
    with pytest.raises(C.ValidationError, match="Status must be one of"):
        C.list_items(status="Overdue")


def test_list_items_overdue_only():
    late = _item("late review", next_review=_iso(-1))
    late_due = _item("late due", due_date=_iso(-3))
    _item("review ok, due late", next_review=_iso(5), due_date=_iso(-10))
    _item("withdrawn", next_review=_iso(-30), status="Withdrawn")
    _item("future", due_date=_iso(10))
    _item("today", due_date=_iso(0))
    got = {i.item_id for i in C.list_items(overdue_only=True)}
    assert got == {late.item_id, late_due.item_id}


# ── update / delete ──

def test_update_item_partial():
    i = _item(owner="Ann")
    out = C.update_item(i.item_id, {"status": "In progress"})
    assert out.status == "In progress" and out.owner == "Ann" and out.title == i.title


def test_update_item_empty_payload_is_noop():
    i = _item()
    assert C.update_item(i.item_id, {}) == i


def test_update_item_validates_and_requires_item():
    i = _item()
    with pytest.raises(C.ValidationError, match="Frequency"):
        C.update_item(i.item_id, {"frequency": "Daily"})
    with pytest.raises(C.ValidationError, match="No compliance item #77"):
        C.update_item(77, {"title": "x"})


def test_delete_item():
    i = _item()
    assert C.delete_item(i.item_id) is True
    assert C.get_item(i.item_id) is None
    assert C.delete_item(i.item_id) is False


# ── mark_reviewed ──

def test_mark_reviewed_bumps_by_frequency_and_marks_compliant():
    i = _item(frequency="Termly")
    out = C.mark_reviewed(i.item_id, reviewed_on="2026-02-01", notes="signed")
    assert out.last_review == "2026-02-01"
    assert out.next_review == "2026-06-01"          # +120 days
    assert out.status == "Compliant" and out.notes == "signed"


def test_mark_reviewed_once_clears_next_review_and_keeps_notes():
    i = _item(frequency="Once", next_review="2026-01-01", notes="keep me")
    out = C.mark_reviewed(i.item_id, reviewed_on="2026-02-01")
    assert out.next_review is None and out.notes == "keep me"


def test_mark_reviewed_defaults_to_today():
    i = _item(frequency="Annual")
    out = C.mark_reviewed(i.item_id)
    assert out.last_review == TODAY.isoformat()
    assert out.next_review == (TODAY + dt.timedelta(days=365)).isoformat()


def test_mark_reviewed_refusals():
    i = _item()
    with pytest.raises(C.ValidationError, match="Reviewed on must be YYYY-MM-DD"):
        C.mark_reviewed(i.item_id, reviewed_on="today")
    with pytest.raises(C.ValidationError, match="No compliance item #9"):
        C.mark_reviewed(9)


# ── derived views ──

def test_view_item_overdue_and_days():
    i = _item(next_review=_iso(-4), status="Compliant")
    v = C.view_item(i.item_id)
    assert v.derived_status == "Overdue" and v.days_until_due == -4
    assert v.item == i


def test_view_item_uses_due_date_when_no_next_review():
    i = _item(due_date=_iso(7))
    v = C.view_item(i.item_id)
    assert v.derived_status == "Action required" and v.days_until_due == 7


def test_withdrawn_never_overdue_and_undated_has_no_days():
    w = _item(next_review=_iso(-4), status="Withdrawn")
    n = _item("undated")
    assert C.view_item(w.item_id).derived_status == "Withdrawn"
    assert C.view_item(n.item_id).days_until_due is None


def test_view_missing_item_is_none():
    assert C.view_item(5) is None


def test_list_views_passes_filters():
    _item("pol", "Policy", next_review=_iso(-1))
    _item("fin", "Finance", next_review=_iso(-1))
    views = C.list_views(category="Finance")
    assert [v.item.title for v in views] == ["fin"]
    assert views[0].derived_status == "Overdue"


# ── summary ──

def test_summary_empty():
    s = C.summary()
    assert (s.total, s.overdue, s.due_soon, s.no_review_date) == (0, 0, 0, 0)
    assert s.by_category == {c: 0 for c in C.CATEGORIES}
    assert s.by_status == {st: 0 for st in C.DERIVED_STATUSES}


def test_summary_counts():
    _item("over", "Policy", next_review=_iso(-2))
    _item("soon", "Policy", next_review=_iso(30))
    _item("today", "Data", due_date=_iso(0))
    _item("far", "Data", next_review=_iso(31), status="Compliant")
    _item("none", "Training", status="In progress")
    _item("gone", "Finance", next_review=_iso(-9), status="Withdrawn")
    s = C.summary()
    assert s.total == 6
    assert s.overdue == 1
    assert s.due_soon == 2
    assert s.no_review_date == 1
    assert s.by_category["Policy"] == 2 and s.by_category["Data"] == 2
    assert s.by_status["Overdue"] == 1
    assert s.by_status["Action required"] == 2
    assert s.by_status["Compliant"] == 1 and s.by_status["Withdrawn"] == 1
    assert s.by_status["In progress"] == 1


def test_summary_due_soon_window_is_configurable():
    _item("in 10", next_review=_iso(10))
    assert C.summary(due_soon_days=9).due_soon == 0
    assert C.summary(due_soon_days=10).due_soon == 1
