"""Attendance cases, penalty notices, children missing education and EHE."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.local_authority.core import records as r
from education_system.systems.local_authority.modules import children, welfare as W


def _ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


@pytest.mark.parametrize(("pct", "band"), [(None, ""), (40, "Severe"), (85, "Persistent"),
                                           (95, "")])
def test_absence_bands(pct, band):
    assert W.absence_band(pct) == band


def test_one_open_attendance_case(world, make_child):
    c = make_child(school_id=world.oak)
    case = r.save(W.ATTENDANCE_CASES, {"learner_id": c, "school_id": world.oak,
                                       "referred_on": _ago(3), "attendance_pct": 80})
    with pytest.raises(r.ValidationError, match="already has an open"):
        r.save(W.ATTENDANCE_CASES, {"learner_id": c, "school_id": world.oak,
                                    "referred_on": _ago(1)})
    with pytest.raises(r.ValidationError, match="outcome"):
        r.save(W.ATTENDANCE_CASES, {"status": "Closed"}, record_id=case)
    r.save(W.ATTENDANCE_CASES, {"status": "Closed", "outcome": "Improved to 96%"},
           record_id=case)


def _parent(child: int, **extra) -> int:
    return r.save(children.CONTACTS, {"learner_id": child, "name": "Mum",
                                      "relationship": "Mother", "phone": "0161 111 2222",
                                      **extra})


def test_penalty_notice_rules(world, make_child):
    c = make_child(school_id=world.oak)
    mum = _parent(c)
    no_pr = _parent(c, name="Gran", relationship="Grandparent", parental_responsibility=0)
    base = {"learner_id": c, "school_id": world.oak, "reason": W.PN_REASONS[0],
            "sessions_missed": 12, "issued_on": _ago(10)}
    with pytest.raises(r.ValidationError, match="parental"):
        r.save(W.PENALTY_NOTICES, {**base, "parent_id": no_pr})
    with pytest.raises(r.ValidationError, match="threshold"):
        r.save(W.PENALTY_NOTICES, {**base, "parent_id": mum, "sessions_missed": 6})
    first = r.save(W.PENALTY_NOTICES, {**base, "parent_id": mum, "issued_on": _ago(200)})
    r.save(W.PENALTY_NOTICES, {"status": "Paid", "paid_on": _ago(190)}, record_id=first)
    assert r.get(W.PENALTY_NOTICES, first)["amount_paid"] == 80
    second = r.save(W.PENALTY_NOTICES, {**base, "parent_id": mum})
    row = r.get(W.PENALTY_NOTICES, second)
    assert row["second_notice"] == 1 and W.amount_due(row) == 160
    with pytest.raises(r.ValidationError, match="third"):
        r.save(W.PENALTY_NOTICES, {**base, "parent_id": mum, "issued_on": _ago(1)})
    with pytest.raises(r.ValidationError, match="notes"):
        r.save(W.PENALTY_NOTICES, {"status": "Withdrawn"}, record_id=second)


def test_late_payment_is_160_and_after_28_days_refused(world, make_child):
    c = make_child(school_id=world.oak)
    mum = _parent(c)
    pn = r.save(W.PENALTY_NOTICES, {"learner_id": c, "parent_id": mum,
                                    "reason": W.PN_REASONS[1], "sessions_missed": 10,
                                    "issued_on": _ago(40)})
    r.save(W.PENALTY_NOTICES, {"status": "Paid", "paid_on": _ago(15)}, record_id=pn)
    assert r.get(W.PENALTY_NOTICES, pn)["amount_paid"] == 160
    with pytest.raises(r.ValidationError, match="28 days"):
        r.save(W.PENALTY_NOTICES, {"status": "Paid", "paid_on": _ago(1)}, record_id=pn)


def test_cme_updates_the_child(world, make_child):
    c = make_child(school_id=world.oak)
    case = r.save(W.CME, {"learner_id": c, "reported_on": _ago(5), "source": W.CME_SOURCES[0],
                          "last_school_id": world.oak})
    assert r.get(children.CHILDREN, c)["education"] == "Not in education"
    with pytest.raises(r.ValidationError, match="enquiries"):
        r.save(W.CME, {"status": W.CME_OUTCOMES[1]}, record_id=case)
    with pytest.raises(r.ValidationError, match="found on roll"):
        r.save(W.CME, {"status": W.CME_OUTCOMES[1], "enquiries": "Called school"},
               record_id=case)
    r.save(W.CME, {"status": W.CME_OUTCOMES[1], "enquiries": "Called school",
                   "found_school_id": world.elm}, record_id=case)
    child = r.get(children.CHILDREN, c)
    assert (child["education"], child["school_id"]) == ("At school", world.elm)
    assert r.get(W.CME, case)["closed_on"] == date.today().isoformat()


def test_cme_leaves_a_pre_school_child_alone(make_child):
    c = make_child(age=3, education="Not yet school age")
    r.save(W.CME, {"learner_id": c, "reported_on": _ago(1), "source": W.CME_SOURCES[-1]})
    assert r.get(children.CHILDREN, c)["education"] == "Not yet school age"


def test_ehe_consent_for_special_school_ehc_child(world, make_child):
    c = make_child(school_id=world.special, sen_status="EHC plan")
    with pytest.raises(r.ValidationError, match="consents"):
        r.save(W.EHE, {"learner_id": c, "notified_on": _ago(2),
                       "from_school_id": world.special})
    e = r.save(W.EHE, {"learner_id": c, "notified_on": _ago(2), "from_school_id": world.special,
                       "consent": "Given", "first_contact_on": _ago(1)})
    row = r.get(W.EHE, e)
    assert row["next_review"] == W.dates.add_months(date.today() - timedelta(days=1),
                                                    12).isoformat()
    assert r.get(children.CHILDREN, c)["education"] == "Elective home education"
    with pytest.raises(r.ValidationError, match="isn't suitable"):
        r.save(W.EHE, {"sao_stage": "Notice served"}, record_id=e)
