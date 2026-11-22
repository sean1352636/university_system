"""The linked-platform API: learners, transfers, systems and events.

Routes (mounted at ``/api/v1``):

========  =====================================  =====================================
Method    Path                                   Gate
========  =====================================  =====================================
GET       /learners/<journey_id>                 learner360.view in a system holding them
GET       /learners/<journey_id>/history         learner360.view  (same scope)
GET       /learners/<journey_id>/progression     learner360.view  (same scope)
GET       /learners/<journey_id>/qualifications  learner360.view  (same scope)
GET       /learners/<journey_id>/enrolments      learner360.view  (same scope)
POST      /progression                           transfer.approve at the source
POST      /transfers                             transfer.approve at source or destination
GET       /transfers                             transfer.view  (scoped to your systems)
GET       /transfers/<id>                        transfer.view at either end
GET       /transfers/<id>/events                 transfer.view at either end
POST      /transfers/<id>/approve                transfer.approve at the source
POST      /transfers/<id>/reject                 transfer.approve at the destination
POST      /transfers/<id>/acknowledge            transfer.acknowledge at the destination
POST      /transfers/<id>/complete               transfer.acknowledge at the destination
GET       /tasks                                 any signed-in user (their own tasks)
GET       /systems                               any signed-in user; ops detail needs events.view
GET       /events                                events.view  (scoped; payloads superadmin-only)
GET       /events/dead-letters                   superadmin
POST      /events/dead-letters/retry             superadmin
POST      /events/dead-letters/abandon           superadmin
========  =====================================  =====================================

These are platform routes, not system routes: every one of them spans
systems by construction, which is why they live here and not under any
``systems/<system>/interfaces/api``. Authorisation is by the cross-system
permissions in ``role_manager``: the decorator turns away users who hold
the permission nowhere, and each handler then checks the object — a
learner is visible to staff of a system that holds them, a transfer to
staff at either end of it. A superadmin sees everything.

Every read of learner or transfer data is audited as
``cross_system.access`` and every action as ``cross_system.transfer`` (or
``cross_system.handover`` for an approval). Audit is fail-closed: if the
entry cannot be written the response is withheld with a 503.

Handover payloads are never returned from here; see
``transfer_monitor.public``.
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Any

from flask import Blueprint, g, jsonify, request

from education_system.platform.delivery.api.security.authentication import (
    cross_system_permission_required,
    is_superadmin_user,
    permitted_systems_for,
    superadmin_required,
    token_required,
)
from education_system.platform.features.analytics import journey_analytics
from education_system.platform.features.analytics import transfer_monitor as tm
from education_system.platform.identity.auth.role_manager import (
    PERM_EVENTS_VIEW,
    PERM_LEARNER360_VIEW,
    PERM_TRANSFER_APPROVE,
    PERM_TRANSFER_VIEW,
    has_cross_system_permission,
)
from education_system.platform.integrations.external import cross_system_bus

logger = logging.getLogger(__name__)

learners_bp = Blueprint("linked_platform", __name__)

_db_path: str | None = None
_audit_db_path: str | None = None

_QUALIFICATION_EVENTS: tuple[str, ...] = (
    cross_system_bus.EVENT_QUALIFICATION_AWARDED,
    cross_system_bus.EVENT_UNIVERSITY_DEGREE_AWARDED,
    cross_system_bus.EVENT_APPRENTICESHIP_COMPLETED,
    cross_system_bus.EVENT_PROGRAMME_COMPLETED,
    cross_system_bus.EVENT_LEARNER_GRADUATED,
)

# Keys that may hold handover content, stripped from anything returned.
_HANDOVER_KEYS = frozenset({"handover_json", "handover_payload"})


def init_learner_routes(db_path: str | None = None,
                        audit_db_path: str | None = None) -> None:
    """Point the routes at an auth DB and an audit DB (tests pass temp ones)."""
    global _db_path, _audit_db_path
    _db_path = db_path
    _audit_db_path = audit_db_path
    logger.info("Linked-platform (learners/transfers/events) routes initialised.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _jsonable(value: Any) -> Any:
    """Strip handover content and make dataclasses/sets JSON-friendly."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        value = dataclasses.asdict(value)
    elif hasattr(value, "to_dict") and callable(value.to_dict):
        value = value.to_dict()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items() if k not in _HANDOVER_KEYS}
    if isinstance(value, (list, tuple, set, frozenset)):
        items = [_jsonable(v) for v in value]
        return sorted(items, key=str) if isinstance(value, (set, frozenset)) else items
    return value


