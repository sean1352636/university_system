"""API routes for absence requests."""

from flask import Blueprint, jsonify, request, g
from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.shared.api.content_negotiation import negotiate_response
from education_system.college_system.modules.domain.absence_requests.services.absence_requests_service import AbsenceRequestService
from education_system.college_system.core.i18n import t

absence_request_bp = Blueprint("absence-requests", __name__, url_prefix="/api/absence-requests")

_db_path = None


def init_absence_request_routes(db_path=None):
    global _db_path
    _db_path = db_path


@absence_request_bp.route("", methods=["GET"])
@token_required
def list_requests():
    svc = AbsenceRequestService(_db_path)
    limit, offset = get_pagination_params()
    sort_by = request.args.get("sort_by", "id")
    sort_order = request.args.get("sort_order", "desc")
    filters = {}
    for key in ("staff_id", "absence_type", "status"):
        val = request.args.get(key)
        if val:
            filters[key] = int(val) if key == "staff_id" else val
    for key in ("date_from", "date_to"):
        val = request.args.get(key)
        if val:
            filters[key] = val
    # Authorization scoping: non-admin users can only see their own requests
    role = g.current_user.get("role", "")
    if role != "admin":
        filters["staff_id"] = g.current_user["user_id"]
    items = svc.list_requests(limit=limit, offset=offset,
                              sort_by=sort_by, sort_order=sort_order, **filters)
    total = svc.count_requests(**{k: v for k, v in filters.items()
                                  if k not in ("date_from", "date_to")})
    return jsonify(paginated_response(items, total))


@absence_request_bp.route("/mine", methods=["GET"])
@token_required
def my_requests():
    svc = AbsenceRequestService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.get_my_requests(
        g.current_user["user_id"],
        status=request.args.get("status"),
        absence_type=request.args.get("absence_type"),
        date_from=request.args.get("date_from"),
        date_to=request.args.get("date_to"),
        sort_by=request.args.get("sort_by", "id"),
        sort_order=request.args.get("sort_order", "desc"),
        limit=limit, offset=offset,
    )
    return jsonify({"data": items})


@absence_request_bp.route("/upcoming", methods=["GET"])
@token_required
def upcoming_requests():
    svc = AbsenceRequestService(_db_path)
    role = g.current_user.get("role", "")
    staff_id = None if role == "admin" else g.current_user["user_id"]
    items = svc.get_upcoming(staff_id=staff_id)
    return jsonify({"data": items})


@absence_request_bp.route("/stats", methods=["GET"])
@token_required
@role_required("admin")
def get_stats():
    svc = AbsenceRequestService(_db_path)
    year = request.args.get("year")
    result = svc.get_stats(academic_year=year)
    return jsonify({"data": result})


@absence_request_bp.route("/export", methods=["GET"])
@token_required
@role_required("admin")
def export_requests():
    svc = AbsenceRequestService(_db_path)
    filters = {}
    for key in ("staff_id", "absence_type", "status"):
        val = request.args.get(key)
        if val:
            filters[key] = int(val) if key == "staff_id" else val
    for key in ("date_from", "date_to"):
        val = request.args.get(key)
        if val:
            filters[key] = val
    items = svc.list_requests(limit=10000, **filters)
    return negotiate_response(
        items,
        columns=["id", "staff_id", "absence_type", "start_date", "end_date",
                 "days_requested", "reason", "status", "rejection_reason",
                 "approved_by", "created_at", "updated_at"],
        filename="absence_requests",
    )


@absence_request_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_request(pk):
    svc = AbsenceRequestService(_db_path)
    item = svc.get_request(pk)
    if not item:
        return jsonify({"error": t("api.absence_requests.not_found")}), 404
    # Non-admin users can only view their own requests
    if g.current_user.get("role") != "admin" and item["staff_id"] != g.current_user["user_id"]:
        return jsonify({"error": "Access denied."}), 403
    return jsonify({"data": item})


@absence_request_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_request():
    data = get_json_body()
    require_fields(data, "staff_id", "absence_type", "start_date", "end_date")
    svc = AbsenceRequestService(_db_path)
    item = svc.create_request(**data)
    return jsonify({"message": t("api.absence_requests.created"), "data": item}), 201


@absence_request_bp.route("/drafts", methods=["POST"])
@token_required
@role_required("admin", "staff")
def save_draft():
    data = get_json_body()
    data.setdefault("staff_id", g.current_user["user_id"])
    svc = AbsenceRequestService(_db_path)
    item = svc.save_draft(**data)
    return jsonify({"message": "Draft saved.", "data": item}), 201


@absence_request_bp.route("/drafts/<int:pk>/submit", methods=["POST"])
@token_required
@role_required("admin", "staff")
def submit_draft(pk):
    svc = AbsenceRequestService(_db_path)
    item = svc.submit_draft(pk, staff_id=g.current_user["user_id"])
    return jsonify({"message": t("api.absence_requests.created"), "data": item}), 201


