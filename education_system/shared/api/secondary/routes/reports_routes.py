"""Reports API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.academics.reports.services.report_service import ReportService

reports_bp = Blueprint("reports", __name__, url_prefix="/api/reports")

_db_path = None


def init_reports_routes(db_path=None):
    global _db_path
    _db_path = db_path


@reports_bp.route("/attendance", methods=["GET"])
@token_required
@role_required("admin", "teacher")
def attendance_summary():
    svc = ReportService(_db_path)
    result = svc.attendance_summary()
    return jsonify({"data": result})


@reports_bp.route("/grades", methods=["GET"])
@token_required
@role_required("admin", "teacher")
def grade_summary():
    svc = ReportService(_db_path)
    result = svc.grade_summary()
    return jsonify({"data": result})


@reports_bp.route("/behaviour", methods=["GET"])
@token_required
@role_required("admin", "teacher")
def behaviour_summary():
    svc = ReportService(_db_path)
    result = svc.behaviour_summary()
    return jsonify({"data": result})


@reports_bp.route("/subject/<int:subject_id>", methods=["GET"])
@token_required
@role_required("admin", "teacher")
def subject_performance(subject_id):
    svc = ReportService(_db_path)
    result = svc.subject_performance(subject_id)
    return jsonify({"data": result})


@reports_bp.route("/year-group/<year_group>", methods=["GET"])
@token_required
@role_required("admin", "teacher")
def year_group_overview(year_group):
    svc = ReportService(_db_path)
    result = svc.year_group_overview(year_group)
    return jsonify({"data": result})

