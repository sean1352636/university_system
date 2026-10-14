"""Authenticated API for the university assistant and review-first auto-grading."""

from __future__ import annotations

from dataclasses import asdict

from flask import Blueprint, jsonify, request

from education_system.platform.delivery.api.university.auth import token_required
from education_system.systems.university.domains.academics.domain.services.ai_grading.auto_grader import (
    score_submission,
)
from education_system.systems.university.infrastructure.exceptions import ValidationError
from education_system.systems.university.services.ai_features.nlp_engine import (
    generate_chatbot_reply,
)

ai_features_bp = Blueprint("ai_features", __name__, url_prefix="/api/ai")


@ai_features_bp.post("/chat")
@token_required
def chat():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message") or "").strip()
    if not message:
        raise ValidationError("message is required")
    if len(message) > 4_000:
        raise ValidationError("message must not exceed 4000 characters")
    reply = generate_chatbot_reply(message, str(data.get("context") or ""))
    return jsonify({"reply": reply, "grounded": True, "human_handoff": False})


@ai_features_bp.post("/grade")
@token_required
def grade():
    data = request.get_json(silent=True) or {}
    text = str(data.get("submission") or "").strip()
    if not text:
        raise ValidationError("submission is required")
    try:
        max_marks = float(data.get("max_marks", 100))
    except (TypeError, ValueError) as exc:
        raise ValidationError("max_marks must be numeric") from exc
    if not 0 < max_marks <= 10_000:
        raise ValidationError("max_marks must be between 0 and 10000")
    result = score_submission(
        text,
        max_marks,
        assignment_description=str(data.get("rubric") or ""),
    )
    payload = asdict(result)
    payload.update({"status": "suggested", "requires_human_review": True})
    return jsonify(payload)


__all__ = ["ai_features_bp"]
