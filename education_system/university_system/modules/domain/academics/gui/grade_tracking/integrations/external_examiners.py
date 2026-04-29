"""External examiners adapter — moderation gate hook.

Wraps ``ExternalExaminerService.record_findings`` so a bulk grade
import can record a moderation visit / action item without the
grade GUI knowing the examiner schema.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def record_moderation_event(
    *,
    visit_id: int | None = None,
    module_code: str = "",
    findings: str = "",
    recommendations: str | None = None,
    created_by: str | None = None,
) -> bool:
    """Record a moderation finding for a grade import.

    ``visit_id=None`` means we couldn't find an active visit for the
    module; in that case we just log and bail. Returns True on
    success.
    """
    if not visit_id:
        logger.debug(
            "record_moderation_event: no visit_id supplied for module %s — skipping",
            module_code,
        )
        return False
    try:
        from education_system.university_system.modules.domain.academics.external_examiners.services.external_examiner_service import (
            ExternalExaminerService,
        )
    except ImportError as exc:
        logger.debug("ExternalExaminerService unavailable: %s", exc)
        return False
    try:
        svc = ExternalExaminerService()
        svc.record_findings(
            visit_id=visit_id,
            findings=findings or f"Bulk grade import for {module_code}",
            recommendations=recommendations,
            created_by=created_by,
        )
        return True
    except Exception as exc:
        logger.warning(
            "record_moderation_event(visit=%s, module=%s) failed: %s",
            visit_id, module_code, exc,
        )
        return False


def find_active_visit_for_module(module_code: str) -> int | None:
    """Best-effort lookup: return the most recent visit_id whose
    department or notes reference ``module_code``.

    Returns None if nothing matches — callers should treat that as
    "no moderation gate currently applies".
    """
    if not module_code:
        return None
    try:
        from education_system.university_system.infrastructure.database.db import sqlite3
        from education_system.university_system.modules.shared.constants.paths import (
            DEFAULT_DB_PATH,
        )
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='examiner_visits'"
            ).fetchone()
            if not row:
                return None
            r = conn.execute(
                """
                SELECT id FROM examiner_visits
                WHERE department LIKE ? OR notes LIKE ?
                ORDER BY id DESC LIMIT 1
                """,
                (f"%{module_code}%", f"%{module_code}%"),
            ).fetchone()
            return int(r[0]) if r else None
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("find_active_visit_for_module failed: %s", exc)
        return None