def _int_arg(name: str, default: int, *, low: int = 1, high: int = 1000) -> int:
    try:
        value = int(request.args.get(name, default))
    except (TypeError, ValueError):
        value = default
    return max(low, min(high, value))


def _bool_arg(name: str) -> bool:
    return str(request.args.get(name, "")).lower() in ("1", "true", "yes")


def _audit(action_name: str, target_type: str, target_id: str | None, **details):
    """Record the access; return an error response if it could not be recorded."""
    from education_system.platform.governance.audit.logger import AuditAction, AuditLogger
    action = getattr(AuditAction, action_name)
    user = g.current_user
    try:
        AuditLogger("platform", db_path=_audit_db_path).log(
            action, user_id=user.get("user_id"), username=user.get("username"),
            target_type=target_type, target_id=target_id,
            details={"endpoint": request.path, "method": request.method,
                     **_jsonable(details)},
            ip_address=request.remote_addr)
    except Exception:
        logger.exception("Audit write failed for %s %s", request.method, request.path)
        return jsonify({"error": "Audit unavailable",
                        "message": "The access could not be recorded, so it "
                                   "was not performed."}), 503
    return None


def _learner_scope(journey_id: str):
    """``(systems holding the learner, None)`` or ``(None, error response)``.

    A merged journey id is followed to its survivor first (see
    :func:`_resolve`), so the scope is checked on the record actually read.
    """
    systems = tm.learner_systems(_resolve(journey_id), db_path=_db_path)
    if systems is None:
        return None, (jsonify({"error": "Learner not found",
                               "journey_id": journey_id}), 404)
    held = permitted_systems_for(PERM_LEARNER360_VIEW)
    if held is not None and not (systems & held):
        return None, (jsonify({
            "error": "Access denied",
            "message": "This learner is not enrolled in a system you can view"}), 403)
    return systems, None


def _resolve(journey_id: str) -> str:
    """The surviving journey for *journey_id* (itself if unmerged or unknown).

    A client holding an id from before a merge keeps working rather than
    reading a tombstone; responses carry the survivor's id.
    """
    return tm.resolve_journey(journey_id, db_path=_db_path) or journey_id


def _transition_or_404(transition_id: str):
    row = tm.get_transition(transition_id, db_path=_db_path)
    if row is None:
        return None, (jsonify({"error": "Transfer not found",
                               "transition_id": transition_id}), 404)
    return row, None


def _can_view_transition(row: dict) -> bool:
    held = permitted_systems_for(PERM_TRANSFER_VIEW)
    if held is None:
        return True
    return bool({row.get("source_system"), row.get("destination_system")} & held)


# ---------------------------------------------------------------------------
# Learners
# ---------------------------------------------------------------------------

def _fallback_360(journey_id: str) -> dict:
    """The learner view assembled from the workflow's own readers.

    Used until ``cross_system.learner_360.build_learner_360`` exists.
    """
    from education_system.platform.cross_system import enrolments, identity_service
    return {
        "journey": identity_service.get(journey_id, db_path=_db_path),
        "enrolment_history": enrolments.journey_history(journey_id, db_path=_db_path),
        "transitions": tm.search_transitions(journey_id=journey_id, limit=500,
                                             db_path=_db_path),
        "moves": journey_analytics.journey_moves(journey_id, db_path=_db_path),
    }


def _viewer(systems_holding: set[str]) -> tuple[str | None, str | None]:
    """``(viewer_role, viewer_system)`` for the Learner 360 visibility tier.

    A superadmin is the trusted platform tier (``None``). Anyone else sees
    the learner as their role in a system that holds the learner and in
    which they may view learners — the same system the scope check passed
    them on.
    """
    if is_superadmin_user():
        return None, None
    from education_system.platform.kernel.core.system_keys import canonical_system_key
    held = permitted_systems_for(PERM_LEARNER360_VIEW) or set()
    for entry in g.current_user.get("systems", []):
        system = canonical_system_key(entry.get("system_key"))
        if system in held and system in systems_holding:
            return entry.get("role"), system
    return "external", None


