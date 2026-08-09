"""REST API for Primary Multiplication Tables Check (MTC)."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

mtc_bp = Blueprint("pri_mtc", __name__, url_prefix="/api/mtc")


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


def _dump_result(rec):
    """MTCResult with computed properties included."""
    d = dataclasses.asdict(rec)
    d["met_expected"] = rec.met_expected
    d["full_marks"] = rec.full_marks
    return d


@mtc_bp.route("", methods=["GET"])
@mtc_bp.route("/", methods=["GET"])
@_token_required
def list_results():
    from education_system.systems.primary.domain.assessment.mtc import mtc as data

    met = request.args.get("met_expected")
    met_val = None
    if met is not None:
        met_val = met.lower() in ("1", "true", "yes")
    try:
        pairs = data.list_results(
            academic_year=request.args.get("academic_year"),
            pupil_id=request.args.get("pupil_id"),
            met_expected=met_val,
            year_group=request.args.get("year_group"),
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    rows = [
        {"result": _dump_result(rec), "pupil": _dump(pupil)}
        for rec, pupil in pairs
    ]
    return jsonify({"items": rows, "count": len(rows)})


@mtc_bp.route("/<int:result_id>", methods=["GET"])
@_token_required
def get_result(result_id: int):
    from education_system.systems.primary.domain.assessment.mtc import mtc as data

    rec = data.get(result_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump_result(rec))


@mtc_bp.route("", methods=["POST"])
@mtc_bp.route("/", methods=["POST"])
@_token_required
def create_result():
    from education_system.systems.primary.domain.assessment.mtc import mtc as data

    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump_result(rec)), 201


@mtc_bp.route("/<int:result_id>", methods=["PUT"])
@_token_required
def update_result(result_id: int):
    from education_system.systems.primary.domain.assessment.mtc import mtc as data

    if data.get(result_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update(result_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump_result(rec))


@mtc_bp.route("/<int:result_id>", methods=["DELETE"])
@_token_required
def delete_result(result_id: int):
    from education_system.systems.primary.domain.assessment.mtc import mtc as data

    if not data.delete(result_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "result_id": result_id})


@mtc_bp.route("/pupil/<pupil_id>", methods=["GET"])
@_token_required
def list_for_pupil(pupil_id: str):
    from education_system.systems.primary.domain.assessment.mtc import mtc as data

    try:
        rows = data.list_for_pupil(pupil_id)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    items = [_dump_result(r) for r in rows]
    return jsonify({"items": items, "count": len(items)})


@mtc_bp.route("/summary/<academic_year>", methods=["GET"])
@_token_required
def year_summary(academic_year: str):
    from education_system.systems.primary.domain.assessment.mtc import mtc as data

    try:
        return jsonify(data.year_summary(academic_year))
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400


@mtc_bp.route("/years", methods=["GET"])
@_token_required
def known_years():
    from education_system.systems.primary.domain.assessment.mtc import mtc as data

    years = data.known_years()
    return jsonify({"items": years, "count": len(years)})
