"""Bridge between scheduled exams and the external examiners module.

The exam scheduler used to track a single internal instructor per exam.
External examiners — appointed academics from other institutions who
review modules and assessments for quality assurance — were tracked in
a sibling module with no link. This shim exposes a small linking table
so an exam can be associated with one or more external examiners
without duplicating their details on the exam row.

Storage: a single auxiliary table ``exam_external_examiners`` is created
on demand. ``role`` is free-text (e.g. ``"Chief Examiner"``,
``"Reader"``); leave blank for unspecified.

External examiners themselves are owned by
:class:`ExternalExaminerService`; we only manage the link.
"""

from __future__ import annotations

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

_LINK_DDL = """
CREATE TABLE IF NOT EXISTS exam_external_examiners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id INTEGER NOT NULL,
    examiner_id INTEGER NOT NULL,
    role TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE (exam_id, examiner_id)
)
"""


def _connect():
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        # Make sure the linking table exists. Cheap idempotent DDL.
        conn.execute(_LINK_DDL)
        conn.commit()
        return conn
    except Exception as exc:
        logger.debug("DB unavailable for external examiner links: %s", exc)
        return None


def _examiner_pk_column(conn) -> str:
    """Return the actual PK column name on external_examiners.

    Older deployments use ``examiner_id`` while the service's ad-hoc
    ``CREATE TABLE IF NOT EXISTS`` would use ``id``. We detect at runtime
    so the JOIN works against either layout.
    """
    try:
        cols = {r[1] for r in conn.execute(
            "PRAGMA table_info(external_examiners)").fetchall()}
        return "examiner_id" if "examiner_id" in cols else "id"
    except Exception:
        return "id"


def _service():
    """Return an ExternalExaminerService instance, or None on import failure."""
    try:
        from education_system.university_system.modules.domain.academics.external_examiners.services.external_examiner_service import (
            ExternalExaminerService,
        )
        return ExternalExaminerService()
    except Exception as exc:
        logger.debug("ExternalExaminerService unavailable: %s", exc)
        return None


# ── Public service API ──────────────────────────────────────────────────


def list_active_examiners() -> List[Dict]:
    """Return ``[{id, name, institution, specialisation, ...}, ...]``.

    Falls back to all examiners (any status) if the service doesn't
    enforce a status field.
    """
    svc = _service()
    if svc is None:
        return []
    try:
        return svc.list_examiners(status="active") or svc.list_examiners()
    except TypeError:
        try:
            return svc.list_examiners()
        except Exception:
            return []
    except Exception as exc:
        logger.debug("list_active_examiners failed: %s", exc)
        return []


def attach_examiner(exam_id: int, examiner_id: int,
                    role: str = "") -> bool:
    """Link an examiner to an exam. Idempotent (UNIQUE on the pair)."""
    conn = _connect()
    if conn is None:
        return False
    try:
        with conn:
            conn.execute(
                "INSERT OR IGNORE INTO exam_external_examiners "
                "(exam_id, examiner_id, role) VALUES (?, ?, ?)",
                (int(exam_id), int(examiner_id), role or ""),
            )
        return True
    except Exception as exc:
        logger.error("attach_examiner failed: %s", exc)
        return False


def detach_examiner(exam_id: int, examiner_id: int) -> bool:
    conn = _connect()
    if conn is None:
        return False
    try:
        with conn:
            conn.execute(
                "DELETE FROM exam_external_examiners "
                "WHERE exam_id = ? AND examiner_id = ?",
                (int(exam_id), int(examiner_id)),
            )
        return True
    except Exception as exc:
        logger.error("detach_examiner failed: %s", exc)
        return False


def list_examiners_for_exam(exam_id: int) -> List[Dict]:
    """Return the list of examiners attached to *exam_id*, joined to the
    examiner's master record so the caller has name/institution."""
    conn = _connect()
    if conn is None:
        return []
    try:
        pk = _examiner_pk_column(conn)
        # Schema differs between deployments: some have `specialisation`,
        # some have `expertise_area`. Build the SELECT defensively.
        ee_cols = {r[1] for r in conn.execute(
            "PRAGMA table_info(external_examiners)").fetchall()}
        spec_expr = (
            "ee.specialisation" if "specialisation" in ee_cols
            else ("ee.expertise_area" if "expertise_area" in ee_cols
                  else "''")
        )
        rows = conn.execute(
            f"""SELECT l.examiner_id, l.role, l.created_at,
                       ee.name, ee.institution, ee.email,
                       {spec_expr} AS specialisation
                FROM exam_external_examiners l
                JOIN external_examiners ee ON ee.{pk} = l.examiner_id
                WHERE l.exam_id = ?
                ORDER BY ee.name""",
            (int(exam_id),),
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:
        logger.debug("list_examiners_for_exam failed: %s", exc)
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def list_exams_for_examiner(examiner_id: int) -> List[Dict]:
    """Return scheduled exams an external examiner is attached to."""
    conn = _connect()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """SELECT l.role, e.id, e.module_code, e.module_name,
                      e.date, e.start_time, e.end_time, e.room
               FROM exam_external_examiners l
               JOIN exams e ON e.id = l.exam_id
               WHERE l.examiner_id = ?
               ORDER BY e.date, e.start_time""",
            (int(examiner_id),),
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:
        logger.debug("list_exams_for_examiner failed: %s", exc)
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass
