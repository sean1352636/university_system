from __future__ import annotations

from flask import Flask

from education_system.platform.delivery.api.university.auth import create_access_token

from education_system.api.university.academics import ai_features_routes


def _app(monkeypatch) -> Flask:
    app = Flask(__name__)
    app.config["API_CONFIG"] = {
        "jwt": {"secret_key": "test-secret-key-at-least-thirty-two-bytes", "algorithm": "HS256"}
    }
    app.register_blueprint(ai_features_routes.ai_features_bp)
    app.config.update(TESTING=True)
    return app


def _headers(app: Flask) -> dict[str, str]:
    token = create_access_token(
        {"username": "lecturer", "id": 1, "role": "staff"}, app.config["API_CONFIG"]
    )
    return {"Authorization": f"Bearer {token}"}


def test_chat_requires_message_and_returns_grounded_reply(monkeypatch) -> None:
    app = _app(monkeypatch)
    monkeypatch.setattr(ai_features_routes, "generate_chatbot_reply", lambda message, context: f"Reply: {message}")
    with app.test_client() as client:
        response = client.post("/api/ai/chat", json={"message": "When is term?"}, headers=_headers(app))
    assert response.status_code == 200
    assert response.get_json() == {"reply": "Reply: When is term?", "grounded": True, "human_handoff": False}


def test_grading_is_always_a_reviewable_suggestion(monkeypatch) -> None:
    app = _app(monkeypatch)
    with app.test_client() as client:
        response = client.post(
            "/api/ai/grade",
            json={"submission": "A structured answer.\n\nWith a conclusion.", "max_marks": 40, "rubric": "structured conclusion"},
            headers=_headers(app),
        )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["status"] == "suggested"
    assert payload["requires_human_review"] is True
    assert payload["max_marks"] == 40
