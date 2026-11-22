from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.special_education.core import records as r
from education_system.systems.special_education.modules import support_plans as sp


def _plan(learner, **extra):
    return r.save(sp.PLANS, {"learner_id": learner, "start_date": "2026-09-01", **extra})


def test_review_defaults_to_twelve_weeks(learner):
    assert r.get(sp.PLANS, _plan(learner))["review_date"] == "2026-11-24"


def test_one_active_plan_per_learner(learner):
    _plan(learner, status="Active")
    with pytest.raises(r.ValidationError, match="already has an active plan"):
        _plan(learner, status="Active")


def test_targets_and_reviews_take_the_plans_learner(learner):
    pid = _plan(learner)
    tid = r.save(sp.TARGETS, {"plan_id": pid, "target": "Read 20 words"})
    assert r.get(sp.TARGETS, tid)["learner_id"] == learner


def test_review_moves_plan_on_and_close_closes_it(learner):
    pid = _plan(learner, status="Active")
    r.save(sp.REVIEWS, {"plan_id": pid, "review_date": "2026-11-20", "outcome": "Continue"})
    assert r.get(sp.PLANS, pid)["review_date"] == (
        date(2026, 11, 20) + timedelta(weeks=12)).isoformat()
    r.save(sp.REVIEWS, {"plan_id": pid, "review_date": "2027-02-01",
                        "outcome": "Close - needs met"})
    assert r.get(sp.PLANS, pid)["status"] == "Closed"


def test_review_before_plan_start_refused(learner):
    pid = _plan(learner)
    with pytest.raises(r.ValidationError, match="before the plan started"):
        r.save(sp.REVIEWS, {"plan_id": pid, "review_date": "2026-01-01", "outcome": "Continue"})
