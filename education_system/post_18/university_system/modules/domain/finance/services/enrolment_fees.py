"""Tuition / module fee assessment driven by enrolment events.

When a student enrols in a module the rest of the system writes one row
to ``student_modules``. This service mirrors that into the finance
domain: looking up an applicable ``program_fees`` row for the module
(and academic year, if specified) and inserting a matching ``unpaid``
row into ``student_fees``. Drops cancel the unpaid assessment without
touching anything that's already been paid — refunds are a separate
concern.

Idempotency: re-assessing the same (student, module, academic_year)
won't produce a duplicate ``student_fees`` row. The match key is the
``fee_type_id`` from the resolved ``program_fees`` row plus the student;
re-running just leaves the existing row alone.

If no ``program_fees`` row matches the module, the assessment is a
no-op (returns ``None``). This is the intended state for free or
unmetered modules; populate ``program_fees`` to start charging.
"""

from __future__ import annotations

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


def _connect():
    try:
        from education_system.post_18.university_system.infrastructure.database.db import get_connection
        return get_connection()
    except Exception as exc:
        logger.debug("DB unavailable for enrolment fee service: %s", exc)
        return None


def _resolve_program_fees(conn, module_code: str,
                          academic_year: Optional[str]) -> List[dict]:
    """Return ``program_fees`` rows that match this enrolment.

    ``program_fees.course`` is a free-text field; we match it against
    either ``module_code`` or the parent course's ``code`` so admins can
    assess fees per-module or per-course as suits them. When
    *academic_year* is given, only fees for that year are returned;
    otherwise rows with NULL ``academic_year`` (i.e. evergreen) match.
    """
    # Try to also resolve to a course code so per-course fees are picked up.
    try:
        cur = conn.execute(
            "SELECT COALESCE(c.code, c.course_code) FROM courses c "
            "WHERE c.code = ? OR c.course_code = ? "
            "LIMIT 1",
            (module_code, module_code),
        )
        row = cur.fetchone()
        course_code = row[0] if row else None
    except Exception:
        course_code = None

    candidates = [module_code]
    if course_code and course_code != module_code:
        candidates.append(course_code)

    placeholders = ",".join(["?"] * len(candidates))
    sql = (
        "SELECT program_fee_id, fee_type_id, amount, currency, "
        "       due_date, academic_year "
        "FROM program_fees "
        f"WHERE course IN ({placeholders})"  # nosec B608
    )
    params: List = list(candidates)
    if academic_year:
        sql += " AND (academic_year = ? OR academic_year IS NULL)"
        params.append(academic_year)

    try:
        rows = conn.execute(sql, params).fetchall()
    except Exception as exc:
        logger.debug("program_fees lookup failed: %s", exc)
        return []

    return [
        {
            "program_fee_id": r[0],
            "fee_type_id": r[1],
            "amount": r[2],
            "currency": r[3],
            "due_date": r[4],
            "academic_year": r[5],
        }
        for r in rows
    ]


def assess_module_enrolment_fee(student_id: str, module_code: str,
                                academic_year: Optional[str] = None
                                ) -> List[int]:
    """Create ``student_fees`` rows for an enrolment. Returns the list of
    new ``student_fee_id`` values. Idempotent: if a row already exists
    for the same (student, fee_type, academic_year) it's left alone.
    """
    conn = _connect()
    if conn is None:
        return []

    created: List[int] = []
    try:
        with conn:
            fees = _resolve_program_fees(conn, module_code, academic_year)
            if not fees:
                return []

            for fee in fees:
                # Skip if this fee was already assessed for the student.
                # We dedupe on (student_id, fee_type_id, academic_year)
                # so two enrolments in different academic years can each
                # be assessed but a duplicate enrolment doesn't double-bill.
                if fee["academic_year"]:
                    existing = conn.execute(
                        "SELECT 1 FROM student_fees sf "
                        "JOIN program_fees pf "
                        "  ON pf.fee_type_id = sf.fee_type_id "
                        "WHERE sf.student_id = ? "
                        "  AND sf.fee_type_id = ? "
                        "  AND COALESCE(pf.academic_year,'') = ? "
                        "  AND sf.status != 'cancelled' LIMIT 1",
                        (student_id, fee["fee_type_id"],
                         fee["academic_year"] or ""),
                    ).fetchone()
                else:
                    existing = conn.execute(
                        "SELECT 1 FROM student_fees "
                        "WHERE student_id = ? "
                        "  AND fee_type_id = ? "
                        "  AND status != 'cancelled' LIMIT 1",
                        (student_id, fee["fee_type_id"]),
                    ).fetchone()

                if existing:
                    continue

                cur = conn.execute(
                    "INSERT INTO student_fees "
                    "(student_id, fee_type_id, amount, currency, "
                    " status, due_date, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, 'unpaid', ?, "
                    " datetime('now'), datetime('now'))",
                    (student_id, fee["fee_type_id"], fee["amount"],
                     fee["currency"] or "GBP", fee["due_date"]),
                )
                if cur.lastrowid:
                    created.append(int(cur.lastrowid))
        if created:
            logger.info(
                "Assessed %d fee(s) for student %s on module %s",
                len(created), student_id, module_code,
            )
            # Auto-post AR + revenue to GL for each new fee (never raises)
            try:
                from education_system.post_18.university_system.modules.domain.finance.ledger import notify_ledger
                for fid in created:
                    notify_ledger('fee_assignment', fid, posted_by='enrolment_fees')
            except Exception as _e:
                logger.warning("ledger hook failed: %s", _e)
        return created
    except Exception as exc:
        logger.error("assess_module_enrolment_fee failed: %s", exc)
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def cancel_module_enrolment_fee(student_id: str, module_code: str,
                                academic_year: Optional[str] = None
                                ) -> int:
    """Mark unpaid fee assessments for this enrolment as ``cancelled``.

    Returns the number of rows changed. Paid rows are left alone — drops
    after payment go through the refund flow, not here.
    """
    conn = _connect()
    if conn is None:
        return 0
    try:
        with conn:
            fees = _resolve_program_fees(conn, module_code, academic_year)
            if not fees:
                return 0
            fee_type_ids = [f["fee_type_id"] for f in fees]
            placeholders = ",".join(["?"] * len(fee_type_ids))
            cur = conn.execute(
                "UPDATE student_fees "
                "SET status = 'cancelled', updated_at = datetime('now') "
                f"WHERE student_id = ? AND fee_type_id IN ({placeholders}) "  # nosec B608
                "  AND status = 'unpaid'",
                [student_id, *fee_type_ids],
            )
            return cur.rowcount or 0
    except Exception as exc:
        logger.error("cancel_module_enrolment_fee failed: %s", exc)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass
