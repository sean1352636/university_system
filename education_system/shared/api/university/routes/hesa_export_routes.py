"""HESA export routes: statutory returns, field mappings, and submission logs."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

hesa_export_bp = Blueprint("hesa_export", __name__, url_prefix="/api/hesa-export")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- returns ----

@hesa_export_bp.route("/returns", methods=["GET"])
@token_required
def list_returns():
    status = request.args.get("status")
    return_type = request.args.get("return_type")
    academic_year = request.args.get("academic_year")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if return_type:
            conditions.append("return_type = ?")
            params.append(return_type)
        if academic_year:
            conditions.append("academic_year = ?")
            params.append(academic_year)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM hesa_returns" + where + " ORDER BY id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM hesa_returns" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "hesa_returns", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@hesa_export_bp.route("/returns/<int:return_id>", methods=["GET"])
@token_required
def get_return(return_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM hesa_returns WHERE id = ?", (return_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"HESA return {return_id} not found")
    log_activity("view", "hesa_return", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@hesa_export_bp.route("/returns", methods=["POST"])
@token_required
def create_return():
    data = request.get_json(silent=True) or {}
    for field in ["academic_year", "return_type"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO hesa_returns
               (academic_year, return_type, created_by, notes)
               VALUES (?, ?, ?, ?)""",
            (data["academic_year"], data["return_type"],
             data.get("created_by", g.current_user.get("sub", "")),
             data.get("notes", "")),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM hesa_returns WHERE id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "hesa_return", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@hesa_export_bp.route("/returns/<int:return_id>/status", methods=["PUT"])
@token_required
def update_return_status(return_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM hesa_returns WHERE id = ?", (return_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"HESA return {return_id} not found")

    data = request.get_json(silent=True) or {}
    if "status" not in data:
        raise ValidationError("Missing required field: status")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            "UPDATE hesa_returns SET status = ? WHERE id = ?",
            (data["status"], return_id),
        )
        if data["status"] == "submitted":
            conn.execute(
                "UPDATE hesa_returns SET submitted_at = ? WHERE id = ?",
                (now, return_id),
            )
        conn.execute(
            """INSERT INTO hesa_submission_log
               (return_id, action, details, performed_by)
               VALUES (?, ?, ?, ?)""",
            (return_id, f"status_changed_to_{data['status']}",
             data.get("details", ""), g.current_user.get("sub", "")),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM hesa_returns WHERE id = ?", (return_id,)
        ).fetchone()

    log_activity("update", "hesa_return_status", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- field mappings ----

@hesa_export_bp.route("/field-mappings", methods=["GET"])
@token_required
def list_field_mappings():
    return_type = request.args.get("return_type")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if return_type:
            conditions.append("return_type = ?")
            params.append(return_type)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        rows = conn.execute(
            "SELECT * FROM hesa_field_mappings" + where + " ORDER BY id",
            params,
        ).fetchall()

    log_activity("view", "hesa_field_mappings", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@hesa_export_bp.route("/field-mappings", methods=["POST"])
@token_required
def create_field_mapping():
    data = request.get_json(silent=True) or {}
    for field in ["return_type", "hesa_field", "local_field"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO hesa_field_mappings
               (return_type, hesa_field, local_field, transform_rule)
               VALUES (?, ?, ?, ?)""",
            (data["return_type"], data["hesa_field"], data["local_field"],
             data.get("transform_rule", "")),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM hesa_field_mappings WHERE id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "hesa_field_mapping", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- submission log ----

@hesa_export_bp.route("/returns/<int:return_id>/log", methods=["GET"])
@token_required
def get_submission_log(return_id: int):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM hesa_submission_log WHERE return_id = ? ORDER BY performed_at DESC",
            (return_id,),
        ).fetchall()

    log_activity("view", "hesa_submission_log", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- statistics ----

@hesa_export_bp.route("/statistics", methods=["GET"])
@token_required
def get_statistics():
    with get_connection() as conn:
        total_returns = conn.execute("SELECT COUNT(*) FROM hesa_returns").fetchone()[0]
        draft_returns = conn.execute("SELECT COUNT(*) FROM hesa_returns WHERE status = 'draft'").fetchone()[0]
        submitted_returns = conn.execute("SELECT COUNT(*) FROM hesa_returns WHERE status = 'submitted'").fetchone()[0]
        total_mappings = conn.execute("SELECT COUNT(*) FROM hesa_field_mappings").fetchone()[0]

    log_activity("view", "hesa_statistics", user=g.current_user.get("sub"))
    return jsonify({
        "total_returns": total_returns,
        "draft_returns": draft_returns,
        "submitted_returns": submitted_returns,
        "total_field_mappings": total_mappings,
    })


@hesa_export_bp.route("/returns/<int:return_id>/generate-xml", methods=["POST"])
@token_required
def generate_xml_export(return_id: int):
    import xml.etree.ElementTree as ET

    with get_connection() as conn:
        ret = conn.execute(
            "SELECT * FROM hesa_returns WHERE id = ?", (return_id,)
        ).fetchone()
    if not ret:
        raise ValidationError(f"HESA return {return_id} not found")

    ret_dict = _row_to_dict(ret)
    root = ET.Element("HESAReturn")
    root.set("AcademicYear", ret_dict.get("academic_year", ""))
    root.set("ReturnType", ret_dict.get("return_type", ""))
    root.set("GeneratedAt", datetime.now().isoformat())

    institution = ET.SubElement(root, "Institution")
    ET.SubElement(institution, "UKPRN").text = "10000001"
    ET.SubElement(institution, "InstitutionName").text = "University"

    if ret_dict.get("return_type") == "Student":
        students_elem = ET.SubElement(root, "StudentRecords")
        with get_connection() as conn:
            try:
                rows = conn.execute("SELECT * FROM students LIMIT 1000").fetchall()
                for row in rows:
                    s = _row_to_dict(row)
                    student_elem = ET.SubElement(students_elem, "Student")
                    ET.SubElement(student_elem, "StudentID").text = str(s.get("student_id", ""))
                    ET.SubElement(student_elem, "FirstName").text = str(s.get("first_name", s.get("name", "")))
                    ET.SubElement(student_elem, "LastName").text = str(s.get("last_name", ""))
                    ET.SubElement(student_elem, "Course").text = str(s.get("course", s.get("program", "")))
            except Exception:
                ET.SubElement(students_elem, "Error").text = "Could not retrieve student data"

    xml_str = ET.tostring(root, encoding="unicode", xml_declaration=True)

    with transaction() as conn:
        conn.execute("UPDATE hesa_returns SET xml_data = ? WHERE id = ?", (xml_str, return_id))

    log_activity("generate", "hesa_xml_export", user=g.current_user.get("sub"))
    return jsonify({"return_id": return_id, "xml": xml_str})


@hesa_export_bp.route("/returns/<int:return_id>/log", methods=["POST"])
@token_required
def log_submission_action(return_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM hesa_returns WHERE id = ?", (return_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"HESA return {return_id} not found")

    data = request.get_json(silent=True) or {}
    if "action" not in data:
        raise ValidationError("Missing required field: action")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO hesa_submission_log
               (return_id, action, details, performed_by)
               VALUES (?, ?, ?, ?)""",
            (return_id, data["action"], data.get("details", ""),
             data.get("performed_by", g.current_user.get("sub", ""))),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM hesa_submission_log WHERE id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "hesa_submission_log_entry", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
