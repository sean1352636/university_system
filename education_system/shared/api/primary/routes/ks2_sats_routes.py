"""REST API for Primary KS2 SATs (Year 6)."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

ks2_sats_bp = Blueprint("pri_ks2_sats", __name__, url_prefix="/api/ks2-sats")


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


@ks2_sats_bp.route("", methods=["GET"])
@ks2_sats_bp.route("/", methods=["GET"])
@_token_required
def list_ks2_sats():
    from education_system.primarysch_system.modules.domain.ks2_sats import (
        ks2_sats as data,
    )
    try:
        pairs = data.list_results(
            academic_year=request.args.get("academic_year"),
            subject=request.args.get("subject"),
            outcome=request.args.get("outcome"),
            pupil_id=request.args.get("pupil_id"),
            year_group=request.args.get("year_group"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    items = []
    for rec, pupil in pairs:
        row = _dump(rec)
        row["pupil"] = _dump(pupil)
        items.append(row)
    return jsonify({"items": items, "count": len(items)})


@ks2_sats_bp.route("/summary", methods=["GET"])
@_token_required
def summary_ks2_sats():
    from education_system.primarysch_system.modules.domain.ks2_sats import (
        ks2_sats as data,
    )
    try:
        result = data.summary(
            academic_year=request.args.get("academic_year"),
            subject=request.args.get("subject"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


@ks2_sats_bp.route("/cohort-summary", methods=["GET"])
@_token_required
def cohort_summary_ks2_sats():
    from education_system.primarysch_system.modules.domain.ks2_sats import (
        ks2_sats as data,
    )
    academic_year = request.args.get("academic_year", "")
    try:
        result = data.cohort_combined_summary(academic_year)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


@ks2_sats_bp.route("/years", methods=["GET"])
@_token_required
def years_ks2_sats():
    from education_system.primarysch_system.modules.domain.ks2_sats import (
        ks2_sats as data,
    )
    rows = data.known_years()
    return jsonify({"items": rows, "count": len(rows)})


@ks2_sats_bp.route("/pupil/<pupil_id>", methods=["GET"])
@_token_required
def list_for_pupil_ks2_sats(pupil_id):
    from education_system.primarysch_system.modules.domain.ks2_sats import (
        ks2_sats as data,
    )
    try:
        rows = data.list_for_pupil(pupil_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@ks2_sats_bp.route("/<int:result_id>", methods=["GET"])
@_token_required
def get_ks2_sats(result_id):
    from education_system.primarysch_system.modules.domain.ks2_sats import (
        ks2_sats as data,
    )
    rec = data.get(result_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@ks2_sats_bp.route("", methods=["POST"])
@ks2_sats_bp.route("/", methods=["POST"])
@_token_required
def create_ks2_sats():
    from education_system.primarysch_system.modules.domain.ks2_sats import (
        ks2_sats as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@ks2_sats_bp.route("/<int:result_id>", methods=["PUT"])
@_token_required
def update_ks2_sats(result_id):
    from education_system.primarysch_system.modules.domain.ks2_sats import (
        ks2_sats as data,
    )
    if data.get(result_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update(result_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@ks2_sats_bp.route("/<int:result_id>", methods=["DELETE"])
@_token_required
def delete_ks2_sats(result_id):
    from education_system.primarysch_system.modules.domain.ks2_sats import (
        ks2_sats as data,
    )
    if not data.delete(result_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})
