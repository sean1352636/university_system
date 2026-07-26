"""REST API for Nursery Permissions & Consents.

Exposes CRUD over the parental-consent register (per-child permissions for
photographs, outings, sun cream, emergency treatment, etc.).
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

consents_bp = Blueprint("nsy_consents", __name__, url_prefix="/api/consents")


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


@consents_bp.route("", methods=["GET"])
@_token_required
def list_consents():
    from education_system.systems.nursery.domain.governance.consents import consents as data
    pupil_id = request.args.get("pupil_id") or None
    rows = data.list_consents(pupil_id=pupil_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@consents_bp.route("/<consent_id>", methods=["GET"])
@_token_required
def get_consent(consent_id):
    from education_system.systems.nursery.domain.governance.consents import consents as data
    row = data.get_consent(consent_id)
    if row is None:
        return jsonify({"error": "Consent not found"}), 404
    return jsonify(_dump(row))


@consents_bp.route("", methods=["POST"])
@_token_required
def create_consent():
    from education_system.systems.nursery.domain.governance.consents import consents as data
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_consent(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row)), 201


@consents_bp.route("/<consent_id>", methods=["PUT"])
@_token_required
def update_consent(consent_id):
    from education_system.systems.nursery.domain.governance.consents import consents as data
    if data.get_consent(consent_id) is None:
        return jsonify({"error": "Consent not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_consent(consent_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row))


@consents_bp.route("/<consent_id>", methods=["DELETE"])
@_token_required
def delete_consent(consent_id):
    from education_system.systems.nursery.domain.governance.consents import consents as data
    if not data.delete_consent(consent_id):
        return jsonify({"error": "Consent not found"}), 404
    return jsonify({"deleted": consent_id})
