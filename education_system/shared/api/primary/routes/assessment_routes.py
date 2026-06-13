"""REST API for Primary Assessment Records."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

assessment_bp = Blueprint("pri_assessment", __name__, url_prefix="/api/assessment")


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


def _dump_pair(pair):
    rec, pupil = pair
    return {"record": _dump(rec), "pupil": _dump(pupil)}


@assessment_bp.route("", methods=["GET"])
@assessment_bp.route("/", methods=["GET"])
@_token_required
def list_assessments():
    from education_system.primarysch_system.modules.domain.assessment import (
        assessment as data,
    )
    args = request.args
    try:
        rows = data.list_records(
            academic_year=args.get("academic_year"),
            term=args.get("term"),
            subject=args.get("subject"),
            grade=args.get("grade"),
            pupil_id=args.get("pupil_id"),
            year_group=args.get("year_group"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    items = [_dump_pair(p) for p in rows]
    return jsonify({"items": items, "count": len(items)})


@assessment_bp.route("/<int:assessment_id>", methods=["GET"])
@_token_required
def get_assessment(assessment_id: int):
    from education_system.primarysch_system.modules.domain.assessment import (
        assessment as data,
    )
    rec = data.get(assessment_id)
    if rec is None:
        return jsonify({"error": "Assessment record not found"}), 404
    return jsonify(_dump(rec))


@assessment_bp.route("", methods=["POST"])
@assessment_bp.route("/", methods=["POST"])
@_token_required
def create_assessment():
    from education_system.primarysch_system.modules.domain.assessment import (
        assessment as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@assessment_bp.route("/<int:assessment_id>", methods=["PUT"])
@_token_required
def update_assessment(assessment_id: int):
    from education_system.primarysch_system.modules.domain.assessment import (
        assessment as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update(assessment_id, payload)
    except data.ValidationError as exc:
        msg = str(exc)
        if msg == f"No assessment record #{assessment_id}":
            return jsonify({"error": msg}), 404
        return jsonify({"error": msg}), 400
    return jsonify(_dump(rec))


@assessment_bp.route("/<int:assessment_id>", methods=["DELETE"])
@_token_required
def delete_assessment(assessment_id: int):
    from education_system.primarysch_system.modules.domain.assessment import (
        assessment as data,
    )
    if not data.delete(assessment_id):
        return jsonify({"error": "Assessment record not found"}), 404
    return jsonify({"deleted": True, "assessment_id": assessment_id})


@assessment_bp.route("/pupil/<pupil_id>", methods=["GET"])
@_token_required
def list_pupil_assessments(pupil_id: str):
    from education_system.primarysch_system.modules.domain.assessment import (
        assessment as data,
    )
    try:
        rows = data.list_for_pupil(pupil_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@assessment_bp.route("/years", methods=["GET"])
@_token_required
def list_years():
    from education_system.primarysch_system.modules.domain.assessment import (
        assessment as data,
    )
    rows = data.known_years()
    return jsonify({"items": rows, "count": len(rows)})


@assessment_bp.route("/subjects", methods=["GET"])
@_token_required
def list_subjects():
    from education_system.primarysch_system.modules.domain.assessment import (
        assessment as data,
    )
    rows = data.known_subjects()
    return jsonify({"items": rows, "count": len(rows)})


@assessment_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    from education_system.primarysch_system.modules.domain.assessment import (
        assessment as data,
    )
    args = request.args
    try:
        result = data.grade_summary(
            academic_year=args.get("academic_year"),
            term=args.get("term"),
            subject=args.get("subject"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)
