"""Online form hardening: honeypot, salt, atomic submit, confirmation
e-mail, consents and parent contact."""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.admissions import (
    admissions as adm,
)
from education_system.systems.sixth_form.domain.admissions import (
    applicant_details as det,
)
from education_system.systems.sixth_form.domain.admissions import (
    online_application as oa,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)

FORM = {
    "first_name": "Olly", "last_name": "Formtest", "dob": "2010-01-01",
    "email": "olly@example.com", "phone": "07700900999",
    "subject_1": "Mathematics", "predicted_gcses": "Maths 6",
    "previous_school": "Old School", "privacy_notice_accepted": True,
}


@pytest.fixture
def form_env(admdb, outbox, sign_in, monkeypatch):
    monkeypatch.setattr(oa, "_salt_cache", None)
    monkeypatch.setattr(access, "_current", access.ANONYMOUS)
    return outbox


def _staff(sign_in):
    sign_in("adm1")


def test_submit_confirms_and_stores_extras(form_env, sign_in):
    ref = oa.submit({**FORM, "consent_contact_school": True,
                     "parent_consent": True, "parent_name": "Pat Formtest",
                     "parent_relationship": "Mother",
                     "parent_email": "pat@example.com"}, client_ip="10.0.0.1")
    _staff(sign_in)
    sub = oa.get_submission(reference_no=ref)
    a = adm.get_applicant(sub.applicant_id)
    assert a.status == adm.ONLINE_UNVERIFIED
    assert a.consent_contact_school and a.parent_consent
    assert [c.email for c in det.list_contacts(a.applicant_id)] \
        == ["pat@example.com"]
    confirm = form_env[-1]
    assert confirm.to_address == "olly@example.com" and ref in confirm.body


def test_honeypot_accepted_and_dropped(form_env, sign_in):
    ref = oa.submit({**FORM, oa.HONEYPOT_FIELD: "http://spam"},
                    client_ip="10.0.0.2")
    assert ref.startswith("OA-")
    _staff(sign_in)
    assert oa.get_submission(reference_no=ref) is None
    assert adm.list_applicants(search="Formtest") == []
    assert form_env == []


def test_bad_parent_contact_rejected_up_front(form_env, sign_in):
    with pytest.raises(oa.ValidationError, match="parent"):
        oa.submit({**FORM, "parent_name": "Pat"}, client_ip="10.0.0.3")
    _staff(sign_in)
    assert adm.list_applicants(search="Formtest") == []


def test_mail_failure_does_not_fail_submission(form_env, sign_in,
                                               monkeypatch):
    from education_system.systems.sixth_form.domain.admissions import (
        admissions_comms,
    )

    def boom(*a, **k):
        raise RuntimeError("outbox down")
    monkeypatch.setattr(admissions_comms, "send_application_received", boom)
    ref = oa.submit(FORM, client_ip="10.0.0.4")
    _staff(sign_in)
    assert oa.get_submission(reference_no=ref).applicant_id


def test_failed_link_leaves_nothing_behind(form_env, sign_in, monkeypatch):
    real = adm._log_event

    def fail_on_received(conn, aid, detail, **kw):
        if detail.startswith("Online application"):
            raise RuntimeError("disk full")
        return real(conn, aid, detail, **kw)
    monkeypatch.setattr(adm, "_log_event", fail_on_received)
    with pytest.raises(RuntimeError):
        oa.submit(FORM, client_ip="10.0.0.5")
    monkeypatch.setattr(adm, "_log_event", real)
    _staff(sign_in)
    assert adm.list_applicants(search="Formtest") == []
    with adm._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM "
                            "admissions_online_submissions").fetchone()[0] == 0


def test_failed_create_releases_reservation(form_env, monkeypatch, sign_in):
    def boom(*a, **k):
        raise adm.ValidationError("nope")
    monkeypatch.setattr(adm, "create_applicant", boom)
    with pytest.raises(adm.ValidationError):
        oa.submit(FORM, client_ip="10.0.0.6")
    with adm._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM "
                            "admissions_online_submissions").fetchone()[0] == 0


def test_throttle(form_env, monkeypatch):
    monkeypatch.setattr(oa, "MAX_PER_WINDOW", 1)
    oa.submit(FORM, client_ip="10.0.0.7")
    with pytest.raises(oa.RateLimited):
        oa.submit({**FORM, "email": "other@example.com"},
                  client_ip="10.0.0.7")


def test_salt_fails_closed_in_production(monkeypatch, tmp_path):
    from education_system import paths
    monkeypatch.delenv("SIXTHFORM_APPLY_SALT", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setattr(oa, "_salt_cache", None)
    monkeypatch.setattr(paths, "PLATFORM_SECRETS_DIR", tmp_path)
    with pytest.raises(oa.SaltNotConfigured):
        oa.client_hash("1.2.3.4")
    (tmp_path / oa.SALT_FILE_NAME).write_text("file-salt\n")
    assert oa.apply_salt() == "file-salt"
    monkeypatch.setattr(oa, "_salt_cache", None)
    (tmp_path / oa.SALT_FILE_NAME).unlink()
    monkeypatch.setenv("APP_ENV", "development")
    assert oa.client_hash("1.2.3.4") != oa.client_hash("1.2.3.5")