def _build_360(journey_id: str, systems_holding: set[str]) -> tuple[Any, str]:
    role, system = _viewer(systems_holding)
    record = tm.learner_360_record(journey_id, viewer_role=role,
                                   viewer_system=system, db_path=_db_path)
    if record is not None:
        return record, "learner_360"
    return _fallback_360(journey_id), "fallback"


@learners_bp.route("/learners/<journey_id>", methods=["GET"])
@cross_system_permission_required(PERM_LEARNER360_VIEW)
def learner_360(journey_id: str):
    systems, error = _learner_scope(journey_id)
    if error:
        return error
    journey_id = _resolve(journey_id)
    data, source = _build_360(journey_id, systems)
    if data is None:
        return jsonify({"error": "Learner not found", "journey_id": journey_id}), 404
    denied = _audit("CROSS_SYSTEM_ACCESS", "journey", journey_id,
                    view="learner_360", systems=sorted(systems))
    if denied:
        return denied
    return jsonify({"journey_id": journey_id, "source": source,
                    "systems": sorted(systems), "learner": _jsonable(data)})


@learners_bp.route("/learners/<journey_id>/history", methods=["GET"])
@cross_system_permission_required(PERM_LEARNER360_VIEW)
def learner_history(journey_id: str):
    systems, error = _learner_scope(journey_id)
    if error:
        return error
    journey_id = _resolve(journey_id)
    from education_system.platform.cross_system import enrolments
    body = {
        "journey_id": journey_id,
        "enrolments": enrolments.list_enrolments(journey_id, db_path=_db_path),
        "transitions": tm.search_transitions(journey_id=journey_id, limit=500,
                                             db_path=_db_path),
        "moves": journey_analytics.journey_moves(journey_id, db_path=_db_path),
        # What was published about the learner: names and systems, not
        # payloads — the payload view is the event monitor's, superadmin-only.
        "events": cross_system_bus.list_events(
            journey_id=journey_id, include_payload=False, limit=200,
            db_path=_db_path),
    }
    denied = _audit("CROSS_SYSTEM_ACCESS", "journey", journey_id,
                    view="history", systems=sorted(systems))
    return denied or jsonify(_jsonable(body))


@learners_bp.route("/learners/<journey_id>/progression", methods=["GET"])
@cross_system_permission_required(PERM_LEARNER360_VIEW)
def learner_progression(journey_id: str):
    systems, error = _learner_scope(journey_id)
    if error:
        return error
    journey_id = _resolve(journey_id)
    from education_system.platform.cross_system import identity_service, progression
    journey = identity_service.get(journey_id, db_path=_db_path) or {}
    current = journey.get("current_system")
    transitions = tm.search_transitions(journey_id=journey_id, limit=500,
                                        db_path=_db_path)
    body = {
        "journey_id": journey_id,
        "current_system": current,
        "recommended_next": progression.next_phase(current) if current else None,
        "permitted_destinations": progression.known_destinations(current) if current else [],
        "open": [t for t in transitions if t["status"] not in tm.CLOSED_STATUSES],
        "transitions": transitions,
    }
    denied = _audit("CROSS_SYSTEM_ACCESS", "journey", journey_id,
                    view="progression", systems=sorted(systems))
    return denied or jsonify(_jsonable(body))


