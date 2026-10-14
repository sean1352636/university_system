"""The linked-platform API: learners, transfers, systems and events.

A bare Flask app with only the learners blueprint, a temp auth DB (also the
one ``token_required`` re-reads users from) and a temp audit DB. The full
app factory is not used: it mounts every system's routes, and importing
those can write to the live databases.
"""

import sqlite3

import pytest
from flask import Flask

from education_system.paths import SYSTEM_ORDER
from education_system.platform.cross_system import enrolment_schema, identity_service
from education_system.platform.delivery.api import registry
from education_system.platform.delivery.api.routes import learners_routes
from education_system.platform.delivery.api.security import authentication
from education_system.platform.identity.auth.schema import initialise_auth_db

SUPERADMIN = [(s, "admin") for s in ("university", "sixth_form", "secondary", "primary")]


@pytest.fixture(autouse=True)
def _jwt_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-for-learners-api-0123456789abcdef")


@pytest.fixture()
def auth_db(tmp_path, monkeypatch):
    path = str(tmp_path / "auth.db")
    initialise_auth_db(path)
    identity_service._initialised.discard(path)
    enrolment_schema._initialised.discard(path)
    monkeypatch.setattr(authentication, "_auth_db_path", path)
    return path


@pytest.fixture()
def audit_db(tmp_path):
    return str(tmp_path / "audit.db")


@pytest.fixture()
def client(auth_db, audit_db):
    learners_routes.init_learner_routes(db_path=auth_db, audit_db_path=audit_db)
    app = Flask(__name__)
    app.register_blueprint(learners_routes.learners_bp, url_prefix="/api/v1")
    yield app.test_client()
    learners_routes.init_learner_routes()


@pytest.fixture()
def journey(auth_db):
    return identity_service.get_or_create_journey(
        first_name="Grace", last_name="Hopper", date_of_birth="2010-12-09",
        system="secondary", student_id="Y11-7", db_path=auth_db)


def _login(db, username, systems):
    conn = sqlite3.connect(db)
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, display_name, is_active) "
        "VALUES (?, 'x', ?, 1)", (username, username))
    uid = cur.lastrowid
    for system, role in systems:
        conn.execute("INSERT INTO user_systems (user_id, system_key, role) "
                     "VALUES (?, ?, ?)", (uid, system, role))
    conn.commit()
    conn.close()
    token = authentication.generate_token(
        uid, username, [{"system_key": s, "role": r} for s, r in systems])
    return {"Authorization": f"Bearer {token}"}


def _audit_rows(audit_db, action, resource_id=None):
    conn = sqlite3.connect(audit_db)
    sql = "SELECT COUNT(*) FROM audit_log WHERE action = ?"
    args = [action]
    if resource_id is not None:
        sql += " AND resource_id = ?"
        args.append(resource_id)
    n = conn.execute(sql, args).fetchone()[0]
    conn.close()
    return n


# ── Scoping helpers ──────────────────────────────────────────────────────

def test_platform_paths_are_unscoped():
    f = authentication._system_key_from_path
    for path in ("/api/v1/learners/abc", "/api/v1/systems", "/api/v1/events",
                 "/api/v1/transfers/x/approve", "/api/v1/progression", "/api/v1/tasks"):
        assert f(path) is None, path
    assert f("/api/v1/sixthform/students") == "sixth_form"


def test_mount_table_names_all_seven_systems():
    assert set(registry.mounts_by_system()) == set(SYSTEM_ORDER)


# ── Learners ─────────────────────────────────────────────────────────────

def test_learner_requires_authentication(client, journey):
    assert client.get(f"/api/v1/learners/{journey}").status_code == 401


def test_student_is_refused(client, auth_db, journey):
    headers = _login(auth_db, "api_student", [("secondary", "student")])
    assert client.get(f"/api/v1/learners/{journey}", headers=headers).status_code == 403


