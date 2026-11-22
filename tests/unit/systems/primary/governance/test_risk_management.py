"""Risk register, actions and reviews (domain.governance.risk_management.risk_management)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.governance.risk_management import (
    risk_management as RM,
)

TODAY = dt.date.today()


def _iso(days: int) -> str:
    return (TODAY + dt.timedelta(days=days)).isoformat()


def _risk(title="Cyber attack", **extra):
    extra.setdefault("identified_date", "2026-01-01")
    return RM.create_risk({"title": title, **extra})


# ── score bands ──

@pytest.mark.parametrize("score, band", [
    (None, "—"), (0, "—"), (1, "Low"), (4, "Low"), (5, "Medium"), (9, "Medium"),
    (10, "High"), (14, "High"), (15, "Critical"), (25, "Critical"), (26, "—"),
])
def test_score_band(score, band):
    assert RM.score_band(score) == band


# ── create / read ──

def test_create_risk_defaults():
    r = RM.create_risk({"title": "  Flood  "})
    assert r.title == "Flood"
    assert (r.category, r.status, r.treatment) == ("Operational", "Identified", "Treat")
    assert (r.likelihood, r.impact, r.review_frequency_days) == (3, 3, 90)
    assert r.identified_date == TODAY.isoformat()
    assert r.next_review == _iso(90)
    assert r.residual_likelihood is None and r.residual_score is None
    assert r.inherent_score == 9 and r.inherent_band == "Medium" and r.residual_band == "—"
    assert r.is_open is True
    assert RM.get_risk(r.risk_id) == r


def test_create_risk_scores_and_fields():
    r = _risk(category="IT / Cyber", owner=" IT lead ", likelihood="4", impact=5,
              residual_likelihood=2, residual_impact="2", treatment="Transfer",
              controls=" MFA ", description=" d ", notes=" n ", status="Mitigating")
    assert (r.category, r.owner, r.controls, r.description, r.notes) == \
        ("IT / Cyber", "IT lead", "MFA", "d", "n")
    assert r.inherent_score == 20 and r.inherent_band == "Critical"
    assert r.residual_score == 4 and r.residual_band == "Low"
    assert (r.treatment, r.status) == ("Transfer", "Mitigating")


def test_next_review_from_last_reviewed_or_identified():
    assert _risk(review_frequency_days=30).next_review == "2026-01-31"
    assert _risk("b", last_reviewed="2026-02-01", review_frequency_days=10).next_review == \
        "2026-02-11"
    assert _risk("c", next_review="2026-07-01").next_review == "2026-07-01"


def test_get_missing_risk_is_none():
    assert RM.get_risk(3) is None


# ── risk validation ──

def test_title_required():
    with pytest.raises(RM.ValidationError, match="Title is required"):
        RM.create_risk({"title": " "})


@pytest.mark.parametrize("field, label", [
    ("likelihood", "Likelihood"), ("impact", "Impact"),
    ("residual_likelihood", "Residual likelihood"), ("residual_impact", "Residual impact"),
])
def test_scores_must_be_1_to_5(field, label):
    with pytest.raises(RM.ValidationError, match=f"{label} must be 1..5"):
        _risk(**{field: 0})
    with pytest.raises(RM.ValidationError, match=f"{label} must be 1..5"):
        _risk(**{field: 6})
    with pytest.raises(RM.ValidationError, match=f"{label} must be a whole number"):
        _risk(**{field: "high"})


def test_vocabularies_enforced():
    with pytest.raises(RM.ValidationError, match="Category must be one of"):
        _risk(category="Weather")
    with pytest.raises(RM.ValidationError, match="Status must be one of"):
        _risk(status="Open")
    with pytest.raises(RM.ValidationError, match="Treatment must be one of"):
        _risk(treatment="Ignore")


def test_review_frequency_range_and_dates():
    with pytest.raises(RM.ValidationError, match="1..3650"):
        _risk(review_frequency_days=0)
    with pytest.raises(RM.ValidationError, match="1..3650"):
        _risk(review_frequency_days=3651)
    with pytest.raises(RM.ValidationError, match="Identified date must be YYYY-MM-DD"):
        _risk(identified_date="Jan 1")
    with pytest.raises(RM.ValidationError, match="Last reviewed must be YYYY-MM-DD"):
        _risk(last_reviewed="x")
    with pytest.raises(RM.ValidationError, match="Next review must be YYYY-MM-DD"):
        _risk(next_review="x")


# ── list / filter ──

def test_list_risks_empty():
    assert RM.list_risks() == []


def test_list_risks_ordered_by_score_then_next_review():
    low = _risk("low", likelihood=1, impact=1)
    hi_late = _risk("hi late", likelihood=5, impact=4, next_review="2026-09-01")
    hi_soon = _risk("hi soon", likelihood=4, impact=5, next_review="2026-03-01")
    assert [r.risk_id for r in RM.list_risks()] == [hi_soon.risk_id, hi_late.risk_id, low.risk_id]


def test_list_risks_filters():
    a = _risk("Fire", category="Health & Safety", owner="Site manager",
              controls="alarms tested", likelihood=2, impact=5)
    b = _risk("Budget", category="Financial", status="Closed", likelihood=4, impact=4)
    c = _risk("Staffing", status="Accepted", notes="recruitment drive", likelihood=1, impact=2)
    ids = lambda rs: [r.risk_id for r in rs]  # noqa: E731
    assert ids(RM.list_risks(status="Closed")) == [b.risk_id]
    assert ids(RM.list_risks(category="Health & Safety")) == [a.risk_id]
    assert ids(RM.list_risks(owner="site")) == [a.risk_id]
    assert ids(RM.list_risks(open_only=True)) == [a.risk_id]
    assert ids(RM.list_risks(min_score=10)) == [b.risk_id, a.risk_id]
    assert ids(RM.list_risks(search="alarms")) == [a.risk_id]
    assert ids(RM.list_risks(search="recruitment")) == [c.risk_id]


def test_list_risks_review_due_only():
    due = _risk("due", next_review=_iso(0))
    _risk("later", next_review=_iso(1))
    assert [r.risk_id for r in RM.list_risks(review_due_only=True)] == [due.risk_id]
    assert RM.get_risk(due.risk_id).is_review_due is True


# ── update / delete ──

def test_update_risk_merges():
    r = _risk(owner="Ann", likelihood=2, impact=2)
    out = RM.update_risk(r.risk_id, {"impact": 5, "status": "Monitoring"})
    assert (out.likelihood, out.impact, out.inherent_score) == (2, 5, 10)
    assert out.status == "Monitoring" and out.owner == "Ann" and out.title == r.title
    assert out.next_review == r.next_review


def test_update_risk_can_clear_residuals():
    r = _risk(residual_likelihood=2, residual_impact=2)
    out = RM.update_risk(r.risk_id, {"residual_likelihood": None})
    assert out.residual_likelihood is None and out.residual_score is None


def test_update_risk_validates_and_requires_risk():
    r = _risk()
    with pytest.raises(RM.ValidationError, match="Likelihood must be 1..5"):
        RM.update_risk(r.risk_id, {"likelihood": 9})
    with pytest.raises(RM.ValidationError, match="No risk #77"):
        RM.update_risk(77, {"title": "x"})


def test_delete_risk_cascades_actions_and_reviews():
    r = _risk()
    a = RM.add_action(r.risk_id, {"description": "Patch"})
    v = RM.add_review(r.risk_id, {"review_date": "2026-02-01"})
    assert RM.delete_risk(r.risk_id) is True
    assert RM.get_risk(r.risk_id) is None
    assert RM.get_action(a.action_id) is None and RM.get_review(v.review_id) is None
    assert RM.delete_risk(r.risk_id) is False


# ── actions ──

def test_add_action_defaults_and_fields():
    r = _risk()
    a = RM.add_action(r.risk_id, {"description": "  Train staff ", "owner": " DSL ",
                                  "due_date": "2026-12-01", "evidence": " cert "})
    assert (a.risk_id, a.description, a.owner) == (r.risk_id, "Train staff", "DSL")
    assert (a.status, a.due_date, a.evidence, a.completed_date) == \
        ("Planned", "2026-12-01", "cert", None)
    assert RM.get_action(a.action_id) == a


def test_done_action_gets_completed_date():
    r = _risk()
    a = RM.add_action(r.risk_id, {"description": "x", "status": "Done"})
    assert a.completed_date == TODAY.isoformat() and a.is_done is True
    b = RM.add_action(r.risk_id, {"description": "y", "status": "Done",
                                  "completed_date": "2026-01-05"})
    assert b.completed_date == "2026-01-05"


def test_action_validation():
    r = _risk()
    with pytest.raises(RM.ValidationError, match="Description is required"):
        RM.add_action(r.risk_id, {"description": ""})
    with pytest.raises(RM.ValidationError, match="Status must be one of"):
        RM.add_action(r.risk_id, {"description": "x", "status": "Started"})
    with pytest.raises(RM.ValidationError, match="Due date must be YYYY-MM-DD"):
        RM.add_action(r.risk_id, {"description": "x", "due_date": "Friday"})
    with pytest.raises(RM.ValidationError, match="No risk #66"):
        RM.add_action(66, {"description": "x"})


def test_action_is_overdue():
    r = _risk()
    late = RM.add_action(r.risk_id, {"description": "late", "due_date": _iso(-1)})
    today = RM.add_action(r.risk_id, {"description": "today", "due_date": _iso(0)})
    done = RM.add_action(r.risk_id, {"description": "done", "due_date": _iso(-1),
                                     "status": "Cancelled"})
    undated = RM.add_action(r.risk_id, {"description": "undated"})
    assert late.is_overdue and not today.is_overdue
    assert not done.is_overdue and not undated.is_overdue


def test_list_actions_order_and_filters():
    r1 = _risk("one")
    r2 = _risk("two")
    a = RM.add_action(r1.risk_id, {"description": "a", "due_date": "2026-06-01"})
    b = RM.add_action(r1.risk_id, {"description": "b"})
    c = RM.add_action(r2.risk_id, {"description": "c", "due_date": "2026-01-01",
                                   "status": "Done"})
    d = RM.add_action(r2.risk_id, {"description": "d", "due_date": _iso(-2),
                                   "status": "In Progress"})
    all_ids = [x.action_id for x in RM.list_actions()]
    assert all_ids[-1] == b.action_id                     # undated last
    assert all_ids.index(c.action_id) < all_ids.index(a.action_id)
    assert {x.action_id for x in RM.list_actions(risk_id=r1.risk_id)} == {a.action_id, b.action_id}
    assert [x.action_id for x in RM.list_actions(status="Done")] == [c.action_id]
    assert c.action_id not in {x.action_id for x in RM.list_actions(open_only=True)}
    overdue = {x.action_id for x in RM.list_actions(overdue_only=True)}
    assert d.action_id in overdue and c.action_id not in overdue and b.action_id not in overdue


def test_update_action_merges_and_completes():
    r = _risk()
    a = RM.add_action(r.risk_id, {"description": "x", "owner": "Ann"})
    out = RM.update_action(a.action_id, {"status": "Done"})
    assert out.status == "Done" and out.completed_date == TODAY.isoformat()
    assert out.owner == "Ann" and out.description == "x"
    with pytest.raises(RM.ValidationError, match="No action #404"):
        RM.update_action(404, {"status": "Done"})


def test_delete_action():
    r = _risk()
    a = RM.add_action(r.risk_id, {"description": "x"})
    assert RM.delete_action(a.action_id) is True
    assert RM.get_action(a.action_id) is None
    assert RM.delete_action(a.action_id) is False


# ── reviews ──

def test_add_review_rolls_risk_forward():
    r = _risk(likelihood=4, impact=4, review_frequency_days=30)
    v = RM.add_review(r.risk_id, {"review_date": "2026-03-01", "reviewer": " Head ",
                                  "summary": " better ", "new_likelihood": 2,
                                  "new_impact": "3", "new_status": "Monitoring"})
    assert (v.reviewer, v.summary, v.new_likelihood, v.new_impact, v.new_status) == \
        ("Head", "better", 2, 3, "Monitoring")
    after = RM.get_risk(r.risk_id)
    assert after.last_reviewed == "2026-03-01"
    assert after.next_review == "2026-03-31"
    assert (after.likelihood, after.impact, after.status) == (2, 3, "Monitoring")


def test_add_review_without_new_scores_keeps_them():
    r = _risk(likelihood=5, impact=2)
    RM.add_review(r.risk_id, {})
    after = RM.get_risk(r.risk_id)
    assert (after.likelihood, after.impact, after.status) == (5, 2, "Identified")
    assert after.last_reviewed == TODAY.isoformat()
    assert after.next_review == _iso(90)


def test_review_validation():
    r = _risk()
    with pytest.raises(RM.ValidationError, match="New likelihood must be 1..5"):
        RM.add_review(r.risk_id, {"new_likelihood": 7})
    with pytest.raises(RM.ValidationError, match="New status must be one of"):
        RM.add_review(r.risk_id, {"new_status": "Dead"})
    with pytest.raises(RM.ValidationError, match="Review date must be YYYY-MM-DD"):
        RM.add_review(r.risk_id, {"review_date": "01/03/2026"})
    with pytest.raises(RM.ValidationError, match="No risk #12"):
        RM.add_review(12, {})
    assert RM.list_reviews(risk_id=r.risk_id) == []


def test_list_reviews_newest_first_limit_and_delete():
    r = _risk()
    old = RM.add_review(r.risk_id, {"review_date": "2026-01-10"})
    new = RM.add_review(r.risk_id, {"review_date": "2026-04-10"})
    assert [v.review_id for v in RM.list_reviews(risk_id=r.risk_id)] == \
        [new.review_id, old.review_id]
    assert [v.review_id for v in RM.list_reviews(limit=1)] == [new.review_id]
    assert RM.delete_review(old.review_id) is True
    assert RM.get_review(old.review_id) is None
    assert RM.delete_review(old.review_id) is False


# ── view / overview / heatmap ──

def test_view_risk():
    r = _risk()
    RM.add_action(r.risk_id, {"description": "late", "due_date": _iso(-3)})
    RM.add_action(r.risk_id, {"description": "done", "status": "Done"})
    RM.add_action(r.risk_id, {"description": "open"})
    RM.add_review(r.risk_id, {"review_date": "2026-02-02"})
    v = RM.view_risk(r.risk_id)
    assert (v.action_total, v.action_open, v.action_overdue) == (3, 2, 1)
    assert v.last_review == "2026-02-02"
    assert RM.view_risk(999) is None


def test_view_risk_without_reviews():
    r = _risk()
    v = RM.view_risk(r.risk_id)
    assert v.last_review is None and v.action_total == 0


def test_overview_empty():
    o = RM.overview()
    assert (o.total, o.open, o.closed, o.reviews_due, o.high_or_critical) == (0, 0, 0, 0, 0)
    assert o.by_band == {"Low": 0, "Medium": 0, "High": 0, "Critical": 0}
    assert o.top_risks == [] and o.actions_total == 0


def test_overview_counts():
    a = _risk("crit", likelihood=5, impact=5, next_review=_iso(-1))      # open, due
    b = _risk("high", likelihood=3, impact=4, status="Closed", next_review=_iso(-1))
    c = _risk("med", likelihood=3, impact=3, category="Estates", status="Mitigating",
              next_review=_iso(5))
    _risk("low", likelihood=1, impact=2, status="Accepted")
    RM.add_action(a.risk_id, {"description": "x", "due_date": _iso(-1)})
    RM.add_action(c.risk_id, {"description": "y", "status": "Done"})
    o = RM.overview()
    assert (o.total, o.open, o.closed) == (4, 2, 1)
    assert o.reviews_due == 1               # closed risk past review not counted
    assert o.high_or_critical == 2
    assert o.by_band == {"Low": 1, "Medium": 1, "High": 1, "Critical": 1}
    assert o.by_category["Estates"] == 1 and o.by_category["Operational"] == 3
    assert o.by_status["Closed"] == 1 and o.by_status["Accepted"] == 1
    assert (o.actions_total, o.actions_open, o.actions_overdue) == (2, 1, 1)
    assert o.top_risks[0] == (a.risk_id, "crit", 25, "Identified")
    assert o.top_risks[1] == (b.risk_id, "high", 12, "Closed")


def test_heatmap_counts_open_risks_only():
    grid = RM.heatmap()
    assert len(grid) == 25 and sum(grid.values()) == 0
    _risk("a", likelihood=2, impact=4)
    _risk("b", likelihood=2, impact=4, status="Monitoring")
    _risk("c", likelihood=5, impact=1)
    _risk("closed", likelihood=2, impact=4, status="Closed")
    grid = RM.heatmap()
    assert grid[(2, 4)] == 2 and grid[(5, 1)] == 1
    assert sum(grid.values()) == 3
