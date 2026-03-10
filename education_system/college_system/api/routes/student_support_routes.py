"""Student Support API routes."""

from flask import Blueprint, jsonify, request, g

from education_system.college_system.api.auth import token_required, role_required
from education_system.college_system.api.validators import get_json_body, require_fields
from education_system.college_system.modules.domain.student_support.services.student_support_service import StudentSupportService

student_support_bp = Blueprint("student_support", __name__, url_prefix="/api/support")

_db_path = None


def init_student_support_routes(db_path=None):
    global _db_path
    _db_path = db_path


@student_support_bp.route("/interventions", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def create_intervention():
    data = get_json_body()
    require_fields(data, "student_id", "staff_id", "intervention_type")
    svc = StudentSupportService(_db_path)
    item = svc.create_intervention(
        data["student_id"], data["staff_id"],
        data["intervention_type"],
        targets=data.get("targets"),
        sessions_planned=data.get("sessions_planned", 0),
    )
    return jsonify({"message": "Intervention created.", "data": item}), 201


@student_support_bp.route("/interventions", methods=["GET"])
@token_required
def list_interventions():
    svc = StudentSupportService(_db_path)
    student_id = request.args.get("student_id", type=int)
    status = request.args.get("status")
    items = svc.list_interventions(student_id=student_id, status=status)
    return jsonify({"data": items, "count": len(items)})


@student_support_bp.route("/interventions/<int:iid>", methods=["GET"])
@token_required
def get_intervention(iid):
    svc = StudentSupportService(_db_path)
    item = svc.get_intervention(iid)
    if not item:
        return jsonify({"error": "Intervention not found."}), 404
    return jsonify({"data": item})


@student_support_bp.route("/interventions/<int:iid>", methods=["PUT"])
@token_required
@role_required("admin", "staff", "instructor")
def update_intervention(iid):
    data = get_json_body()
    svc = StudentSupportService(_db_path)
    item = svc.update_intervention(iid, **data)
    return jsonify({"message": "Intervention updated.", "data": item})


@student_support_bp.route("/risks", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def create_risk():
    data = get_json_body()
    require_fields(data, "student_id", "risk_type", "risk_level")
    svc = StudentSupportService(_db_path)
    risk = svc.create_risk(
        data["student_id"], data["risk_type"], data["risk_level"],
        identified_by=g.current_user.get("user_id", 0),
        mitigations=data.get("mitigations"),
    )
    return jsonify({"message": "Risk created.", "data": risk}), 201


@student_support_bp.route("/risks", methods=["GET"])
@token_required
def list_risks():
    svc = StudentSupportService(_db_path)
    student_id = request.args.get("student_id", type=int)
    status = request.args.get("status")
    risks = svc.list_risks(student_id=student_id, status=status)
    return jsonify({"data": risks, "count": len(risks)})


@student_support_bp.route("/risks/<int:rid>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_risk(rid):
    data = get_json_body()
    svc = StudentSupportService(_db_path)
    risk = svc.update_risk(rid, **data)
    return jsonify({"message": "Risk updated.", "data": risk})


@student_support_bp.route("/risks/<int:rid>/resolve", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def resolve_risk(rid):
    svc = StudentSupportService(_db_path)
    risk = svc.resolve_risk(rid)
    return jsonify({"message": "Risk resolved.", "data": risk})


@student_support_bp.route("/documents", methods=["POST"])
@token_required
@role_required("admin", "staff")
def upload_document():
    data = get_json_body()
    require_fields(data, "student_id", "document_type", "title")
    svc = StudentSupportService(_db_path)
    doc = svc.upload_document(
        data["student_id"], data["document_type"], data["title"],
        uploaded_by=g.current_user.get("user_id", 0),
        file_path=data.get("file_path"),
        expiry_date=data.get("expiry_date"),
    )
    return jsonify({"message": "Document uploaded.", "data": doc}), 201


@student_support_bp.route("/documents", methods=["GET"])
@token_required
def list_documents():
    svc = StudentSupportService(_db_path)
    student_id = request.args.get("student_id", type=int)
    docs = svc.list_documents(student_id=student_id)
    return jsonify({"data": docs, "count": len(docs)})


@student_support_bp.route("/documents/<int:did>/verify", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def verify_document(did):
    svc = StudentSupportService(_db_path)
    doc = svc.verify_document(did, g.current_user.get("user_id", 0))
    return jsonify({"message": "Document verified.", "data": doc})


@student_support_bp.route("/student/<int:sid>/profile", methods=["GET"])
@token_required
def student_profile(sid):
    svc = StudentSupportService(_db_path)
    profile = svc.get_student_risk_profile(sid)
    return jsonify({"data": profile})