@absence_request_bp.route("/<int:pk>/duplicate", methods=["POST"])
@token_required
@role_required("admin", "staff")
def duplicate_request(pk):
    svc = AbsenceRequestService(_db_path)
    item = svc.duplicate_request(pk, staff_id=g.current_user["user_id"])
    return jsonify({"message": "Request duplicated as draft.", "data": item}), 201


@absence_request_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_request(pk):
    svc = AbsenceRequestService(_db_path)
    # Ownership check: staff can only update their own requests
    if g.current_user.get("role") != "admin":
        existing = svc.get_request(pk)
        if not existing:
            return jsonify({"error": t("api.absence_requests.not_found")}), 404
        if existing["staff_id"] != g.current_user["user_id"]:
            return jsonify({"error": "You can only update your own requests."}), 403
        if existing["status"] != "pending":
            return jsonify({"error": "Only pending requests can be edited."}), 403
    data = get_json_body()
    item = svc.update_request(pk, _actor_id=g.current_user["user_id"], **data)
    return jsonify({"message": t("api.absence_requests.updated"), "data": item})


@absence_request_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_request(pk):
    svc = AbsenceRequestService(_db_path)
    svc.delete_request(pk, actor_id=g.current_user["user_id"])
    return jsonify({"message": "Request soft-deleted."})


@absence_request_bp.route("/<int:pk>/restore", methods=["POST"])
@token_required
@role_required("admin")
def restore_request(pk):
    svc = AbsenceRequestService(_db_path)
    result = svc.restore_request(pk, actor_id=g.current_user["user_id"])
    return jsonify({"message": "Request restored.", "data": result})


@absence_request_bp.route("/<int:pk>/purge", methods=["DELETE"])
@token_required
@role_required("admin")
def purge_request(pk):
    svc = AbsenceRequestService(_db_path)
    svc.purge_request(pk)
    return jsonify({"message": "Request permanently deleted."})


@absence_request_bp.route("/<int:pk>/approve", methods=["POST"])
@token_required
@role_required("admin")
def approve_request(pk):
    svc = AbsenceRequestService(_db_path)
    result = svc.approve_request(pk, approved_by=g.current_user["user_id"])
    return jsonify({"message": t("api.absence_requests.approved"), "data": result})


@absence_request_bp.route("/<int:pk>/reject", methods=["POST"])
@token_required
@role_required("admin")
def reject_request(pk):
    data = get_json_body()
    rejection_reason = data.get("rejection_reason")
    svc = AbsenceRequestService(_db_path)
    result = svc.reject_request(pk, approved_by=g.current_user["user_id"],
                                rejection_reason=rejection_reason)
    return jsonify({"message": t("api.absence_requests.rejected"), "data": result})


@absence_request_bp.route("/<int:pk>/cancel", methods=["POST"])
@token_required
def cancel_request(pk):
    svc = AbsenceRequestService(_db_path)
    result = svc.cancel_request(pk, staff_id=g.current_user["user_id"])
    return jsonify({"message": t("api.absence_requests.updated"), "data": result})


@absence_request_bp.route("/<int:pk>/hr-approve", methods=["POST"])
@token_required
@role_required("admin")
def hr_approve_request(pk):
    svc = AbsenceRequestService(_db_path)
    result = svc.hr_approve_request(pk, hr_user_id=g.current_user["user_id"])
    return jsonify({"message": "Request HR-approved.", "data": result})


@absence_request_bp.route("/<int:pk>/hr-reject", methods=["POST"])
@token_required
@role_required("admin")
def hr_reject_request(pk):
    data = get_json_body()
    svc = AbsenceRequestService(_db_path)
    result = svc.hr_reject_request(pk, hr_user_id=g.current_user["user_id"],
                                   reason=data.get("reason"))
    return jsonify({"message": "Request HR-rejected.", "data": result})


@absence_request_bp.route("/entitlements/mine", methods=["GET"])
@token_required
def my_entitlements():
    svc = AbsenceRequestService(_db_path)
    year = request.args.get("year")
    items = svc.list_entitlements(g.current_user["user_id"], academic_year=year)
    return jsonify({"data": items})


@absence_request_bp.route("/entitlements/<int:staff_id>", methods=["GET"])
@token_required
@role_required("admin")
def staff_entitlements(staff_id):
    svc = AbsenceRequestService(_db_path)
    year = request.args.get("year")
    items = svc.list_entitlements(staff_id, academic_year=year)
    return jsonify({"data": items})


@absence_request_bp.route("/entitlements/<int:staff_id>", methods=["PUT"])
@token_required
@role_required("admin")
def set_entitlement(staff_id):
    data = get_json_body()
    require_fields(data, "absence_type", "total_days")
    svc = AbsenceRequestService(_db_path)
    result = svc.set_entitlement(
        staff_id, data["absence_type"], float(data["total_days"]),
        academic_year=data.get("academic_year"),
        carried_over=float(data.get("carried_over", 0)),
    )
    return jsonify({"message": "Entitlement updated.", "data": result})


