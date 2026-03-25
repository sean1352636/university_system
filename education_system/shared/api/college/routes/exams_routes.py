"""API routes for exams."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.exams.services.exams_service import ExamsService
from education_system.college_system.core.i18n import t

exams_bp = Blueprint("exams", __name__, url_prefix="/api/exams")

_db_path = None


def init_exams_routes(db_path=None):
    global _db_path
    _db_path = db_path


@exams_bp.route("/entries", methods=["GET"])
@token_required
def list_entries():
    svc = ExamsService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_entries(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@exams_bp.route("/entries", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_entry():
    data = get_json_body()
    svc = ExamsService(_db_path)
    result = svc.create_entry(**data)
    return jsonify({"message": t("api.exams.created"), "data": result}), 201
@exams_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required('admin')
def delete_exam(pk):
    svc = ExamsService(_db_path)
    svc.delete_exam(pk)
    return jsonify({"message": t("api.exams.deleted")})
@exams_bp.route("/timetable", methods=["GET"])
@token_required
def list_timetable():
    svc = ExamsService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_timetable(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@exams_bp.route("/timetable", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_timetable_slot():
    data = get_json_body()
    svc = ExamsService(_db_path)
    result = svc.create_timetable_slot(**data)
    return jsonify({"message": t("api.exams.created"), "data": result}), 201
@exams_bp.route("/results", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_results():
    svc = ExamsService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_results(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@exams_bp.route("/results", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def record_result():
    data = get_json_body()
    svc = ExamsService(_db_path)
    result = svc.record_result(**data)
    return jsonify({"message": t("api.exams.created"), "data": result}), 201
