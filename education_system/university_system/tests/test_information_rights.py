"""Smoke tests for the information_rights module (SAR / FOI / EIR)."""

import os
import tempfile
from datetime import date

import pytest

from education_system.university_system.modules.domain.legal.information_rights import (  # noqa: E501
    InformationRightsService,
    InformationRightsError,
)
from education_system.university_system.modules.domain.legal.information_rights.services.information_rights_core import (  # noqa: E501
    compute_deadline,
    _add_calendar_months,
    _add_working_days,
)


@pytest.fixture()
def svc():
    with tempfile.TemporaryDirectory() as tmp:
        yield InformationRightsService(os.path.join(tmp, "ir.db"))


# -- pure deadline maths ---------------------------------------------------

def test_calendar_month_clamps_short_months():
    # 31 Jan + 1 month -> 28 Feb (non-leap)
    assert _add_calendar_months(date(2025, 1, 31), 1) == date(2025, 2, 28)
    # 31 Jan + 1 month -> 29 Feb (leap)
    assert _add_calendar_months(date(2024, 1, 31), 1) == date(2024, 2, 29)
    # 31 May + 3 months -> 31 Aug (no clamp)
    assert _add_calendar_months(date(2025, 5, 31), 3) == date(2025, 8, 31)


def test_working_days_skip_weekends():
    # Friday 2026-05-08 + 1 wd = Mon 2026-05-11
    assert _add_working_days(date(2026, 5, 8), 1) == date(2026, 5, 11)
    # 20 working days from Mon 2026-05-04 = Mon 2026-06-01
    assert _add_working_days(date(2026, 5, 4), 20) == date(2026, 6, 1)


def test_compute_deadline_dispatches_by_type():
    assert compute_deadline("SAR", date(2026, 5, 9)) == date(2026, 6, 9)
    assert (compute_deadline("SAR", date(2026, 5, 9), extended=True)
            == date(2026, 8, 9))
    # FOI: 20 wd from Sat 2026-05-09 -> Fri 2026-06-05
    # (clock starts day after Sat = Sun, skip; first wd is Mon 5/11)
    assert compute_deadline("FOI", date(2026, 5, 9)) == date(2026, 6, 5)
    assert compute_deadline("EIR", date(2026, 5, 9)) == date(2026, 6, 5)
    with pytest.raises(InformationRightsError):
        compute_deadline("XYZ", date(2026, 5, 9))


# -- intake ---------------------------------------------------------------

def test_create_sar_starts_pending_id_and_sets_deadline(svc):
    r = svc.create_request(
        "SAR", "Alice Example", "alice@example.com",
        "All my student records",
        received_on=date(2026, 5, 9),
    )
    assert r["reference"].startswith("SAR-2026-")
    assert r["status"] == "awaiting_id"
    assert r["identity_status"] == "pending"
    assert r["deadline_on"] == "2026-06-09"


def test_create_foi_skips_id_step(svc):
    r = svc.create_request(
        "FOI", "Bob Reporter", "bob@news.example",
        "Vice-Chancellor expenses 2024-25",
        received_on=date(2026, 5, 4),  # Mon
    )
    assert r["status"] == "received"
    assert r["identity_status"] == "not_required"
    assert r["deadline_on"] == "2026-06-01"


def test_create_validates_inputs(svc):
    with pytest.raises(InformationRightsError):
        svc.create_request("FOI", "", "x@x.com", "summary")
    with pytest.raises(InformationRightsError):
        svc.create_request("FOI", "x", "no-at-sign", "summary")
    with pytest.raises(InformationRightsError):
        svc.create_request("FOI", "x", "x@x.com", "")
    with pytest.raises(InformationRightsError):
        svc.create_request("XYZ", "x", "x@x.com", "summary")


# -- lifecycle ------------------------------------------------------------

def test_identity_verification_restarts_clock(svc):
    r = svc.create_request("SAR", "A", "a@a.com", "summary",
                           received_on=date(2026, 5, 1))
    assert r["deadline_on"] == "2026-06-01"
    out = svc.mark_identity_verified(
        r["request_id"], verified_on=date(2026, 5, 9))
    assert out["identity_status"] == "verified"
    assert out["status"] == "in_progress"
    assert out["deadline_on"] == "2026-06-09"


def test_identity_verification_only_for_sar(svc):
    r = svc.create_request("FOI", "A", "a@a.com", "summary",
                           received_on=date(2026, 5, 1))
    with pytest.raises(InformationRightsError):
        svc.mark_identity_verified(r["request_id"])


