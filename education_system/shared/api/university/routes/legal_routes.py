"""Legal services routes: cases, consultations, documents, and payments."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

legal_bp = Blueprint("legal", __name__, url_prefix="/api/legal")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- cases ----

@legal_bp.route("/cases", methods=["GET"])
@token_required
def list_cases():
    search = request.args.get("search")
    client_id = request.args.get("client_id")
    status = request.args.get("status")
    case_type = request.args.get("case_type")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM legal_cases WHERE case_title LIKE ? OR client_name LIKE ? OR case_number LIKE ?",
                (pattern, pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if client_id:
            conditions.append("client_id = ?")
            params.append(client_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if case_type:
            conditions.append("case_type = ?")
            params.append(case_type)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM legal_cases" + where + " ORDER BY case_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM legal_cases" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "legal_cases", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@legal_bp.route("/cases/<int:case_id>", methods=["GET"])
@token_required
def get_case(case_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM legal_cases WHERE case_id = ?", (case_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"cases {case_id} not found")
    log_activity("view", "legal_cases", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@legal_bp.route("/cases", methods=["POST"])
@token_required
def create_case():
    data = request.get_json(silent=True) or {}
    for field in ["client_id", "client_name", "case_type", "case_title"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO legal_cases
               (client_id, client_name, case_type, case_title, client_email, case_description, priority, assigned_lawyer, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["client_id"], data["client_name"], data["case_type"], data["case_title"], data.get("client_email", ""), data.get("case_description", ""), data.get("priority", ""), data.get("assigned_lawyer", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM legal_cases WHERE case_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "legal_cases", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- consultations ----

@legal_bp.route("/consultations", methods=["GET"])
@token_required
def list_consultations():
    search = request.args.get("search")
    case_id = request.args.get("case_id")
    client_id = request.args.get("client_id")
    status = request.args.get("status")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM legal_consultations WHERE lawyer_name LIKE ?",
                (pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if case_id:
            conditions.append("case_id = ?")
            params.append(case_id)
        if client_id:
            conditions.append("client_id = ?")
            params.append(client_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM legal_consultations" + where + " ORDER BY consultation_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM legal_consultations" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "legal_consultations", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@legal_bp.route("/consultations/<int:consultation_id>", methods=["GET"])
@token_required
def get_consultation(consultation_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM legal_consultations WHERE consultation_id = ?", (consultation_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"consultations {consultation_id} not found")
    log_activity("view", "legal_consultations", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@legal_bp.route("/consultations", methods=["POST"])
@token_required
def create_consultation():
    data = request.get_json(silent=True) or {}
    for field in ["client_id", "client_name", "scheduled_date", "scheduled_time"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO legal_consultations
               (client_id, client_name, scheduled_date, scheduled_time, case_id, client_email, consultation_type, duration_minutes, lawyer_id, lawyer_name, fee, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["client_id"], data["client_name"], data["scheduled_date"], data["scheduled_time"], data.get("case_id", ""), data.get("client_email", ""), data.get("consultation_type", ""), data.get("duration_minutes", ""), data.get("lawyer_id", ""), data.get("lawyer_name", ""), data.get("fee", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM legal_consultations WHERE consultation_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "legal_consultations", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- agreement status ----

@legal_bp.route("/agreements/<int:case_id>/status", methods=["PUT"])
@token_required
def update_agreement_status(case_id: int):
    data = request.get_json(silent=True) or {}
    if "status" not in data:
        raise ValidationError("Missing required field: status")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        existing = conn.execute(
            "SELECT * FROM legal_cases WHERE case_id = ?", (case_id,)
        ).fetchone()
        if not existing:
            raise ValidationError(f"Case {case_id} not found")

        conn.execute(
            "UPDATE legal_cases SET status = ?, updated_at = ? WHERE case_id = ?",
            (data["status"], now, case_id),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM legal_cases WHERE case_id = ?", (case_id,)
        ).fetchone()

    log_activity("update_status", "legal_cases", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- disputes ----

@legal_bp.route("/disputes/<int:case_id>/close", methods=["POST"])
@token_required
def close_dispute(case_id: int):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        existing = conn.execute(
            "SELECT * FROM legal_cases WHERE case_id = ?", (case_id,)
        ).fetchone()
        if not existing:
            raise ValidationError(f"Case {case_id} not found")

        conn.execute(
            "UPDATE legal_cases SET status = 'closed', closed_at = ?, updated_at = ? WHERE case_id = ?",
            (now, now, case_id),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM legal_cases WHERE case_id = ?", (case_id,)
        ).fetchone()

    log_activity("close", "legal_cases", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- search agreements by case number ----

@legal_bp.route("/agreements/search", methods=["GET"])
@token_required
def search_agreements():
    case_number = request.args.get("case_number", "")
    if not case_number:
        raise ValidationError("Missing required query parameter: case_number")

    with get_connection() as conn:
        pattern = f"%{escape_like(case_number)}%"
        rows = conn.execute(
            "SELECT * FROM legal_cases WHERE case_number LIKE ? ORDER BY created_at DESC",
            (pattern,),
        ).fetchall()

    items = [_row_to_dict(r) for r in rows]
    log_activity("search", "legal_cases", user=g.current_user.get("sub"))
    return jsonify({"items": items, "total": len(items)})


# ---- statistics ----

@legal_bp.route("/statistics", methods=["GET"])
@token_required
def get_statistics():
    with get_connection() as conn:
        # Cases by status
        status_rows = conn.execute(
            "SELECT status, COUNT(*) as count FROM legal_cases GROUP BY status"
        ).fetchall()
        by_status = {r[0]: r[1] for r in status_rows}

        # Cases by type
        type_rows = conn.execute(
            "SELECT case_type, COUNT(*) as count FROM legal_cases GROUP BY case_type"
        ).fetchall()
        by_type = {r[0]: r[1] for r in type_rows}

        # Revenue
        revenue_row = conn.execute(
            "SELECT SUM(total_fees), SUM(amount_paid) FROM legal_cases"
        ).fetchone()

        # Cases this month
        first_of_month = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        month_row = conn.execute(
            "SELECT COUNT(*) FROM legal_cases WHERE created_at >= ?",
            (first_of_month,),
        ).fetchone()

    log_activity("view", "legal_statistics", user=g.current_user.get("sub"))
    return jsonify({
        "by_status": by_status,
        "by_type": by_type,
        "total_fees": revenue_row[0] or 0,
        "total_paid": revenue_row[1] or 0,
        "cases_this_month": month_row[0],
        "total_cases": sum(by_status.values()),
    })


# ---- documents ----

@legal_bp.route("/documents", methods=["POST"])
@token_required
def create_document():
    data = request.get_json(silent=True) or {}
    for field in ["case_id", "document_type", "document_name"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO documents
               (source_type, reference_id, reference_type, document_type,
                document_name, file_path, file_content, version_number,
                uploaded_by, notes, upload_date)
               VALUES ('legal', ?, 'case', ?, ?, ?, ?, 1, ?, ?, ?)""",
            (
                str(data["case_id"]),
                data["document_type"],
                data["document_name"],
                data.get("file_path", ""),
                data.get("file_content", ""),
                data.get("created_by", g.current_user.get("sub", "")),
                data.get("notes", ""),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM documents WHERE document_id = ? AND source_type = 'legal'",
            (new_id,),
        ).fetchone()

    log_activity("create", "legal_documents", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@legal_bp.route("/documents", methods=["GET"])
@token_required
def list_documents():
    case_id = request.args.get("case_id")

    conditions = ["source_type = 'legal'"]
    params: list = []
    if case_id:
        conditions.append("reference_id = ? AND reference_type = 'case'")
        params.append(str(case_id))

    where = " WHERE " + " AND ".join(conditions)
    page, per_page, offset = get_pagination_params()
    params_count = list(params)
    params.extend([per_page, offset])

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM documents" + where + " ORDER BY document_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM documents" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "legal_documents", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@legal_bp.route("/documents/<int:document_id>", methods=["GET"])
@token_required
def get_document(document_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM documents WHERE document_id = ? AND source_type = 'legal'",
            (document_id,),
        ).fetchone()
    if not row:
        raise ValidationError(f"Document {document_id} not found")
    log_activity("view", "legal_documents", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- payments ----

@legal_bp.route("/payments", methods=["POST"])
@token_required
def record_payment():
    data = request.get_json(silent=True) or {}
    for field in ["client_id", "amount", "payment_type", "payment_method"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    import uuid
    transaction_ref = f"LEG-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"

    notes_parts = [f"Legal Services Fee - {transaction_ref}"]
    if data.get("consultation_id"):
        notes_parts.append(f"consultation_id={data['consultation_id']}")
    notes_text = "; ".join(notes_parts)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    case_id = data.get("case_id")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO payments
               (source_type, reference_id, reference_type, student_id, customer_email,
                amount, payment_type, payment_method, payment_reference, status,
                receipt_sent, processed_by, notes, created_at)
               VALUES ('legal', ?, 'case', ?, ?, ?, ?, ?, ?, 'completed', 0, ?, ?, ?)""",
            (
                str(case_id) if case_id else None,
                data["client_id"],
                data.get("client_email", ""),
                float(data["amount"]),
                data["payment_type"],
                data["payment_method"],
                transaction_ref,
                data.get("processed_by", g.current_user.get("sub", "")),
                notes_text,
                now,
            ),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        if case_id:
            conn.execute(
                "UPDATE legal_cases SET amount_paid = amount_paid + ?, updated_at = ? WHERE case_id = ?",
                (float(data["amount"]), now, case_id),
            )

        if data.get("consultation_id"):
            conn.execute(
                "UPDATE legal_consultations SET payment_status = 'paid', payment_id = ? WHERE consultation_id = ?",
                (str(new_id), data["consultation_id"]),
            )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM payments WHERE payment_id = ? AND source_type = 'legal'",
            (new_id,),
        ).fetchone()

    log_activity("create", "legal_payments", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@legal_bp.route("/payments", methods=["GET"])
@token_required
def list_payments():
    client_id = request.args.get("client_id")
    case_id = request.args.get("case_id")
    status = request.args.get("status")

    conditions = ["source_type = 'legal'"]
    params: list = []
    if client_id:
        conditions.append("student_id = ?")
        params.append(client_id)
    if case_id:
        conditions.append("reference_id = ? AND reference_type = 'case'")
        params.append(str(case_id))
    if status:
        conditions.append("status = ?")
        params.append(status)

    where = " WHERE " + " AND ".join(conditions)
    page, per_page, offset = get_pagination_params()
    params_count = list(params)
    params.extend([per_page, offset])

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM payments" + where + " ORDER BY payment_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM payments" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "legal_payments", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


# ---- consultations (additional endpoints) ----

@legal_bp.route("/consultations/upcoming", methods=["GET"])
@token_required
def list_upcoming_consultations():
    days = request.args.get("days", 7, type=int)
    today = datetime.now().strftime("%Y-%m-%d")
    from datetime import timedelta
    end_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")

    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM legal_consultations
               WHERE scheduled_date >= ? AND scheduled_date <= ?
               AND status = 'scheduled'
               ORDER BY scheduled_date, scheduled_time""",
            (today, end_date),
        ).fetchall()

    items = [_row_to_dict(r) for r in rows]
    log_activity("view", "legal_consultations_upcoming", user=g.current_user.get("sub"))
    return jsonify({"items": items, "total": len(items)})


@legal_bp.route("/consultations/<int:consultation_id>", methods=["PUT"])
@token_required
def update_consultation(consultation_id: int):
    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No update fields provided")

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM legal_consultations WHERE consultation_id = ?",
            (consultation_id,),
        ).fetchone()
    if not existing:
        raise ValidationError(f"Consultation {consultation_id} not found")

    allowed_fields = [
        "scheduled_date", "scheduled_time", "duration_minutes", "lawyer_id",
        "lawyer_name", "fee", "notes", "status", "consultation_type",
        "client_email", "payment_status",
    ]
    set_parts = []
    params: list = []
    for field in allowed_fields:
        if field in data:
            set_parts.append(f"{field} = ?")
            params.append(data[field])

    if not set_parts:
        raise ValidationError("No valid update fields provided")

    params.append(consultation_id)
    with transaction() as conn:
        conn.execute(
            "UPDATE legal_consultations SET " + ", ".join(set_parts) + " WHERE consultation_id = ?",
            params,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM legal_consultations WHERE consultation_id = ?",
            (consultation_id,),
        ).fetchone()

    log_activity("update", "legal_consultations", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@legal_bp.route("/consultations/<int:consultation_id>", methods=["DELETE"])
@token_required
def cancel_consultation(consultation_id: int):
    data = request.get_json(silent=True) or {}
    reason = data.get("reason", "")

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM legal_consultations WHERE consultation_id = ?",
            (consultation_id,),
        ).fetchone()
    if not existing:
        raise ValidationError(f"Consultation {consultation_id} not found")

    with transaction() as conn:
        conn.execute(
            "UPDATE legal_consultations SET status = 'cancelled', notes = notes || ' | Cancelled: ' || ? WHERE consultation_id = ?",
            (reason, consultation_id),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM legal_consultations WHERE consultation_id = ?",
            (consultation_id,),
        ).fetchone()

    log_activity("cancel", "legal_consultations", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))