@learners_bp.route("/learners/<journey_id>/qualifications", methods=["GET"])
@cross_system_permission_required(PERM_LEARNER360_VIEW)
def learner_qualifications(journey_id: str):
    systems, error = _learner_scope(journey_id)
    if error:
        return error
    journey_id = _resolve(journey_id)
    qualifications = None
    source = "events"
    role, system = _viewer(systems)
    record = tm.learner_360_record(journey_id, viewer_role=role,
                                   viewer_system=system, db_path=_db_path)
    if isinstance(record, dict) and "qualifications" in record:
        qualifications, source = _jsonable(record["qualifications"]), "learner_360"
    if qualifications is None:
        # The persisted cross-system record (learner_qualification), when
        # the Learner 360 view is not installed.
        try:
            from education_system.platform.cross_system import qualifications as quals
            qualifications = quals.list_for_journey(journey_id, db_path=_db_path)
            source = "learner_qualification"
        except (ImportError, AttributeError):
            qualifications = None
    if qualifications is None:
        # Until the learner view carries them, the awards the systems have
        # published are the cross-system record of what was achieved.
        qualifications = []
        for name in _QUALIFICATION_EVENTS:
            for event in cross_system_bus.list_events(
                    event_name=name, journey_id=journey_id, limit=200,
                    db_path=_db_path):
                qualifications.append({
                    "event": name, "awarded_by": event["source_system"],
                    "recorded_at": event["created_at"],
                    "details": event.get("payload") or {}})
        qualifications.sort(key=lambda q: q["recorded_at"] or "")
    denied = _audit("CROSS_SYSTEM_ACCESS", "journey", journey_id,
                    view="qualifications", systems=sorted(systems))
    return denied or jsonify({"journey_id": journey_id, "source": source,
                              "qualifications": _jsonable(qualifications)})


@learners_bp.route("/learners/<journey_id>/enrolments", methods=["GET"])
@cross_system_permission_required(PERM_LEARNER360_VIEW)
def learner_enrolments(journey_id: str):
    systems, error = _learner_scope(journey_id)
    if error:
        return error
    journey_id = _resolve(journey_id)
    from education_system.platform.cross_system import enrolments
    rows = enrolments.list_enrolments(journey_id, db_path=_db_path)
    denied = _audit("CROSS_SYSTEM_ACCESS", "journey", journey_id,
                    view="enrolments", systems=sorted(systems))
    return denied or jsonify({"journey_id": journey_id, "enrolments": rows})


# ---------------------------------------------------------------------------
# Starting a move
# ---------------------------------------------------------------------------

def _start(kind: str):
    from education_system.platform.cross_system import enrolments, identity_service
    from education_system.platform.cross_system.transitions import TransitionError

    body = request.get_json(silent=True) or {}
    journey_id = body.get("journey_id")
    if not journey_id:
        return jsonify({"error": "journey_id is required"}), 400
    destination = body.get("destination_system")
    if kind == "transfer" and not destination:
        return jsonify({"error": "destination_system is required for a transfer"}), 400
    journey = identity_service.get(journey_id, db_path=_db_path)
    if journey is None:
        return jsonify({"error": "Learner not found", "journey_id": journey_id}), 404

    source = body.get("source_system")
    enrolment_id = body.get("source_enrolment_id")
    if not source and enrolment_id:
        enrolment = enrolments.get_enrolment(enrolment_id, db_path=_db_path)
        if enrolment is None or enrolment["journey_id"] != journey_id:
            return jsonify({"error": "source_enrolment_id does not belong to "
                                     "this learner"}), 400
        source = enrolment["system"]
    if not source and not enrolment_id:
        source = journey.get("current_system")

    user_systems = g.current_user.get("systems", [])
    allowed = has_cross_system_permission(user_systems, PERM_TRANSFER_APPROVE, source)
    if not allowed and kind == "transfer":
        # A receiving institution may open an in-year transfer in.
        allowed = has_cross_system_permission(
            user_systems, PERM_TRANSFER_APPROVE, destination)
    if not allowed:
        return jsonify({"error": "Access denied",
                        "message": "Requires transfer.approve at the source"
                                   + (" or destination" if kind == "transfer" else "")}), 403

    status = body.get("status", "expected") if kind == "transfer" else "expected"
    try:
        row = tm.start_transfer(
            journey_id=journey_id, destination_system=destination,
            source_system=source, source_enrolment_id=enrolment_id,
            reason=body.get("reason"), status=status,
            actor_user_id=g.current_user.get("user_id"), db_path=_db_path)
    except TransitionError as exc:
        return jsonify({"error": str(exc)}), 400
    denied = _audit("CROSS_SYSTEM_TRANSFER", "transition", row.get("transition_id"),
                    step="start", kind=kind, journey_id=journey_id,
                    source_system=row.get("source_system"),
                    destination_system=row.get("destination_system"))
    if denied:
        return denied
    return jsonify(_jsonable(row)), 201


