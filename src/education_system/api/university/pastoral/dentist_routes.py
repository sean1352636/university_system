"""Dental services routes: patients, appointments, treatments, and records.

Dental records are health data. The clinic team (dentists and the rest of
the health team, see ``_health_access``) works with every patient; anyone
else reaches only their own patient record - matched on the username or
local account id the clinic stores in ``dentist_patients.user_id`` - and may
book, cancel and pay for their own appointments. Lists, search, schedules
and statistics are for the clinic team.
"""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.api.university.pastoral._health_access import (
    audit_health_view,
    deny_unless_health_team,
    health_caller,
    is_health_team,
)
from education_system.platform.delivery.api.university.auth import token_required
from education_system.platform.delivery.api.university.pagination import get_pagination_params, paginated_response
from education_system.systems.university.infrastructure.exceptions import ValidationError
from education_system.systems.university.infrastructure.sql_safety import escape_like
from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity

logger = logging.getLogger(__name__)

dentist_bp = Blueprint("dentist", __name__, url_prefix="/api/dentist")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


_FORBIDDEN = {"error": "Forbidden", "status": 403}


def _own_identities() -> set[str]:
    """The values ``dentist_patients.user_id`` holds for the caller.

    The GUI stores the username, the CLI the local ``users.id``; the token's
    own ``user_id`` may be the shared auth.db id, so the local one is looked
    up by username.
    """
    who = health_caller()
    if who is None:
        return set()
    from education_system.systems.university.infrastructure.auth.session_user import (
        resolve_local_identity,
    )
    local_id, student_id = resolve_local_identity(who.username)
    return {str(v) for v in (who.username, local_id, student_id) if v not in (None, "")}


def _own_patient_ids(conn) -> list[int]:
    mine = sorted(_own_identities())
    if not mine:
        return []
    marks = ",".join("?" * len(mine))
    return [r[0] for r in conn.execute(
        f"SELECT patient_id FROM dentist_patients WHERE user_id IN ({marks})",  # nosec B608
        mine)]


def _deny_unless_patient_access(patient_id, area: str, *, record_id=None, conn=None):
    """403 unless the caller is the clinic team or ``patient_id`` is their own; audits the view."""
    if patient_id is None:
        return jsonify({**_FORBIDDEN, "message": "No patient on this record"}), 403
    if conn is None:
        with get_connection() as own_conn:
            row = own_conn.execute("SELECT user_id FROM dentist_patients WHERE patient_id = ?",
                                   (patient_id,)).fetchone()
    else:
        row = conn.execute("SELECT user_id FROM dentist_patients WHERE patient_id = ?",
                           (patient_id,)).fetchone()
    owner = None if row is None else row[0]
    if not is_health_team() and (owner is None or str(owner) not in _own_identities()):
        return jsonify({**_FORBIDDEN,
                        "message": "You can only see your own dental records"}), 403
    return audit_health_view(f"dentist_{area}", student_id=owner,
                             record_id=record_id if record_id is not None else patient_id)


# ---- patients ----

