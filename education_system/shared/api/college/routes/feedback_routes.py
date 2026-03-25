"""API routes for feedback."""

from flask import Blueprint, jsonify, request
from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.feedback.services.feedback_service import FeedbackService
from education_system.college_system.core.i18n import t

feedback_bp = Blueprint("feedback", __name__, url_prefix="/api/feedback")

_db_path = None


def init_feedback_routes(db_path=None):
    global _db_path
    _db_path = db_path


@feedback_bp.route("", methods=["GET"])
@token_required
def list_feedbacks():
    svc = FeedbackService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_feedbacks(limit=limit, offset=offset)
    total = svc.count_feedbacks()
    return jsonify(paginated_response(items, total))


@feedback_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_feedback(pk):
    svc = FeedbackService(_db_path)
    item = svc.get_feedback(pk)
    if not item:
        return jsonify({"error": t("api.feedback.not_found")}), 404
    return jsonify({"data": item})


@feedback_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def create_feedback():
    data = get_json_body()
    require_fields(data, "title")
    svc = FeedbackService(_db_path)
    item = svc.create_feedback(**data)
    return jsonify({"message": t("api.feedback.submitted"), "data": item}), 201


@feedback_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff", "instructor")
def update_feedback(pk):
    data = get_json_body()
    svc = FeedbackService(_db_path)
    item = svc.update_feedback(pk, **data)
    return jsonify({"message": t("api.feedback.updated"), "data": item})


@feedback_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_feedback(pk):
    svc = FeedbackService(_db_path)
    svc.delete_feedback(pk)
    return jsonify({"message": t("api.feedback.deleted")})
