"""REST API for Primary GDPR / Data Protection."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

gdpr_bp = Blueprint("pri_gdpr", __name__, url_prefix="/api/gdpr")


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
    from education_system.primarysch_system.modules.domain.gdpr import gdpr as data
    return data


# ── Requests (data-subject rights requests) ───────────────────────

@gdpr_bp.route("/requests", methods=["GET"])
@gdpr_bp.route("/requests/", methods=["GET"])
@_token_required
def list_requests():
    data = _data()
    rows = data.list_requests(
        status=request.args.get("status"),
        request_type=request.args.get("request_type"),
        subject_type=request.args.get("subject_type"),
        open_only=request.args.get("open_only", "").lower()
        in ("1", "true", "yes"),
        overdue_only=request.args.get("overdue_only", "").lower()
        in ("1", "true", "yes"),
        search=request.args.get("search"),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@gdpr_bp.route("/requests/<int:request_id>", methods=["GET"])
@_token_required
def get_request(request_id: int):
    data = _data()
    row = data.get_request(request_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@gdpr_bp.route("/requests", methods=["POST"])
@gdpr_bp.route("/requests/", methods=["POST"])
@_token_required
def create_request():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_request(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@gdpr_bp.route("/requests/<int:request_id>", methods=["PUT"])
@_token_required
def update_request(request_id: int):
    data = _data()
    if data.get_request(request_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_request(request_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@gdpr_bp.route("/requests/<int:request_id>", methods=["DELETE"])
@_token_required
def delete_request(request_id: int):
    data = _data()
    if not data.delete_request(request_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


# ── Processing activities (Article 30 register) ───────────────────

@gdpr_bp.route("/processing", methods=["GET"])
@gdpr_bp.route("/processing/", methods=["GET"])
@_token_required
def list_processing():
    data = _data()
    rows = data.list_processing(
        status=request.args.get("status"),
        lawful_basis=request.args.get("lawful_basis"),
        search=request.args.get("search"),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@gdpr_bp.route("/processing/<int:activity_id>", methods=["GET"])
@_token_required
def get_processing(activity_id: int):
    data = _data()
    row = data.get_processing(activity_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@gdpr_bp.route("/processing", methods=["POST"])
@gdpr_bp.route("/processing/", methods=["POST"])
@_token_required
def create_processing():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_processing(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@gdpr_bp.route("/processing/<int:activity_id>", methods=["PUT"])
@_token_required
def update_processing(activity_id: int):
    data = _data()
    if data.get_processing(activity_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_processing(activity_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@gdpr_bp.route("/processing/<int:activity_id>", methods=["DELETE"])
@_token_required
def delete_processing(activity_id: int):
    data = _data()
    if not data.delete_processing(activity_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


# ── Breaches (personal-data breach log) ───────────────────────────

@gdpr_bp.route("/breaches", methods=["GET"])
@gdpr_bp.route("/breaches/", methods=["GET"])
@_token_required
def list_breaches():
    data = _data()
    rows = data.list_breaches(
        status=request.args.get("status"),
        severity=request.args.get("severity"),
        open_only=request.args.get("open_only", "").lower()
        in ("1", "true", "yes"),
        ico_only=request.args.get("ico_only", "").lower()
        in ("1", "true", "yes"),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@gdpr_bp.route("/breaches/<int:breach_id>", methods=["GET"])
@_token_required
def get_breach(breach_id: int):
    data = _data()
    row = data.get_breach(breach_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@gdpr_bp.route("/breaches", methods=["POST"])
@gdpr_bp.route("/breaches/", methods=["POST"])
@_token_required
def create_breach():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_breach(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@gdpr_bp.route("/breaches/<int:breach_id>", methods=["PUT"])
@_token_required
def update_breach(breach_id: int):
    data = _data()
    if data.get_breach(breach_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_breach(breach_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@gdpr_bp.route("/breaches/<int:breach_id>", methods=["DELETE"])
@_token_required
def delete_breach(breach_id: int):
    data = _data()
    if not data.delete_breach(breach_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


# ── Consents (consent records) ────────────────────────────────────

@gdpr_bp.route("/consents", methods=["GET"])
@gdpr_bp.route("/consents/", methods=["GET"])
@_token_required
def list_consents():
    data = _data()
    rows = data.list_consents(
        subject_ref=request.args.get("subject_ref"),
        purpose=request.args.get("purpose"),
        active_only=request.args.get("active_only", "").lower()
        in ("1", "true", "yes"),
        search=request.args.get("search"),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@gdpr_bp.route("/consents/<int:consent_id>", methods=["GET"])
@_token_required
def get_consent(consent_id: int):
    data = _data()
    row = data.get_consent(consent_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@gdpr_bp.route("/consents", methods=["POST"])
@gdpr_bp.route("/consents/", methods=["POST"])
@_token_required
def create_consent():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_consent(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@gdpr_bp.route("/consents/<int:consent_id>", methods=["PUT"])
@_token_required
def update_consent(consent_id: int):
    data = _data()
    if data.get_consent(consent_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_consent(consent_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@gdpr_bp.route("/consents/<int:consent_id>", methods=["DELETE"])
@_token_required
def delete_consent(consent_id: int):
    data = _data()
    if not data.delete_consent(consent_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


# ── Summary ───────────────────────────────────────────────────────

@gdpr_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    data = _data()
    return jsonify(_dump(data.overview()))
