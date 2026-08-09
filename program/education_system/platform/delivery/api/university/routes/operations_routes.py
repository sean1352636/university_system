"""Authorized university operational health and event-delivery controls."""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from education_system.platform.delivery.api.university.auth import (
    admin_required,
    token_required,
)
from education_system.platform.integrations.external.cross_system_bus import (
    abandon_failed_delivery,
    list_failed_deliveries,
    retry_failed_delivery,
)
from education_system.systems.university.infrastructure.activity_logger import (
    log_activity,
)
from education_system.systems.university.services.degraded_states import (
    list_degraded_states,
    resolve_degraded_state,
)
from education_system.systems.university.services.operational_health import (
    health_report,
)

operations_bp = Blueprint(
    "university_operations",
    __name__,
    url_prefix="/api/operations",
)


@operations_bp.get("/health")
@token_required
@admin_required
def get_operational_health():
    report = health_report()
    status_code = 503 if report["status"] == "failed" else 200
    return jsonify(report), status_code


@operations_bp.get("/degraded-states")
@token_required
@admin_required
def get_degraded_states():
    return jsonify({"items": list_degraded_states()})


@operations_bp.post("/degraded-states/<int:state_id>/resolve")
@token_required
@admin_required
def resolve_state(state_id: int):
    data = request.get_json(silent=True) or {}
    changed = resolve_degraded_state(
        state_id,
        resolved_by=str(g.current_user.get("sub") or ""),
        notes=str(data.get("notes", "")),
    )
    return jsonify({"resolved": changed})


@operations_bp.get("/event-deliveries")
@token_required
@admin_required
def event_deliveries():
    exhausted = request.args.get("dead_letters", "").lower() in {"1", "true"}
    return jsonify({
        "items": list_failed_deliveries(
            consumer_system=request.args.get("consumer_system"),
            exhausted_only=exhausted,
        )
    })


def _event_identity() -> tuple[str, str, str]:
    data = request.get_json(silent=True) or {}
    values = (
        str(data.get("event_id", "")),
        str(data.get("consumer_system", "")),
        str(data.get("consumer_handler", "")),
    )
    if not all(values):
        raise ValueError(
            "event_id, consumer_system and consumer_handler are required"
        )
    return values


@operations_bp.post("/event-deliveries/retry")
@token_required
@admin_required
def retry_event_delivery():
    event_id, consumer, handler = _event_identity()
    changed = retry_failed_delivery(event_id, consumer, handler)
    log_activity(
        "retry",
        "cross_system_event_delivery",
        user=g.current_user.get("sub"),
        details={"event_id": event_id, "consumer": consumer, "handler": handler},
    )
    return jsonify({"queued": changed})


@operations_bp.post("/event-deliveries/abandon")
@token_required
@admin_required
def abandon_event_delivery():
    data = request.get_json(silent=True) or {}
    event_id, consumer, handler = _event_identity()
    reason = str(data.get("reason", ""))
    changed = abandon_failed_delivery(
        event_id, consumer, handler, reason=reason
    )
    log_activity(
        "abandon",
        "cross_system_event_delivery",
        user=g.current_user.get("sub"),
        details={
            "event_id": event_id,
            "consumer": consumer,
            "handler": handler,
            "reason": reason,
        },
    )
    return jsonify({"abandoned": changed})


__all__ = ["operations_bp"]