@learners_bp.route("/progression", methods=["POST"])
@cross_system_permission_required(PERM_TRANSFER_APPROVE)
def start_progression():
    """Start a phase progression; the destination defaults to the next phase."""
    return _start("progression")


@learners_bp.route("/transfers", methods=["POST"])
@cross_system_permission_required(PERM_TRANSFER_APPROVE)
def start_transfer():
    """Start a transfer to a named destination (any institution or phase)."""
    return _start("transfer")


# ---------------------------------------------------------------------------
# Transfers
# ---------------------------------------------------------------------------

@learners_bp.route("/transfers", methods=["GET"])
@cross_system_permission_required(PERM_TRANSFER_VIEW)
def list_transfers():
    args = request.args
    try:
        rows = tm.search_transitions(
            status=args.get("status"), source_system=args.get("source_system"),
            destination_system=args.get("destination_system"),
            journey_id=args.get("journey_id"), open_only=_bool_arg("open"),
            since=args.get("since"), limit=_int_arg("limit", 200, high=2000),
            systems=permitted_systems_for(PERM_TRANSFER_VIEW), db_path=_db_path)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    denied = _audit("CROSS_SYSTEM_ACCESS", "transitions", None,
                    view="list", filters=dict(args), returned=len(rows))
    return denied or jsonify({"transfers": _jsonable(rows), "count": len(rows)})


@learners_bp.route("/transfers/<transition_id>", methods=["GET"])
@cross_system_permission_required(PERM_TRANSFER_VIEW)
def get_transfer(transition_id: str):
    row, error = _transition_or_404(transition_id)
    if error:
        return error
    if not _can_view_transition(row):
        return jsonify({"error": "Access denied"}), 403
    detail = tm.transition_detail(transition_id, db_path=_db_path)
    denied = _audit("CROSS_SYSTEM_ACCESS", "transition", transition_id, view="detail")
    return denied or jsonify(_jsonable(detail))


@learners_bp.route("/transfers/<transition_id>/events", methods=["GET"])
@cross_system_permission_required(PERM_TRANSFER_VIEW)
def transfer_events(transition_id: str):
    row, error = _transition_or_404(transition_id)
    if error:
        return error
    if not _can_view_transition(row):
        return jsonify({"error": "Access denied"}), 403
    events, source = tm.transition_events(transition_id, db_path=_db_path)
    denied = _audit("CROSS_SYSTEM_ACCESS", "transition", transition_id, view="events")
    return denied or jsonify({"transition_id": transition_id, "source": source,
                              "events": _jsonable(events)})


def _transfer_action(transition_id: str, action: str):
    from education_system.platform.cross_system.transitions import TransitionError

    row, error = _transition_or_404(transition_id)
    if error:
        return error
    if row["status"] in tm.CLOSED_STATUSES:
        # Refused here rather than left to the workflow: some steps do work
        # (closing enrolments, journey rows) before they discover the
        # transition is already closed.
        return jsonify({"error": f"Transfer is already {row['status']}"}), 409
    system = tm.action_system(action, row)
    permission = tm.action_permission(action)
    if not has_cross_system_permission(g.current_user.get("systems", []),
                                       permission, system):
        return jsonify({"error": "Access denied",
                        "message": f"Requires {permission} in {system or 'the relevant system'}"}), 403
    body = request.get_json(silent=True) or {}
    reason = body.get("reason")
    if action == "reject" and not (reason or "").strip():
        return jsonify({"error": "reason is required to reject a transfer"}), 400
    handover = body.get("handover")
    if handover is not None and not isinstance(handover, dict):
        return jsonify({"error": "handover must be an object"}), 400
    try:
        result = tm.perform_action(
            action, transition_id,
            actor_user_id=g.current_user.get("user_id"),
            actor=g.current_user.get("username"),
            reason=reason, notes=body.get("notes"), handover=handover,
            consent=body.get("consent"),
            consent_reference=body.get("consent_reference"),
            start_date=body.get("start_date"), db_path=_db_path)
    except tm.ActionUnavailable as exc:
        return jsonify({"error": "Not available", "message": str(exc)}), 501
    except TransitionError as exc:
        return jsonify({"error": str(exc)}), 409
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    denied = _audit(
        "CROSS_BOUNDARY_HANDOVER" if action == "approve" else "CROSS_SYSTEM_TRANSFER",
        "transition", transition_id, step=action, system=system,
        status=result.get("status"))
    return denied or jsonify(_jsonable(result))