def test_staff_of_the_learners_system_can_read_and_it_is_audited(
        client, auth_db, audit_db, journey):
    headers = _login(auth_db, "api_teacher", [("secondary", "teacher")])
    r = client.get(f"/api/v1/learners/{journey}", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert body["journey_id"] == journey
    assert "secondary" in body["systems"]
    assert body["source"] in ("learner_360", "fallback")
    assert _audit_rows(audit_db, "cross_system.access", journey) == 1


def test_staff_of_another_system_is_refused(client, auth_db, journey):
    headers = _login(auth_db, "api_primary_teacher", [("primary", "teacher")])
    assert client.get(f"/api/v1/learners/{journey}", headers=headers).status_code == 403


def test_superadmin_reads_any_learner_and_unknown_is_404(client, auth_db, journey):
    headers = _login(auth_db, "api_boss", SUPERADMIN)
    assert client.get(f"/api/v1/learners/{journey}", headers=headers).status_code == 200
    assert client.get("/api/v1/learners/no-such-journey",
                      headers=headers).status_code == 404


@pytest.mark.parametrize("view, key", [("history", "enrolments"),
                                       ("progression", "transitions"),
                                       ("qualifications", "qualifications"),
                                       ("enrolments", "enrolments")])
def test_learner_sub_views(client, auth_db, journey, view, key):
    headers = _login(auth_db, f"api_viewer_{view}", [("secondary", "teacher")])
    r = client.get(f"/api/v1/learners/{journey}/{view}", headers=headers)
    assert r.status_code == 200
    assert key in r.get_json()


# ── Starting and acting on transfers ─────────────────────────────────────

def test_transfer_lifecycle_and_scoping(client, auth_db, audit_db, journey):
    school_admin = _login(auth_db, "api_school_admin", [("secondary", "admin")])
    college_admin = _login(auth_db, "api_college_admin", [("sixth_form", "admin")])
    primary_admin = _login(auth_db, "api_primary_admin", [("primary", "admin")])

    r = client.post("/api/v1/transfers", headers=school_admin,
                    json={"journey_id": journey, "destination_system": "sixth_form"})
    assert r.status_code == 201, r.get_json()
    tid = r.get_json()["transition_id"]
    assert r.get_json()["source_system"] == "secondary"
    assert _audit_rows(audit_db, "cross_system.transfer", tid) == 1

    # Listing is scoped to the systems at either end.
    assert client.get("/api/v1/transfers", headers=college_admin).get_json()["count"] == 1
    assert client.get("/api/v1/transfers", headers=primary_admin).get_json()["count"] == 0
    assert client.get(f"/api/v1/transfers/{tid}", headers=primary_admin).status_code == 403
    events = client.get(f"/api/v1/transfers/{tid}/events", headers=college_admin)
    assert events.status_code == 200 and events.get_json()["events"]

    # Approval releases the source's information: the college cannot do it.
    assert client.post(f"/api/v1/transfers/{tid}/approve", headers=college_admin,
                       json={"handover": {"first_name": "Grace"}}).status_code == 403
    r = client.post(f"/api/v1/transfers/{tid}/approve", headers=school_admin,
                    json={"handover": {"first_name": "Grace"},
                          "consent_reference": "C-1"})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["status"] == "handover_approved"
    assert r.get_json()["has_handover"] is True
    assert "handover_json" not in r.get_json()
    assert _audit_rows(audit_db, "cross_system.handover", tid) == 1

    # Rejection needs a reason; completion belongs to the destination.
    assert client.post(f"/api/v1/transfers/{tid}/reject", headers=college_admin,
                       json={}).status_code == 400
    assert client.post(f"/api/v1/transfers/{tid}/complete", headers=school_admin,
                       json={}).status_code == 403
    r = client.post(f"/api/v1/transfers/{tid}/complete", headers=college_admin,
                    json={"start_date": "2027-09-06"})
    assert r.status_code == 200 and r.get_json()["status"] == "completed"
    # A closed transfer cannot move again.
    assert client.post(f"/api/v1/transfers/{tid}/complete", headers=college_admin,
                       json={}).status_code == 409


def test_progression_needs_approve_at_the_source(client, auth_db, journey):
    teacher = _login(auth_db, "api_teacher2", [("secondary", "teacher")])
    assert client.post("/api/v1/progression", headers=teacher,
                       json={"journey_id": journey}).status_code == 403
    college_admin = _login(auth_db, "api_college_admin2", [("sixth_form", "admin")])
    # Holds transfer.approve, but not at this learner's source (secondary).
    assert client.post("/api/v1/progression", headers=college_admin,
                       json={"journey_id": journey}).status_code == 403
    school_admin = _login(auth_db, "api_school_admin2", [("secondary", "admin")])
    r = client.post("/api/v1/progression", headers=school_admin,
                    json={"journey_id": journey})
    assert r.status_code == 201
    assert r.get_json()["destination_system"]  # the recommended next phase
    assert client.post("/api/v1/transfers", headers=school_admin,
                       json={"journey_id": journey}).status_code == 400


def test_action_that_the_workflow_lacks_is_501_or_works(client, auth_db, journey):
    school_admin = _login(auth_db, "api_school_admin3", [("secondary", "admin")])
    college_admin = _login(auth_db, "api_college_admin3", [("sixth_form", "admin")])
    tid = client.post("/api/v1/transfers", headers=school_admin, json={
        "journey_id": journey, "destination_system": "sixth_form"}).get_json()["transition_id"]
    r = client.post(f"/api/v1/transfers/{tid}/reject", headers=college_admin,
                    json={"reason": "No places"})
    # 501 until transitions.reject exists; then a normal 200.
    assert r.status_code in (200, 501)


# ── Systems, events, dead letters ────────────────────────────────────────

def test_systems_lists_all_seven(client, auth_db, monkeypatch):
    from education_system.platform.features.analytics import platform_registry
    # Resolving the real manifests imports every system package; the mount
    # data under test is the platform's own.
    monkeypatch.setattr(platform_registry, "manifests", lambda: ([
        {"key": k, "display_name": k, "package_dir": None, "interfaces": []}
        for k in SYSTEM_ORDER], None))
    headers = _login(auth_db, "api_teacher3", [("secondary", "teacher")])
    body = client.get("/api/v1/systems", headers=headers).get_json()
    assert body["count"] == 7
    by_key = {row["key"]: row for row in body["systems"]}
    assert by_key["sixth_form"]["api_prefix"] == "/api/v1/sixthform"
    assert "intake" not in by_key["sixth_form"]  # ops detail needs events.view


def test_events_are_scoped_and_payloads_superadmin_only(client, auth_db, journey):
    school_admin = _login(auth_db, "api_school_admin4", [("secondary", "admin")])
    client.post("/api/v1/transfers", headers=school_admin,
                json={"journey_id": journey, "destination_system": "sixth_form"})

    body = client.get("/api/v1/events", headers=school_admin).get_json()
    assert body["count"] >= 1
    assert all("payload" not in e for e in body["events"])

    boss = _login(auth_db, "api_boss2", SUPERADMIN)
    body = client.get("/api/v1/events", headers=boss).get_json()
    assert all("payload" in e for e in body["events"])

    primary_admin = _login(auth_db, "api_primary_admin2", [("primary", "admin")])
    assert client.get("/api/v1/events", headers=primary_admin).get_json()["count"] == 0
    teacher = _login(auth_db, "api_teacher4", [("secondary", "teacher")])
    assert client.get("/api/v1/events", headers=teacher).status_code == 403
    assert client.get("/api/v1/events?status=bogus", headers=boss).status_code == 400


def test_dead_letters_are_superadmin_only(client, auth_db):
    school_admin = _login(auth_db, "api_school_admin5", [("secondary", "admin")])
    assert client.get("/api/v1/events/dead-letters",
                      headers=school_admin).status_code == 403
    boss = _login(auth_db, "api_boss3", SUPERADMIN)
    assert client.get("/api/v1/events/dead-letters", headers=boss).status_code == 200
    assert client.post("/api/v1/events/dead-letters/retry", headers=boss,
                       json={}).status_code == 400


def test_tasks_endpoint(client, auth_db):
    headers = _login(auth_db, "api_teacher5", [("secondary", "teacher")])
    r = client.get("/api/v1/tasks", headers=headers)
    assert r.status_code == 200 and "tasks" in r.get_json()
