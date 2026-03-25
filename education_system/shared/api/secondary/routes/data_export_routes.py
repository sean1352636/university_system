"""Data Export API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.admin.data_export.services.export_service import ExportService

data_export_bp = Blueprint("data_export", __name__, url_prefix="/api/data-export")

_db_path = None


def init_data_export_routes(db_path=None):
    global _db_path
    _db_path = db_path


@data_export_bp.route("/students", methods=["GET"])
@token_required
@role_required("admin")
def export_students():
    svc = ExportService(_db_path)
    result = svc.export_students()
    from flask import Response
    return Response(result, mimetype="text/csv",
                   headers={"Content-Disposition": "attachment; filename=export_students.csv"})


@data_export_bp.route("/grades", methods=["GET"])
@token_required
@role_required("admin")
def export_grades():
    svc = ExportService(_db_path)
    result = svc.export_grades()
    from flask import Response
    return Response(result, mimetype="text/csv",
                   headers={"Content-Disposition": "attachment; filename=export_grades.csv"})


@data_export_bp.route("/attendance", methods=["GET"])
@token_required
@role_required("admin")
def export_attendance():
    svc = ExportService(_db_path)
    result = svc.export_attendance()
    from flask import Response
    return Response(result, mimetype="text/csv",
                   headers={"Content-Disposition": "attachment; filename=export_attendance.csv"})


@data_export_bp.route("/behaviour", methods=["GET"])
@token_required
@role_required("admin")
def export_behaviour():
    svc = ExportService(_db_path)
    result = svc.export_behaviour()
    from flask import Response
    return Response(result, mimetype="text/csv",
                   headers={"Content-Disposition": "attachment; filename=export_behaviour.csv"})


@data_export_bp.route("/timetable", methods=["GET"])
@token_required
@role_required("admin")
def export_timetable():
    svc = ExportService(_db_path)
    result = svc.export_timetable()
    from flask import Response
    return Response(result, mimetype="text/csv",
                   headers={"Content-Disposition": "attachment; filename=export_timetable.csv"})

