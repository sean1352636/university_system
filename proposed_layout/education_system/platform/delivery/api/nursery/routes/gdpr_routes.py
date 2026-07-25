"""REST API for Nursery GDPR / Data Protection.

Exposes CRUD over the four GDPR registers (data-subject requests,
processing activities, breaches, consents) plus a compliance overview.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

gdpr_bp = Blueprint("nsy_gdpr", __name__, url_prefix="/api/gdpr")


def _token_required(view):
    try:
        from education_system.platform.delivery.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("NURSERY_API_TOKEN")
            got = request.headers.get("X-Nursery-Token")
            if expected and got and got == expected:
                g.current_user = {"sub": "service", "role": "service"}
                return view(*args, **kwargs)
            return jsonify({"error": "Unauthorized"}), 401
        return wrapper


def _dump(obj):
    """Serialize a domain dataclass (or list of them) to JSON-safe data."""
    if isinstance(obj, list):
        return [_dump(o) for o in obj]
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


def _truthy(v: str | None) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on") if v else False


# ── Requests (primary register) ───────────────────────────────────

@gdpr_bp.route("", methods=["GET"])
@gdpr_bp.route("/", methods=["GET"])
@_token_required
def list_requests():
    from education_system.systems.nursery.domain.governance.gdpr import gdpr as data
    rows = data.list_requests(
        status=request.args.get("status"),
        request_type=request.args.get("request_type"),
        subject_type=request.args.get("subject_type"),
        open_only=_truthy(request.args.get("open_only")),
        overdue_only=_truthy(request.args.get("overdue_only")),
        search=request.args.get("search"),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@gdpr_bp.route("/<int:request_id>", methods=["GET"])
@_token_required
def get_request(request_id: int):
    from education_system.systems.nursery.domain.governance.gdpr import gdpr as data
    obj = data.get_request(request_id)
    if obj is None:
        return jsonify({"error": "Request not found"}), 404
    return jsonify(_dump(obj))


@gdpr_bp.route("", methods=["POST"])
@gdpr_bp.route("/", methods=["POST"])
@_token_required
def create_request():
    from education_system.systems.nursery.domain.governance.gdpr import gdpr as data
    try:
        obj = data.create_request(request.get_json(force=True, silent=True) or {})
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj)), 201


@gdpr_bp.route("/<int:request_id>", methods=["PUT"])
@_token_required
def update_request(request_id: int):
    from education_system.systems.nursery.domain.governance.gdpr import gdpr as data
    if data.get_request(request_id) is None:
        return jsonify({"error": "Request not found"}), 404
    try:
        obj = data.update_request(
            request_id, request.get_json(force=True, silent=True) or {})
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@gdpr_bp.route("/<int:request_id>", methods=["DELETE"])
@_token_required
def delete_request(request_id: int):
    from education_system.systems.nursery.domain.governance.gdpr import gdpr as data
    if not data.delete_request(request_id):
        return jsonify({"error": "Request not found"}), 404
    return jsonify({"deleted": request_id})


# ── Processing activities (RoPA) ──────────────────────────────────

@gdpr_bp.route("/processing", methods=["GET"])
@_token_required
def list_processing():
    from education_system.systems.nursery.domain.governance.gdpr import gdpr as data
    rows = data.list_processing(
        status=request.args.get("status"),
        lawful_basis=request.args.get("lawful_basis"),
        search=request.args.get("search"),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@gdpr_bp.route("/processing/<int:activity_id>", methods=["GET"])
@_token_required
def get_processing(activity_id: int):
    from education_system.systems.nursery.domain.governance.gdpr import gdpr as data
    obj = data.get_processing(activity_id)
    if obj is None:
        return jsonify({"error": "Processing activity not found"}), 404
    return jsonify(_dump(obj))


@gdpr_bp.route("/processing", methods=["POST"])
@_token_required
def create_processing():
    from education_system.systems.nursery.domain.governance.gdpr import gdpr as data
    try:
        obj = data.create_processing(
            request.get_json(force=True, silent=True) or {})
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj)), 201


@gdpr_bp.route("/processing/<int:activity_id>", methods=["PUT"])
@_token_required
def update_processing(activity_id: int):
    from education_system.systems.nursery.domain.governance.gdpr import gdpr as data
    if data.get_processing(activity_id) is None:
        return jsonify({"error": "Processing activity not found"}), 404
    try:
        obj = data.update_processing(
            activity_id, request.get_json(force=True, silent=True) or {})
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@gdpr_bp.route("/processing/<int:activity_id>", methods=["DELETE"])
@_token_required
def delete_processing(activity_id: int):
    from education_system.systems.nursery.domain.governance.gdpr import gdpr as data
    if not data.delete_processing(activity_id):
        return jsonify({"error": "Processing activity not found"}), 404
    return jsonify({"deleted": activity_id})


# ── Breaches ──────────────────────────────────────────────────────

@gdpr_bp.route("/breaches", methods=["GET"])
@_token_required
def list_breaches():
    from education_system.systems.nursery.domain.governance.gdpr import gdpr as data
    rows = data.list_breaches(
        status=request.args.get("status"),
        severity=request.args.get("severity"),
        open_only=_truthy(request.args.get("open_only")),
        ico_only=_truthy(request.args.get("ico_only")),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@gdpr_bp.route("/breaches/<int:breach_id>", methods=["GET"])
@_token_required
def get_breach(breach_id: int):
    from education_system.systems.nursery.domain.governance.gdpr import gdpr as data
    obj = data.get_breach(breach_id)
    if obj is None:
        return jsonify({"error": "Breach not found"}), 404
    return jsonify(_dump(obj))


@gdpr_bp.route("/breaches", methods=["POST"])
@_token_required
def create_breach():
    from education_system.systems.nursery.domain.governance.gdpr import gdpr as data
    try:
        obj = data.create_breach(request.get_json(force=True, silent=True) or {})
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj)), 201


@gdpr_bp.route("/breaches/<int:breach_id>", methods=["PUT"])
@_token_required
def update_breach(breach_id: int):
    from education_system.systems.nursery.domain.governance.gdpr import gdpr as data
    if data.get_breach(breach_id) is None:
        return jsonify({"error": "Breach not found"}), 404
    try:
        obj = data.update_breach(
            breach_id, request.get_json(force=True, silent=True) or {})
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@gdpr_bp.route("/breaches/<int:breach_id>", methods=["DELETE"])
@_token_required
def delete_breach(breach_id: int):
    from education_system.systems.nursery.domain.governance.gdpr import gdpr as data
    if not data.delete_breach(breach_id):
        return jsonify({"error": "Breach not found"}), 404
    return jsonify({"deleted": breach_id})


# ── Consents ──────────────────────────────────────────────────────

@gdpr_bp.route("/consents", methods=["GET"])
@_token_required
def list_consents():
    from education_system.systems.nursery.domain.governance.gdpr import gdpr as data
    rows = data.list_consents(
        subject_ref=request.args.get("subject_ref"),
        purpose=request.args.get("purpose"),
        active_only=_truthy(request.args.get("active_only")),
        search=request.args.get("search"),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@gdpr_bp.route("/consents/<int:consent_id>", methods=["GET"])
@_token_required
def get_consent(consent_id: int):
    from education_system.systems.nursery.domain.governance.gdpr import gdpr as data
    obj = data.get_consent(consent_id)
    if obj is None:
        return jsonify({"error": "Consent not found"}), 404
    return jsonify(_dump(obj))


@gdpr_bp.route("/consents", methods=["POST"])
@_token_required
def create_consent():
    from education_system.systems.nursery.domain.governance.gdpr import gdpr as data
    try:
        obj = data.create_consent(request.get_json(force=True, silent=True) or {})
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj)), 201


@gdpr_bp.route("/consents/<int:consent_id>", methods=["PUT"])
@_token_required
def update_consent(consent_id: int):
    from education_system.systems.nursery.domain.governance.gdpr import gdpr as data
    if data.get_consent(consent_id) is None:
        return jsonify({"error": "Consent not found"}), 404
    try:
        obj = data.update_consent(
            consent_id, request.get_json(force=True, silent=True) or {})
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@gdpr_bp.route("/consents/<int:consent_id>/withdraw", methods=["POST"])
@_token_required
def withdraw_consent(consent_id: int):
    from education_system.systems.nursery.domain.governance.gdpr import gdpr as data
    if data.get_consent(consent_id) is None:
        return jsonify({"error": "Consent not found"}), 404
    body = request.get_json(force=True, silent=True) or {}
    try:
        obj = data.withdraw_consent(
            consent_id,
            withdrawn_date=body.get("withdrawn_date"),
            notes=body.get("notes"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@gdpr_bp.route("/consents/<int:consent_id>", methods=["DELETE"])
@_token_required
def delete_consent(consent_id: int):
    from education_system.systems.nursery.domain.governance.gdpr import gdpr as data
    if not data.delete_consent(consent_id):
        return jsonify({"error": "Consent not found"}), 404
    return jsonify({"deleted": consent_id})


# ── Overview ──────────────────────────────────────────────────────

@gdpr_bp.route("/overview", methods=["GET"])
@_token_required
def overview():
    from education_system.systems.nursery.domain.governance.gdpr import gdpr as data
    return jsonify(_dump(data.overview()))
