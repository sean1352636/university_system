"""REST API for Primary Surveys."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

surveys_bp = Blueprint("pri_surveys", __name__, url_prefix="/api/surveys")


def _token_required(view):
    try:
        from education_system.platform.delivery.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("PRIMARY_API_TOKEN")
            got = request.headers.get("X-Primary-Token")
            if expected and got and got == expected:
                g.current_user = {"sub": "service", "role": "service"}
                return view(*args, **kwargs)
            return jsonify({"error": "Unauthorized"}), 401
        return wrapper


def _dump(obj):
    if isinstance(obj, list):
        return [_dump(o) for o in obj]
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


def _data():
    from education_system.systems.primary.domain.pastoral.surveys import (
        surveys as data,
    )
    return data


# ── Surveys ─────────────────────────────────────────────────────────

@surveys_bp.route("", methods=["GET"])
@surveys_bp.route("/", methods=["GET"])
@_token_required
def list_surveys():
    data = _data()
    args = request.args
    open_only = (args.get("open_only") or "").strip().lower() in (
        "1", "true", "yes", "on")
    rows = data.list_surveys(
        audience=args.get("audience") or None,
        status=args.get("status") or None,
        created_by_like=args.get("created_by_like") or None,
        name_like=args.get("name_like") or None,
        open_only=open_only,
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@surveys_bp.route("/summary", methods=["GET"])
@_token_required
def surveys_summary():
    data = _data()
    return jsonify(_dump(data.summary()))


@surveys_bp.route("/<int:survey_id>", methods=["GET"])
@_token_required
def get_survey(survey_id: int):
    data = _data()
    obj = data.get_survey(survey_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@surveys_bp.route("", methods=["POST"])
@surveys_bp.route("/", methods=["POST"])
@_token_required
def create_survey():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.create_survey(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj)), 201


@surveys_bp.route("/<int:survey_id>", methods=["PUT"])
@_token_required
def update_survey(survey_id: int):
    data = _data()
    if data.get_survey(survey_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.update_survey(survey_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@surveys_bp.route("/<int:survey_id>", methods=["DELETE"])
@_token_required
def delete_survey(survey_id: int):
    data = _data()
    if not data.delete_survey(survey_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "survey_id": survey_id})


# ── Workflow ─────────────────────────────────────────────────────────

@surveys_bp.route("/<int:survey_id>/publish", methods=["POST"])
@_token_required
def publish_survey(survey_id: int):
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.publish(survey_id, open_on=payload.get("open_on"))
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@surveys_bp.route("/<int:survey_id>/close", methods=["POST"])
@_token_required
def close_survey(survey_id: int):
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.close_survey(survey_id, close_on=payload.get("close_on"))
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@surveys_bp.route("/<int:survey_id>/archive", methods=["POST"])
@_token_required
def archive_survey(survey_id: int):
    data = _data()
    try:
        obj = data.archive(survey_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@surveys_bp.route("/<int:survey_id>/status", methods=["POST"])
@_token_required
def set_survey_status(survey_id: int):
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.set_status(survey_id, payload.get("status"))
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


# ── Analysis ─────────────────────────────────────────────────────────

@surveys_bp.route("/<int:survey_id>/stats", methods=["GET"])
@_token_required
def survey_stats(survey_id: int):
    data = _data()
    try:
        rows = data.question_stats(survey_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify({"items": _dump(rows), "count": len(rows)})


# ── Responses ───────────────────────────────────────────────────────

@surveys_bp.route("/<int:survey_id>/responses", methods=["GET"])
@_token_required
def list_responses(survey_id: int):
    data = _data()
    if data.get_survey(survey_id) is None:
        return jsonify({"error": "Not found"}), 404
    rows = data.list_responses(survey_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@surveys_bp.route("/<int:survey_id>/responses", methods=["POST"])
@_token_required
def submit_response(survey_id: int):
    data = _data()
    payload = request.get_json(silent=True) or {}
    raw_answers = payload.get("answers") or {}
    try:
        answers = {int(k): v for k, v in raw_answers.items()}
    except (TypeError, ValueError, AttributeError):
        return jsonify({"error": "answers must be a mapping of "
                                 "question index to value"}), 400
    try:
        obj = data.submit_response(
            survey_id,
            answers=answers,
            respondent_name=payload.get("respondent_name"),
            respondent_role=payload.get("respondent_role"),
            anonymous=payload.get("anonymous"),
            submitted_on=payload.get("submitted_on"),
            notes=payload.get("notes"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj)), 201


@surveys_bp.route("/responses/<int:response_id>", methods=["GET"])
@_token_required
def get_response(response_id: int):
    data = _data()
    obj = data.get_response(response_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@surveys_bp.route("/responses/<int:response_id>", methods=["DELETE"])
@_token_required
def delete_response(response_id: int):
    data = _data()
    if not data.delete_response(response_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "response_id": response_id})
