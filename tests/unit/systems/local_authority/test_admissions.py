"""Applications, offers, appeals and fair access."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.local_authority.core import records as r
from education_system.systems.local_authority.modules import admissions as A
from education_system.systems.local_authority.modules import children


def _ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


def _reception_child(make_child, entry: int) -> int:
    return r.save(children.CHILDREN, {"first_name": "Amy", "last_name": "Shaw",
                                      "dob": date(entry - 4, 3, 1).isoformat(),
                                      "education": "Not yet school age"})


def test_closing_and_offer_days():
    assert A.closing_date(A.YEAR7, 2027) == date(2026, 10, 31)
    assert A.closing_date(A.RECEPTION, 2027) == date(2027, 1, 15)
    assert A.offer_day(A.YEAR7, 2027) == date(2027, 3, 1)
    assert A.offer_day(A.RECEPTION, 2027) == date(2027, 4, 16)
    assert A.offer_day(A.YEAR7, 2026) == date(2026, 3, 2)   # 1 March 2026 is a Sunday


def test_normal_round_age_phase_and_preferences(world, make_child):
    entry = date.today().year + 1
    kid = _reception_child(make_child, entry)
    base = {"learner_id": kid, "round": A.RECEPTION, "received_on": _ago(1)}
    with pytest.raises(r.ValidationError, match="not Reception"):
        r.save(A.APPLICATIONS, {**base, "entry_year": entry + 1, "pref1_id": world.oak})
    with pytest.raises(r.ValidationError, match="secondary school"):
        r.save(A.APPLICATIONS, {**base, "entry_year": entry, "pref1_id": world.high})
    with pytest.raises(r.ValidationError, match="different school"):
        r.save(A.APPLICATIONS, {**base, "entry_year": entry, "pref1_id": world.oak,
                                "pref2_id": world.oak})
    aid = r.save(A.APPLICATIONS, {**base, "entry_year": entry, "pref1_id": world.oak})
    with pytest.raises(r.ValidationError, match="already a live"):
        r.save(A.APPLICATIONS, {**base, "entry_year": entry, "pref1_id": world.elm})
    if A.offer_day(A.RECEPTION, entry) > date.today():
        with pytest.raises(r.ValidationError, match="national offer day"):
            r.save(A.APPLICATIONS, {"status": "Offered", "offered_school_id": world.oak},
                   record_id=aid)


def test_in_year_offer_basis_and_pan(world, make_child):
    a = make_child("A", "X")
    b = make_child("B", "X")
    first = r.save(A.APPLICATIONS, {"learner_id": a, "round": A.IN_YEAR, "received_on": _ago(2),
                                    "pref1_id": world.elm, "pref2_id": world.oak})
    r.save(A.APPLICATIONS, {"status": "Offered", "offered_school_id": world.oak},
           record_id=first)
    assert r.get(A.APPLICATIONS, first)["offer_basis"] == "2nd preference"
    second = r.save(A.APPLICATIONS, {"learner_id": b, "round": A.IN_YEAR,
                                     "received_on": _ago(2), "pref1_id": world.oak})
    with pytest.raises(r.ValidationError, match="all 1 places"):
        r.save(A.APPLICATIONS, {"status": "Offered", "offered_school_id": world.oak},
               record_id=second)
    with pytest.raises(r.ValidationError, match="future"):
        r.save(A.APPLICATIONS, {"status": "Offered", "offered_school_id": world.elm,
                                "offered_on": (date.today() + timedelta(days=3)).isoformat()},
               record_id=second)
    assert A.decision_due(r.get(A.APPLICATIONS, second)) > date.today() - timedelta(days=2)


def test_upheld_appeal_becomes_the_offer(world, make_child):
    b = make_child("B", "X")
    aid = r.save(A.APPLICATIONS, {"learner_id": b, "round": A.IN_YEAR, "received_on": _ago(5),
                                  "pref1_id": world.oak, "status": "Refused"})
    with pytest.raises(r.ValidationError, match="applied for"):
        r.save(A.APPEALS, {"application_id": aid, "school_id": world.elm,
                           "lodged_on": _ago(1)})
    ap = r.save(A.APPEALS, {"application_id": aid, "school_id": world.oak, "lodged_on": _ago(1)})
    assert r.get(A.APPEALS, ap)["learner_id"] == b
    with pytest.raises(r.ValidationError, match="hearing"):
        r.save(A.APPEALS, {"outcome": "Upheld"}, record_id=ap)
    r.save(A.APPEALS, {"outcome": "Upheld", "hearing_on": _ago(0)}, record_id=ap)
    app = r.get(A.APPLICATIONS, aid)
    assert (app["status"], app["offered_school_id"], app["offer_basis"]) == \
        ("Offered", world.oak, "Appeal upheld")


def test_refused_only_in_year(world, make_child):
    entry = date.today().year + 1
    kid = _reception_child(make_child, entry)
    with pytest.raises(r.ValidationError, match="not refused"):
        r.save(A.APPLICATIONS, {"learner_id": kid, "round": A.RECEPTION, "entry_year": entry,
                                "received_on": _ago(1), "pref1_id": world.oak,
                                "status": "Refused"})


def test_fair_access_puts_child_on_roll(world, make_child):
    c = make_child("C", "X")
    f = r.save(A.FAIR_ACCESS, {"learner_id": c, "referred_on": _ago(40), "category": "Homeless"})
    assert A._fap_flag(r.get(A.FAIR_ACCESS, f)).endswith("OVERDUE")
    with pytest.raises(r.ValidationError, match="school allocated"):
        r.save(A.FAIR_ACCESS, {"decision": "Allocated"}, record_id=f)
    r.save(A.FAIR_ACCESS, {"decision": "Allocated", "school_id": world.elm,
                           "panel_on": _ago(5), "on_roll_on": _ago(1)}, record_id=f)
    child = r.get(children.CHILDREN, c)
    assert (child["education"], child["school_id"]) == ("At school", world.elm)
