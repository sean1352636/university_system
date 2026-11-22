"""Admissions scheduled jobs run as a system actor with nobody signed in."""

from __future__ import annotations

import datetime as dt
import sys
import types

from education_system.systems.sixth_form.domain.admissions import (
    admissions as adm,
)
from education_system.systems.sixth_form.infrastructure.scheduler import jobs

TODAY = dt.date.today()


def _signed_out(monkeypatch):
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    monkeypatch.setattr(access, "_current", access.ANONYMOUS)


def test_offer_expiry_job(admdb, sign_in, applicant_payload, monkeypatch):
    sign_in()
    a = adm.create_applicant(applicant_payload())
    adm.make_offer(a.applicant_id)
    adm.set_offer_expiry(a.applicant_id, (TODAY - dt.timedelta(days=2)).isoformat())
    _signed_out(monkeypatch)
    r = jobs.admissions_offer_expiry()
    assert "1 unanswered offer(s) lapsed" in r.summary and not r.errors
    sign_in()
    out = adm.get_applicant(a.applicant_id)
    assert out.status == "Withdrawn"
    assert out.withdrawal_reason == "No response from applicant"
    assert any(e.actor == "system:admissions.offer_expiry"
               for e in adm.list_events(a.applicant_id))


def test_offer_warning_job_sends_once(admdb, sign_in, applicant_payload,
                                      monkeypatch):
    sign_in()
    a = adm.create_applicant(applicant_payload())
    adm.make_offer(a.applicant_id)
    adm.set_offer_expiry(a.applicant_id, (TODAY + dt.timedelta(days=1)).isoformat())
    sent: list[str] = []
    fake = types.ModuleType("admissions_comms")
    fake.send_offer_expiry_warning = sent.append
    monkeypatch.setitem(
        sys.modules,
        "education_system.systems.sixth_form.domain.admissions.admissions_comms",
        fake)
    import education_system.systems.sixth_form.domain.admissions as pkg
    monkeypatch.setattr(pkg, "admissions_comms", fake, raising=False)
    _signed_out(monkeypatch)
    jobs.admissions_offer_warnings()
    jobs.admissions_offer_warnings()
    assert sent == [a.applicant_id]


def test_reference_chase_job_skips_without_comms(admdb, monkeypatch):
    monkeypatch.setattr(jobs, "_admissions_comms", lambda name: None)
    _signed_out(monkeypatch)
    r = jobs.admissions_reference_chase()
    assert "not sent" in r.summary


def test_retention_job_off_by_default(admdb, monkeypatch):
    _signed_out(monkeypatch)
    r = jobs.admissions_retention()
    assert "off" in r.summary and not r.errors


def test_jobs_registered():
    from education_system.systems.sixth_form.infrastructure.scheduler import core
    jobs.register_builtin_jobs()
    names = set(core._REGISTRY)
    assert {"admissions.offer_expiry", "admissions.offer_warnings",
            "admissions.reference_chase", "admissions.retention"} <= names
