"""API routes for student wellbeing."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.student_wellbeing.services.student_wellbeing_service import StudentWellbeingService
from education_system.college_system.core.i18n import t

student_wellbeing_bp = Blueprint("student-wellbeing", __name__, url_prefix="/api/student-wellbeing")

_db_path = None


def init_student_wellbeing_routes(db_path=None):
    global _db_path
    _db_path = db_path


@student_wellbeing_bp.route("/referrals", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_referrals():
    svc = StudentWellbeingService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_referrals(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@student_wellbeing_bp.route("/referrals/<int:pk>", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_referral(pk):
    svc = StudentWellbeingService(_db_path)
    item = svc.get_referral(pk)
    if not item:
        return jsonify({"error": t("api.student_wellbeing.not_found")}), 404
    return jsonify({"data": item})
@student_wellbeing_bp.route("/referrals", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_referral():
    data = get_json_body()
    svc = StudentWellbeingService(_db_path)
    result = svc.create_referral(**data)
    return jsonify({"message": t("api.student_wellbeing.created"), "data": result}), 201
@student_wellbeing_bp.route("/referrals/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_referral(pk):
    data = get_json_body()
    svc = StudentWellbeingService(_db_path)
    result = svc.update_referral(pk, **data)
    return jsonify({"message": t("api.student_wellbeing.updated"), "data": result})
@student_wellbeing_bp.route("/sessions", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_sessions():
    svc = StudentWellbeingService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_sessions(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@student_wellbeing_bp.route("/sessions", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_session():
    data = get_json_body()
    svc = StudentWellbeingService(_db_path)
    result = svc.create_session(**data)
    return jsonify({"message": t("api.student_wellbeing.created"), "data": result}), 201
@student_wellbeing_bp.route("/high-risk", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_high_risk_students():
    svc = StudentWellbeingService(_db_path)
    result = svc.get_high_risk_students()
    return jsonify({"data": result})
@student_wellbeing_bp.route("/stats", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_stats():
    svc = StudentWellbeingService(_db_path)
    result = svc.get_stats()
    return jsonify({"data": result})
