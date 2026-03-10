"""API routes for staff appraisals."""

from flask import Blueprint, jsonify, request
from education_system.college_system.api.auth import token_required, role_required
from education_system.college_system.api.validators import get_json_body, require_fields
from education_system.college_system.api.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.appraisals.services.appraisals_service import AppraisalService

appraisals_bp = Blueprint("appraisals", __name__, url_prefix="/api/appraisals")

_db_path = None


def init_appraisals_routes(db_path=None):
    global _db_path
    _db_path = db_path


@appraisals_bp.route("", methods=["GET"])
@token_required
def list_appraisals():
    svc = AppraisalService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_appraisals(limit=limit, offset=offset)
    total = svc.count_appraisals()
    return jsonify(paginated_response(items, total))


@appraisals_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_appraisal(pk):
    svc = AppraisalService(_db_path)
    item = svc.get_appraisal(pk)
    if not item:
        return jsonify({"error": "Appraisal not found."}), 404
    return jsonify({"data": item})


@appraisals_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_appraisal():
    data = get_json_body()
    require_fields(data, "staff_id", "academic_year")
    svc = AppraisalService(_db_path)
    item = svc.create_appraisal(**data)
    return jsonify({"message": "Appraisal created.", "data": item}), 201


@appraisals_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_appraisal(pk):
    data = get_json_body()
    svc = AppraisalService(_db_path)
    item = svc.update_appraisal(pk, **data)
    return jsonify({"message": "Appraisal updated.", "data": item})


@appraisals_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_appraisal(pk):
    svc = AppraisalService(_db_path)
    svc.delete_appraisal(pk)
    return jsonify({"message": "Appraisal deleted."})