def test_extension_only_once_and_only_for_sar(svc):
    foi = svc.create_request("FOI", "A", "a@a.com", "x",
                             received_on=date(2026, 5, 1))
    with pytest.raises(InformationRightsError):
        svc.apply_extension(foi["request_id"], "complex")

    sar = svc.create_request("SAR", "A", "a@a.com", "x",
                             received_on=date(2026, 5, 1))
    out = svc.apply_extension(sar["request_id"],
                              "Complex multi-system search")
    assert out["extended"] == 1
    assert out["status"] == "extended"
    assert out["deadline_on"] == "2026-08-01"
    with pytest.raises(InformationRightsError):
        svc.apply_extension(sar["request_id"], "again")


def test_extension_requires_reason(svc):
    sar = svc.create_request("SAR", "A", "a@a.com", "x",
                             received_on=date(2026, 5, 1))
    with pytest.raises(InformationRightsError):
        svc.apply_extension(sar["request_id"], "   ")


def test_status_transitions_blocked_when_closed(svc):
    r = svc.create_request("FOI", "A", "a@a.com", "x",
                           received_on=date(2026, 5, 1))
    svc.close_request(r["request_id"], "fully_disclosed")
    with pytest.raises(InformationRightsError):
        svc.set_status(r["request_id"], "in_progress")
    with pytest.raises(InformationRightsError):
        svc.close_request(r["request_id"], "withdrawn")


# -- exemptions / redactions / comms / audit ------------------------------

def test_exemption_redaction_and_audit_chain(svc):
    r = svc.create_request("FOI", "B", "b@b.com", "expenses",
                           received_on=date(2026, 5, 4))
    eid = svc.apply_exemption(
        r["request_id"], "FOIA", "s.40",
        "Personal data of named staff; UK GDPR Art.6 lawful basis "
        "would not be met for disclosure to the world at large.",
        actor="dpo")
    assert eid > 0

    rid = svc.log_redaction(
        r["request_id"], "expenses_2025.pdf",
        "third_party_pii",
        "Names and bank details of contractors redacted under s.40.",
        page="3-5", location="table 2",
        exemption_id=eid, actor="dpo",
    )
    assert rid > 0

    with pytest.raises(InformationRightsError):
        svc.log_redaction(r["request_id"], "x.pdf",
                          "bad_type", "rationale")
    with pytest.raises(InformationRightsError):
        svc.apply_exemption(r["request_id"], "FOIA", "s.40", "")

    cid = svc.log_communication(r["request_id"], "outbound", "email",
                                "Sent partial response", "body...")
    assert cid > 0

    audit = svc.list_audit(r["request_id"])
    events = [a["event"] for a in audit]
    assert "created" in events
    assert "exemption_applied" in events
    assert "redaction_logged" in events
    assert "comm_outbound" in events


def test_redaction_exemption_must_belong_to_request(svc):
    r1 = svc.create_request("FOI", "A", "a@a.com", "x")
    r2 = svc.create_request("FOI", "B", "b@b.com", "y")
    eid = svc.apply_exemption(r1["request_id"], "FOIA", "s.40",
                              "third party")
    with pytest.raises(InformationRightsError):
        svc.log_redaction(r2["request_id"], "f.pdf",
                          "exempt_info", "rationale",
                          exemption_id=eid)


# -- dashboard ------------------------------------------------------------

def test_dashboard_buckets_overdue_and_due_soon(svc):
    today = date(2026, 5, 9)
    overdue = svc.create_request("FOI", "A", "a@a.com", "x",
                                 received_on=date(2026, 3, 1))
    due_soon = svc.create_request("FOI", "B", "b@b.com", "y",
                                  received_on=date(2026, 4, 13))
    svc.create_request("SAR", "C", "c@c.com", "z",
                       received_on=date(2026, 5, 1))

    s = svc.dashboard_summary(today=today)
    refs_overdue = [r["reference"] for r in s["overdue"]]
    refs_due_soon = [r["reference"] for r in s["due_soon"]]
    assert overdue["reference"] in refs_overdue
    # due_soon's FOI deadline = +20wd from 2026-04-13 = 2026-05-11 -> 2 days out
    assert due_soon["reference"] in refs_due_soon
    assert s["total_open"] == 3
    assert s["overdue_count"] >= 1


def test_close_marks_terminal_and_blocks_further_changes(svc):
    r = svc.create_request("FOI", "A", "a@a.com", "x")
    out = svc.close_request(r["request_id"], "refused_exemption",
                            note="s.40 applied")
    assert out["status"] == "refused"
    assert out["outcome"] == "refused_exemption"
    assert out["closed_on"]
