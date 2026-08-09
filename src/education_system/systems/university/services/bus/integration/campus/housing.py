"""Focused components extracted from the legacy integration bus."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.services.events.in_process import (
    EVENT_CASE_OPENED,
    EVENT_CERT_CHANGED,
    EVENT_CHARGE_RAISED,
    EVENT_COURSE_CHANGED,
    EVENT_ENROLMENT_CHANGED,
    EVENT_EXAM_CHANGED,
    EVENT_INCIDENT_LOGGED,
    EVENT_MODULE_SCHEDULE_CHANGED,
    EVENT_SELECTION_CHANGED,
    EVENT_STAFF_AVAILABILITY_CHANGED,
    EVENT_TERM_CHANGED,
    publish,
    subscribe,
)

logger = logging.getLogger(__name__)
from education_system.systems.university.services.bus.integration.finance.reporting import _admin_user_id
from education_system.systems.university.services.bus.integration.finance.subscribers import _REFUND_PREVIEW_SQL
from education_system.systems.university.services.bus.integration.publishing import log_and_publish

def publish_housing_move_out(assignment_id: int, *, student_id: str,
                              room_id: str, building_id: str | None = None,
                              actual_move_out_date: str,
                              new_status: str) -> None:
    """Publish a housing move-out / termination.

    Origin: ``housing.assignments.update_assignment_status`` when
    new_status ∈ {'Terminated', 'Expired'}. Subscribers (this
    module) queue a deposit refund preview row and email the
    inspector to schedule a checkout walk-through.
    """
    log_and_publish(
        EVENT_INCIDENT_LOGGED,
        source="housing",
        kind="housing_move_out",
        severity="low",
        assignment_id=int(assignment_id),
        student_id=str(student_id),
        room_id=str(room_id),
        building_id=str(building_id) if building_id else None,
        actual_move_out_date=actual_move_out_date,
        new_status=new_status,
    )

def _on_housing_move_out(**payload: Any) -> None:
    if payload.get("kind") != "housing_move_out":
        return
    student_id = payload.get("student_id")
    if not student_id:
        return

    # Queue a refund preview using whatever deposit can be looked up.
    deposit = _lookup_housing_deposit(payload.get("assignment_id"))
    try:
        with transaction() as conn:
            conn.executescript(_REFUND_PREVIEW_SQL)
            conn.execute(
                "INSERT INTO refund_previews "
                "(student_id, course_code, amount, reason, status) "
                "VALUES (?, ?, ?, ?, 'pending')",
                (str(student_id),
                 f"housing:{payload.get('room_id')}",
                 float(deposit),
                 f"Housing move-out ({payload.get('new_status')})"),
            )
            conn.commit()
    except Exception as exc:
        logger.debug("housing→refund_previews failed: %s", exc)

    # Email the inspector (first user with an inspections role; fallback admin).
    try:
        from education_system.systems.university.services.bus.email_bus import (
            send_templated,
        )
        recipient = _housing_inspector_user_id() or _admin_user_id() or "admin"
        send_templated(
            recipient, "hs.incident.logged",
            {
                "incident_id": f"checkout:{payload.get('assignment_id')}",
                "severity": "low",
                "location": f"room {payload.get('room_id')}",
            },
            related_to=f"housing_assignment:{payload.get('assignment_id')}",
            force=True,
        )
    except Exception as exc:
        logger.debug("housing inspector email failed: %s", exc)

def _lookup_housing_deposit(assignment_id: Any) -> float:
    if assignment_id is None:
        return 0.0
    try:
        with get_connection() as conn:
            for sql in (
                "SELECT deposit_amount FROM housing_assignments WHERE assignment_id = ?",
                "SELECT amount FROM housing_payments "
                "WHERE assignment_id = ? AND LOWER(payment_type) = 'deposit' "
                "ORDER BY payment_id DESC LIMIT 1",
            ):
                try:
                    row = conn.execute(sql, (assignment_id,)).fetchone()
                    if row and row[0] is not None:
                        return float(row[0])
                except Exception:
                    continue
    except Exception:
        pass
    return 0.0

def _housing_inspector_user_id() -> str | None:
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT user_id FROM users "
                "WHERE LOWER(role) IN ('housing_inspector', 'inspector', "
                "                      'housing_manager') "
                "AND email IS NOT NULL LIMIT 1"
            ).fetchone()
            return str(row[0]) if row else None
    except Exception:
        return None
