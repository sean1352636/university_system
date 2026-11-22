"""Learners and clients: references, checks and duplicates."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.training_provider.core import records as r
from education_system.systems.training_provider.modules import clients, learners


def _day(n: int) -> str:
    return (date.today() + timedelta(days=n)).isoformat()


def test_reference_and_postcode_are_filled(make_learner):
    lid = make_learner(postcode="m11aa", email="ann@x.com")
    row = r.get(learners.LEARNERS, lid)
    assert row["learner_ref"] == "TP000001"
    assert row["postcode"] == "M1 1AA"


def test_duplicate_name_and_dob_refused(make_learner):
    make_learner()
    with pytest.raises(r.ValidationError, match="same name and date of birth"):
        make_learner()


def test_email_is_unique(make_learner):
    make_learner(email="a@x.com")
    with pytest.raises(r.ValidationError, match="e-mail"):
        make_learner("Bob", "Ray", email="a@x.com")


def test_under_14_refused(make_learner):
    with pytest.raises(r.ValidationError, match="14 or"):
        make_learner(dob=date(date.today().year - 12, 1, 1).isoformat())


def test_employer_funding_needs_the_employer(make_learner):
    with pytest.raises(r.ValidationError, match="employer"):
        make_learner(funding="Employer")


def test_uln_check_digit():
    assert learners.uln_check_digit_ok("1234567899")
    assert not learners.uln_check_digit_ok("1234567890")
    with pytest.raises(r.ValidationError, match="ULN"):
        r.save(learners.LEARNERS, {"first_name": "A", "last_name": "B", "uln": "123"})


def test_client_account_number_and_hold_reason():
    cid = r.save(clients.CLIENTS, {"name": "Acme"})
    assert r.get(clients.CLIENTS, cid)["account_no"] == "CL0001"
    with pytest.raises(r.ValidationError, match="on hold"):
        r.save(clients.CLIENTS, {"status": "On hold"}, record_id=cid)


def test_contract_discount_only_while_active_and_in_date():
    cid = r.save(clients.CLIENTS, {"name": "Acme"})
    r.save(clients.CONTRACTS, {"client_id": cid, "title": "F", "start_date": _day(-10),
                               "end_date": _day(10), "discount_pct": 15, "status": "Active"})
    assert clients.contract_discount(cid, date.today()) == 15
    assert clients.contract_discount(cid, date.today() + timedelta(days=30)) == 0


def test_active_contract_cannot_have_ended():
    cid = r.save(clients.CLIENTS, {"name": "Acme"})
    with pytest.raises(r.ValidationError, match="Expired"):
        r.save(clients.CONTRACTS, {"client_id": cid, "title": "F", "start_date": _day(-60),
                                   "end_date": _day(-1), "status": "Active"})
