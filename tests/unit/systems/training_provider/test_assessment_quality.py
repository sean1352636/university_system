"""Results, certificates, observations, IQA sampling and feedback."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.training_provider.core import records as r
from education_system.systems.training_provider.modules import assessment, quality, sessions


def _day(n: int) -> str:
    return (date.today() + timedelta(days=n)).isoformat()


@pytest.fixture
def attended(world, make_learner):
    """Two learners on the FAW session: A at every day, B absent on one."""
    a, b = make_learner("A", "X"), make_learner("B", "X")
    for lid in (a, b):
        r.save(sessions.BOOKINGS, {"learner_id": lid, "session_id": world.session})
    days = sessions.session_days(r.get(sessions.SESSIONS, world.session))
    for i, d in enumerate(days):
        sessions.take_register(world.session, d, {a: "Present",
                                                  b: "Absent" if i == 1 else "Present"})
    return a, b


def _result(world, learner, **extra) -> int:
    return r.save(assessment.RESULTS, {"learner_id": learner, "session_id": world.session,
                                       "assessed_on": _day(-8), "assessor_id": world.trainer,
                                       **extra})


def test_outcome_from_pass_mark(world, attended):
    rid = _result(world, attended[0], score=75)
    row = r.get(assessment.RESULTS, rid)
    assert row["outcome"] == "Pass" and row["attempt"] == 1


def test_accredited_pass_needs_full_attendance(world, attended):
    with pytest.raises(r.ValidationError, match="full attendance"):
        _result(world, attended[1], score=90)
    assert r.get(assessment.RESULTS, _result(world, attended[1], score=40))["outcome"] == "Fail"


def test_no_new_attempt_after_a_pass(world, attended):
    _result(world, attended[0], score=90)
    with pytest.raises(r.ValidationError, match="already passed"):
        _result(world, attended[0], score=95)


def test_learner_without_a_place_cannot_have_a_result(world, make_learner):
    with pytest.raises(r.ValidationError, match="no place"):
        _result(world, make_learner("Z", "Q"), score=90)


def test_certificate_needs_a_pass_and_gets_number_and_expiry(world, attended):
    a, b = attended
    with pytest.raises(r.ValidationError, match="Pass result"):
        r.save(assessment.CERTIFICATES, {"learner_id": a, "session_id": world.session})
    _result(world, a, score=90)
    assert assessment.issue_due(world.session) == 1
    cert = r.list_records(assessment.CERTIFICATES)[0]
    assert cert["cert_no"] == f"TP-{date.today().year}-00001"
    assert cert["expires_on"][:4] == str(date.today().year + 3)
    assert assessment.validity(cert) == "Valid"
    with pytest.raises(r.ValidationError, match="already issued"):
        r.save(assessment.CERTIFICATES, {"learner_id": a, "session_id": world.session})
    with pytest.raises(r.ValidationError, match="reason"):
        r.save(assessment.CERTIFICATES, {"status": "Revoked"}, record_id=cert["id"])


def test_renewal_window(world):
    row = {"status": "Issued", "expires_on": _day(30)}
    assert assessment.validity(row).startswith("Renew by")
    assert assessment.validity({"status": "Issued", "expires_on": _day(-1)}) == "EXPIRED"


def test_weak_observation_needs_actions_and_quick_reobservation(world):
    with pytest.raises(r.ValidationError, match="actions"):
        r.save(quality.OBSERVATIONS, {"trainer_id": world.trainer, "observed_on": _day(-5),
                                      "observer": "QA", "grade": "Inadequate"})
    oid = r.save(quality.OBSERVATIONS, {"trainer_id": world.trainer, "observed_on": _day(-5),
                                        "observer": "QA", "grade": "Requires improvement",
                                        "actions": "Plan"})
    nxt = r.to_date(r.get(quality.OBSERVATIONS, oid)["next_due"])
    assert nxt <= date.today() + timedelta(days=95)


def test_iqa_rules(world, attended):
    rid = _result(world, attended[0], score=90)
    with pytest.raises(r.ValidationError, match="own"):
        r.save(quality.IQA_SAMPLES, {"result_id": rid, "iqa_id": world.trainer,
                                     "sampled_on": _day(-1)})
    with pytest.raises(r.ValidationError, match="action"):
        r.save(quality.IQA_SAMPLES, {"result_id": rid, "iqa_id": world.iqa,
                                     "sampled_on": _day(-1), "decision": "Not agreed"})
    r.save(quality.IQA_SAMPLES, {"result_id": rid, "iqa_id": world.iqa,
                                 "sampled_on": _day(-1)})
    assert quality.sample_rate() == 100


def test_complaint_response_due_and_resolution(world):
    fid = r.save(quality.FEEDBACK, {"kind": "Complaint", "received_on": _day(-20),
                                    "comments": "Cold room", "rating": 2})
    assert quality.response_due(r.get(quality.FEEDBACK, fid)) < date.today()
    with pytest.raises(r.ValidationError, match="response"):
        r.save(quality.FEEDBACK, {"status": "Resolved"}, record_id=fid)
    with pytest.raises(r.ValidationError, match="1 \\(poor\\)"):
        r.save(quality.FEEDBACK, {"rating": 6}, record_id=fid)
