"""API routes for ucas."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.ucas.services.ucas_service import UCASService
from education_system.college_system.core.i18n import t

ucas_bp = Blueprint("ucas", __name__, url_prefix="/api/ucas")

_db_path = None


def init_ucas_routes(db_path=None):
    global _db_path
    _db_path = db_path


@ucas_bp.route("/applications", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_applications():
    svc = UCASService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_applications(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@ucas_bp.route("/applications/<int:pk>", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_application(pk):
    svc = UCASService(_db_path)
    item = svc.get_application(pk)
    if not item:
        return jsonify({"error": t("api.ucas.not_found")}), 404
    return jsonify({"data": item})
@ucas_bp.route("/applications", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_application():
    data = get_json_body()
    svc = UCASService(_db_path)
    result = svc.create_application(**data)
    return jsonify({"message": t("api.ucas.created"), "data": result}), 201
@ucas_bp.route("/applications/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_application(pk):
    data = get_json_body()
    svc = UCASService(_db_path)
    result = svc.update_application(pk, **data)
    return jsonify({"message": t("api.ucas.updated"), "data": result})
@ucas_bp.route("/applications/<int:pk>/submit", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def submit_application(pk):
    data = get_json_body()
    svc = UCASService(_db_path)
    result = svc.submit_application(pk, **data)
    return jsonify({"message": t("api.ucas.success"), "data": result}), 201
@ucas_bp.route("/applications/<int:pk>/choices", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_choices(pk):
    svc = UCASService(_db_path)
    result = svc.list_choices(pk)
    return jsonify({"data": result})
@ucas_bp.route("/applications/<int:pk>/choices", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def add_choice(pk):
    data = get_json_body()
    svc = UCASService(_db_path)
    result = svc.add_choice(pk, **data)
    return jsonify({"message": t("api.ucas.success"), "data": result}), 201
@ucas_bp.route("/stats", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_statistics():
    svc = UCASService(_db_path)
    result = svc.get_statistics()
    return jsonify({"data": result})