@learners_bp.route("/transfers/<transition_id>/approve", methods=["POST"])
@cross_system_permission_required(PERM_TRANSFER_VIEW)
def approve_transfer(transition_id: str):
    return _transfer_action(transition_id, "approve")


@learners_bp.route("/transfers/<transition_id>/reject", methods=["POST"])
@cross_system_permission_required(PERM_TRANSFER_VIEW)
def reject_transfer(transition_id: str):
    return _transfer_action(transition_id, "reject")


@learners_bp.route("/transfers/<transition_id>/acknowledge", methods=["POST"])
@cross_system_permission_required(PERM_TRANSFER_VIEW)
def acknowledge_transfer(transition_id: str):
    return _transfer_action(transition_id, "acknowledge")


@learners_bp.route("/transfers/<transition_id>/complete", methods=["POST"])
@cross_system_permission_required(PERM_TRANSFER_VIEW)
def complete_transfer(transition_id: str):
    return _transfer_action(transition_id, "complete")


# ---------------------------------------------------------------------------
# Tasks, systems, events
# ---------------------------------------------------------------------------

@learners_bp.route("/tasks", methods=["GET"])
@token_required
def my_tasks():
    from education_system.platform.features.calendar.cross_system_tasks import list_tasks
    tasks = list_tasks(g.current_user.get("systems", []), db_path=_db_path,
                       limit=_int_arg("limit", 200, high=1000))
    return jsonify({"tasks": _jsonable(tasks), "count": len(tasks)})


@learners_bp.route("/systems", methods=["GET"])
@token_required
def list_systems():
    """Every system in the registry — all seven — and how it is mounted.

    Identity and interfaces are public to any signed-in user; adapter and
    intake health are operational detail for holders of ``events.view``.
    """
    from education_system.platform.delivery.api import registry as api_registry
    from education_system.platform.features.analytics import platform_registry

    ops = has_cross_system_permission(g.current_user.get("systems", []),
                                      PERM_EVENTS_VIEW)
    rows = (platform_registry.describe_systems(db_path=_db_path) if ops
            else platform_registry.manifests()[0])
    mounts = api_registry.mounts_by_system()
    for row in rows:
        mount = mounts.get(row["key"])
        row["api_prefix"] = mount.prefix if mount else None
        row["api_wired"] = bool(mount and mount.wired)
    return jsonify({"systems": _jsonable(rows), "count": len(rows)})


@learners_bp.route("/events", methods=["GET"])
@cross_system_permission_required(PERM_EVENTS_VIEW)
def list_bus_events():
    args = request.args
    try:
        rows = cross_system_bus.list_events(
            event_name=args.get("event_name"), journey_id=args.get("journey_id"),
            source_system=args.get("source_system"),
            target_system=args.get("target_system"), since=args.get("since"),
            status=args.get("status"), transition_id=args.get("transition_id"),
            limit=_int_arg("limit", 200),
            systems=permitted_systems_for(PERM_EVENTS_VIEW),
            include_payload=is_superadmin_user(), db_path=_db_path)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    denied = _audit("CROSS_SYSTEM_ACCESS", "events", None, view="list",
                    filters=dict(args), returned=len(rows))
    return denied or jsonify({"events": _jsonable(rows), "count": len(rows),
                              "statuses": list(cross_system_bus.DELIVERY_STATUSES)})


