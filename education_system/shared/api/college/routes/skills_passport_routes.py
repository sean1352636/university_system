"""API routes for skills passport."""

from flask import Blueprint, jsonify, request
from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.skills_passport.services.skills_passport_service import SkillsPassportService
from education_system.college_system.core.i18n import t

skills_passport_bp = Blueprint("skills-passport", __name__, url_prefix="/api/skills-passport")

_db_path = None


def init_skills_passport_routes(db_path=None):
    global _db_path
    _db_path = db_path


@skills_passport_bp.route("", methods=["GET"])
@token_required
def list_categories():
    svc = SkillsPassportService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_categories(limit=limit, offset=offset)
    total = svc.count_categories()
    return jsonify(paginated_response(items, total))


@skills_passport_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_category(pk):
    svc = SkillsPassportService(_db_path)
    item = svc.get_category(pk)
    if not item:
        return jsonify({"error": t("api.skills_passport.not_found")}), 404
    return jsonify({"data": item})


@skills_passport_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def create_category():
    data = get_json_body()
    require_fields(data, "name")
    svc = SkillsPassportService(_db_path)
    item = svc.create_category(**data)
    return jsonify({"message": t("api.skills_passport.created"), "data": item}), 201


@skills_passport_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff", "instructor")
def update_category(pk):
    data = get_json_body()
    svc = SkillsPassportService(_db_path)
    item = svc.update_category(pk, **data)
    return jsonify({"message": t("api.skills_passport.updated"), "data": item})


@skills_passport_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_category(pk):
    svc = SkillsPassportService(_db_path)
    svc.delete_category(pk)
    return jsonify({"message": t("api.skills_passport.deleted")})
