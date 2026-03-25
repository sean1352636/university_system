"""API routes for letter templates."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.letter_templates.services.letter_templates_service import LetterTemplateService
from education_system.college_system.core.i18n import t

letter_templates_bp = Blueprint("letter-templates", __name__, url_prefix="/api/letter-templates")

_db_path = None


def init_letter_templates_routes(db_path=None):
    global _db_path
    _db_path = db_path


@letter_templates_bp.route("", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_templates():
    svc = LetterTemplateService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_templates(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@letter_templates_bp.route("/<int:pk>", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_template(pk):
    svc = LetterTemplateService(_db_path)
    item = svc.get_template(pk)
    if not item:
        return jsonify({"error": t("api.letter_templates.not_found")}), 404
    return jsonify({"data": item})
@letter_templates_bp.route("", methods=["POST"])
@token_required
@role_required('admin')
def create_template():
    data = get_json_body()
    svc = LetterTemplateService(_db_path)
    result = svc.create_template(**data)
    return jsonify({"message": t("api.letter_templates.created"), "data": result}), 201
@letter_templates_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin')
def update_template(pk):
    data = get_json_body()
    svc = LetterTemplateService(_db_path)
    result = svc.update_template(pk, **data)
    return jsonify({"message": t("api.letter_templates.updated"), "data": result})
@letter_templates_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required('admin')
def delete_template(pk):
    svc = LetterTemplateService(_db_path)
    svc.delete_template(pk)
    return jsonify({"message": t("api.letter_templates.deleted")})
@letter_templates_bp.route("/letters", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_letters():
    svc = LetterTemplateService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_letters(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@letter_templates_bp.route("/<int:pk>/generate", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def generate_letter(pk):
    data = get_json_body()
    svc = LetterTemplateService(_db_path)
    result = svc.generate_letter(pk, **data)
    return jsonify({"message": t("api.letter_templates.success"), "data": result}), 201
@letter_templates_bp.route("/stats", methods=["GET"])
@token_required
@role_required('admin')
def get_stats():
    svc = LetterTemplateService(_db_path)
    result = svc.get_stats()
    return jsonify({"data": result})