@learners_bp.route("/events/dead-letters", methods=["GET"])
@superadmin_required
def list_dead_letters():
    rows = cross_system_bus.list_failed_deliveries(
        exhausted_only=not _bool_arg("include_retrying"),
        consumer_system=request.args.get("consumer_system"),
        limit=_int_arg("limit", 100), db_path=_db_path)
    for row in rows:
        row.pop("payload_json", None)
    return jsonify({"dead_letters": _jsonable(rows), "count": len(rows)})


def _delivery_key(body: dict):
    keys = ("event_id", "consumer_system", "consumer_handler")
    missing = [k for k in keys if not body.get(k)]
    if missing:
        return None, (jsonify({"error": f"Missing: {', '.join(missing)}"}), 400)
    return tuple(body[k] for k in keys), None


@learners_bp.route("/events/dead-letters/retry", methods=["POST"])
@superadmin_required
def retry_dead_letter():
    body = request.get_json(silent=True) or {}
    key, error = _delivery_key(body)
    if error:
        return error
    if not cross_system_bus.retry_failed_delivery(*key, db_path=_db_path):
        return jsonify({"error": "No failed delivery with that key"}), 404
    denied = _audit("CONFIG_CHANGE", "bus_delivery", key[0], step="retry",
                    consumer_system=key[1], consumer_handler=key[2])
    return denied or jsonify({"retried": True})


@learners_bp.route("/events/dead-letters/abandon", methods=["POST"])
@superadmin_required
def abandon_dead_letter():
    body = request.get_json(silent=True) or {}
    key, error = _delivery_key(body)
    if error:
        return error
    reason = (body.get("reason") or "").strip()
    if not reason:
        return jsonify({"error": "reason is required"}), 400
    if not cross_system_bus.abandon_failed_delivery(*key, reason=reason,
                                                    db_path=_db_path):
        return jsonify({"error": "No failed delivery with that key"}), 404
    denied = _audit("CONFIG_CHANGE", "bus_delivery", key[0], step="abandon",
                    consumer_system=key[1], consumer_handler=key[2], reason=reason)
    return denied or jsonify({"abandoned": True})


# Failed best-effort syncs that never reached the bus (journey registration,
# progression announce/publish) — see platform/cross_system/sync_failures.py.

@learners_bp.route("/sync-failures", methods=["GET"])
@superadmin_required
def list_sync_failures():
    from education_system.platform.cross_system import sync_failures
    status = request.args.get("status", sync_failures.OPEN)
    if status not in (*sync_failures.STATUSES, "all"):
        return jsonify({"error": f"status must be one of "
                                 f"{', '.join(sync_failures.STATUSES)} or all"}), 400
    rows = sync_failures.list_failures(
        status=None if status == "all" else status,
        limit=_int_arg("limit", 200), db_path=_db_path)
    return jsonify({"sync_failures": _jsonable(rows), "count": len(rows)})


@learners_bp.route("/sync-failures/<int:failure_id>/retry", methods=["POST"])
@superadmin_required
def retry_sync_failure(failure_id: int):
    from education_system.platform.cross_system import sync_failures
    actor = g.current_user.get("username")
    try:
        sync_failures.retry(failure_id, actor=actor, db_path=_db_path)
    except sync_failures.SyncFailureError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:
        logger.exception("Retry of sync failure %s failed", failure_id)
        return jsonify({"retried": False, "error": str(exc)}), 502
    denied = _audit("CONFIG_CHANGE", "sync_failure", str(failure_id), step="retry")
    return denied or jsonify({"retried": True})


@learners_bp.route("/sync-failures/<int:failure_id>/abandon", methods=["POST"])
@superadmin_required
def abandon_sync_failure(failure_id: int):
    from education_system.platform.cross_system import sync_failures
    reason = ((request.get_json(silent=True) or {}).get("reason") or "").strip()
    if not reason:
        return jsonify({"error": "reason is required"}), 400
    if not sync_failures.abandon(failure_id, reason=reason,
                                 actor=g.current_user.get("username"), db_path=_db_path):
        return jsonify({"error": "No open sync failure with that id"}), 404
    denied = _audit("CONFIG_CHANGE", "sync_failure", str(failure_id), step="abandon",
                    reason=reason)
    return denied or jsonify({"abandoned": True})


__all__ = ["init_learner_routes", "learners_bp"]
