"""Tests for the two follow-ups:

* identity_backfill now stamps journey_id onto existing local rows.
* the journey API is gated to staff-level roles.
"""

import sqlite3

import pytest
from flask import Flask

from education_system.shared.api import auth as api_auth
from education_system.shared.api.journey_routes import journey_bp
from education_system.shared.auth.schema import initialise_auth_db
from education_system.shared.cross_system import identity_backfill, identity_service


# ── Backfill stamping ────────────────────────────────────────────────────

@pytest.fixture()
def auth_db(tmp_path):
    path = str(tmp_path / "auth.db")
    initialise_auth_db(path)
    identity_service._initialised.discard(path)
    return path


def _make_primary_db(tmp_path):
    """A primary.db with two pre-existing pupils and NO journey_id column."""
    p = tmp_path / "primary.db"
    conn = sqlite3.connect(str(p))
    conn.execute(
        "CREATE TABLE pupils (pupil_id TEXT PRIMARY KEY, first_name TEXT, "
        "last_name TEXT, date_of_birth TEXT)")
    conn.executemany(
        "INSERT INTO pupils VALUES (?,?,?,?)",
        [("P1", "Ada", "Lovelace", "2015-12-10"),
         ("P2", "Grace", "Hopper", "2015-12-09")])
    conn.commit()
    conn.close()
    return p


def test_backfill_stamps_existing_rows(tmp_path, auth_db):
    primary = _make_primary_db(tmp_path)
    stats = identity_backfill.backfill_system(
        "primary", db_path=str(primary), auth_db=auth_db)

    assert stats["linked"] == 2
    assert stats["stamped"] == 2

    # The journey_id column was added and populated, and it matches the
    # registry's journey for that pupil.
    conn = sqlite3.connect(str(primary))
    conn.row_factory = sqlite3.Row
    rows = {r["pupil_id"]: r["journey_id"]
            for r in conn.execute(
                "SELECT pupil_id, journey_id FROM pupils").fetchall()}
    conn.close()
    assert all(rows.values()), "every row should be stamped"

    j = identity_service.find_by_student("primary", "P1", db_path=auth_db)
    assert rows["P1"] == j["journey_id"]


def test_backfill_dry_run_does_not_stamp(tmp_path, auth_db):
    primary = _make_primary_db(tmp_path)
    stats = identity_backfill.backfill_system(
        "primary", db_path=str(primary), auth_db=auth_db, dry_run=True)
    assert stats["linked"] == 2
    assert stats["stamped"] == 0
    conn = sqlite3.connect(str(primary))
    cols = {r[1] for r in conn.execute("PRAGMA table_info(pupils)").fetchall()}
    conn.close()
    assert "journey_id" not in cols  # untouched


def test_backfill_stamp_false(tmp_path, auth_db):
    primary = _make_primary_db(tmp_path)
    stats = identity_backfill.backfill_system(
        "primary", db_path=str(primary), auth_db=auth_db, stamp=False)
    assert stats["linked"] == 2
    assert stats["stamped"] == 0


def test_backfill_is_idempotent(tmp_path, auth_db):
    primary = _make_primary_db(tmp_path)
    identity_backfill.backfill_system("primary", db_path=str(primary),
                                      auth_db=auth_db)
    again = identity_backfill.backfill_system("primary", db_path=str(primary),
                                              auth_db=auth_db)
    assert again["linked"] == 2 and again["stamped"] == 2
    # Still only two journeys in the registry.
    conn = sqlite3.connect(auth_db)
    n = conn.execute("SELECT COUNT(*) FROM student_journey").fetchone()[0]
    conn.close()
    assert n == 2


# ── API role gating ──────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _jwt_secret(monkeypatch):
    monkeypatch.setenv(
        "JWT_SECRET_KEY", "test-secret-for-journey-api-0123456789abcdef")


@pytest.fixture()
def client():
    app = Flask(__name__)
    app.register_blueprint(journey_bp, url_prefix="/api/v1/journey")
    return app.test_client()


def _token(systems):
    return api_auth.generate_token(1, "tester", systems)


def _auth(systems):
    return {"Authorization": f"Bearer {_token(systems)}"}


def test_api_requires_authentication(client):
    r = client.get("/api/v1/journey/abc/overview")
    assert r.status_code == 401


def test_api_refuses_student_and_parent(client):
    for role in ("student", "parent"):
        r = client.get("/api/v1/journey/abc/overview",
                       headers=_auth([{"system_key": "primary", "role": role}]))
        assert r.status_code == 403, f"{role} should be refused"


@pytest.mark.parametrize("role", ["admin", "staff", "teacher"])
def test_api_allows_staff_roles(client, role):
    # Passes the role gate; the (unknown) journey then yields 404, proving
    # the handler ran rather than being blocked at the gate.
    r = client.get(
        "/api/v1/journey/does-not-exist/overview",
        headers=_auth([{"system_key": "secondary", "role": role}]))
    assert r.status_code == 404


def test_api_staff_in_any_system_is_allowed(client):
    # Student in primary but teacher in school → allowed (cross-system).
    r = client.get(
        "/api/v1/journey/does-not-exist/overview",
        headers=_auth([
            {"system_key": "primary", "role": "student"},
            {"system_key": "secondary", "role": "teacher"},
        ]))
    assert r.status_code == 404
