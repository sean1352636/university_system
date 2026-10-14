"""Forward durable bus events to external webhook subscribers.

Every event in :data:`cross_system_bus.KNOWN_EVENTS` is offered to
:meth:`WebhookService.dispatch`; subscriptions filter by event type and by
system (the event's source or target).

What leaves the platform is deliberately thin: the event's metadata and the
identifiers in its payload, never the payload itself. Bus payloads are
already kept free of handover data, but they still carry things like
course names, stage notes and consent summaries that were fine to share
between the platform's own systems and are not fine to post to an arbitrary
URL. A receiver that needs more calls back through the API with the ids,
and is authorised there.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from education_system.platform.integrations.external import cross_system_bus

logger = logging.getLogger(__name__)

HANDLER_NAME = "platform.integrations.webhooks.bus_forwarder"

#: Start the delivery thread after queueing. Tests turn this off so that
#: queueing is observable without anything attempting an HTTP request.
BACKGROUND_DELIVERY = True

# Payload keys that are safe to forward even though they are not ids: each
# is a workflow state or a system key, never learner data.
_SAFE_SCALAR_KEYS = frozenset({
    "status", "stage", "action", "destination_system", "source_system",
})

_services: dict[str | None, Any] = {}
_services_lock = threading.Lock()
_registered = False


def _is_id_key(key: str) -> bool:
    return key.endswith("_id") or key.endswith("_ids")


def _scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def build_webhook_payload(envelope: dict) -> dict:
    """The outbound body for one bus event: metadata plus identifiers only.

    Lists of ids are forwarded when every element is a scalar; anything
    else — nested dicts, lists of names — is dropped rather than guessed at.
    """
    ids: dict[str, Any] = {}
    for key, value in (envelope.get("payload") or {}).items():
        if not isinstance(key, str):
            continue
        if _is_id_key(key):
            if _scalar(value):
                ids[key] = value
            elif isinstance(value, (list, tuple)) and all(_scalar(v) for v in value):
                ids[key] = list(value)
        elif key in _SAFE_SCALAR_KEYS and _scalar(value):
            ids[key] = value
    return {
        "event_id": envelope.get("event_id"),
        "event_name": envelope.get("event_name"),
        "event_version": envelope.get("event_version"),
        "occurred_at": envelope.get("created_at"),
        "correlation_id": envelope.get("correlation_id"),
        "journey_id": envelope.get("journey_id"),
        "source_system": envelope.get("source_system"),
        "target_system": envelope.get("target_system"),
        "data": ids,
    }


def _webhook_db_for(auth_db_path: str | None) -> str | None:
    """Keep the webhook DB beside whichever auth DB the event came from.

    ``None`` is the production default (``WebhookService`` resolves its own
    path). An explicit auth DB is a test or an alternate deployment, and its
    deliveries belong next to it rather than in the live webhooks.db.
    """
    if not auth_db_path:
        return None
    return str(Path(auth_db_path).with_name("webhooks.db"))


def _service(db_path: str | None):
    with _services_lock:
        svc = _services.get(db_path)
        if svc is None:
            from education_system.platform.integrations.webhooks.webhook_service import (
                WebhookService,
            )
            svc = WebhookService(db_path=db_path)
            _services[db_path] = svc
        return svc


def forward(envelope: dict) -> int:
    """Queue webhook deliveries for one bus event. Returns how many."""
    event_name = envelope.get("event_name")
    if event_name not in cross_system_bus.KNOWN_EVENTS:
        return 0
    systems = [s for s in (envelope.get("source_system"),
                           envelope.get("target_system")) if s]
    svc = _service(_webhook_db_for(cross_system_bus.current_dispatch_db_path()))
    queued = svc.dispatch(
        event_name, build_webhook_payload(envelope),
        systems=systems or ["shared"], bus_event_id=envelope.get("event_id"),
        process=BACKGROUND_DELIVERY)
    if queued:
        logger.info("Queued %d webhook delivery(ies) for %s %s",
                    queued, event_name, envelope.get("event_id"))
    return queued


def register_consumer() -> None:
    """Subscribe the forwarder to every catalogued event. Idempotent."""
    global _registered
    if _registered:
        return
    for name in sorted(cross_system_bus.KNOWN_EVENTS):
        cross_system_bus.subscribe(name, forward, handler_name=HANDLER_NAME)
    _registered = True


def reset_for_test() -> None:
    """Forget cached services and the registration flag."""
    global _registered
    with _services_lock:
        _services.clear()
    _registered = False


__all__ = [
    "BACKGROUND_DELIVERY",
    "HANDLER_NAME",
    "build_webhook_payload",
    "forward",
    "register_consumer",
    "reset_for_test",
]
