"""API routes for work journal."""

from flask import Blueprint, jsonify, request
from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.work_journal.services.work_journal_service import WorkJournalService
from education_system.college_system.core.i18n import t

work_journal_bp = Blueprint("work-journal", __name__, url_prefix="/api/work-journal")

_db_path = None


def init_work_journal_routes(db_path=None):
    global _db_path
    _db_path = db_path


@work_journal_bp.route("", methods=["GET"])
@token_required
def list_placements():
    svc = WorkJournalService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_placements(limit=limit, offset=offset)
    total = svc.count_placements()
    return jsonify(paginated_response(items, total))


@work_journal_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_placement(pk):
    svc = WorkJournalService(_db_path)
    item = svc.get_placement(pk)
    if not item:
        return jsonify({"error": t("api.work_journal.not_found")}), 404
    return jsonify({"data": item})


@work_journal_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def create_placement():
    data = get_json_body()
    require_fields(data, "student_id", "employer_name", "start_date")
    svc = WorkJournalService(_db_path)
    item = svc.create_placement(**data)
    return jsonify({"message": t("api.work_journal.created"), "data": item}), 201


@work_journal_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff", "instructor")
def update_placement(pk):
    data = get_json_body()
    svc = WorkJournalService(_db_path)
    item = svc.update_placement(pk, **data)
    return jsonify({"message": t("api.work_journal.updated"), "data": item})


@work_journal_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_placement(pk):
    svc = WorkJournalService(_db_path)
    svc.delete_placement(pk)
    return jsonify({"message": t("api.work_journal.deleted")})
