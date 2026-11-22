"""Applicant portal: code sign-in, applicant-only view, offer replies,
uploads and contact changes — all logged "via applicant portal"."""

from __future__ import annotations

import datetime as _dt
import re

import pytest

from education_system.systems.sixth_form.domain.admissions import (
    admissions as adm,
)
from education_system.systems.sixth_form.domain.admissions import (
    applicant_portal as portal,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)

DOB = "2010-03-04"


@pytest.fixture
def applicant(admdb, outbox, sign_in, applicant_payload, monkeypatch):
    sign_in("adm1")
    a = adm.create_applicant(applicant_payload(notes="staff note"))
    # The portal runs with nobody signed in.
    monkeypatch.setattr(access, "_current", access.ANONYMOUS)
    return a


def _code(outbox) -> str:
    m = [x for x in outbox if x.subject == "Your applicant portal code"][-1]
    return re.search(r"code is: (\d{6})", m.body).group(1)


def _sign_in(a, outbox) -> str:
    portal.request_code(a.applicant_id, DOB, client_ip="1.1.1.1")
    return portal.verify_code(a.applicant_id, DOB, _code(outbox),
                              client_ip="1.1.1.1")


def test_wrong_dob_sends_nothing(applicant, outbox):
    portal.request_code(applicant.applicant_id, "2000-01-01",
                        client_ip="1.1.1.1")
    assert outbox == []


def test_code_is_single_use_and_hashed(applicant, outbox, admdb):
    portal.request_code(applicant.applicant_id, DOB, client_ip="1.1.1.1")
    code = _code(outbox)
    with adm._connect() as conn:
        stored = conn.execute("SELECT code_hash FROM admissions_portal_codes"
                              ).fetchone()[0]
    assert code not in stored
    token = portal.verify_code(applicant.applicant_id, DOB, code,
                               client_ip="1.1.1.1")
    assert token
    with pytest.raises(portal.AuthFailed):
        portal.verify_code(applicant.applicant_id, DOB, code,
                           client_ip="1.1.1.1")


def test_code_attempt_limit(applicant, outbox):
    portal.request_code(applicant.applicant_id, DOB, client_ip="2.2.2.2")
    code = _code(outbox)
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(portal.MAX_CODE_ATTEMPTS):
        with pytest.raises(portal.AuthFailed):
            portal.verify_code(applicant.applicant_id, DOB, wrong,
                               client_ip=f"9.9.9.{_}")
    with pytest.raises(portal.AuthFailed):
        portal.verify_code(applicant.applicant_id, DOB, code,
                           client_ip="2.2.2.2")


def test_failed_lookups_rate_limited(applicant):
    with pytest.raises(portal.RateLimited):
        for _ in range(portal.MAX_FAILURES_PER_CLIENT + 1):
            portal.request_code("OA-NOPE2345", DOB, client_ip="3.3.3.3")


def test_view_hides_internal_detail(applicant, outbox):
    token = _sign_in(applicant, outbox)
    view = portal.status_view(token)
    text = repr(view)
    assert view["stage"] == "Under review"
    assert "staff note" not in text
    assert "reference_status" not in text


def test_accept_offer(applicant, outbox, sign_in, monkeypatch):
    sign_in("adm1")
    adm.make_offer(applicant.applicant_id, conditions="6 in Maths")
    monkeypatch.setattr(access, "_current", access.ANONYMOUS)
    token = _sign_in(applicant, outbox)
    view = portal.status_view(token)
    assert view["can_respond_to_offer"] and view["offer"]["conditions"] \
        == "6 in Maths"
    assert portal.accept_offer(token)["stage"] == "Offer accepted"
    sign_in("adm1")
    a = adm.get_applicant(applicant.applicant_id)
    assert a.status == "Offer Accepted"
    assert any("via applicant portal" in e.detail
               and e.actor == "system:applicant-portal"
               for e in adm.list_events(a.applicant_id))


def test_decline_needs_listed_reason(applicant, outbox, sign_in, monkeypatch):
    sign_in("adm1")
    adm.make_offer(applicant.applicant_id)
    monkeypatch.setattr(access, "_current", access.ANONYMOUS)
    token = _sign_in(applicant, outbox)
    with pytest.raises(portal.PortalError):
        portal.decline_offer(token, "because")
    view = portal.decline_offer(token, adm.WITHDRAWAL_REASONS[0])
    assert view["stage"] == "Offer declined"


def test_expired_offer_cannot_be_accepted(applicant, outbox, sign_in,
                                          monkeypatch):
    sign_in("adm1")
    adm.make_offer(applicant.applicant_id)
    adm.set_offer_expiry(applicant.applicant_id,
                         (_dt.date.today() - _dt.timedelta(days=1)).isoformat())
    monkeypatch.setattr(access, "_current", access.ANONYMOUS)
    token = _sign_in(applicant, outbox)
    with pytest.raises(portal.PortalError, match="expired"):
        portal.accept_offer(token)


def test_upload_limits(applicant, outbox, monkeypatch):
    token = _sign_in(applicant, outbox)
    out = portal.upload_document(token, "../my file.pdf", b"%PDF-1.4 x",
                                 doc_type="Transcript")
    assert out["label"] == "my_file.pdf (applicant portal)"
    with pytest.raises(portal.PortalError):
        portal.upload_document(token, "x.pdf", b"MZ not a pdf")
    with pytest.raises(portal.PortalError):
        portal.upload_document(token, "x.pdf", b"%PDF-1.4 x",
                               doc_type="Reference Letter")
    monkeypatch.setattr(portal, "MAX_UPLOAD_BYTES", 8)
    with pytest.raises(portal.PortalError):
        portal.upload_document(token, "x.pdf", b"%PDF-1.4 too big")
    assert len(portal.status_view(token)["documents"]) == 1


def test_contact_change_notifies_old_address(applicant, outbox):
    token = _sign_in(applicant, outbox)
    view = portal.update_contact(token, email="new@example.com")
    assert view["contact"]["email"] == "new@example.com"
    notice = outbox[-1]
    assert notice.to_address == "zed.t@example.com"
    assert "changed" in notice.subject
    with pytest.raises(portal.PortalError):
        portal.update_contact(token, email="not-an-email")


def test_sign_out_ends_session(applicant, outbox):
    token = _sign_in(applicant, outbox)
    portal.sign_out(token)
    with pytest.raises(portal.AuthFailed):
        portal.status_view(token)


def test_bad_token(applicant):
    with pytest.raises(portal.AuthFailed):
        portal.status_view("nope")
