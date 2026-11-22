"""Per-course integrity toggles (AI detection, plagiarism, collaboration).

Different courses have different academic-integrity expectations: a
group-coursework module may legitimately allow collaboration that would
be flagged in a closed-book essay. This module reads the per-course
policy from ``course_integrity_settings`` (schema:
``academic_integrity_schema``) and exposes ``is_*_enabled`` helpers the
detector code calls before running. Changes go through
``application/integrity/access.set_module_settings``, which checks the
person is the module's staff or an integrity officer.

Keying note: the rest of the system identifies courses via
``module_code`` (used as the FK across ``student_modules``,
``modules``, ``textbooks``, ``module_schedule``, etc.), so this table
follows the same convention. A "course" here is whatever lives in the
``modules`` table.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Sensible defaults when no row exists for a module — match the
# project-wide expectation that integrity checks run by default.
DEFAULTS: Dict = {
    "ai_detection_enabled": True,
    "plagiarism_enabled": True,
    "similarity_threshold": 0.3,
    "allow_collaboration": False,
    "notes": "",
}


def _connect():
    try:
        from education_system.systems.university.application.integrity import (
            access as integrity_access,
        )
        from education_system.systems.university.infrastructure.database.db import get_connection
        conn = get_connection(row_factory=False)
        integrity_access.ensure(conn)
        return conn
    except Exception as exc:
        logger.debug("DB unavailable for integrity settings: %s", exc)
        return None


def get_course_integrity_settings(module_code: str) -> Dict:
    """Return the integrity policy for *module_code*, or DEFAULTS if no
    explicit row has been written. The threshold falls back to the
    university default review threshold."""
    out = dict(DEFAULTS)
    if not module_code:
        return out
    conn = _connect()
    if conn is None:
        return out
    try:
        from education_system.systems.university.application.integrity import (
            access as integrity_access,
        )
        out["similarity_threshold"] = integrity_access.module_threshold(conn, module_code)
        row = conn.execute(
            "SELECT ai_detection_enabled, plagiarism_enabled, allow_collaboration, notes "
            "FROM course_integrity_settings WHERE module_code = ?", (module_code,)).fetchone()
        if row:
            out["ai_detection_enabled"] = bool(row[0])
            out["plagiarism_enabled"] = bool(row[1])
            out["allow_collaboration"] = bool(row[2])
            out["notes"] = row[3] or ""
        return out
    except Exception as exc:
        logger.debug("get_course_integrity_settings failed: %s", exc)
        return out
    finally:
        conn.close()


def update_course_integrity_settings(module_code: str,
                                      updated_by: Optional[str] = None,
                                      **fields) -> bool:
    """Change a module's settings as *updated_by* (a username), who must be
    the module's staff or an integrity officer. *fields* is any subset of
    ``ai_detection_enabled``, ``plagiarism_enabled``,
    ``similarity_threshold``, ``allow_collaboration``, ``notes``.

    Returns True on success; raises PermissionError when not allowed."""
    if not module_code or not updated_by:
        return False
    current = get_course_integrity_settings(module_code)
    current.update({k: v for k, v in fields.items() if k in DEFAULTS})
    conn = _connect()
    if conn is None:
        return False
    try:
        from education_system.systems.university.application.integrity import (
            access as integrity_access,
        )
        who = integrity_access.person(conn, updated_by)
        integrity_access.set_module_settings(
            conn, who, module_code, enabled=current["plagiarism_enabled"],
            threshold=current["similarity_threshold"],
            allow_collaboration=current["allow_collaboration"], notes=current["notes"])
        conn.execute("UPDATE course_integrity_settings SET ai_detection_enabled = ? "
                     "WHERE module_code = ?", (1 if current["ai_detection_enabled"] else 0,
                                               module_code))
        conn.commit()
        return True
    except PermissionError:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        logger.error("update_course_integrity_settings failed: %s", exc)
        return False
    finally:
        conn.close()


def is_plagiarism_enabled(module_code: str) -> bool:
    return get_course_integrity_settings(module_code)["plagiarism_enabled"]


def is_ai_detection_enabled(module_code: str) -> bool:
    return get_course_integrity_settings(module_code)["ai_detection_enabled"]


def get_similarity_threshold(module_code: str) -> float:
    return float(get_course_integrity_settings(module_code)["similarity_threshold"])
