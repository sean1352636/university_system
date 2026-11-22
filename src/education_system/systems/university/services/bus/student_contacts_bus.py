"""Read-only port: a student's contacts with services outside Pastoral.

Student Support's 360 view (``pastoral ... student_support.history360``)
shows a student's mitigating-circumstances claims (Assessment), bursary
applications (Finance) and safeguarding concerns (Safeguarding). Those are
other slices, so the view reads them here rather than importing them.

Each reader applies its owner's access rule for the viewer — a dict
``{'username', 'role', 'student_id', 'teams'}`` (``teams``: the viewer's
support teams) — and returns summaries only (dates, statuses, references):
never claim grounds, circumstances, incomes or concern text.

* :func:`mitigating_claims` — the student; admins; Academic Registry.
* :func:`bursary_applications` — the student; admins; Fees & Funding.
* :func:`safeguarding_concerns` — safeguarding leads only (the
  Safeguarding slice's own permission: 'close' — DSL, safeguarding and
  admin roles). Anonymous, whistleblowing and purged concerns never appear.
"""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)

ADMIN_ROLES = ("admin", "super_admin", "superadmin")


def _owner(viewer: dict, student_id: str) -> bool:
    return bool(viewer.get("student_id")) and str(viewer["student_id"]) == str(student_id)


def _has_table(conn, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                        (name,)).fetchone() is not None


def _rows(sql: str, params: tuple, table: str) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        if not _has_table(conn, table):
            return []
        cur = conn.execute(sql, params)
        names = [d[0] for d in cur.description]
        return [dict(zip(names, tuple(r))) for r in cur.fetchall()]
    finally:
        conn.close()


def may_see_mitigating(viewer: dict, student_id: str) -> bool:
    return (_owner(viewer, student_id) or viewer.get("role") in ADMIN_ROLES
            or "academic_registry" in set(viewer.get("teams") or ()))


def mitigating_claims(student_id: str, viewer: dict) -> list[dict[str, Any]]:
    """``[{'id', 'date', 'status', 'module_code', 'assessment_ref'}]``."""
    if not may_see_mitigating(viewer, student_id):
        return []
    return _rows("SELECT id, submitted_at AS date, status, module_code, assessment_ref "
                 "FROM mc_claims WHERE student_id = ? ORDER BY submitted_at DESC, id DESC",
                 (str(student_id),), "mc_claims")


def may_see_bursary(viewer: dict, student_id: str) -> bool:
    return (_owner(viewer, student_id) or viewer.get("role") in ADMIN_ROLES
            or "finance" in set(viewer.get("teams") or ()))


def bursary_applications(student_id: str, viewer: dict) -> list[dict[str, Any]]:
    """``[{'id', 'date', 'status', 'fund', 'decided_at'}]``."""
    if not may_see_bursary(viewer, student_id):
        return []
    return _rows("SELECT a.application_id AS id, a.submitted_at AS date, a.status, "
                 "f.name AS fund, a.decided_at FROM bursary_applications a "
                 "LEFT JOIN bursary_funds f ON f.fund_id = a.fund_id WHERE a.student_id = ? "
                 "ORDER BY a.submitted_at DESC, a.application_id DESC",
                 (str(student_id),), "bursary_applications")


def may_see_safeguarding(viewer: dict) -> bool:
    from education_system.systems.university.domains.safeguarding.domain.permissions import can
    return can({"role": viewer.get("role") or ""}, "close")


def _safeguarding_connection():
    from education_system.systems.university.domains.safeguarding.infrastructure.db import _connect
    return _connect()


def safeguarding_concerns(username: str, viewer: dict) -> list[dict[str, Any]]:
    """``[{'id', 'date', 'status', 'severity'}]`` for safeguarding leads."""
    if not username or not may_see_safeguarding(viewer):
        return []
    try:
        conn = _safeguarding_connection()
    except Exception:
        logger.warning("Safeguarding store unavailable for the 360 view", exc_info=True)
        return []
    try:
        if not _has_table(conn, "safeguarding_submissions"):
            return []
        cols = {r[1] for r in conn.execute("PRAGMA table_info(safeguarding_submissions)")}
        where = "LOWER(username) = LOWER(?)"
        for flag in ("anonymous", "whistleblowing", "purged"):
            if flag in cols:
                where += f" AND COALESCE({flag}, 0) = 0"
        cur = conn.execute(f"SELECT id, submitted_at AS date, status, severity "  # nosec B608
                           f"FROM safeguarding_submissions WHERE {where} "
                           "ORDER BY submitted_at DESC, id DESC", (str(username),))
        names = [d[0] for d in cur.description]
        return [dict(zip(names, tuple(r))) for r in cur.fetchall()]
    finally:
        conn.close()


__all__ = ["mitigating_claims", "bursary_applications", "safeguarding_concerns",
           "may_see_mitigating", "may_see_bursary", "may_see_safeguarding"]
