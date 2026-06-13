"""REST API for Primary Pupil Premium."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

pupil_premium_bp = Blueprint(
    "pri_pupil_premium", __name__, url_prefix="/api/pupil-premium")


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
    from education_system.primarysch_system.modules.domain.pupil_premium import (
        pupil_premium as data,
    )
    return data


# ── Pupil-premium records ───────────────────────────────────────

@pupil_premium_bp.route("", methods=["GET"])
@pupil_premium_bp.route("/", methods=["GET"])
@_token_required
def list_records():
    data = _data()
    try:
        rows = data.list_records(
            year_group=request.args.get("year_group"),
            academic_year=request.args.get("academic_year"),
            category=request.args.get("category"),
            status=request.args.get("status"),
            pupil_id=request.args.get("pupil_id"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@pupil_premium_bp.route("/<int:pp_id>", methods=["GET"])
@_token_required
def get_record(pp_id: int):
    data = _data()
    rec = data.get(pp_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@pupil_premium_bp.route("", methods=["POST"])
@pupil_premium_bp.route("/", methods=["POST"])
@_token_required
def create_record():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.upsert(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@pupil_premium_bp.route("/<int:pp_id>", methods=["PUT"])
@_token_required
def update_record(pp_id: int):
    data = _data()
    existing = data.get(pp_id)
    if existing is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    payload.setdefault("pupil_id", existing.pupil_id)
    payload.setdefault("academic_year", existing.academic_year)
    try:
        rec = data.upsert(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@pupil_premium_bp.route("/<int:pp_id>", methods=["DELETE"])
@_token_required
def delete_record(pp_id: int):
    data = _data()
    if not data.delete(pp_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": pp_id})


@pupil_premium_bp.route("/<int:pp_id>/summary", methods=["GET"])
@_token_required
def record_summary(pp_id: int):
    data = _data()
    try:
        summary = data.record_summary(pp_id)
    except data.ValidationError:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(summary))


@pupil_premium_bp.route("/summary", methods=["GET"])
@_token_required
def cohort_summary():
    data = _data()
    summary = data.cohort_summary(
        year_group=request.args.get("year_group"),
        academic_year=request.args.get("academic_year"),
    )
    return jsonify(_dump(summary))


# ── Interventions ───────────────────────────────────────────────

@pupil_premium_bp.route("/<int:pp_id>/interventions", methods=["GET"])
@_token_required
def list_interventions(pp_id: int):
    data = _data()
    rows = data.list_interventions(pp_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@pupil_premium_bp.route("/interventions/<int:intervention_id>", methods=["GET"])
@_token_required
def get_intervention(intervention_id: int):
    data = _data()
    rec = data.get_intervention(intervention_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@pupil_premium_bp.route("/interventions", methods=["POST"])
@_token_required
def create_intervention():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.add_intervention(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@pupil_premium_bp.route("/interventions/<int:intervention_id>", methods=["PUT"])
@_token_required
def update_intervention(intervention_id: int):
    data = _data()
    if data.get_intervention(intervention_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update_intervention(intervention_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@pupil_premium_bp.route("/interventions/<int:intervention_id>", methods=["DELETE"])
@_token_required
def delete_intervention(intervention_id: int):
    data = _data()
    if not data.delete_intervention(intervention_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": intervention_id})
