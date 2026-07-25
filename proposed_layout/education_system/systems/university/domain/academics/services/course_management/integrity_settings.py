"""Per-course integrity toggles (AI detection, plagiarism, collaboration).

Different courses have different academic-integrity expectations: a
group-coursework module may legitimately allow collaboration that would
be flagged in a closed-book essay. This service stores the per-course
policy in a lightweight ``course_integrity_settings`` table (created on
demand) and exposes ``is_*_enabled`` helpers the actual detector code
calls before running.

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

_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS course_integrity_settings (
    module_code TEXT PRIMARY KEY,
    ai_detection_enabled INTEGER DEFAULT 1,
    plagiarism_enabled INTEGER DEFAULT 1,
    similarity_threshold REAL DEFAULT 0.3,
    allow_collaboration INTEGER DEFAULT 0,
    notes TEXT,
    updated_at TEXT DEFAULT (datetime('now')),
    updated_by TEXT
)
"""

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
        from education_system.systems.university.infrastructure.database.db import get_connection
        conn = get_connection()
        conn.execute(_TABLE_DDL)
        conn.commit()
        return conn
    except Exception as exc:
        logger.debug("DB unavailable for integrity settings: %s", exc)
        return None


def get_course_integrity_settings(module_code: str) -> Dict:
    """Return the integrity policy for *module_code*, or DEFAULTS if no
    explicit row has been written. Returned dict always has every key
    present so callers can read fields unconditionally."""
    out = dict(DEFAULTS)
    if not module_code:
        return out
    conn = _connect()
    if conn is None:
        return out
    try:
        row = conn.execute(
            "SELECT ai_detection_enabled, plagiarism_enabled, "
            "       similarity_threshold, allow_collaboration, notes "
            "FROM course_integrity_settings WHERE module_code = ?",
            (module_code,),
        ).fetchone()
        if row:
            out["ai_detection_enabled"] = bool(row[0])
            out["plagiarism_enabled"] = bool(row[1])
            out["similarity_threshold"] = float(row[2]) if row[2] is not None else DEFAULTS["similarity_threshold"]
            out["allow_collaboration"] = bool(row[3])
            out["notes"] = row[4] or ""
        return out
    except Exception as exc:
        logger.debug("get_course_integrity_settings failed: %s", exc)
        return out
    finally:
        try:
            conn.close()
        except Exception:
            pass


def update_course_integrity_settings(module_code: str,
                                      updated_by: Optional[str] = None,
                                      **fields) -> bool:
    """Upsert the per-course settings. *fields* is any subset of:
    ``ai_detection_enabled``, ``plagiarism_enabled``,
    ``similarity_threshold``, ``allow_collaboration``, ``notes``.

    Returns True on success.
    """
    if not module_code:
        return False
    allowed = set(DEFAULTS.keys())
    sanitized = {k: v for k, v in fields.items() if k in allowed}
    if not sanitized:
        return False

    conn = _connect()
    if conn is None:
        return False
    try:
        with conn:
            # Coerce bools to int for SQLite
            for k in ("ai_detection_enabled", "plagiarism_enabled",
                      "allow_collaboration"):
                if k in sanitized:
                    sanitized[k] = 1 if sanitized[k] else 0

            existing = conn.execute(
                "SELECT 1 FROM course_integrity_settings WHERE module_code = ?",
                (module_code,),
            ).fetchone()
            if existing:
                set_parts = ", ".join(f"{k} = ?" for k in sanitized)
                params = list(sanitized.values()) + [
                    "datetime('now')", updated_by or "", module_code,
                ]
                # We can't bind datetime('now') as a placeholder; use a
                # literal in the SET clause instead.
                conn.execute(
                    f"UPDATE course_integrity_settings "  # nosec B608
                    f"SET {set_parts}, updated_at = datetime('now'), "
                    f"    updated_by = ? "
                    f"WHERE module_code = ?",
                    list(sanitized.values()) + [updated_by or "", module_code],
                )
            else:
                # Fill any missing fields with defaults
                full = dict(DEFAULTS)
                full.update(sanitized)
                full["allow_collaboration"] = 1 if full["allow_collaboration"] else 0
                full["ai_detection_enabled"] = 1 if full["ai_detection_enabled"] else 0
                full["plagiarism_enabled"] = 1 if full["plagiarism_enabled"] else 0
                conn.execute(
                    "INSERT INTO course_integrity_settings "
                    "(module_code, ai_detection_enabled, "
                    " plagiarism_enabled, similarity_threshold, "
                    " allow_collaboration, notes, updated_by) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (module_code, full["ai_detection_enabled"],
                     full["plagiarism_enabled"],
                     full["similarity_threshold"],
                     full["allow_collaboration"],
                     full["notes"], updated_by or ""),
                )
        logger.info(
            "Integrity settings updated for %s: %s", module_code,
            ", ".join(f"{k}={sanitized[k]}" for k in sanitized),
        )
        return True
    except Exception as exc:
        logger.error("update_course_integrity_settings failed: %s", exc)
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def is_plagiarism_enabled(module_code: str) -> bool:
    return get_course_integrity_settings(module_code)["plagiarism_enabled"]


def is_ai_detection_enabled(module_code: str) -> bool:
    return get_course_integrity_settings(module_code)["ai_detection_enabled"]


def get_similarity_threshold(module_code: str) -> float:
    return float(get_course_integrity_settings(module_code)["similarity_threshold"])
