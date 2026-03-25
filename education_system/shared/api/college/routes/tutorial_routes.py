"""API routes for tutorial."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.tutorial.services.tutorial_service import TutorialService
from education_system.college_system.core.i18n import t

tutorial_bp = Blueprint("tutorial", __name__, url_prefix="/api/tutorial")

_db_path = None


def init_tutorial_routes(db_path=None):
    global _db_path
    _db_path = db_path


@tutorial_bp.route("/assignments", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_assignments():
    svc = TutorialService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_assignments(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@tutorial_bp.route("/assignments/<int:pk>", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_assignment(pk):
    svc = TutorialService(_db_path)
    item = svc.get_assignment(pk)
    if not item:
        return jsonify({"error": t("api.tutorial.not_found")}), 404
    return jsonify({"data": item})
@tutorial_bp.route("/assignments", methods=["POST"])
@token_required
@role_required('admin')
def create_assignment():
    data = get_json_body()
    svc = TutorialService(_db_path)
    result = svc.create_assignment(**data)
    return jsonify({"message": t("api.tutorial.created"), "data": result}), 201
@tutorial_bp.route("/assignments/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin')
def update_assignment(pk):
    data = get_json_body()
    svc = TutorialService(_db_path)
    result = svc.update_assignment(pk, **data)
    return jsonify({"message": t("api.tutorial.updated"), "data": result})
@tutorial_bp.route("/sessions", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_sessions():
    svc = TutorialService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_sessions(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@tutorial_bp.route("/sessions", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_session():
    data = get_json_body()
    svc = TutorialService(_db_path)
    result = svc.create_session(**data)
    return jsonify({"message": t("api.tutorial.created"), "data": result}), 201
@tutorial_bp.route("/records", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_records():
    svc = TutorialService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_records(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@tutorial_bp.route("/records", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_record():
    data = get_json_body()
    svc = TutorialService(_db_path)
    result = svc.create_record(**data)
    return jsonify({"message": t("api.tutorial.created"), "data": result}), 201
@tutorial_bp.route("/stats", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_stats():
    svc = TutorialService(_db_path)
    result = svc.get_stats()
    return jsonify({"data": result})