@dentist_bp.route("/patients", methods=["GET"])
@token_required
def list_patients():
    search = request.args.get("search")
    user_id = request.args.get("user_id")
    if not is_health_team():
        # Outside the clinic team: your own patient record(s) only.
        mine = _own_identities()
        if search or (user_id and str(user_id) not in mine):
            return deny_unless_health_team("list or search dental patients")
        with get_connection() as conn:
            ids = _own_patient_ids(conn)
            marks = ",".join("?" * len(ids)) or "NULL"
            rows = conn.execute(
                f"SELECT * FROM dentist_patients WHERE patient_id IN ({marks})",  # nosec B608
                ids).fetchall()
        denial = audit_health_view("dentist_patients", student_id=health_caller().username)
        if denial is not None:
            return denial
        items = [_row_to_dict(r) for r in rows]
        return jsonify({"items": items, "total": len(items)})

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM dentist_patients WHERE user_name LIKE ? OR user_email LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            denial = audit_health_view("dentist_patients")
            if denial is not None:
                return denial
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM dentist_patients" + where + " ORDER BY patient_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM dentist_patients" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    denial = audit_health_view("dentist_patients", student_id=user_id)
    if denial is not None:
        return denial
    log_activity("view", "dentist_patients", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@dentist_bp.route("/patients/<int:patient_id>", methods=["GET"])
@token_required
def get_patient(patient_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM dentist_patients WHERE patient_id = ?", (patient_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"patients {patient_id} not found")
    denial = _deny_unless_patient_access(patient_id, "patient")
    if denial is not None:
        return denial
    log_activity("view", "dentist_patients", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@dentist_bp.route("/patients", methods=["POST"])
@token_required
def create_patient():
    data = request.get_json(silent=True) or {}
    if not is_health_team():
        # Registering yourself with the clinic: the record is keyed on your username.
        who = health_caller()
        if data.get("user_id") and str(data["user_id"]) not in _own_identities():
            return jsonify({**_FORBIDDEN,
                            "message": "You can only register yourself with the clinic"}), 403
        data["user_id"] = who.username if who is not None else data.get("user_id")
    for field in ["user_id", "user_name", "user_email"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO dentist_patients
               (user_id, user_name, user_email, user_phone, date_of_birth, address, emergency_contact, emergency_phone, allergies, insurance_provider, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["user_id"], data["user_name"], data["user_email"], data.get("user_phone", ""), data.get("date_of_birth", ""), data.get("address", ""), data.get("emergency_contact", ""), data.get("emergency_phone", ""), data.get("allergies", ""), data.get("insurance_provider", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM dentist_patients WHERE patient_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "dentist_patients", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- appointments ----

@dentist_bp.route("/appointments", methods=["GET"])
@token_required
def list_appointments():
    search = request.args.get("search")
    patient_id = request.args.get("patient_id")
    status = request.args.get("status")
    team = is_health_team()
    if search and not team:
        return deny_unless_health_team("search dental appointments")

    with get_connection() as conn:
        own_ids = None if team else _own_patient_ids(conn)
        if own_ids is not None and patient_id and int(patient_id) not in own_ids:
            return jsonify({**_FORBIDDEN,
                            "message": "You can only see your own appointments"}), 403
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM dentist_appointments WHERE dentist_name LIKE ?",
                (pattern,),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if own_ids is not None and not patient_id:
            conditions.append("patient_id IN (" + (",".join("?" * len(own_ids)) or "NULL") + ")")
            params.extend(own_ids)
        if patient_id:
            conditions.append("patient_id = ?")
            params.append(patient_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM dentist_appointments" + where + " ORDER BY appointment_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM dentist_appointments" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    denial = audit_health_view("dentist_appointments")
    if denial is not None:
        return denial
    log_activity("view", "dentist_appointments", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@dentist_bp.route("/appointments/<int:appointment_id>", methods=["GET"])
@token_required
def get_appointment(appointment_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM dentist_appointments WHERE appointment_id = ?", (appointment_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"appointments {appointment_id} not found")
    denial = _deny_unless_patient_access(row["patient_id"], "appointment",
                                         record_id=appointment_id)
    if denial is not None:
        return denial
    log_activity("view", "dentist_appointments", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@dentist_bp.route("/appointments", methods=["POST"])
@token_required
def create_appointment():
    data = request.get_json(silent=True) or {}
    for field in ["patient_id", "dentist_id", "dentist_name", "appointment_date", "appointment_time"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")
    denial = _deny_unless_patient_access(data["patient_id"], "appointment_booking")
    if denial is not None:
        return denial
    if not is_health_team():
        data.pop("notes", None)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        taken = conn.execute(
            """SELECT 1 FROM dentist_appointments
               WHERE dentist_id = ? AND appointment_date = ? AND appointment_time = ?
               AND COALESCE(status, 'scheduled') NOT IN ('cancelled', 'no_show')""",
            (data["dentist_id"], data["appointment_date"], data["appointment_time"]),
        ).fetchone()
        if taken:
            raise ValidationError("That slot is already booked - choose another time")
        conn.execute(
            """INSERT INTO dentist_appointments
               (patient_id, dentist_id, dentist_name, appointment_date, appointment_time, duration_minutes, treatment_type, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["patient_id"], data["dentist_id"], data["dentist_name"], data["appointment_date"], data["appointment_time"], data.get("duration_minutes", 30), data.get("treatment_type", ""), data.get("notes", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM dentist_appointments WHERE appointment_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "dentist_appointments", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- treatments ----

@dentist_bp.route("/treatments", methods=["GET"])
@token_required
def list_treatments():
    search = request.args.get("search")
    patient_id = request.args.get("patient_id")
    treatment_type = request.args.get("treatment_type")
    denial = deny_unless_health_team("list dental treatments")
    if denial is not None:
        return denial

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM dentist_treatments WHERE description LIKE ?",
                (pattern,),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if patient_id:
            conditions.append("patient_id = ?")
            params.append(patient_id)
        if treatment_type:
            conditions.append("treatment_type = ?")
            params.append(treatment_type)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM dentist_treatments" + where + " ORDER BY treatment_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM dentist_treatments" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    denial = audit_health_view("dentist_treatments")
    if denial is not None:
        return denial
    log_activity("view", "dentist_treatments", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@dentist_bp.route("/treatments/<int:treatment_id>", methods=["GET"])
@token_required
def get_treatment(treatment_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM dentist_treatments WHERE treatment_id = ?", (treatment_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"treatments {treatment_id} not found")
    denial = _deny_unless_patient_access(row["patient_id"], "treatment", record_id=treatment_id)
    if denial is not None:
        return denial
    log_activity("view", "dentist_treatments", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@dentist_bp.route("/treatments", methods=["POST"])
@token_required
def create_treatment():
    denial = deny_unless_health_team("record dental treatments")
    if denial is not None:
        return denial
    data = request.get_json(silent=True) or {}
    for field in ["appointment_id", "patient_id", "dentist_id", "treatment_type", "treatment_date"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO dentist_treatments
               (appointment_id, patient_id, dentist_id, treatment_type, treatment_date, dentist_name, tooth_number, description, fee, payment_status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["appointment_id"], data["patient_id"], data["dentist_id"], data["treatment_type"], data["treatment_date"], data.get("dentist_name", ""), data.get("tooth_number", ""), data.get("description", ""), data.get("fee", ""), data.get("payment_status", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM dentist_treatments WHERE treatment_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "dentist_treatments", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- appointment status ----

@dentist_bp.route("/appointments/<int:appointment_id>/status", methods=["PUT"])
@token_required
def update_appointment_status(appointment_id: int):
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    valid_statuses = ["scheduled", "confirmed", "in_progress", "completed", "cancelled", "no_show"]
    if not status or status not in valid_statuses:
        raise ValidationError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM dentist_appointments WHERE appointment_id = ?", (appointment_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Appointment {appointment_id} not found")
    denial = _deny_unless_patient_access(row["patient_id"], "appointment",
                                         record_id=appointment_id)
    if denial is not None:
        return denial
    if not is_health_team():
        # A patient may cancel their own booking, nothing else.
        if status != "cancelled":
            return jsonify({**_FORBIDDEN,
                            "message": "You can only cancel your own appointment"}), 403
        if str(row["status"] or "scheduled") not in ("scheduled", "confirmed"):
            raise ValidationError(f"This appointment is {row['status']} and cannot be cancelled")

    with transaction() as conn:
        conn.execute(
            "UPDATE dentist_appointments SET status = ? WHERE appointment_id = ?",
            (status, appointment_id),
        )
        if status == "completed":
            appt = conn.execute(
                "SELECT patient_id, appointment_date FROM dentist_appointments WHERE appointment_id = ?",
                (appointment_id,),
            ).fetchone()
            if appt:
                conn.execute(
                    "UPDATE dentist_patients SET last_visit = ? WHERE patient_id = ?",
                    (appt[1], appt[0]),
                )

    with get_connection() as conn:
        updated = conn.execute(
            "SELECT * FROM dentist_appointments WHERE appointment_id = ?", (appointment_id,)
        ).fetchone()

    log_activity("update_status", "dentist_appointments", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(updated))


# ---- today's appointments ----

@dentist_bp.route("/appointments/today", methods=["GET"])
@token_required
def get_todays_appointments():
    denial = deny_unless_health_team("see the clinic day list")
    if denial is not None:
        return denial
    today = datetime.now().strftime("%Y-%m-%d")
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT a.*, p.user_name AS patient_name, p.user_phone
               FROM dentist_appointments a
               JOIN dentist_patients p ON a.patient_id = p.patient_id
               WHERE a.appointment_date = ?
               ORDER BY a.appointment_time""",
            (today,),
        ).fetchall()

    log_activity("view", "dentist_appointments_today", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- dentist schedule ----

@dentist_bp.route("/dentists/<dentist_id>/schedule", methods=["GET"])
@token_required
def get_dentist_schedule(dentist_id: str):
    denial = deny_unless_health_team("see a dentist's schedule")
    if denial is not None:
        return denial
    date = request.args.get("date")
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    with get_connection() as conn:
        rows = conn.execute(
            """SELECT a.*, p.user_name AS patient_name
               FROM dentist_appointments a
               JOIN dentist_patients p ON a.patient_id = p.patient_id
               WHERE a.dentist_id = ? AND a.appointment_date = ?
               AND a.status NOT IN ('cancelled', 'no_show')
               ORDER BY a.appointment_time""",
            (dentist_id, date),
        ).fetchall()

    log_activity("view", "dentist_schedule", user=g.current_user.get("sub"))
    return jsonify({"dentist_id": dentist_id, "date": date, "items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- available slots ----

APPOINTMENT_SLOTS = [
    "09:00", "09:30", "10:00", "10:30", "11:00", "11:30",
    "13:00", "13:30", "14:00", "14:30", "15:00", "15:30", "16:00",
]

@dentist_bp.route("/dentists/<dentist_id>/available-slots", methods=["GET"])
@token_required
def get_available_slots(dentist_id: str):
    date = request.args.get("date")
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    with get_connection() as conn:
        rows = conn.execute(
            """SELECT appointment_time FROM dentist_appointments
               WHERE dentist_id = ? AND appointment_date = ?
               AND status NOT IN ('cancelled', 'no_show')""",
            (dentist_id, date),
        ).fetchall()
    booked = {r[0] for r in rows}
    available = [slot for slot in APPOINTMENT_SLOTS if slot not in booked]

    log_activity("view", "dentist_available_slots", user=g.current_user.get("sub"))
    return jsonify({"dentist_id": dentist_id, "date": date, "available_slots": available})


# ---- update patient ----

@dentist_bp.route("/patients/<int:patient_id>", methods=["PUT"])
@token_required
def update_patient(patient_id: int):
    denial = deny_unless_health_team("update a dental patient record")
    if denial is not None:
        return denial
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM dentist_patients WHERE patient_id = ?", (patient_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Patient {patient_id} not found")

    data = request.get_json(silent=True) or {}
    set_parts: list[str] = []
    values: list = []
    for col in (
        "address", "allergies", "emergency_contact", "emergency_phone",
        "insurance_number", "insurance_provider", "medical_history",
        "notes", "user_phone",
    ):
        if col in data:
            set_parts.append(f"{col} = ?")
            values.append(data[col])
    if not set_parts:
        raise ValidationError("No valid fields to update")

    set_clause = ", ".join(set_parts)
    values.append(patient_id)

    with transaction() as conn:
        conn.execute(
            f"UPDATE dentist_patients SET {set_clause} WHERE patient_id = ?",
            values,
        )

    with get_connection() as conn:
        updated = conn.execute(
            "SELECT * FROM dentist_patients WHERE patient_id = ?", (patient_id,)
        ).fetchone()

    log_activity("update", "dentist_patients", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(updated))


# ---- search patients ----

@dentist_bp.route("/patients/search", methods=["GET"])
@token_required
def search_patients():
    denial = deny_unless_health_team("search dental patients")
    if denial is not None:
        return denial
    q = request.args.get("q", "")
    if not q:
        raise ValidationError("Missing search query parameter 'q'")

    pattern = f"%{escape_like(q)}%"
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM dentist_patients
               WHERE patient_number LIKE ? OR user_name LIKE ? OR user_email LIKE ?
               ORDER BY user_name""",
            (pattern, pattern, pattern),
        ).fetchall()

    denial = audit_health_view("dentist_patient_search")
    if denial is not None:
        return denial
    log_activity("search", "dentist_patients", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- patient treatment history ----

@dentist_bp.route("/patients/<int:patient_id>/treatments", methods=["GET"])
@token_required
def get_patient_treatments(patient_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT patient_id FROM dentist_patients WHERE patient_id = ?", (patient_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Patient {patient_id} not found")
    denial = _deny_unless_patient_access(patient_id, "patient_treatments")
    if denial is not None:
        return denial

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM dentist_treatments WHERE patient_id = ? ORDER BY treatment_date DESC",
            (patient_id,),
        ).fetchall()

    log_activity("view", "dentist_patient_treatments", user=g.current_user.get("sub"))
    return jsonify({"patient_id": patient_id, "items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- prescriptions ----

@dentist_bp.route("/prescriptions", methods=["POST"])
@token_required
def create_prescription():
    denial = deny_unless_health_team("prescribe")
    if denial is not None:
        return denial
    data = request.get_json(silent=True) or {}
    for field in ["patient_id", "dentist_id", "dentist_name", "medication", "dosage", "frequency", "duration"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    prescribed_date = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO dentist_prescriptions
               (patient_id, dentist_id, dentist_name, treatment_id,
                medication, dosage, frequency, duration, instructions, prescribed_date, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["patient_id"], data["dentist_id"], data["dentist_name"],
                data.get("treatment_id"), data["medication"], data["dosage"],
                data["frequency"], data["duration"], data.get("instructions", ""),
                prescribed_date, now,
            ),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM dentist_prescriptions WHERE prescription_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "dentist_prescriptions", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@dentist_bp.route("/patients/<int:patient_id>/prescriptions", methods=["GET"])
@token_required
def get_patient_prescriptions(patient_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT patient_id FROM dentist_patients WHERE patient_id = ?", (patient_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Patient {patient_id} not found")
    denial = _deny_unless_patient_access(patient_id, "patient_prescriptions")
    if denial is not None:
        return denial

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM dentist_prescriptions WHERE patient_id = ? ORDER BY prescribed_date DESC",
            (patient_id,),
        ).fetchall()

    log_activity("view", "dentist_patient_prescriptions", user=g.current_user.get("sub"))
    return jsonify({"patient_id": patient_id, "items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- payments ----

@dentist_bp.route("/payments", methods=["POST"])
@token_required
def record_payment():
    """Take a payment for the clinic.

    Goes through the clinic's one payment path
    (``dentist.services.TransactionManager.record_payment``), which writes the
    clinic transaction and the central Finance ``payments`` row together and
    posts it to the ledger - the same path the CLI and GUI use. A patient may
    pay for their own treatment; the clinic team for anyone.
    """
    data = request.get_json(silent=True) or {}
    for field in ["user_id", "patient_id", "amount", "payment_method"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")
    denial = _deny_unless_patient_access(data["patient_id"], "payment")
    if denial is not None:
        return denial
    try:
        amount = float(data["amount"])
    except (TypeError, ValueError):
        raise ValidationError("amount must be a number") from None
    if amount <= 0:
        raise ValidationError("amount must be more than zero")

    from education_system.systems.university.domains.health.domain.health.dentist.services import (
        TransactionManager,
    )
    processed_by = g.current_user.get("sub")
    if is_health_team():
        processed_by = data.get("processed_by") or processed_by
    result = TransactionManager.record_payment(
        user_id=str(data["user_id"]), patient_id=data["patient_id"], amount=amount,
        payment_method=data["payment_method"],
        transaction_type=data.get("transaction_type", "treatment"),
        treatment_id=data.get("treatment_id"), processed_by=processed_by,
        description=data.get("description"))
    if not result:
        raise ValidationError("The payment could not be recorded")

    log_activity("create", "dentist_payment", user=g.current_user.get("sub"))
    return jsonify(result), 201


@dentist_bp.route("/patients/<int:patient_id>/payments", methods=["GET"])
@token_required
def get_patient_payments(patient_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT patient_id FROM dentist_patients WHERE patient_id = ?", (patient_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Patient {patient_id} not found")
    denial = _deny_unless_patient_access(patient_id, "patient_payments")
    if denial is not None:
        return denial

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM transactions WHERE source_type = 'dentist' AND customer_id = ? ORDER BY created_at DESC",
            (patient_id,),
        ).fetchall()

    log_activity("view", "dentist_patient_payments", user=g.current_user.get("sub"))
    return jsonify({"patient_id": patient_id, "items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- statistics ----

@dentist_bp.route("/statistics", methods=["GET"])
@token_required
def get_statistics():
    denial = deny_unless_health_team("see clinic statistics")
    if denial is not None:
        return denial
    date = request.args.get("date")
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    with get_connection() as conn:
        total_appointments = conn.execute(
            "SELECT COUNT(*) FROM dentist_appointments WHERE appointment_date = ?",
            (date,),
        ).fetchone()[0]

        completed = conn.execute(
            "SELECT COUNT(*) FROM dentist_appointments WHERE appointment_date = ? AND status = 'completed'",
            (date,),
        ).fetchone()[0]

        cancelled = conn.execute(
            "SELECT COUNT(*) FROM dentist_appointments WHERE appointment_date = ? AND status = 'cancelled'",
            (date,),
        ).fetchone()[0]

        no_shows = conn.execute(
            "SELECT COUNT(*) FROM dentist_appointments WHERE appointment_date = ? AND status = 'no_show'",
            (date,),
        ).fetchone()[0]

        revenue = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE source_type = 'dentist' AND DATE(created_at) = ?",
            (date,),
        ).fetchone()[0]

        treatments_performed = conn.execute(
            "SELECT COUNT(*) FROM dentist_treatments WHERE treatment_date = ?",
            (date,),
        ).fetchone()[0]

        total_patients = conn.execute(
            "SELECT COUNT(*) FROM dentist_patients",
        ).fetchone()[0]

        pending_payments = conn.execute(
            "SELECT COUNT(*) FROM dentist_treatments WHERE payment_status = 'pending'",
        ).fetchone()[0]

    log_activity("view", "dentist_statistics", user=g.current_user.get("sub"))
    return jsonify({
        "date": date,
        "total_appointments": total_appointments,
        "completed_appointments": completed,
        "cancelled_appointments": cancelled,
        "no_show_appointments": no_shows,
        "treatments_performed": treatments_performed,
        "revenue": revenue,
        "total_patients": total_patients,
        "pending_payments": pending_payments,
    })
