"""REST API for Primary Safeguarding."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

safeguarding_bp = Blueprint("pri_safeguarding", __name__, url_prefix="/api/safeguarding")


def _token_required(view):
    try:
        from education_system.shared.api.auth import token_required
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
    from education_system.primarysch_system.modules.domain.safeguarding import (
        safeguarding as data,
    )
    return data


# ── Concerns ────────────────────────────────────────────────────

@safeguarding_bp.route("", methods=["GET"])
@safeguarding_bp.route("/", methods=["GET"])
@_token_required
def list_concerns():
    data = _data()
    args = request.args
    try:
        rows = data.list_concerns(
            pupil_id=args.get("pupil_id"),
            year_group=args.get("year_group"),
            category=args.get("category"),
            severity=args.get("severity"),
            status=args.get("status"),
            date_from=args.get("date_from"),
            date_to=args.get("date_to"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@safeguarding_bp.route("/<int:concern_id>", methods=["GET"])
@_token_required
def get_concern(concern_id):
    data = _data()
    rec = data.get(concern_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@safeguarding_bp.route("", methods=["POST"])
@safeguarding_bp.route("/", methods=["POST"])
@_token_required
def create_concern():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.raise_concern(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@safeguarding_bp.route("/<int:concern_id>", methods=["PUT"])
@_token_required
def update_concern(concern_id):
    data = _data()
    if data.get(concern_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update(concern_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@safeguarding_bp.route("/<int:concern_id>", methods=["DELETE"])
@_token_required
def delete_concern(concern_id):
    data = _data()
    if not data.delete(concern_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "concern_id": concern_id})


@safeguarding_bp.route("/<int:concern_id>/summary", methods=["GET"])
@_token_required
def concern_summary(concern_id):
    data = _data()
    try:
        summary = data.concern_summary(concern_id)
    except data.ValidationError:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(summary))


# ── Actions ─────────────────────────────────────────────────────

@safeguarding_bp.route("/<int:concern_id>/actions", methods=["GET"])
@_token_required
def list_actions(concern_id):
    data = _data()
    if data.get(concern_id) is None:
        return jsonify({"error": "Not found"}), 404
    rows = data.list_actions(concern_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@safeguarding_bp.route("/actions/<int:action_id>", methods=["GET"])
@_token_required
def get_action(action_id):
    data = _data()
    rec = data.get_action(action_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@safeguarding_bp.route("/actions", methods=["POST"])
@_token_required
def create_action():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.add_action(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@safeguarding_bp.route("/actions/<int:action_id>", methods=["DELETE"])
@_token_required
def delete_action(action_id):
    data = _data()
    if not data.delete_action(action_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "action_id": action_id})


# ── Reports ─────────────────────────────────────────────────────

@safeguarding_bp.route("/cohort-summary", methods=["GET"])
@_token_required
def cohort_summary():
    data = _data()
    args = request.args
    try:
        summary = data.cohort_summary(
            year_group=args.get("year_group"),
            date_from=args.get("date_from"),
            date_to=args.get("date_to"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(summary))
