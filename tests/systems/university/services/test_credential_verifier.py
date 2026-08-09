from __future__ import annotations

from education_system.systems.university.services import credential_verifier


def test_public_verifier_has_health_and_redacts_internal_record(monkeypatch):
    monkeypatch.setattr(
        credential_verifier,
        "verify_credential",
        lambda **_: {
            "valid": True,
            "reason": "valid",
            "credential": {
                "credential_type": "degree",
                "credential_name": "BSc",
                "issue_date": "2026-07-01",
                "blockchain_hash": "abc",
                "student_id": "private",
                "metadata": "private",
            },
        },
    )
    app = credential_verifier.create_app()
    with app.test_client() as client:
        assert client.get("/health/live").status_code == 200
        response = client.get("/v1/credentials/abc")
    assert response.status_code == 200
    assert "student_id" not in response.get_json()["credential"]
    assert "metadata" not in response.get_json()["credential"]
