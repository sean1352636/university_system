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
from education_system.systems.university.services.bus.integration.publishing import log_and_publish

def publish_permit_issued(permit_id: str, *, holder_id: str,
                          fee: float, zone: str, permit_type: str,
                          plate: str | None = None,
                          email: str | None = None,
                          start_date: str | None = None,
                          end_date: str | None = None) -> None:
    """Publish a permit issuance from the legacy CLI/GUI writer
    paths that don't go through ``parking_bus.issue_permit``.

    Subscriber raises the charge against the holder's finance
    account and emails the holder. Idempotent on
    ``reference_id='permit:<permit_id>'``.
    """
    log_and_publish(
        EVENT_INCIDENT_LOGGED,
        source="mobility",
        kind="permit_issued",
        severity="low",
        permit_id=str(permit_id),
        holder_id=str(holder_id),
        fee=float(fee or 0),
        zone=zone,
        permit_type=permit_type,
        plate=plate,
        email=email,
        start_date=start_date,
        end_date=end_date,
    )

def _on_permit_issued(**payload: Any) -> None:
    if payload.get("kind") != "permit_issued":
        return
    fee = float(payload.get("fee") or 0)
    holder_id = payload.get("holder_id")
    if not holder_id or fee <= 0:
        return
    try:
        from education_system.systems.university.services.bus.finance_bus import (
            raise_charge,
        )
        raise_charge(
            holder_id, fee,
            source="parking_permit",
            description=(
                f"Parking permit fee — {payload.get('permit_type')} "
                f"({payload.get('zone')}); plate {payload.get('plate') or 'n/a'}"
            ),
            reference_id=f"permit:{payload.get('permit_id')}",
        )
    except Exception as exc:
        logger.debug("permit→finance failed: %s", exc)
