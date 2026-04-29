"""Legal services adapter — export grade audit trail for misconduct.

Pulls the immutable-audit rows the grade GUI writes (resource_type
in 'grade', 'module', 'assessment') for a student and bundles them
into a dict legal can attach to a case. Optional: also opens a
legal_cases row of ``case_type='grade_audit'`` referencing the export.
"""

from __future__ import annotations

import logging
from datetime import datetime

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH

logger = logging.getLogger(__name__)


def export_grade_audit_for_legal(
    *,
    student_id: str,
    open_case: bool = False,
    student_name: str = "",
    student_email: str = "",
    created_by: str | None = None,
) -> dict | None:
    """Return a dict containing the student's grade-related audit rows.

    Shape: ``{student_id, generated_at, audit_rows, case_id}``.
    ``case_id`` is None unless ``open_case=True`` and the legal
    services module is reachable.
    """
    if not student_id:
        return None

    audit_rows: list[dict] = []
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            tables = {
                r[0] for r in cur.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if "immutable_audit_log" in tables:
                cur.execute(
                    """
                    SELECT * FROM immutable_audit_log
                    WHERE resource_type IN ('grade','module','assessment')
                      AND (resource_id = ? OR
                           details LIKE ?)
                    ORDER BY id DESC
                    LIMIT 200
                    """,
                    (str(student_id), f'%"student_id":%{student_id}%'),
                )
                audit_rows = [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
    except Exception as exc:
        logger.warning(
            "export_grade_audit_for_legal read failed for %s: %s",
            student_id, exc,
        )

    case_id = None
    if open_case:
        try:
            from education_system.university_system.modules.domain.legal.services.legal_services_core import (
                CaseManager,
            )
            case_id = CaseManager.create_case(
                client_id=str(student_id),
                client_name=student_name or str(student_id),
                client_email=student_email or "",
                case_type="grade_audit",
                case_title=f"Grade audit export — {student_id}",
                case_description=(
                    f"Bundled {len(audit_rows)} grade/module/assessment audit "
                    f"row(s) for legal review."
                ),
                priority="normal",
                created_by=created_by,
            )
        except ImportError as exc:
            logger.debug("legal_services_core unavailable: %s", exc)
        except Exception as exc:
            logger.warning("legal case creation failed for %s: %s", student_id, exc)

    return {
        "student_id": str(student_id),
        "generated_at": datetime.now().isoformat(),
        "audit_rows": audit_rows,
        "case_id": case_id,
    }
