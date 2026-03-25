"""API routes for pastoral."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.pastoral.services.pastoral_service import PastoralService
from education_system.college_system.core.i18n import t

pastoral_bp = Blueprint("pastoral", __name__, url_prefix="/api/pastoral")

_db_path = None


def init_pastoral_routes(db_path=None):
    global _db_path
    _db_path = db_path


@pastoral_bp.route("/notes", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_notes():
    svc = PastoralService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_notes(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@pastoral_bp.route("/notes/<int:pk>", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_note(pk):
    svc = PastoralService(_db_path)
    item = svc.get_note(pk)
    if not item:
        return jsonify({"error": t("api.pastoral.not_found")}), 404
    return jsonify({"data": item})
@pastoral_bp.route("/notes", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def add_note():
    data = get_json_body()
    svc = PastoralService(_db_path)
    result = svc.add_note(**data)
    return jsonify({"message": t("api.pastoral.created"), "data": result}), 201
@pastoral_bp.route("/notes/<int:pk>", methods=["DELETE"])
@token_required
@role_required('admin')
def delete_note(pk):
    svc = PastoralService(_db_path)
    svc.delete_note(pk)
    return jsonify({"message": t("api.pastoral.deleted")})
@pastoral_bp.route("/wellbeing", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_wellbeing():
    svc = PastoralService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_wellbeing(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@pastoral_bp.route("/wellbeing", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def record_wellbeing():
    data = get_json_body()
    svc = PastoralService(_db_path)
    result = svc.record_wellbeing(**data)
    return jsonify({"message": t("api.pastoral.created"), "data": result}), 201
@pastoral_bp.route("/lac", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_lac_records():
    svc = PastoralService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_lac_records(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@pastoral_bp.route("/lac", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_lac_record():
    data = get_json_body()
    svc = PastoralService(_db_path)
    result = svc.create_lac_record(**data)
    return jsonify({"message": t("api.pastoral.created"), "data": result}), 201
