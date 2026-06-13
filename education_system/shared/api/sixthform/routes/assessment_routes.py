"""REST API for Sixth Form Assessment.

Exposes HTTP endpoints over three central assessment submodules:

* ``predicted_grades`` — per-(student, subject) predicted A-Level grades
  (full CRUD; create is an upsert keyed on student+subject).
* ``target_setting``   — per-(student, subject) grade targets plus their
  periodic review snapshots (full CRUD for both targets and reviews).
* ``gradebook``        — derived, read-only grade views over homework
  submissions, plus per-assignment grade-boundary overrides (CRUD).

Auth mirrors the other sixth-form route modules: a JWT bearer token
(validated by the university ``token_required`` if importable) or an
``X-Sixthform-Token`` header matching ``SIXTHFORM_API_TOKEN``.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

assessment_bp = Blueprint(
    "sf_assessment", __name__, url_prefix="/api/sixthform/assessment")


def _token_required(view):
    try:
        from education_system.shared.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("SIXTHFORM_API_TOKEN")
            got = request.headers.get("X-Sixthform-Token")
            if expected and got and got == expected:
                g.current_user = {"sub": "service", "role": "service"}
                return view(*args, **kwargs)
            return jsonify({"error": "Unauthorized"}), 401
        return wrapper


def _dump(obj):
    """Serialize a domain dataclass (or list of them) to JSON-safe dicts."""
    if isinstance(obj, list):
        return [_dump(o) for o in obj]
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


# ── predicted_grades ───────────────────────────────────────────────

@assessment_bp.route("/predicted-grades", methods=["GET"])
@_token_required
def list_predictions_route():
    from education_system.sixthform_system.modules.domain.assessment.predicted_grades import (
        predicted_grades as data,
    )
    try:
        rows = data.list_predictions(
            student_id=request.args.get("student_id"),
            subject=request.args.get("subject"),
            grade=request.args.get("grade"),
            confidence=request.args.get("confidence"),
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"predictions": _dump(rows), "count": len(rows)})


@assessment_bp.route("/predicted-grades/<int:prediction_id>", methods=["GET"])
@_token_required
def get_prediction_route(prediction_id: int):
    from education_system.sixthform_system.modules.domain.assessment.predicted_grades import (
        predicted_grades as data,
    )
    p = data.get_prediction(prediction_id)
    if p is None:
        return jsonify({"error": f"No prediction {prediction_id}"}), 404
    return jsonify(_dump(p))


@assessment_bp.route("/predicted-grades", methods=["POST"])
@_token_required
def create_prediction_route():
    from education_system.sixthform_system.modules.domain.assessment.predicted_grades import (
        predicted_grades as data,
    )
    try:
        p = data.save_prediction(request.get_json(force=True, silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(p)), 201


@assessment_bp.route("/predicted-grades/<int:prediction_id>", methods=["PUT"])
@_token_required
def update_prediction_route(prediction_id: int):
    from education_system.sixthform_system.modules.domain.assessment.predicted_grades import (
        predicted_grades as data,
    )
    if data.get_prediction(prediction_id) is None:
        return jsonify({"error": f"No prediction {prediction_id}"}), 404
    try:
        p = data.update_prediction(
            prediction_id, request.get_json(force=True, silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(p))


@assessment_bp.route("/predicted-grades/<int:prediction_id>", methods=["DELETE"])
@_token_required
def delete_prediction_route(prediction_id: int):
    from education_system.sixthform_system.modules.domain.assessment.predicted_grades import (
        predicted_grades as data,
    )
    if not data.delete_prediction(prediction_id):
        return jsonify({"error": f"No prediction {prediction_id}"}), 404
    return jsonify({"deleted": prediction_id})


# ── target_setting: targets ────────────────────────────────────────

@assessment_bp.route("/targets", methods=["GET"])
@_token_required
def list_targets_route():
    from education_system.sixthform_system.modules.domain.assessment.target_setting import (
        target_setting as data,
    )

    def _flag(name: str) -> bool:
        return request.args.get(name, "").lower() in ("1", "true", "yes")

    try:
        rows = data.list_targets(
            student_id=request.args.get("student_id"),
            subject_name=request.args.get("subject_name"),
            status=request.args.get("status"),
            year_group=request.args.get("year_group"),
            mte_grade=request.args.get("mte_grade"),
            on_track_only=_flag("on_track_only"),
            at_risk_only=_flag("at_risk_only"),
            review_overdue=_flag("review_overdue"),
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"targets": _dump(rows), "count": len(rows)})


@assessment_bp.route("/targets/<int:target_id>", methods=["GET"])
@_token_required
def get_target_route(target_id: int):
    from education_system.sixthform_system.modules.domain.assessment.target_setting import (
        target_setting as data,
    )
    t = data.get_target(target_id)
    if t is None:
        return jsonify({"error": f"No target {target_id}"}), 404
    return jsonify(_dump(t))


@assessment_bp.route("/targets", methods=["POST"])
@_token_required
def create_target_route():
    from education_system.sixthform_system.modules.domain.assessment.target_setting import (
        target_setting as data,
    )
    try:
        t = data.create_target(request.get_json(force=True, silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(t)), 201


@assessment_bp.route("/targets/<int:target_id>", methods=["PUT"])
@_token_required
def update_target_route(target_id: int):
    from education_system.sixthform_system.modules.domain.assessment.target_setting import (
        target_setting as data,
    )
    if data.get_target(target_id) is None:
        return jsonify({"error": f"No target {target_id}"}), 404
    try:
        t = data.update_target(
            target_id, request.get_json(force=True, silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(t))


@assessment_bp.route("/targets/<int:target_id>", methods=["DELETE"])
@_token_required
def delete_target_route(target_id: int):
    from education_system.sixthform_system.modules.domain.assessment.target_setting import (
        target_setting as data,
    )
    if not data.delete_target(target_id):
        return jsonify({"error": f"No target {target_id}"}), 404
    return jsonify({"deleted": target_id})


# ── target_setting: reviews ────────────────────────────────────────

@assessment_bp.route("/targets/<int:target_id>/reviews", methods=["GET"])
@_token_required
def list_reviews_route(target_id: int):
    from education_system.sixthform_system.modules.domain.assessment.target_setting import (
        target_setting as data,
    )
    if data.get_target(target_id) is None:
        return jsonify({"error": f"No target {target_id}"}), 404
    rows = data.list_reviews(target_id=target_id)
    return jsonify({"reviews": _dump(rows), "count": len(rows)})


@assessment_bp.route("/targets/<int:target_id>/reviews", methods=["POST"])
@_token_required
def create_review_route(target_id: int):
    from education_system.sixthform_system.modules.domain.assessment.target_setting import (
        target_setting as data,
    )
    if data.get_target(target_id) is None:
        return jsonify({"error": f"No target {target_id}"}), 404
    payload = dict(request.get_json(force=True, silent=True) or {})
    payload["target_id"] = target_id
    try:
        r = data.create_review(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(r)), 201


@assessment_bp.route("/reviews/<int:review_id>", methods=["GET"])
@_token_required
def get_review_route(review_id: int):
    from education_system.sixthform_system.modules.domain.assessment.target_setting import (
        target_setting as data,
    )
    r = data.get_review(review_id)
    if r is None:
        return jsonify({"error": f"No review {review_id}"}), 404
    return jsonify(_dump(r))


@assessment_bp.route("/reviews/<int:review_id>", methods=["PUT"])
@_token_required
def update_review_route(review_id: int):
    from education_system.sixthform_system.modules.domain.assessment.target_setting import (
        target_setting as data,
    )
    if data.get_review(review_id) is None:
        return jsonify({"error": f"No review {review_id}"}), 404
    try:
        r = data.update_review(
            review_id, request.get_json(force=True, silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(r))


@assessment_bp.route("/reviews/<int:review_id>", methods=["DELETE"])
@_token_required
def delete_review_route(review_id: int):
    from education_system.sixthform_system.modules.domain.assessment.target_setting import (
        target_setting as data,
    )
    if not data.delete_review(review_id):
        return jsonify({"error": f"No review {review_id}"}), 404
    return jsonify({"deleted": review_id})


# ── gradebook: derived read views + boundary overrides ─────────────

@assessment_bp.route("/gradebook/students/<student_id>", methods=["GET"])
@_token_required
def gradebook_student_route(student_id: str):
    from education_system.sixthform_system.modules.domain.assessment.gradebook import (
        gradebook as data,
    )
    rows = data.graded_submissions_for_student(student_id)
    return jsonify({"submissions": _dump(rows), "count": len(rows)})


@assessment_bp.route("/gradebook/students/<student_id>/summary", methods=["GET"])
@_token_required
def gradebook_student_summary_route(student_id: str):
    from education_system.sixthform_system.modules.domain.assessment.gradebook import (
        gradebook as data,
    )
    group_id = request.args.get("group_id", type=int)
    summary = data.student_summary(student_id, group_id=group_id)
    return jsonify(_dump(summary))


@assessment_bp.route("/gradebook/groups/<int:group_id>", methods=["GET"])
@_token_required
def gradebook_group_route(group_id: int):
    from education_system.sixthform_system.modules.domain.assessment.gradebook import (
        gradebook as data,
    )
    try:
        rows = data.graded_submissions_for_group(
            group_id,
            type=request.args.get("type"),
            due_from=request.args.get("due_from"),
            due_to=request.args.get("due_to"),
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"submissions": _dump(rows), "count": len(rows)})


@assessment_bp.route("/gradebook/boundaries/<int:assignment_id>", methods=["GET"])
@_token_required
def get_boundaries_route(assignment_id: int):
    from education_system.sixthform_system.modules.domain.assessment.gradebook import (
        gradebook as data,
    )
    b = data.get_boundaries(assignment_id)
    if b is None:
        return jsonify({"error": f"No boundaries for assignment {assignment_id}"}), 404
    return jsonify(_dump(b))


@assessment_bp.route("/gradebook/boundaries/<int:assignment_id>", methods=["PUT"])
@_token_required
def set_boundaries_route(assignment_id: int):
    from education_system.sixthform_system.modules.domain.assessment.gradebook import (
        gradebook as data,
    )
    try:
        b = data.set_boundaries(
            assignment_id, request.get_json(force=True, silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(b))


@assessment_bp.route("/gradebook/boundaries/<int:assignment_id>", methods=["DELETE"])
@_token_required
def clear_boundaries_route(assignment_id: int):
    from education_system.sixthform_system.modules.domain.assessment.gradebook import (
        gradebook as data,
    )
    if not data.clear_boundaries(assignment_id):
        return jsonify({"error": f"No boundaries for assignment {assignment_id}"}), 404
    return jsonify({"cleared": assignment_id})
