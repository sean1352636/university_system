"""Suspensions and exclusions; EHC needs assessments, plans, tribunals and top-ups."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.local_authority.core import records as r
from education_system.systems.local_authority.modules import children, exclusions as X
from education_system.systems.local_authority.modules import send as S


def _ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


def _susp(child: int, school: int, days, **extra) -> int:
    return r.save(X.EXCLUSIONS, {"learner_id": child, "school_id": school,
                                 "kind": "Suspension", "start_date": _ago(0), "days": days,
                                 "reason": X.REASONS[0], **extra})


def test_suspensions_in_halves_up_to_45_days(world, make_child):
    c = make_child(school_id=world.oak)
    with pytest.raises(r.ValidationError, match="halves"):
        _susp(c, world.oak, 1.3)
    sid = _susp(c, world.oak, 44.5)
    assert r.get(X.EXCLUSIONS, sid)["outcome"] is None
    with pytest.raises(r.ValidationError, match="45"):
        _susp(c, world.oak, 1)
    r.save(X.EXCLUSIONS, {"outcome": "Withdrawn by school"}, record_id=sid)
    _susp(c, world.oak, 1)   # a withdrawn suspension doesn't count


def test_sixth_day_only_for_long_suspensions():
    assert X.sixth_day({"kind": "Suspension", "days": 5, "start_date": "2026-11-02"}) is None
    assert X.sixth_day({"kind": "Suspension", "days": 6, "start_date": "2026-11-02"}) is not None


def test_permanent_exclusion_review_and_irp(world, make_child):
    c = make_child(school_id=world.oak)
    base = {"learner_id": c, "school_id": world.oak, "kind": X.KINDS[1],
            "start_date": _ago(40), "reason": X.REASONS[0]}
    with pytest.raises(r.ValidationError, match="notified"):
        r.save(X.EXCLUSIONS, base)
    pex = r.save(X.EXCLUSIONS, {**base, "notified_on": _ago(40)})
    assert X.review_due(r.get(X.EXCLUSIONS, pex)) is not None
    with pytest.raises(r.ValidationError, match="board's review"):
        r.save(X.EXCLUSIONS, {"outcome": "Upheld"}, record_id=pex)
    r.save(X.EXCLUSIONS, {"outcome": "Upheld", "review_on": _ago(30)}, record_id=pex)
    assert r.get(children.CHILDREN, c)["education"] == "Not in education"
    with pytest.raises(r.ValidationError, match="15 school"):
        r.save(X.EXCLUSIONS, {"irp_requested_on": _ago(0)}, record_id=pex)


def test_ehc_request_to_final_plan(world, make_child):
    c = make_child(school_id=world.oak)
    q = r.save(S.EHC_REQUESTS, {"learner_id": c, "received_on": _ago(120),
                                "requested_by": S.REQUESTERS[0]})
    assert r.get(children.CHILDREN, c)["sen_status"] == "EHC needs assessment"
    with pytest.raises(r.ValidationError, match="agreement to assess"):
        r.save(S.EHC_REQUESTS, {"plan_decision": "Issue a plan"}, record_id=q)
    r.save(S.EHC_REQUESTS, {"assess_decision": "Agreed to assess", "decided_on": _ago(80),
                            "plan_decision": "Issue a plan"}, record_id=q)
    with pytest.raises(r.ValidationError, match="draft"):
        r.save(S.EHC_REQUESTS, {"final_issued_on": _ago(5)}, record_id=q)
    with pytest.raises(r.ValidationError, match="15 days"):
        r.save(S.EHC_REQUESTS, {"draft_issued_on": _ago(10), "final_issued_on": _ago(5)},
               record_id=q)
    with pytest.raises(r.ValidationError, match="section I"):
        r.save(S.EHC_REQUESTS, {"draft_issued_on": _ago(30), "final_issued_on": _ago(5)},
               record_id=q)
    r.save(S.EHC_REQUESTS, {"draft_issued_on": _ago(30), "final_issued_on": _ago(5),
                            "setting_id": world.special}, record_id=q)
    assert r.get(S.EHC_REQUESTS, q)["status"] == "Closed"
    plans = r.list_records(S.EHC_PLANS, learner_id=c)
    assert len(plans) == 1 and plans[0]["status"] == "Active"
    assert r.get(children.CHILDREN, c)["sen_status"] == "EHC plan"
    with pytest.raises(r.ValidationError, match="already has an active"):
        r.save(S.EHC_PLANS, {"learner_id": c, "issued_on": _ago(1)})
    with pytest.raises(r.ValidationError, match="reason"):
        r.save(S.EHC_PLANS, {"status": "Ceased"}, record_id=plans[0]["id"])
    r.save(S.EHC_PLANS, {"status": "Ceased", "cease_reason": S.CEASE_REASONS[0]},
           record_id=plans[0]["id"])
    assert r.get(children.CHILDREN, c)["sen_status"] == "SEN Support"


def test_refused_assessment_closes_and_steps_back(make_child):
    c = make_child(sen_status="SEN Support")
    q = r.save(S.EHC_REQUESTS, {"learner_id": c, "received_on": _ago(30),
                                "requested_by": S.REQUESTERS[0]})
    r.save(S.EHC_REQUESTS, {"assess_decision": "Refused to assess"}, record_id=q)
    assert r.get(S.EHC_REQUESTS, q)["status"] == "Closed"
    assert r.get(children.CHILDREN, c)["sen_status"] == "SEN Support"


def test_plan_review_within_12_months(make_child):
    c = make_child()
    p = r.save(S.EHC_PLANS, {"learner_id": c, "issued_on": "2026-01-10",
                             "next_review": "2028-01-01"})
    assert r.get(S.EHC_PLANS, p)["next_review"] == "2027-01-10"


def test_tribunal_mediation_and_lodge_by(make_child):
    c = make_child()
    with pytest.raises(r.ValidationError, match="mediation"):
        r.save(S.TRIBUNALS, {"learner_id": c, "appeal_type": S.APPEAL_TYPES[0],
                             "decision_on": _ago(10)})
    r.save(S.TRIBUNALS, {"learner_id": c, "appeal_type": S.APPEAL_TYPES[3],
                         "decision_on": _ago(10)})
    assert S.lodge_by({"decision_on": "2026-01-10"}) == date(2026, 3, 10)
    assert S.lodge_by({"decision_on": "2026-01-10",
                       "mediation_certificate_on": "2026-03-01"}) == date(2026, 4, 1)


def test_topups_cannot_overlap(world, make_child):
    c = make_child()
    r.save(S.TOPUPS, {"learner_id": c, "setting_id": world.special, "start_date": _ago(100),
                      "annual_amount": 9000})
    with pytest.raises(r.ValidationError, match="overlaps"):
        r.save(S.TOPUPS, {"learner_id": c, "setting_id": world.special,
                          "start_date": _ago(10), "annual_amount": 5000})
    assert len(S.live_topups()) == 1
