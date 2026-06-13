"""REST API for Nursery Photos & Evidence.

Exposes CRUD over the EYFS evidence library (photos, videos, work samples, notes).
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

evidence_bp = Blueprint("nsy_evidence", __name__, url_prefix="/api/evidence")


def _token_required(view):
    try:
        from education_system.shared.api.auth import token_required
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


@evidence_bp.route("", methods=["GET"])
@evidence_bp.route("/", methods=["GET"])
@_token_required
def list_evidence():
    from education_system.nursery_system.modules.domain.evidence import evidence as data
    pupil_id = request.args.get("pupil_id") or None
    rows = data.list_evidence(pupil_id=pupil_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@evidence_bp.route("/<evidence_id>", methods=["GET"])
@_token_required
def get_evidence(evidence_id):
    from education_system.nursery_system.modules.domain.evidence import evidence as data
    ev = data.get_evidence(evidence_id)
    if ev is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(ev))


@evidence_bp.route("", methods=["POST"])
@evidence_bp.route("/", methods=["POST"])
@_token_required
def create_evidence():
    from education_system.nursery_system.modules.domain.evidence import evidence as data
    try:
        ev = data.create_evidence(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(ev)), 201


@evidence_bp.route("/<evidence_id>", methods=["PUT"])
@_token_required
def update_evidence(evidence_id):
    from education_system.nursery_system.modules.domain.evidence import evidence as data
    if data.get_evidence(evidence_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        ev = data.update_evidence(evidence_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(ev))


@evidence_bp.route("/<evidence_id>", methods=["DELETE"])
@_token_required
def delete_evidence(evidence_id):
    from education_system.nursery_system.modules.domain.evidence import evidence as data
    if not data.delete_evidence(evidence_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "evidence_id": evidence_id})
