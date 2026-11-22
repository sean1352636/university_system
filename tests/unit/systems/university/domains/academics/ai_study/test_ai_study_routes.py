"""AI study API: every route goes through the service and is scoped to the caller.

Regression cover for: ``GET /plans?search=`` crashing (``(pattern)`` was not
a tuple); ``GET /plans``, ``/flashcards/due`` and ``/flashcards/decks``
returning any student's rows; and ``PUT /tasks/<id>/complete`` bypassing the
service so no study time was logged.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt
import pytest
from flask import Flask

from education_system.platform.delivery.api.university.auth import _blacklisted_tokens

from datetime import date as _date, timedelta as _timedelta


def day(offset: int) -> str:
    return (_date.today() + _timedelta(days=offset)).isoformat()

PLANNING = ("education_system.systems.university.domains.student_life."
            "domain.study_hub.services.planning")

_SECRET = "ai-study-routes-test"
_ROUTES = "education_system.api.university.academics.ai_study_routes"


def _headers(sub, role="student"):
    payload = {"sub": sub, "user_id": 1, "role": role, "type": "access",
               "iat": datetime.now(timezone.utc),
               "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    return {"Authorization": "Bearer " + jwt.encode(payload, _SECRET, algorithm="HS256")}


def _context(connection):
    context = MagicMock()
    context.__enter__.return_value = connection
    context.__exit__.return_value = False
    return context


@pytest.fixture()
def client(db, student):
    from education_system.api.university.academics import ai_study_routes
    _, transaction = db
    with transaction() as conn:
        conn.execute("INSERT OR IGNORE INTO students (student_id, first_name, last_name) "
                     "VALUES ('S2', 'Bob', 'Two')")
        conn.execute("INSERT OR IGNORE INTO users (username, role, student_id) "
                     "VALUES ('s2', 'student', 'S2')")
    app = Flask(__name__)
    app.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=False, API_CONFIG={
        "jwt": {"secret_key": _SECRET, "algorithm": "HS256"}, "rate_limiting": {"enabled": False}})
    app.register_blueprint(ai_study_routes.ai_study_bp)
    _blacklisted_tokens.clear()
    ai_study_routes._service = None
    identity = MagicMock()
    identity.execute.return_value.fetchone.return_value = (1,)
    with patch("education_system.platform.identity.auth.db.connect",
               return_value=_context(identity)), \
            patch(f"{_ROUTES}.log_activity"), patch(f"{PLANNING}.log_activity"), \
            patch("education_system.systems.university.application.teaching.occurrences."
                  "send_emails", side_effect=lambda e: len(e)):
        yield app.test_client()
    ai_study_routes._service = None
    _blacklisted_tokens.clear()


S1, S2 = _headers("s1"), _headers("s2")
ADMIN = _headers("admin", "admin")


def _plan(client):
    r = client.post("/api/ai-study/plans/generate", json={"course_id": "CS101",
                                                           "exam_date": day(6)}, headers=S1)
    assert r.status_code == 201, r.get_json()
    return r.get_json()["plan_id"]


def test_generate_and_list_own(client):
    pid = _plan(client)
    body = client.get("/api/ai-study/plans", headers=S1).get_json()
    assert [p["plan_id"] for p in body["items"]] == [pid]
    assert client.get("/api/ai-study/plans", headers=S2).get_json()["items"] == []


def test_search_no_longer_crashes(client):
    _plan(client)
    r = client.get("/api/ai-study/plans?search=exam", headers=S1)
    assert r.status_code == 200 and len(r.get_json()["items"]) == 1


def test_other_students_rows_are_refused(client):
    pid = _plan(client)
    assert client.get("/api/ai-study/plans?student_id=S1", headers=S2).status_code == 403
    assert client.get(f"/api/ai-study/plans/{pid}", headers=S2).status_code == 403
    assert client.get("/api/ai-study/flashcards/due?student_id=S1", headers=S2).status_code == 403
    assert client.get("/api/ai-study/flashcards/decks?student_id=S1", headers=S2).status_code == 403
    assert client.delete(f"/api/ai-study/plans/{pid}", headers=S2).status_code == 403


def test_staff_read_but_not_write(client):
    pid = _plan(client)
    assert client.get(f"/api/ai-study/plans/{pid}", headers=ADMIN).status_code == 200
    assert client.delete(f"/api/ai-study/plans/{pid}", headers=ADMIN).status_code == 403


def test_complete_task_logs_study_time(client, db):
    get_connection, _ = db
    pid = _plan(client)
    task = client.get(f"/api/ai-study/plans/{pid}", headers=S1).get_json()["tasks"][0]["task_id"]
    assert client.put(f"/api/ai-study/tasks/{task}/complete", headers=S2).status_code == 403
    assert client.put(f"/api/ai-study/tasks/{task}/complete", headers=S1).status_code == 200
    with get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM study_sessions WHERE source = 'plan_task' "
                            "AND source_id = ?", (task,)).fetchone()[0] == 1


def test_flashcard_flow(client):
    r = client.post("/api/ai-study/flashcards", json={"deck_name": "D", "question": "Q?",
                                                      "answer": "A"}, headers=S1)
    fid = r.get_json()["flashcard_id"]
    assert client.post(f"/api/ai-study/flashcards/{fid}/review", json={"quality": "good"},
                       headers=S2).status_code == 403
    r = client.post(f"/api/ai-study/flashcards/{fid}/review", json={"quality": "hard"}, headers=S1)
    assert r.status_code == 200 and r.get_json()["days_until_next"] == 1
    assert client.post(f"/api/ai-study/flashcards/{fid}/review", json={"quality": "meh"},
                       headers=S1).status_code == 400
    gen = client.post("/api/ai-study/flashcards/generate",
                      json={"deck_name": "N", "notes": "Mitosis: cell division"}, headers=S1)
    assert gen.status_code == 201 and gen.get_json()["source"] == "extracted"


def test_explanations_are_private(client):
    r = client.post("/api/ai-study/concept-explanations",
                    json={"concept_name": "Recursion", "course_id": "CS101"}, headers=S1)
    assert r.status_code == 201 and r.get_json()["source"] == "course_materials"
    eid = r.get_json()["explanation_id"]
    assert client.get(f"/api/ai-study/concept-explanations/{eid}", headers=S2).status_code == 403
    assert client.get(f"/api/ai-study/concept-explanations/{eid}", headers=ADMIN).status_code == 403
    assert client.put(f"/api/ai-study/concept-explanations/{eid}/rate", json={"rating": True},
                      headers=S1).status_code == 400
    assert client.put(f"/api/ai-study/concept-explanations/{eid}/rate", json={"rating": 4},
                      headers=S1).status_code == 200


def test_staff_endpoints(client):
    _plan(client)
    assert client.get("/api/ai-study/staff/overview", headers=S1).status_code == 403
    assert client.post("/api/ai-study/reminders/send", headers=S1).status_code == 403
    rows = client.get("/api/ai-study/staff/overview", headers=ADMIN).get_json()["items"]
    assert [r["student_id"] for r in rows] == ["S1"]
    client.put("/api/ai-study/settings", json={"share_with_tutor": False}, headers=S1)
    assert client.get("/api/ai-study/students/S1/analytics", headers=ADMIN).status_code == 403
    assert client.get("/api/ai-study/students/S1/analytics", headers=S1).status_code == 200
