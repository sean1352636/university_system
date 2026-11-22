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
from education_system.systems.university.services.bus.integration.finance.subscribers import _REFUND_PREVIEW_SQL, _lookup_program_fee

def _on_enrolment_withdrew(**payload: Any) -> None:
    if payload.get("action") != "withdrew":
        return
    student_id = payload.get("student_id")
    course_code = payload.get("course_code")
    if not (student_id and course_code):
        return

    # Cancel any in-progress exam attempts for that module.
    try:
        with transaction() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='exam_portal_attempts'"
            ).fetchone()
            if tbl:
                conn.execute(
                    "UPDATE exam_portal_attempts SET status = 'cancelled' "
                    "WHERE student_id = ? AND status = 'in_progress' "
                    "  AND exam_id IN ("
                    "      SELECT id FROM exam_portal_exams WHERE module_code = ?)",
                    (str(student_id), course_code),
                )
            conn.commit()
    except Exception as exc:
        logger.debug("withdraw → cancel attempts failed: %s", exc)

    # Queue a refund preview row (no auto-charge).
    try:
        with transaction() as conn:
            conn.executescript(_REFUND_PREVIEW_SQL)
            fee = _lookup_program_fee(course_code, None) or 0.0
            conn.execute(
                "INSERT INTO refund_previews "
                "(student_id, course_code, amount, reason, status) "
                "VALUES (?, ?, ?, ?, 'pending')",
                (str(student_id), course_code, float(fee),
                 payload.get("reason") or "withdrawal"),
            )
            conn.commit()
    except Exception as exc:
        logger.debug("withdraw → refund preview failed: %s", exc)

_STUDY_MATCH_LIMIT = 3

def _on_enrolment_added(**payload: Any) -> None:
    if payload.get("action") not in ("enrolled", "added"):
        return
    student_id = payload.get("student_id")
    course_code = payload.get("course_code")
    if not (student_id and course_code):
        return

    try:
        from education_system.systems.university.domains.student_life.domain.study_hub.services.matching import (
            StudyMatchingService,
        )
        svc = StudyMatchingService()
        matches = svc.find_study_matches(
            str(student_id), course_id=course_code, limit=_STUDY_MATCH_LIMIT,
        ) or []
    except Exception as exc:
        logger.debug("study matches lookup failed: %s", exc)
        return

    for m in matches:
        peer_id = m.get("student_id") or m.get("matched_student_id")
        if not peer_id:
            continue
        try:
            svc.create_match_suggestion(
                str(student_id), str(peer_id),
                course_id=course_code,
            )
        except Exception as exc:
            logger.debug("create_match_suggestion failed: %s", exc)
