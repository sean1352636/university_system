"""REST API for Primary Admissions."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

admissions_bp = Blueprint("pri_admissions", __name__, url_prefix="/api/admissions")


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


@admissions_bp.route("", methods=["GET"])
@admissions_bp.route("/", methods=["GET"])
@_token_required
def list_admissions():
    from education_system.systems.primary.domain.admissions import admissions as data
    status = request.args.get("status")
    try:
        rows = data.list_applications(status=status)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)}), 200


@admissions_bp.route("/summary", methods=["GET"])
@_token_required
def summary_admissions():
    from education_system.systems.primary.domain.admissions import admissions as data
    return jsonify(data.status_counts()), 200


@admissions_bp.route("/<application_id>", methods=["GET"])
@_token_required
def get_admission(application_id):
    from education_system.systems.primary.domain.admissions import admissions as data
    app = data.get_application(application_id)
    if app is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(app)), 200


@admissions_bp.route("", methods=["POST"])
@admissions_bp.route("/", methods=["POST"])
@_token_required
def create_admission():
    from education_system.systems.primary.domain.admissions import admissions as data
    payload = request.get_json(silent=True) or {}
    try:
        app = data.create_application(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(app)), 201


@admissions_bp.route("/<application_id>", methods=["PUT"])
@_token_required
def update_admission(application_id):
    from education_system.systems.primary.domain.admissions import admissions as data
    if data.get_application(application_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        app = data.update_application(application_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(app)), 200


@admissions_bp.route("/<application_id>/status", methods=["PUT"])
@_token_required
def set_admission_status(application_id):
    from education_system.systems.primary.domain.admissions import admissions as data
    if data.get_application(application_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        app = data.set_status(application_id, payload.get("status"))
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(app)), 200


@admissions_bp.route("/<application_id>/enrol", methods=["POST"])
@_token_required
def enrol_admission(application_id):
    from education_system.systems.primary.domain.admissions import admissions as data
    if data.get_application(application_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        app, pupil = data.enrol_application(application_id)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"application": _dump(app), "pupil": _dump(pupil)}), 200


@admissions_bp.route("/<application_id>", methods=["DELETE"])
@_token_required
def delete_admission(application_id):
    from education_system.systems.primary.domain.admissions import admissions as data
    if not data.delete_application(application_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "application_id": application_id}), 200
