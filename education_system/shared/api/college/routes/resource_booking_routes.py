"""API routes for resource booking."""

from flask import Blueprint, jsonify, request
from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.resource_booking.services.resource_booking_service import ResourceBookingService
from education_system.college_system.core.i18n import t

resource_booking_bp = Blueprint("resource-booking", __name__, url_prefix="/api/resource-booking")

_db_path = None


def init_resource_booking_routes(db_path=None):
    global _db_path
    _db_path = db_path


@resource_booking_bp.route("", methods=["GET"])
@token_required
def list_resources():
    svc = ResourceBookingService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_resources(limit=limit, offset=offset)
    total = svc.count_resources()
    return jsonify(paginated_response(items, total))


@resource_booking_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_resource(pk):
    svc = ResourceBookingService(_db_path)
    item = svc.get_resource(pk)
    if not item:
        return jsonify({"error": t("api.resource_booking.not_found")}), 404
    return jsonify({"data": item})


@resource_booking_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_resource():
    data = get_json_body()
    require_fields(data, "name", "resource_type")
    svc = ResourceBookingService(_db_path)
    item = svc.create_resource(**data)
    return jsonify({"message": t("api.resource_booking.created"), "data": item}), 201


@resource_booking_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_resource(pk):
    data = get_json_body()
    svc = ResourceBookingService(_db_path)
    item = svc.update_resource(pk, **data)
    return jsonify({"message": t("api.resource_booking.updated"), "data": item})


@resource_booking_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_resource(pk):
    svc = ResourceBookingService(_db_path)
    svc.delete_resource(pk)
    return jsonify({"message": t("api.resource_booking.deleted")})
