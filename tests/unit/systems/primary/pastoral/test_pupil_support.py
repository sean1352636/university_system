"""Pupil-support plans (systems.primary.domain.pastoral.pupil_support.pupil_support)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.pastoral.pupil_support import pupil_support as SP

_n = 0


def _pupil(year="3"):
    global _n
    _n += 1
    return P.create_pupil({"first_name": f"Pupil{_n}", "last_name": f"Test{_n}",
                           "year_group": year, "date_of_birth": "2018-01-01"})


def _plan(pupil, **extra):
    data = {"pupil_id": pupil.pupil_id, "academic_year": "2025/26",
            "title": "Reading boost", "start_date": "2025-09-08", **extra}
    return SP.create_plan(data)


# ── create / read ────────────────────────────────────────────────────

def test_create_plan_defaults_and_read_back():
    ava = _pupil()
    plan = _plan(ava, target="Read 20 mins daily", coordinator="Ms Lee",
                 success_criteria="  Book band up  ", notes="")
    assert plan.plan_id > 0
    assert (plan.plan_type, plan.priority, plan.status) == ("Academic", "Medium", "Draft")
    assert plan.title == "Reading boost" and plan.start_date == "2025-09-08"
    assert plan.success_criteria == "Book band up" and plan.notes is None
    assert plan.pupil_name == ava.full_name and plan.pupil_year == "3"
    assert SP.get_plan(plan.plan_id) == plan


def test_start_date_defaults_to_today():
    plan = _plan(_pupil(), start_date="")
    assert plan.start_date == dt.date.today().isoformat()


def test_get_plan_missing_is_none():
    # A fresh database: the plan reads join pupils, so init_db must create it
    # (send.init_db does); nothing here has created a pupil yet.
    assert SP.get_plan(9999) is None
    assert SP.list_plans() == []


# ── validation ───────────────────────────────────────────────────────

@pytest.mark.parametrize("bad, msg", [
    ({"pupil_id": ""}, "Pupil ID is required"),
    ({"pupil_id": "NOPE"}, "No pupil with id NOPE"),
    ({"academic_year": ""}, "Academic year is required"),
    ({"academic_year": "2025-26"}, "YYYY/YY"),
    ({"plan_type": "Sport"}, "Plan type must be one of"),
    ({"title": "  "}, "Title is required"),
    ({"title": "x" * 121}, "120 chars"),
    ({"priority": "Urgent"}, "Priority must be one of"),
    ({"start_date": "08/09/2025"}, "Start date must be YYYY-MM-DD"),
    ({"start_date": "2025-02-30"}, "Start date is not a real date"),
    ({"end_date": "2025-09-01"}, "End date cannot be before start date"),
    ({"next_review_date": "2025-09-01"}, "Next review date cannot be before start date"),
    ({"status": "Open"}, "Status must be one of"),
    ({"status": "Complete"}, "Outcome is required when status is Complete"),
    ({"status": "Closed"}, "Outcome is required when status is Closed"),
])
def test_plan_validation(bad, msg):
    ava = _pupil()
    with pytest.raises(SP.ValidationError, match=msg):
        _plan(ava, **bad)


def test_title_of_120_chars_and_closed_with_outcome_accepted():
    plan = _plan(_pupil(), title="x" * 120, status="Closed", outcome="Targets met")
    assert plan.status == "Closed" and plan.outcome == "Targets met"


# ── listing / filters / sort ─────────────────────────────────────────

def test_list_sorted_by_priority_then_newest_start():
    ava = _pupil()
    low = _plan(ava, priority="Low", title="low")
    crit = _plan(ava, priority="Critical", title="crit")
    med_old = _plan(ava, title="med old", start_date="2025-09-01")
    med_new = _plan(ava, title="med new", start_date="2025-10-01")
    assert [p.plan_id for p in SP.list_plans()] == [
        crit.plan_id, med_new.plan_id, med_old.plan_id, low.plan_id]


def test_list_filters():
    ava, ben = _pupil("2"), _pupil("5")
    a = _plan(ava, plan_type="SEMH", priority="High", status="Active")
    b = _plan(ben, academic_year="2024/25", start_date="2024-09-02")
    assert [p.plan_id for p in SP.list_plans(pupil_id=ava.pupil_id)] == [a.plan_id]
    assert [p.plan_id for p in SP.list_plans(year_group="5")] == [b.plan_id]
    assert [p.plan_id for p in SP.list_plans(academic_year="2024/25")] == [b.plan_id]
    assert [p.plan_id for p in SP.list_plans(plan_type="SEMH")] == [a.plan_id]
    assert [p.plan_id for p in SP.list_plans(status="Draft")] == [b.plan_id]
    assert [p.plan_id for p in SP.list_plans(priority="High")] == [a.plan_id]


@pytest.mark.parametrize("kw, msg", [
    ({"year_group": "7"}, "Year filter"), ({"plan_type": "x"}, "Type filter"),
    ({"status": "x"}, "Status filter"), ({"priority": "x"}, "Priority filter")])
def test_list_filter_validation(kw, msg):
    with pytest.raises(SP.ValidationError, match=msg):
        SP.list_plans(**kw)


# ── update / status / delete ─────────────────────────────────────────

def test_update_merges_and_revalidates():
    plan = _plan(_pupil(), coordinator="Ms Lee")
    upd = SP.update_plan(plan.plan_id, {"priority": "High", "title": "New title"})
    assert (upd.priority, upd.title, upd.coordinator) == ("High", "New title", "Ms Lee")
    with pytest.raises(SP.ValidationError, match="Priority must be one of"):
        SP.update_plan(plan.plan_id, {"priority": "Huge"})
    with pytest.raises(SP.ValidationError, match="No support plan #999"):
        SP.update_plan(999, {"title": "x"})


def test_set_status_requires_outcome_to_complete():
    plan = _plan(_pupil())
    assert SP.set_status(plan.plan_id, "Active").status == "Active"
    with pytest.raises(SP.ValidationError, match="Outcome is required"):
        SP.set_status(plan.plan_id, "Complete")
    done = SP.set_status(plan.plan_id, "Complete", outcome="Met")
    assert (done.status, done.outcome) == ("Complete", "Met")


def test_delete_plan_cascades_reviews():
    plan = _plan(_pupil())
    rev = SP.add_review({"plan_id": plan.plan_id, "review_date": "2025-10-01"})
    assert SP.delete_plan(plan.plan_id) is True
    assert SP.get_plan(plan.plan_id) is None
    assert SP.get_review(rev.review_id) is None
    assert SP.delete_plan(plan.plan_id) is False


# ── reviews ──────────────────────────────────────────────────────────

def test_add_review_mirrors_next_review_date_and_lists_newest_first():
    plan = _plan(_pupil(), next_review_date="2025-10-01")
    r1 = SP.add_review({"plan_id": plan.plan_id, "review_date": "2025-10-01",
                        "reviewer": "Ms Lee", "progress": "Good",
                        "next_review_date": "2025-11-01"})
    assert r1.outcome == "On track" and r1.reviewer == "Ms Lee"
    assert SP.get_plan(plan.plan_id).next_review_date == "2025-11-01"
    r2 = SP.add_review({"plan_id": str(plan.plan_id), "review_date": "2025-11-01",
                        "outcome": "Adjust"})
    assert SP.get_plan(plan.plan_id).next_review_date == "2025-11-01"
    assert [r.review_id for r in SP.list_reviews(plan.plan_id)] == [r2.review_id, r1.review_id]
    assert SP.delete_review(r1.review_id) is True
    assert SP.delete_review(r1.review_id) is False
    assert [r.review_id for r in SP.list_reviews(plan.plan_id)] == [r2.review_id]


@pytest.mark.parametrize("bad, msg", [
    ({"plan_id": None}, "Plan ID is required"),
    ({"plan_id": "abc"}, "Plan ID must be a number"),
    ({"plan_id": 999}, "No support plan #999"),
    ({"outcome": "Great"}, "Outcome must be one of"),
    ({"review_date": "1/10/2025"}, "Review date must be YYYY-MM-DD"),
    ({"next_review_date": "2025-09-01"}, "Next review date cannot be before review date"),
])
def test_review_validation(bad, msg):
    plan = _plan(_pupil())
    data = {"plan_id": plan.plan_id, "review_date": "2025-10-01", **bad}
    with pytest.raises(SP.ValidationError, match=msg):
        SP.add_review(data)


def test_review_date_defaults_to_today():
    plan = _plan(_pupil())
    assert SP.add_review({"plan_id": plan.plan_id}).review_date == dt.date.today().isoformat()


# ── summaries ────────────────────────────────────────────────────────

def test_plan_summary_counts_outcomes():
    plan = _plan(_pupil())
    for day, outcome in (("2025-10-01", "On track"), ("2025-11-01", "Adjust"),
                         ("2025-12-01", "On track")):
        SP.add_review({"plan_id": plan.plan_id, "review_date": day, "outcome": outcome})
    s = SP.plan_summary(plan.plan_id)
    assert s["review_count"] == 3
    assert s["by_outcome"] == {"On track": 2, "Adjust": 1}
    assert s["last_review"] == "2025-12-01"
    with pytest.raises(SP.ValidationError, match="No support plan"):
        SP.plan_summary(404)


def test_plan_summary_without_reviews():
    s = SP.plan_summary(_plan(_pupil()).plan_id)
    assert (s["review_count"], s["by_outcome"], s["last_review"]) == (0, {}, None)


def test_cohort_summary():
    ava, ben = _pupil("2"), _pupil("4")
    _plan(ava, status="Active", plan_type="SEMH", priority="High")
    _plan(ava, status="Active")
    _plan(ben, academic_year="2024/25", start_date="2024-09-02")
    s = SP.cohort_summary()
    assert s["total"] == 3 and s["active"] == 2
    assert s["by_status"] == {"Active": 2, "Draft": 1}
    assert s["by_type"] == {"SEMH": 1, "Academic": 2}
    assert s["by_priority"] == {"High": 1, "Medium": 2}
    assert SP.cohort_summary(year_group="2")["total"] == 2
    assert SP.cohort_summary(academic_year="2024/25")["total"] == 1
    assert SP.cohort_summary() and SP.cohort_summary(year_group="R")["total"] == 0


def test_overdue_reviews_only_active_and_past():
    ava = _pupil()
    overdue = _plan(ava, status="Active", next_review_date="2025-10-01")
    _plan(ava, status="Active", next_review_date="2025-12-01")
    _plan(ava, status="Draft", next_review_date="2025-10-01")
    _plan(ava, status="Active")
    assert [p.plan_id for p in SP.overdue_reviews("2025-11-01")] == [overdue.plan_id]
    assert SP.overdue_reviews("2025-10-01") == []
