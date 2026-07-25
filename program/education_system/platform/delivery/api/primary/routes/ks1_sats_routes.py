"""REST API for Primary KS1 SATs (Year 2)."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

ks1_sats_bp = Blueprint("pri_ks1_sats", __name__, url_prefix="/api/ks1-sats")


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


@ks1_sats_bp.route("", methods=["GET"])
@ks1_sats_bp.route("/", methods=["GET"])
@_token_required
def list_results():
    from education_system.systems.primary.domain.assessment.ks1_sats import (
        ks1_sats as data,
    )
    try:
        pairs = data.list_results(
            academic_year=request.args.get("academic_year") or None,
            subject=request.args.get("subject") or None,
            outcome=request.args.get("outcome") or None,
            pupil_id=request.args.get("pupil_id") or None,
            year_group=request.args.get("year_group") or None,
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    items = [
        {"result": _dump(rec), "pupil": _dump(pupil)}
        for rec, pupil in pairs
    ]
    return jsonify({"items": items, "count": len(items)})


@ks1_sats_bp.route("/<int:result_id>", methods=["GET"])
@_token_required
def get_result(result_id: int):
    from education_system.systems.primary.domain.assessment.ks1_sats import (
        ks1_sats as data,
    )
    rec = data.get(result_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@ks1_sats_bp.route("", methods=["POST"])
@ks1_sats_bp.route("/", methods=["POST"])
@_token_required
def create_result():
    from education_system.systems.primary.domain.assessment.ks1_sats import (
        ks1_sats as data,
    )
    body = request.get_json(silent=True) or {}
    try:
        rec = data.create(body)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@ks1_sats_bp.route("/<int:result_id>", methods=["PUT"])
@_token_required
def update_result(result_id: int):
    from education_system.systems.primary.domain.assessment.ks1_sats import (
        ks1_sats as data,
    )
    if data.get(result_id) is None:
        return jsonify({"error": "Not found"}), 404
    body = request.get_json(silent=True) or {}
    try:
        rec = data.update(result_id, body)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@ks1_sats_bp.route("/<int:result_id>", methods=["DELETE"])
@_token_required
def delete_result(result_id: int):
    from education_system.systems.primary.domain.assessment.ks1_sats import (
        ks1_sats as data,
    )
    if not data.delete(result_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": result_id})


@ks1_sats_bp.route("/pupil/<pupil_id>", methods=["GET"])
@_token_required
def list_for_pupil(pupil_id: str):
    from education_system.systems.primary.domain.assessment.ks1_sats import (
        ks1_sats as data,
    )
    try:
        rows = data.list_for_pupil(pupil_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@ks1_sats_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    from education_system.systems.primary.domain.assessment.ks1_sats import (
        ks1_sats as data,
    )
    try:
        result = data.summary(
            academic_year=request.args.get("academic_year") or None,
            subject=request.args.get("subject") or None,
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


@ks1_sats_bp.route("/years", methods=["GET"])
@_token_required
def known_years():
    from education_system.systems.primary.domain.assessment.ks1_sats import (
        ks1_sats as data,
    )
    rows = data.known_years()
    return jsonify({"items": _dump(rows), "count": len(rows)})
