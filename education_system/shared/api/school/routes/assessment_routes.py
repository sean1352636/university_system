"""REST API for Secondary School assessment."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

assessment_bp = Blueprint("sec_assessment", __name__, url_prefix="/api/assessment")


def _token_required(view):
    try:
        from education_system.shared.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("SCHOOL_API_TOKEN")
            got = request.headers.get("X-School-Token")
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


def _body() -> dict:
    return request.get_json(silent=True) or {}


# --------------------------------------------------------------------------
# Gradebook  (entry_id: int)
# --------------------------------------------------------------------------

@assessment_bp.route("/gradebook", methods=["GET"])
@_token_required
def list_gradebook():
    from education_system.secondarysch_system.modules.domain.assessment.gradebook import (
        gradebook as data,
    )
    args = request.args
    sid = args.get("subject_id", type=int)
    try:
        rows = data.list_entries(
            pupil_id=args.get("pupil_id"),
            subject_id=sid,
            year_group=args.get("year_group"),
            term=args.get("term"),
            assessment_type=args.get("assessment_type"),
            date_from=args.get("date_from"),
            date_to=args.get("date_to"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@assessment_bp.route("/gradebook/<int:entry_id>", methods=["GET"])
@_token_required
def get_gradebook(entry_id: int):
    from education_system.secondarysch_system.modules.domain.assessment.gradebook import (
        gradebook as data,
    )
    rec = data.get_entry(entry_id)
    if rec is None:
        return jsonify({"error": "Gradebook entry not found"}), 404
    return jsonify(_dump(rec))


@assessment_bp.route("/gradebook", methods=["POST"])
@_token_required
def create_gradebook():
    from education_system.secondarysch_system.modules.domain.assessment.gradebook import (
        gradebook as data,
    )
    try:
        rec = data.upsert_entry(_body())
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@assessment_bp.route("/gradebook/<int:entry_id>", methods=["PUT"])
@_token_required
def update_gradebook(entry_id: int):
    from education_system.secondarysch_system.modules.domain.assessment.gradebook import (
        gradebook as data,
    )
    if data.get_entry(entry_id) is None:
        return jsonify({"error": "Gradebook entry not found"}), 404
    payload = dict(_body())
    payload.pop("entry_id", None)
    try:
        rec = data.upsert_entry(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@assessment_bp.route("/gradebook/<int:entry_id>", methods=["DELETE"])
@_token_required
def delete_gradebook(entry_id: int):
    from education_system.secondarysch_system.modules.domain.assessment.gradebook import (
        gradebook as data,
    )
    if not data.delete_entry(entry_id):
        return jsonify({"error": "Gradebook entry not found"}), 404
    return jsonify({"deleted": True, "entry_id": entry_id})


# --------------------------------------------------------------------------
# Target grades  (target_id: int)
# --------------------------------------------------------------------------

@assessment_bp.route("/targets", methods=["GET"])
@_token_required
def list_targets():
    from education_system.secondarysch_system.modules.domain.assessment.target_grades import (
        target_grades as data,
    )
    args = request.args
    sid = args.get("subject_id", type=int)
    try:
        rows = data.list_targets(
            year_group=args.get("year_group"),
            subject_id=sid,
            pupil_id=args.get("pupil_id"),
            source=args.get("source"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@assessment_bp.route("/targets/<int:target_id>", methods=["GET"])
@_token_required
def get_target(target_id: int):
    from education_system.secondarysch_system.modules.domain.assessment.target_grades import (
        target_grades as data,
    )
    rec = data.get(target_id)
    if rec is None:
        return jsonify({"error": "Target grade not found"}), 404
    return jsonify(_dump(rec))


@assessment_bp.route("/targets", methods=["POST"])
@_token_required
def create_target():
    from education_system.secondarysch_system.modules.domain.assessment.target_grades import (
        target_grades as data,
    )
    try:
        rec = data.upsert(_body())
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@assessment_bp.route("/targets/<int:target_id>", methods=["PUT"])
@_token_required
def update_target(target_id: int):
    from education_system.secondarysch_system.modules.domain.assessment.target_grades import (
        target_grades as data,
    )
    if data.get(target_id) is None:
        return jsonify({"error": "Target grade not found"}), 404
    payload = dict(_body())
    payload.pop("target_id", None)
    try:
        rec = data.upsert(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@assessment_bp.route("/targets/<int:target_id>", methods=["DELETE"])
@_token_required
def delete_target(target_id: int):
    from education_system.secondarysch_system.modules.domain.assessment.target_grades import (
        target_grades as data,
    )
    if not data.delete(target_id):
        return jsonify({"error": "Target grade not found"}), 404
    return jsonify({"deleted": True, "target_id": target_id})


# --------------------------------------------------------------------------
# Exam results  (result_id: int)
# --------------------------------------------------------------------------

@assessment_bp.route("/results", methods=["GET"])
@_token_required
def list_results():
    from education_system.secondarysch_system.modules.domain.assessment.exam_results import (
        exam_results as data,
    )
    args = request.args
    sid = args.get("subject_id", type=int)
    try:
        rows = data.list_results(
            year_group=args.get("year_group"),
            subject_id=sid,
            status=args.get("status"),
            pupil_id=args.get("pupil_id"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@assessment_bp.route("/results/<int:result_id>", methods=["GET"])
@_token_required
def get_result(result_id: int):
    from education_system.secondarysch_system.modules.domain.assessment.exam_results import (
        exam_results as data,
    )
    rec = data.get(result_id)
    if rec is None:
        return jsonify({"error": "Exam result not found"}), 404
    return jsonify(_dump(rec))


@assessment_bp.route("/results", methods=["POST"])
@_token_required
def create_result():
    from education_system.secondarysch_system.modules.domain.assessment.exam_results import (
        exam_results as data,
    )
    try:
        rec = data.upsert(_body())
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@assessment_bp.route("/results/<int:result_id>", methods=["PUT"])
@_token_required
def update_result(result_id: int):
    from education_system.secondarysch_system.modules.domain.assessment.exam_results import (
        exam_results as data,
    )
    existing = data.get(result_id)
    if existing is None:
        return jsonify({"error": "Exam result not found"}), 404
    payload = dict(_body())
    payload.pop("result_id", None)
    payload.setdefault("entry_id", existing.entry_id)
    try:
        rec = data.upsert(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@assessment_bp.route("/results/<int:result_id>", methods=["DELETE"])
@_token_required
def delete_result(result_id: int):
    from education_system.secondarysch_system.modules.domain.assessment.exam_results import (
        exam_results as data,
    )
    if not data.delete(result_id):
        return jsonify({"error": "Exam result not found"}), 404
    return jsonify({"deleted": True, "result_id": result_id})


# --------------------------------------------------------------------------
# Cohort summary (read-only aggregate over exam results)
# --------------------------------------------------------------------------

@assessment_bp.route("/results/summary", methods=["GET"])
@_token_required
def results_summary():
    from education_system.secondarysch_system.modules.domain.assessment.exam_results import (
        exam_results as data,
    )
    args = request.args
    sid = args.get("subject_id", type=int)
    try:
        summary = data.cohort_summary(
            year_group=args.get("year_group"), subject_id=sid)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(summary))
