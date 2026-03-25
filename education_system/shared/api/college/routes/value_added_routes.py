"""API routes for value added."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.value_added.services.value_added_service import ValueAddedService
from education_system.college_system.core.i18n import t

value_added_bp = Blueprint("value-added", __name__, url_prefix="/api/value-added")

_db_path = None


def init_value_added_routes(db_path=None):
    global _db_path
    _db_path = db_path


@value_added_bp.route("/predictions", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_predictions():
    svc = ValueAddedService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_predictions(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@value_added_bp.route("/baseline", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def set_baseline():
    data = get_json_body()
    svc = ValueAddedService(_db_path)
    result = svc.set_baseline(**data)
    return jsonify({"message": t("api.value_added.created"), "data": result}), 201
@value_added_bp.route("/baseline/<student_id>", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_baseline(student_id):
    svc = ValueAddedService(_db_path)
    item = svc.get_baseline(student_id)
    if not item:
        return jsonify({"error": t("api.value_added.not_found")}), 404
    return jsonify({"data": item})
@value_added_bp.route("/prediction", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def set_prediction():
    data = get_json_body()
    svc = ValueAddedService(_db_path)
    result = svc.set_prediction(**data)
    return jsonify({"message": t("api.value_added.created"), "data": result}), 201
@value_added_bp.route("/subject/<subject_code>", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_subject_value_added(subject_code):
    svc = ValueAddedService(_db_path)
    item = svc.get_subject_value_added(subject_code)
    if not item:
        return jsonify({"error": t("api.value_added.not_found")}), 404
    return jsonify({"data": item})
@value_added_bp.route("/college", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_college_value_added():
    svc = ValueAddedService(_db_path)
    result = svc.get_college_value_added()
    return jsonify({"data": result})
