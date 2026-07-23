"""Tests for the REST API + signed tokens."""

from __future__ import annotations

import pytest


# ── tokens ───────────────────────────────────────────────────────────

def test_token_round_trip():
    from education_system.post_16.sixthform_system.api import tokens
    tok = tokens.issue(42, now=1000.0)
    assert tokens.verify(tok, now=1000.0) == 42


def test_token_expiry():
    from education_system.post_16.sixthform_system.api import tokens
    tok = tokens.issue(7, ttl=10, now=1000.0)
    assert tokens.verify(tok, now=1005.0) == 7
    assert tokens.verify(tok, now=2000.0) is None        # expired


def test_token_tamper_detected():
    from education_system.post_16.sixthform_system.api import tokens
    tok = tokens.issue(1, now=1000.0)
    payload, sig = tok.split(".", 1)
    forged = payload + ".AAAA"
    assert tokens.verify(forged, now=1000.0) is None
    assert tokens.verify("garbage", now=1000.0) is None


# ── app ──────────────────────────────────────────────────────────────

@pytest.fixture
def client(feature_db):
    from education_system.post_16.sixthform_system.api import create_app
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_parent_login_and_scoped_access(client, feature_db):
    pp = feature_db.mods["parent_portal"]
    aid = pp.create_account(username="apiparent", password="password1", full_name="Pat")
    pp.link_student(aid, "S1")

    bad = client.post("/api/parent/login", json={"username": "apiparent", "password": "x"})
    assert bad.status_code == 401

    ok = client.post("/api/parent/login", json={"username": "apiparent", "password": "password1"})
    assert ok.status_code == 200
    token = ok.get_json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = client.get("/api/parent/me", headers=headers)
    assert me.status_code == 200
    assert len(me.get_json()["children"]) == 1

    child = client.get("/api/parent/children/S1", headers=headers)
    assert child.status_code == 200
    assert child.get_json()["full_name"] == "Alex Atrisk"

    # S2 is not linked to this account → forbidden.
    assert client.get("/api/parent/children/S2", headers=headers).status_code == 403
    # No token at all → unauthorised.
    assert client.get("/api/parent/me").status_code == 401


def test_staff_endpoints_open_in_dev(client, monkeypatch):
    monkeypatch.delenv("EDU_SIXTHFORM_API_KEY", raising=False)
    assert client.get("/api/risk/summary").status_code == 200
    assert client.post("/api/risk/scan").status_code == 200
    assert client.get("/api/risk/register").status_code == 200
    assert client.get("/api/ucas/overview").status_code == 200
    assert client.get("/api/automation/actions").status_code == 200


def test_staff_endpoints_require_key_when_set(client, monkeypatch):
    monkeypatch.setenv("EDU_SIXTHFORM_API_KEY", "s3cret")
    assert client.get("/api/risk/summary").status_code == 401
    ok = client.get("/api/risk/summary", headers={"X-API-Key": "s3cret"})
    assert ok.status_code == 200


def test_risk_student_404(client, monkeypatch):
    monkeypatch.delenv("EDU_SIXTHFORM_API_KEY", raising=False)
    assert client.get("/api/risk/student/NOPE").status_code == 404
    good = client.get("/api/risk/student/S1")
    assert good.status_code == 200
    assert good.get_json()["band"] in ("Low", "Medium", "High", "Critical")
