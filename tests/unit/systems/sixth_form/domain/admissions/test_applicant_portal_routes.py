"""Applicant portal + application form routes on a bare Flask app (the
domain runs on the temp DB with the faked outbox)."""

from __future__ import annotations

import io
import re

import pytest

from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)

PREFIX = "/api/v1/sixthform/applicant-portal"
FORM = {
    "first_name": "Rae", "last_name": "Routetest", "dob": "2010-01-01",
    "email": "rae@example.com", "phone": "07700900999",
    "subject_1": "Mathematics", "predicted_gcses": "Maths 6",
    "previous_school": "Old School", "privacy_notice_accepted": True,
}


@pytest.fixture
def client(admdb, outbox, monkeypatch):
    flask = pytest.importorskip("flask")
    from education_system.api.sixth_form.routes import (
        applicant_portal_routes,
        applications_routes,
    )
    monkeypatch.setattr(access, "_current", access.ANONYMOUS)
    monkeypatch.setattr(applications_routes, "_hits", {})
    monkeypatch.setattr(applicant_portal_routes, "_hits", {})
    app = flask.Flask(__name__)
    for bp in (applications_routes.applications_bp,
               applicant_portal_routes.applicant_portal_bp):
        app.register_blueprint(
            bp, url_prefix=bp.url_prefix.replace("/api", "/api/v1/sixthform"))
    return app.test_client()


def _code(outbox) -> str:
    m = [x for x in outbox if x.subject == "Your applicant portal code"][-1]
    return re.search(r"code is: (\d{6})", m.body).group(1)


def test_apply_then_portal_round_trip(client, outbox):
    r = client.post("/api/v1/sixthform/applications", json=FORM)
    assert r.status_code == 201 and set(r.json) == {"reference"}
    ref = r.json["reference"]

    same = {"identifier": ref, "dob": "2010-01-01"}
    r1 = client.post(f"{PREFIX}/code", json=same)
    r2 = client.post(f"{PREFIX}/code", json={"identifier": "OA-ZZZZ2345",
                                              "dob": "2010-01-01"})
    assert r1.status_code == r2.status_code == 202
    assert r1.json == r2.json
    assert r1.headers["Cache-Control"] == "no-store"

    r = client.post(f"{PREFIX}/session", json={**same, "code": _code(outbox)})
    assert r.status_code == 200
    h = {"Authorization": f"Bearer {r.json['token']}"}

    r = client.get(f"{PREFIX}/status", headers=h)
    assert r.status_code == 200 and r.json["stage"] == "Received"

    r = client.post(f"{PREFIX}/documents", headers=h,
                    data={"doc_type": "Other",
                          "file": (io.BytesIO(b"%PDF-1.4 x"), "cv.pdf")},
                    content_type="multipart/form-data")
    assert r.status_code == 201

    r = client.put(f"{PREFIX}/contact", headers=h, json={"role": "admin"})
    assert r.status_code == 400

    r = client.post(f"{PREFIX}/offer/accept", headers=h)
    assert r.status_code == 400 and "offer" in r.json["error"]

    assert client.delete(f"{PREFIX}/session", headers=h).status_code == 204
    assert client.get(f"{PREFIX}/status", headers=h).status_code == 401


def test_status_without_token_is_401(client):
    r = client.get(f"{PREFIX}/status")
    assert r.status_code == 401 and set(r.json) == {"error"}


def test_honeypot_looks_like_success(client, outbox):
    r = client.post("/api/v1/sixthform/applications",
                    json={**FORM, "website": "spam"})
    assert r.status_code == 201 and r.json["reference"].startswith("OA-")
    assert outbox == []


def test_forwarded_for_only_from_trusted_proxy(client, monkeypatch):
    from flask import Flask

    from education_system.api.sixth_form.routes import applications_routes
    app = Flask(__name__)
    xff = {"X-Forwarded-For": "6.6.6.6, 7.7.7.7"}
    monkeypatch.delenv(applications_routes.TRUSTED_PROXIES_ENV, raising=False)
    with app.test_request_context(headers=xff,
                                  environ_base={"REMOTE_ADDR": "10.0.0.1"}):
        assert applications_routes.client_ip() == "10.0.0.1"
    monkeypatch.setenv(applications_routes.TRUSTED_PROXIES_ENV, "10.0.0.0/8")
    with app.test_request_context(headers=xff,
                                  environ_base={"REMOTE_ADDR": "10.0.0.1"}):
        assert applications_routes.client_ip() == "7.7.7.7"
    with app.test_request_context(headers=xff,
                                  environ_base={"REMOTE_ADDR": "8.8.8.8"}):
        assert applications_routes.client_ip() == "8.8.8.8"
