"""To-do list (systems.primary.domain.operations.todo.todo)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.operations.todo import todo as TD

TODAY = dt.date.today()


def _iso(days: int) -> str:
    return (TODAY + dt.timedelta(days=days)).isoformat()


def _todo(title="Ring parent", **extra):
    return TD.create_todo({"title": title, **extra})


# ── create / get ──

def test_create_stores_every_field_and_applies_defaults():
    t = TD.create_todo({"title": "  Order books  ", "description": " For Y3 ",
                        "owner": " ann ", "assignee": " bob ",
                        "category": " Admissions ", "due_date": "2030-01-10"})
    got = TD.get_todo(t.todo_id)
    assert got == t
    assert (got.title, got.description, got.owner, got.assignee) == \
        ("Order books", "For Y3", "ann", "bob")
    assert (got.status, got.priority, got.category, got.due_date) == \
        ("Open", "Normal", "Admissions", "2030-01-10")
    assert got.completed_at is None
    assert got.is_open


def test_blank_optional_fields_store_none():
    t = _todo(description="  ", assignee="", category="  ", due_date="")
    assert (t.description, t.assignee, t.category, t.due_date) == (None, None, None, None)
    assert t.owner == ""


def test_create_as_done_stamps_completed_today():
    t = _todo(status="Done")
    assert t.completed_at == TODAY.isoformat()
    assert not t.is_open


def test_get_missing_returns_none():
    assert TD.get_todo(999) is None


# ── validation ──

def test_title_is_required():
    with pytest.raises(TD.ValidationError, match="Title is required"):
        TD.create_todo({"title": "   "})


def test_title_length_limit():
    _todo("x" * TD.MAX_TITLE_LEN)
    with pytest.raises(TD.ValidationError, match="Title must be 200"):
        _todo("x" * (TD.MAX_TITLE_LEN + 1))


def test_owner_and_assignee_length_limit():
    with pytest.raises(TD.ValidationError, match="Owner must be 60"):
        _todo(owner="o" * 61)
    with pytest.raises(TD.ValidationError, match="Assignee must be 60"):
        _todo(assignee="a" * 61)


def test_category_length_limit():
    with pytest.raises(TD.ValidationError, match="Category must be 60"):
        _todo(category="c" * 61)


def test_status_must_be_known():
    with pytest.raises(TD.ValidationError, match="Status must be one of"):
        _todo(status="Finished")


def test_priority_must_be_known():
    with pytest.raises(TD.ValidationError, match="Priority must be one of"):
        _todo(priority="Critical")


def test_due_date_format():
    with pytest.raises(TD.ValidationError, match="Due date must be YYYY-MM-DD"):
        _todo(due_date="10/01/2030")


# ── overdue property ──

def test_is_overdue_only_for_open_past_due():
    assert _todo(due_date=_iso(-1)).is_overdue
    assert not _todo(due_date=TODAY.isoformat()).is_overdue
    assert not _todo(due_date=_iso(-1), status="Done").is_overdue
    assert not _todo(due_date=_iso(-1), status="Cancelled").is_overdue
    assert _todo(due_date=_iso(-1), status="Blocked").is_overdue
    assert not _todo().is_overdue


# ── listing ──

def test_list_orders_open_first_then_priority_then_due_then_newest():
    done = _todo("done", priority="Urgent", status="Done")
    low = _todo("low", priority="Low")
    urgent = _todo("urgent", priority="Urgent")
    high_late = _todo("high late", priority="High", due_date="2030-05-01")
    high_soon = _todo("high soon", priority="High", due_date="2030-01-01")
    high_none_a = _todo("high none a", priority="High")
    high_none_b = _todo("high none b", priority="High")
    ids = [t.todo_id for t in TD.list_todos()]
    assert ids == [urgent.todo_id, high_soon.todo_id, high_late.todo_id,
                   high_none_b.todo_id, high_none_a.todo_id, low.todo_id, done.todo_id]


def test_list_filters():
    a = _todo("a", owner="ann", assignee="bob", priority="High", category="Pastoral",
              due_date="2030-03-01")
    b = _todo("b", owner="bob", status="In Progress", category="Admissions",
              due_date="2030-03-05")
    c = _todo("c", owner="ann", status="Done")
    d = _todo("d", owner="ann", status="Cancelled", due_date=_iso(-5))
    e = _todo("e", owner="ann", status="Blocked", due_date=_iso(-2))

    def ids(**kw):
        return {t.todo_id for t in TD.list_todos(**kw)}

    assert ids(status="Done") == {c.todo_id}
    assert ids(owner=" ann ") == {a.todo_id, c.todo_id, d.todo_id, e.todo_id}
    assert ids(assignee="bob") == {a.todo_id}
    assert ids(priority="High") == {a.todo_id}
    assert ids(category="Admissions") == {b.todo_id}
    assert ids(open_only=True) == {a.todo_id, b.todo_id, e.todo_id}
    assert ids(overdue_only=True) == {e.todo_id}
    assert ids(due_on="2030-03-05") == {b.todo_id}
    assert ids(due_by="2030-03-01") == {a.todo_id, d.todo_id, e.todo_id}
    assert ids(owner="ann", open_only=True) == {a.todo_id, e.todo_id}


def test_list_rejects_bad_filters():
    with pytest.raises(TD.ValidationError, match="Status must be one of"):
        TD.list_todos(status="Nope")
    with pytest.raises(TD.ValidationError, match="Priority must be one of"):
        TD.list_todos(priority="Nope")
    with pytest.raises(TD.ValidationError, match="due_on must be YYYY-MM-DD"):
        TD.list_todos(due_on="tomorrow")
    with pytest.raises(TD.ValidationError, match="due_by must be YYYY-MM-DD"):
        TD.list_todos(due_by="1/1/2030")


def test_list_empty_database():
    assert TD.list_todos() == []


# ── search ──

def test_search_matches_every_text_field_newest_first():
    t1 = _todo("Order reading books")
    t2 = _todo("Plan trip", description="museum reading room")
    t3 = _todo("Call", category="Reading")
    t4 = _todo("Other", owner="reader")
    t5 = _todo("Misc", assignee="reading-lead")
    _todo("Unrelated")
    assert [t.todo_id for t in TD.search_todos("read")] == \
        [t5.todo_id, t4.todo_id, t3.todo_id, t2.todo_id, t1.todo_id]


def test_blank_search_lists_everything():
    _todo("a")
    _todo("b")
    assert len(TD.search_todos("  ")) == 2


# ── update / status ──

def test_update_merges_only_given_fields():
    t = _todo("Original", owner="ann", priority="High", category="Admin")
    out = TD.update_todo(t.todo_id, {"title": "Renamed"})
    assert (out.title, out.owner, out.priority, out.category) == \
        ("Renamed", "ann", "High", "Admin")


def test_update_validates_and_refuses_unknown_id():
    t = _todo()
    with pytest.raises(TD.ValidationError, match="Title is required"):
        TD.update_todo(t.todo_id, {"title": ""})
    with pytest.raises(TD.ValidationError, match="No todo with id 404"):
        TD.update_todo(404, {"title": "x"})


def test_mark_done_stamps_once_and_reopen_clears():
    t = _todo()
    done = TD.mark_done(t.todo_id)
    assert done.status == "Done" and done.completed_at == TODAY.isoformat()
    again = TD.update_todo(t.todo_id, {"title": "Still done"})
    assert again.completed_at == TODAY.isoformat()
    back = TD.reopen(t.todo_id)
    assert back.status == "Open" and back.completed_at is None


def test_set_status_refuses_unknown_status():
    t = _todo()
    with pytest.raises(TD.ValidationError, match="Status must be one of"):
        TD.set_status(t.todo_id, "Paused")
    assert TD.set_status(t.todo_id, "Blocked").status == "Blocked"


# ── delete / clear ──

def test_delete():
    t = _todo()
    assert TD.delete_todo(t.todo_id) is True
    assert TD.get_todo(t.todo_id) is None
    assert TD.delete_todo(t.todo_id) is False


def test_clear_completed_all_and_by_owner():
    _todo("a", owner="ann", status="Done")
    _todo("b", owner="ann", status="Cancelled")
    _todo("c", owner="bob", status="Done")
    keep = _todo("d", owner="ann")
    assert TD.clear_completed(owner="ann") == 2
    assert {t.title for t in TD.list_todos()} == {"c", "d"}
    assert TD.clear_completed() == 1
    assert [t.todo_id for t in TD.list_todos()] == [keep.todo_id]
    assert TD.clear_completed() == 0


# ── summary ──

def test_summary_counts():
    _todo("o1", owner="ann", priority="High", category="Admin", due_date=_iso(-3))
    _todo("o2", owner="ann", due_date=TODAY.isoformat())
    _todo("ip", owner="bob", status="In Progress", priority="Urgent", due_date=_iso(7))
    _todo("bl", status="Blocked", category="Admin", due_date=_iso(8))
    _todo("dn", owner="bob", status="Done", priority="Low", due_date=_iso(-9))
    _todo("cx", owner="ann", status="Cancelled", category="Trips")
    s = TD.summary()
    assert (s.total, s.open, s.in_progress, s.blocked, s.done, s.cancelled) == (6, 2, 1, 1, 1, 1)
    assert (s.overdue, s.due_today, s.due_within_7d) == (1, 1, 1)
    assert s.by_priority == {"Low": 1, "Normal": 3, "High": 1, "Urgent": 1}
    assert s.by_owner == {"ann": 3, "bob": 2, "(none)": 1}
    assert s.by_category == {"Admin": 2, "Trips": 1}


def test_summary_for_one_owner():
    _todo("a", owner="ann")
    _todo("b", owner="ann", status="Done")
    _todo("c", owner="bob")
    s = TD.summary(owner="ann")
    assert (s.total, s.open, s.done) == (2, 1, 1)
    assert s.by_owner == {"ann": 2}


def test_summary_empty():
    s = TD.summary()
    assert s.total == 0 and s.overdue == 0
    assert s.by_priority == {"Low": 0, "Normal": 0, "High": 0, "Urgent": 0}
    assert s.by_owner == {} and s.by_category == {}
