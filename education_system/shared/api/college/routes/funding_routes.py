"""Funding & ILR API routes."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.college_system.modules.domain.funding.services.funding_service import FundingService
from education_system.college_system.core.i18n import t

funding_bp = Blueprint("funding", __name__, url_prefix="/api/funding")

_db_path = None


def init_funding_routes(db_path=None):
    global _db_path
    _db_path = db_path


@funding_bp.route("/records", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_record():
    data = get_json_body()
    require_fields(data, "student_id")
    svc = FundingService(_db_path)
    record = svc.create_funding_record(
        data["student_id"],
        learning_aim=data.get("learning_aim"),
        aim_type=data.get("aim_type"),
        funding_model=data.get("funding_model", "16-19"),
        planned_hours=data.get("planned_hours", 0),
        start_date=data.get("start_date"),
        planned_end_date=data.get("planned_end_date"),
    )
    return jsonify({"message": t("api.funding.created"), "data": record}), 201


@funding_bp.route("/records", methods=["GET"])
@token_required
def list_records():
    svc = FundingService(_db_path)
    student_id = request.args.get("student_id", type=int)
    status = request.args.get("status")
    records = svc.list_funding_records(student_id=student_id, status=status)
    return jsonify({"data": records, "count": len(records)})


@funding_bp.route("/records/<int:rid>", methods=["GET"])
@token_required
def get_record(rid):
    svc = FundingService(_db_path)
    record = svc.get_funding_record(rid)
    if not record:
        return jsonify({"error": t("api.funding.not_found")}), 404
    return jsonify({"data": record})


@funding_bp.route("/records/<int:rid>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_record(rid):
    data = get_json_body()
    svc = FundingService(_db_path)
    record = svc.update_funding_record(rid, **data)
    return jsonify({"message": t("api.funding.updated"), "data": record})


@funding_bp.route("/records/<int:rid>/complete", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def complete_record(rid):
    data = request.get_json(silent=True) or {}
    svc = FundingService(_db_path)
    record = svc.complete_funding_record(rid, data.get("outcome", "achieved"))
    return jsonify({"message": t("api.common.updated"), "data": record})


@funding_bp.route("/records/<int:rid>/withdraw", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def withdraw_record(rid):
    svc = FundingService(_db_path)
    record = svc.withdraw_funding_record(rid)
    return jsonify({"message": t("api.common.updated"), "data": record})


@funding_bp.route("/evidence", methods=["POST"])
@token_required
@role_required("admin", "staff")
def add_evidence():
    data = get_json_body()
    require_fields(data, "funding_record_id")
    svc = FundingService(_db_path)
    ev = svc.add_evidence(
        data["funding_record_id"],
        evidence_type=data.get("evidence_type", "other"),
        file_path=data.get("file_path"),
    )
    return jsonify({"message": t("api.common.created"), "data": ev}), 201


@funding_bp.route("/evidence", methods=["GET"])
@token_required
def list_evidence():
    svc = FundingService(_db_path)
    record_id = request.args.get("funding_record_id", type=int)
    evidence = svc.list_evidence(funding_record_id=record_id)
    return jsonify({"data": evidence, "count": len(evidence)})


@funding_bp.route("/evidence/<int:eid>/verify", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def verify_evidence(eid):
    svc = FundingService(_db_path)
    ev = svc.verify_evidence(eid, g.current_user.get("user_id", 0))
    return jsonify({"message": t("api.common.updated"), "data": ev})


@funding_bp.route("/rules", methods=["POST"])
@token_required
@role_required("admin")
def create_rule():
    data = get_json_body()
    require_fields(data, "rule_code")
    svc = FundingService(_db_path)
    rule = svc.create_rule(
        data["rule_code"],
        description=data.get("description"),
        rule_type=data.get("rule_type", "eligibility"),
        applies_to=data.get("applies_to"),
    )
    return jsonify({"message": t("api.common.created"), "data": rule}), 201


@funding_bp.route("/rules", methods=["GET"])
@token_required
def list_rules():
    svc = FundingService(_db_path)
    rules = svc.list_rules()
    return jsonify({"data": rules, "count": len(rules)})


@funding_bp.route("/resits", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_resit():
    data = get_json_body()
    require_fields(data, "student_id", "subject")
    svc = FundingService(_db_path)
    resit = svc.create_resit(
        data["student_id"], data["subject"],
        gcse_grade_on_entry=data.get("gcse_grade_on_entry"),
        current_level=data.get("current_level"),
        target_grade=data.get("target_grade"),
    )
    return jsonify({"message": t("api.common.created"), "data": resit}), 201


@funding_bp.route("/resits", methods=["GET"])
@token_required
def list_resits():
    svc = FundingService(_db_path)
    student_id = request.args.get("student_id", type=int)
    subject = request.args.get("subject")
    resits = svc.list_resits(student_id=student_id, subject=subject)
    return jsonify({"data": resits, "count": len(resits)})


@funding_bp.route("/resits/<int:rid>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_resit(rid):
    data = get_json_body()
    svc = FundingService(_db_path)
    resit = svc.update_resit(rid, **data)
    return jsonify({"message": t("api.common.updated"), "data": resit})


@funding_bp.route("/ilr-export", methods=["GET"])
@token_required
@role_required("admin")
def ilr_export():
    svc = FundingService(_db_path)
    data = svc.export_ilr_data()
    return jsonify({"data": data, "count": len(data)})


@funding_bp.route("/hours/<int:student_id>", methods=["GET"])
@token_required
def hours_summary(student_id):
    svc = FundingService(_db_path)
    summary = svc.get_hours_summary(student_id)
    return jsonify({"data": summary})