@absence_request_bp.route("/reminders/stale", methods=["POST"])
@token_required
@role_required("admin")
def send_stale_reminders():
    svc = AbsenceRequestService(_db_path)
    stale_days = request.args.get("days", 3, type=int)
    count = svc.send_stale_reminders(stale_days=stale_days)
    return jsonify({"message": f"Reminders sent for {count} stale request(s).", "count": count})


@absence_request_bp.route("/<int:pk>/attachments", methods=["GET"])
@token_required
def list_attachments(pk):
    svc = AbsenceRequestService(_db_path)
    # Non-admin users can only view attachments on their own requests
    if g.current_user.get("role") != "admin":
        req = svc.get_request(pk)
        if not req or req["staff_id"] != g.current_user["user_id"]:
            return jsonify({"error": "Access denied."}), 403
    items = svc.list_attachments(pk)
    return jsonify({"data": items})


@absence_request_bp.route("/<int:pk>/attachments", methods=["POST"])
@token_required
@role_required("admin", "staff")
def add_attachment(pk):
    data = get_json_body()
    require_fields(data, "file_name", "file_path")
    svc = AbsenceRequestService(_db_path)
    item = svc.add_attachment(
        pk, data["file_name"], data["file_path"],
        uploaded_by=g.current_user["user_id"],
        file_type=data.get("file_type"),
        file_size=int(data.get("file_size", 0)),
    )
    return jsonify({"message": "Attachment added.", "data": item}), 201


@absence_request_bp.route("/attachments/<int:att_id>", methods=["DELETE"])
@token_required
@role_required("admin", "staff")
def delete_attachment(att_id):
    svc = AbsenceRequestService(_db_path)
    svc.delete_attachment(att_id, user_id=g.current_user["user_id"])
    return jsonify({"message": "Attachment deleted."})


@absence_request_bp.route("/<int:pk>/audit", methods=["GET"])
@token_required
@role_required("admin")
def get_audit_log(pk):
    svc = AbsenceRequestService(_db_path)
    items = svc.get_audit_log(pk)
    return jsonify({"data": items})


@absence_request_bp.route("/<int:pk>/resubmit", methods=["POST"])
@token_required
@role_required("admin", "staff")
def resubmit_request(pk):
    data = get_json_body()
    svc = AbsenceRequestService(_db_path)
    result = svc.resubmit_request(pk, staff_id=g.current_user["user_id"], **data)
    return jsonify({"message": "Request resubmitted.", "data": result}), 201


@absence_request_bp.route("/batch/approve", methods=["POST"])
@token_required
@role_required("admin")
def batch_approve():
    data = get_json_body()
    require_fields(data, "ids")
    svc = AbsenceRequestService(_db_path)
    result = svc.batch_approve(data["ids"], approved_by=g.current_user["user_id"])
    return jsonify({"data": result})


@absence_request_bp.route("/batch/reject", methods=["POST"])
@token_required
@role_required("admin")
def batch_reject():
    data = get_json_body()
    require_fields(data, "ids")
    svc = AbsenceRequestService(_db_path)
    result = svc.batch_reject(data["ids"], approved_by=g.current_user["user_id"],
                              rejection_reason=data.get("rejection_reason"))
    return jsonify({"data": result})


@absence_request_bp.route("/holidays", methods=["GET"])
@token_required
def list_holidays():
    svc = AbsenceRequestService(_db_path)
    year = request.args.get("year")
    items = svc.list_holidays(academic_year=year)
    return jsonify({"data": items})


@absence_request_bp.route("/holidays", methods=["POST"])
@token_required
@role_required("admin")
def add_holiday():
    data = get_json_body()
    require_fields(data, "date", "name")
    svc = AbsenceRequestService(_db_path)
    item = svc.add_holiday(data["date"], data["name"],
                           academic_year=data.get("academic_year"))
    return jsonify({"message": "Holiday added.", "data": item}), 201


@absence_request_bp.route("/holidays/<int:holiday_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_holiday(holiday_id):
    svc = AbsenceRequestService(_db_path)
    svc.delete_holiday(holiday_id)
    return jsonify({"message": "Holiday deleted."})


@absence_request_bp.route("/balance-summary", methods=["GET"])
@token_required
@role_required("admin")
def balance_summary():
    svc = AbsenceRequestService(_db_path)
    year = request.args.get("year")
    items = svc.get_balance_summary(academic_year=year)
    return jsonify({"data": items})


@absence_request_bp.route("/data-retention/purge", methods=["POST"])
@token_required
@role_required("admin")
def purge_expired_data():
    svc = AbsenceRequestService(_db_path)
    days = request.args.get("days", type=int)
    result = svc.purge_expired_data(retention_days=days)
    return jsonify({"message": "Data retention purge complete.", "data": result})
