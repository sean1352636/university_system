"""API routes for peer mentoring."""

from flask import Blueprint, jsonify, request
from education_system.college_system.api.auth import token_required, role_required
from education_system.college_system.api.validators import get_json_body, require_fields
from education_system.college_system.api.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.peer_mentoring.services.peer_mentoring_service import PeerMentoringService

peer_mentoring_bp = Blueprint("peer-mentoring", __name__, url_prefix="/api/peer-mentoring")

_db_path = None


def init_peer_mentoring_routes(db_path=None):
    global _db_path
    _db_path = db_path


@peer_mentoring_bp.route("", methods=["GET"])
@token_required
def list_pairs():
    svc = PeerMentoringService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_pairs(limit=limit, offset=offset)
    total = svc.count_pairs()
    return jsonify(paginated_response(items, total))


@peer_mentoring_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_pair(pk):
    svc = PeerMentoringService(_db_path)
    item = svc.get_pair(pk)
    if not item:
        return jsonify({"error": "Pair not found."}), 404
    return jsonify({"data": item})


@peer_mentoring_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def create_pair():
    data = get_json_body()
    require_fields(data, "mentor_id", "mentee_id")
    svc = PeerMentoringService(_db_path)
    item = svc.create_pair(**data)
    return jsonify({"message": "Pair created.", "data": item}), 201


@peer_mentoring_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff", "instructor")
def update_pair(pk):
    data = get_json_body()
    svc = PeerMentoringService(_db_path)
    item = svc.update_pair(pk, **data)
    return jsonify({"message": "Pair updated.", "data": item})


@peer_mentoring_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_pair(pk):
    svc = PeerMentoringService(_db_path)
    svc.delete_pair(pk)
    return jsonify({"message": "Pair deleted."})
