"""Retention policy: off by default, governance-gated, safe erasure."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.sixth_form.domain.admissions import (
    admissions as adm,
    record_safety as rs,
    retention,
)

FAR = dt.date.today() + dt.timedelta(days=800)


def _app(applicant_payload, first):
    return adm.create_applicant(
        applicant_payload(first_name=first, email=f"{first.lower()}@example.com"),
        allow_duplicate=True)


def test_off_by_default_and_governance_gate(admdb, sign_in):
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    sign_in()
    assert retention.get_policy().enabled is False
    with pytest.raises(access.AccessDenied):
        retention.set_policy(enabled=True)
    with pytest.raises(access.AccessDenied):
        retention.run(dry_run=False)


def test_candidates_and_run(admdb, sign_in, applicant_payload):
    sign_in("adm1")
    rejected = _app(applicant_payload, "Rex")
    adm.reject(rejected.applicant_id)
    open_one = _app(applicant_payload, "Ola")
    pending = _app(applicant_payload, "Pen")
    adm.withdraw(pending.applicant_id)
    rs.request_erasure(pending.applicant_id, reason="Applicant asked")

    sign_in("gov1", capabilities={"admissions", "governance"})
    # Off: a real run erases nothing, a dry run still previews.
    assert retention.run(dry_run=False, today=FAR).erased == []
    preview = retention.run(dry_run=True, today=FAR)
    ids = [c.applicant_id for c in preview.candidates]
    assert ids == [rejected.applicant_id]
    assert open_one.applicant_id not in ids and pending.applicant_id not in ids
    # Not yet due.
    assert retention.candidates(today=dt.date.today()) == []

    pol = retention.set_policy(enabled=True, months=6)
    assert pol.enabled_by == "gov1"
    r = retention.run(dry_run=False, today=FAR)
    assert r.erased == [rejected.applicant_id]
    assert adm.get_applicant(rejected.applicant_id) is None
    log = rs.erasure_log(1)[0]
    assert log["requested_by"] == retention.REQUESTED_BY
    assert log["approved_by"] == "gov1"
    assert "Retention policy" in log["reason"]
    assert retention.run_history(1)[0]["erased"] == 1


def test_policy_validation(admdb, sign_in):
    sign_in("gov1", capabilities={"admissions", "governance"})
    with pytest.raises(adm.ValidationError):
        retention.set_policy(months=0)
    with pytest.raises(adm.ValidationError):
        retention.set_policy(statuses=["Enrolled"])
    p = retention.set_policy(enabled=True, statuses=["Rejected"])
    assert p.statuses == ("Rejected",)
    assert retention.set_policy(enabled=False).enabled_by is None
