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

def publish_accommodation_decision(request_id: int, *, student_id: str,
                                    status: str, accommodation_type: str,
                                    extended_time_pct: int = 0,
                                    separate_room: bool = False,
                                    reader_scribe: bool = False,
                                    assistive_technology: str | None = None,
                                    exam_id: int | None = None) -> None:
    """Publish an accommodation decision.

    Origin: ``AccommodationRequestManager.review_request`` and
    ``ExamAccommodationManager.create_accommodation``. Subscribers
    (this module) tag matching ``exam_portal_attempts`` rows so the
    invigilator knows extra time / reader service applies, and they
    extend the per-attempt ``time_remaining`` proportionally.
    """
    log_and_publish(
        EVENT_SELECTION_CHANGED,
        source="student_affairs",
        action="accommodation_decided",
        request_id=int(request_id),
        student_id=str(student_id),
        status=status,
        accommodation_type=accommodation_type,
        extended_time_pct=int(extended_time_pct or 0),
        separate_room=bool(separate_room),
        reader_scribe=bool(reader_scribe),
        assistive_technology=assistive_technology,
        exam_id=exam_id,
    )

def _on_accommodation_decided(**payload: Any) -> None:
    if payload.get("action") != "accommodation_decided":
        return
    if payload.get("status") != "approved":
        return
    student_id = payload.get("student_id")
    if not student_id:
        return
    extra_pct = int(payload.get("extended_time_pct") or 0)

    try:
        with transaction() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='exam_portal_attempts'"
            ).fetchone()
            if not tbl:
                return
            cols = {r[1] for r in conn.execute(
                "PRAGMA table_info(exam_portal_attempts)").fetchall()}
            if "accommodation_notes" not in cols:
                conn.execute(
                    "ALTER TABLE exam_portal_attempts "
                    "ADD COLUMN accommodation_notes TEXT"
                )
            note = _format_accommodation_note(payload)

            # Tag any in-progress / not-yet-started attempts. Done
            # attempts stay untouched — the accommodation can't
            # retroactively change a graded score.
            sql_filter = "student_id = ? AND status IN ('in_progress', 'pending', 'scheduled')"
            params: list[Any] = [str(student_id)]
            if payload.get("exam_id") is not None:
                sql_filter += " AND exam_id = ?"
                params.append(int(payload["exam_id"]))

            conn.execute(
                f"UPDATE exam_portal_attempts "
                f"SET accommodation_notes = COALESCE(accommodation_notes, '') || ? "
                f"WHERE {sql_filter}",
                (note + "; ", *params),
            )
            if extra_pct > 0:
                conn.execute(
                    f"UPDATE exam_portal_attempts "
                    f"SET time_remaining = CAST("
                    f"  COALESCE(time_remaining, 0) * (1 + ?/100.0) AS INTEGER) "
                    f"WHERE {sql_filter}",
                    (extra_pct, *params),
                )
            conn.commit()
    except Exception as exc:
        logger.debug("accommodation→exam tag failed: %s", exc)

def _format_accommodation_note(payload: dict[str, Any]) -> str:
    bits = [payload.get("accommodation_type") or "accommodation"]
    if payload.get("extended_time_pct"):
        bits.append(f"+{payload['extended_time_pct']}% time")
    if payload.get("separate_room"):
        bits.append("separate room")
    if payload.get("reader_scribe"):
        bits.append("reader/scribe")
    if payload.get("assistive_technology"):
        bits.append(f"AT: {payload['assistive_technology']}")
    return ", ".join(bits)
