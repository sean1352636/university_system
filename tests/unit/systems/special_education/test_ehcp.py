from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.special_education.core import records as r
from education_system.systems.special_education.modules import ehcp, learners

TODAY = date.today()


def _iso(weeks_ago: float) -> str:
    return (TODAY - timedelta(weeks=weeks_ago)).isoformat()


def _request(learner, weeks_ago=9, **extra):
    return r.save(ehcp.EHCPS, {"learner_id": learner, "request_date": _iso(weeks_ago), **extra})


def test_decision_deadline_is_six_weeks(learner):
    row = r.get(ehcp.EHCPS, _request(learner, 9))
    nxt = ehcp.next_deadline(row)
    assert nxt.what == "Decision to assess" and nxt.overdue
    assert nxt.due == TODAY - timedelta(weeks=3)


def test_stage_needs_its_date(learner):
    eid = _request(learner)
    with pytest.raises(r.ValidationError, match="needs the decision"):
        r.save(ehcp.EHCPS, {"stage": "Assessing"}, record_id=eid)


def test_one_open_ehcp_per_learner(learner):
    _request(learner)
    with pytest.raises(r.ValidationError, match="already has an open EHCP"):
        _request(learner)


def test_family_gets_fifteen_days_on_the_draft(learner):
    eid = _request(learner, 19)
    with pytest.raises(r.ValidationError, match="15 days"):
        r.save(ehcp.EHCPS, {"decision_date": _iso(14), "draft_date": _iso(1),
                            "final_date": TODAY.isoformat()}, record_id=eid)


def test_final_date_issues_plan_and_sets_status(learner):
    eid = _request(learner, 19)
    r.save(ehcp.EHCPS, {"decision_date": _iso(14), "draft_date": _iso(4),
                        "final_date": TODAY.isoformat()}, record_id=eid)
    assert r.get(ehcp.EHCPS, eid)["stage"] == "Final issued"
    assert r.get(learners.LEARNERS, learner)["sen_status"] == "EHCP"
    assert ehcp.timeliness()["on_time"] == 1
    r.save(ehcp.EHCPS, {"stage": "Ceased", "cease_date": TODAY.isoformat()}, record_id=eid)
    assert r.get(learners.LEARNERS, learner)["sen_status"] == "SEN Support"


def test_dates_must_run_in_order(learner):
    eid = _request(learner, 9)
    with pytest.raises(r.ValidationError, match="can't be before"):
        r.save(ehcp.EHCPS, {"decision_date": _iso(10)}, record_id=eid)


def test_annual_review_only_for_issued_plan_and_updates_last_review(learner):
    eid = _request(learner, 30)
    with pytest.raises(r.ValidationError, match="no final"):
        r.save(ehcp.REVIEWS, {"ehcp_id": eid})
    r.save(ehcp.EHCPS, {"decision_date": _iso(25), "draft_date": _iso(14),
                        "final_date": _iso(10)}, record_id=eid)
    r.save(ehcp.REVIEWS, {"ehcp_id": eid, "meeting_date": TODAY.isoformat()})
    assert r.get(ehcp.EHCPS, eid)["last_review_date"] == TODAY.isoformat()
    nxt = ehcp.next_deadline(r.get(ehcp.EHCPS, eid))
    assert nxt.what == "Annual review" and nxt.due.year == TODAY.year + 1


def test_advice_due_defaults_to_six_weeks(learner):
    eid = _request(learner)
    aid = r.save(ehcp.ADVICE, {"ehcp_id": eid, "advice_type": "Health",
                               "requested_on": "2026-09-01"})
    row = r.get(ehcp.ADVICE, aid)
    assert row["due_on"] == "2026-10-13" and row["learner_id"] == learner
