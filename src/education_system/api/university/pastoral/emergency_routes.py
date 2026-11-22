"""Emergency routes: alerts, contacts, incidents.

Alerts are for everyone signed in (raised and closed by admins). A
student's emergency contacts are theirs and the health team's (see
``_health_access``). Incidents are reported by anyone, and read and
updated by staff.
"""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.api.university.pastoral._health_access import (
    deny_unless_may_view_health,
    health_caller,
    is_health_team,
    own_student_id,
)
from education_system.platform.delivery.api.university.auth import (
    admin_required,
    staff_required,
    token_required,
)
from education_system.platform.delivery.api.university.pagination import get_pagination_params, paginated_response
from education_system.platform.delivery.api.university.validators import (
    validate_emergency_alert_create,
    validate_emergency_contact_create,
    validate_incident_create,
)
from education_system.systems.university.infrastructure.exceptions import ValidationError
from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity

logger = logging.getLogger(__name__)

emergency_bp = Blueprint("emergency", __name__, url_prefix="/api/emergency")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- Emergency Alerts ----

@emergency_bp.route("/alerts", methods=["GET"])
@token_required
def list_alerts():
    active_only = request.args.get("active_only", "false").lower() == "true"
    alert_type = request.args.get("alert_type")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if active_only:
            conditions.append("active = 1")
        if alert_type:
            conditions.append("alert_type = ?")
            params.append(alert_type)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        rows = conn.execute(
            "SELECT * FROM emergency_alerts" + where + " ORDER BY created_date DESC",
            params,
        ).fetchall()

    log_activity("view", "emergency_alerts", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@emergency_bp.route("/alerts", methods=["POST"])
@token_required
@admin_required
def create_alert():
    data = request.get_json(silent=True) or {}
    validate_emergency_alert_create(data)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO emergency_alerts
               (alert_title, alert_message, alert_type, created_date, created_by, active)
               VALUES (?, ?, ?, ?, ?, 1)""",
            (
                data["alert_title"],
                data["alert_message"],
                data["alert_type"],
                now,
                g.current_user.get("user_id"),
            ),
        )
        alert_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM emergency_alerts WHERE id = ?", (alert_id,)
        ).fetchone()

    log_activity("create", "emergency_alert", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@emergency_bp.route("/alerts/<int:alert_id>/deactivate", methods=["PUT"])
@token_required
@admin_required
def deactivate_alert(alert_id: int):
    with transaction() as conn:
        conn.execute(
            "UPDATE emergency_alerts SET active = 0 WHERE id = ?", (alert_id,)
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM emergency_alerts WHERE id = ?", (alert_id,)
        ).fetchone()

    if not row:
        raise ValidationError(f"Alert {alert_id} not found")

    log_activity("update", "emergency_alert_deactivate", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Emergency Contacts ----
#
# One store and one set of rules shared with the GUI and CLI:
# ``domains/health/domain/health/services/contacts`` (list_contacts /
# save_contact / delete_contact / set_primary). It checks access, writes the
# audit entries and keeps exactly one primary contact per student.


def _contacts():
    from education_system.systems.university.domains.health.domain.health.services import (
        contacts,
    )
    return contacts


def _contact_owner(contact_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT student_id FROM emergency_contacts WHERE id = ?", (contact_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Emergency contact {contact_id} not found")
    return row[0]


def _contact_call(fn, *args):
    """Run a contacts-service call, mapping its refusals to API errors."""
    try:
        return fn(*args), None
    except PermissionError as exc:
        return None, (jsonify({"error": "Forbidden", "message": str(exc), "status": 403}), 403)
    except ValueError as exc:
        raise ValidationError(str(exc)) from None


@emergency_bp.route("/contacts", methods=["GET"])
@token_required
def list_contacts():
    student_id = request.args.get("student_id") or own_student_id()
    if not student_id:
        raise ValidationError("student_id query parameter is required")
    # The service checks access and writes the (fail-closed) audit entry.
    items, denial = _contact_call(_contacts().list_contacts, health_caller(), student_id)
    if denial is not None:
        return denial

    log_activity("view", "emergency_contacts", user=g.current_user.get("sub"))
    return jsonify({"items": items, "total": len(items)})


@emergency_bp.route("/contacts", methods=["POST"])
@token_required
def create_contact():
    data = request.get_json(silent=True) or {}
    if not is_health_team():
        own = own_student_id()
        if own is None or str(data.get("student_id") or own) != own:
            return jsonify({"error": "Forbidden", "status": 403,
                            "message": "You can only add your own emergency contacts"}), 403
        data["student_id"] = own
    validate_emergency_contact_create(data)

    contact_id, denial = _contact_call(_contacts().save_contact, health_caller(),
                                       data["student_id"], data)
    if denial is not None:
        return denial

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM emergency_contacts WHERE id = ?", (contact_id,)
        ).fetchone()

    log_activity("create", "emergency_contact", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@emergency_bp.route("/contacts/<int:contact_id>", methods=["PUT"])
@token_required
def update_contact(contact_id: int):
    """Change one contact (all fields are sent, as on the GUI form)."""
    student_id = _contact_owner(contact_id)
    denial = deny_unless_may_view_health(student_id, "emergency_contacts", record_id=contact_id)
    if denial is not None:
        return denial
    data = request.get_json(silent=True) or {}
    _saved, denial = _contact_call(_contacts().save_contact, health_caller(), student_id, data,
                                   contact_id)
    if denial is not None:
        return denial
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM emergency_contacts WHERE id = ?", (contact_id,)
        ).fetchone()
    log_activity("update", "emergency_contact", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@emergency_bp.route("/contacts/<int:contact_id>", methods=["DELETE"])
@token_required
def delete_contact(contact_id: int):
    student_id = _contact_owner(contact_id)
    denial = deny_unless_may_view_health(student_id, "emergency_contacts", record_id=contact_id)
    if denial is not None:
        return denial
    _done, denial = _contact_call(_contacts().delete_contact, health_caller(), student_id,
                                  contact_id)
    if denial is not None:
        return denial
    log_activity("delete", "emergency_contact", user=g.current_user.get("sub"))
    return jsonify({"message": "Emergency contact deleted", "id": contact_id})


@emergency_bp.route("/contacts/<int:contact_id>/primary", methods=["PUT"])
@token_required
def make_primary_contact(contact_id: int):
    student_id = _contact_owner(contact_id)
    denial = deny_unless_may_view_health(student_id, "emergency_contacts", record_id=contact_id)
    if denial is not None:
        return denial
    _done, denial = _contact_call(_contacts().set_primary, health_caller(), student_id,
                                  contact_id)
    if denial is not None:
        return denial
    log_activity("update", "emergency_contact_primary", user=g.current_user.get("sub"))
    return jsonify({"message": "Primary emergency contact set", "id": contact_id})


# ---- Incidents ----

@emergency_bp.route("/incidents", methods=["GET"])
@token_required
@staff_required
def list_incidents():
    status = request.args.get("status")
    severity = request.args.get("severity")
    incident_type = request.args.get("incident_type")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if severity:
            conditions.append("severity = ?")
            params.append(severity)
        if incident_type:
            conditions.append("incident_type = ?")
            params.append(incident_type)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM incidents" + where + " ORDER BY incident_datetime DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM incidents" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "incidents", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@emergency_bp.route("/incidents", methods=["POST"])
@token_required
def create_incident():
    data = request.get_json(silent=True) or {}
    validate_incident_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO incidents
               (incident_type, severity, description, location,
                incident_datetime, reported_by_staff_id, witnesses,
                immediate_action_taken, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open')""",
            (
                data["incident_type"],
                data.get("severity", "low"),
                data["description"],
                data.get("location"),
                data["incident_datetime"],
                data.get("reported_by_staff_id"),
                data.get("witnesses"),
                data.get("immediate_action_taken"),
            ),
        )
        iid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM incidents WHERE id = ?", (iid,)
        ).fetchone()

    log_activity("create", "incident", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@emergency_bp.route("/incidents/<int:incident_id>", methods=["PUT"])
@token_required
@staff_required
def update_incident(incident_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM incidents WHERE id = ?", (incident_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Incident {incident_id} not found")

    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No fields provided for update")

    set_clauses = []
    values = []
    allowed = [
        "status", "severity", "resolution", "resolved_by_staff_id",
        "resolved_datetime", "follow_up_notes", "follow_up_completed",
    ]
    for field in allowed:
        if field in data:
            set_clauses.append(field + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    values.append(incident_id)
    with transaction() as conn:
        conn.execute(
            "UPDATE incidents SET " + ", ".join(set_clauses) + " WHERE id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM incidents WHERE id = ?", (incident_id,)
        ).fetchone()

    log_activity("update", "incident", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))
