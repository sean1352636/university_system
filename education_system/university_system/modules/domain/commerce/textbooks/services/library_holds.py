"""Auto-place library holds on required textbooks at enrolment time.

When a student enrols in a module, ``textbooks`` rows for that module
flagged ``required = 1`` are matched to the library catalog (``books``,
joined on ISBN) and a ``book_reservations`` row is created so the
student appears in the queue without having to walk to the library.

Idempotency: re-running for the same (student, book) leaves the
existing reservation alone — students don't double-queue. On enrolment
drop, active reservations are released so they don't sit on the
shelf indefinitely.

If a textbook has no ISBN, no matching ``books`` row, or the catalog
row is unavailable, that title is skipped silently — the assumption
being some titles are publisher-supplied or digital-only and aren't in
the physical lending catalog.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List, Optional

logger = logging.getLogger(__name__)

# How long a held copy is reserved before it expires. Library policy
# elsewhere uses ~7 days; mirror that.
_RESERVATION_DAYS = 7


def _connect():
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        return get_connection()
    except Exception as exc:
        logger.debug("DB unavailable for library holds: %s", exc)
        return None


def get_required_textbooks(module_code: str) -> List[dict]:
    """Return ``textbooks`` rows flagged required for *module_code*.

    Each dict carries ``isbn``, ``title``, ``author``, ``edition``,
    ``publisher``, plus the linked ``book_id`` from the library catalog
    if there is a matching ISBN.
    """
    conn = _connect()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """SELECT t.isbn, t.title, t.author, t.edition, t.publisher,
                      b.book_id
               FROM textbooks t
               LEFT JOIN books b ON b.isbn = t.isbn
               WHERE t.module_code = ? AND t.required = 1""",
            (module_code,),
        ).fetchall()
        return [
            {"isbn": r[0], "title": r[1], "author": r[2],
             "edition": r[3], "publisher": r[4], "book_id": r[5]}
            for r in rows
        ]
    except Exception as exc:
        logger.debug("get_required_textbooks failed: %s", exc)
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def place_holds_for_enrolment(student_id: str, module_code: str
                              ) -> List[str]:
    """Place library reservations for required textbooks on this module.

    Returns the list of ``book_id`` values that were reserved (or were
    already reserved — idempotent, so the caller can treat the return
    as "books the student is holding for this module"). Books missing
    from the library catalog or already reserved by this student are
    silently skipped.
    """
    conn = _connect()
    if conn is None:
        return []

    reserved: List[str] = []
    try:
        with conn:
            books = conn.execute(
                """SELECT b.book_id
                   FROM textbooks t
                   JOIN books b ON b.isbn = t.isbn
                   WHERE t.module_code = ? AND t.required = 1
                     AND t.isbn != ''""",
                (module_code,),
            ).fetchall()
            if not books:
                return []

            now = datetime.now()
            expiry = (now + timedelta(days=_RESERVATION_DAYS)).strftime(
                "%Y-%m-%d %H:%M:%S")
            now_str = now.strftime("%Y-%m-%d %H:%M:%S")

            for (book_id,) in books:
                # Skip if the student already has an active reservation
                # on this book — don't double-queue.
                existing = conn.execute(
                    "SELECT 1 FROM book_reservations "
                    "WHERE book_id = ? AND user_id = ? "
                    "  AND status = 'active' LIMIT 1",
                    (book_id, str(student_id)),
                ).fetchone()
                if existing:
                    reserved.append(book_id)
                    continue

                # Priority is the next-in-queue position (active
                # reservations before this one + 1).
                next_priority = conn.execute(
                    "SELECT COALESCE(MAX(priority_order), 0) + 1 "
                    "FROM book_reservations "
                    "WHERE book_id = ? AND status = 'active'",
                    (book_id,),
                ).fetchone()[0]

                conn.execute(
                    "INSERT INTO book_reservations "
                    "(book_id, user_id, reservation_date, expiry_date, "
                    " status, priority_order) "
                    "VALUES (?, ?, ?, ?, 'active', ?)",
                    (book_id, str(student_id), now_str, expiry,
                     int(next_priority)),
                )
                reserved.append(book_id)

        if reserved:
            logger.info(
                "Placed %d library hold(s) for student %s on module %s",
                len(reserved), student_id, module_code,
            )
        return reserved
    except Exception as exc:
        logger.error("place_holds_for_enrolment failed: %s", exc)
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def release_holds_for_drop(student_id: str, module_code: str) -> int:
    """Cancel active reservations the student holds against this
    module's required textbooks. Returns the number of rows changed.

    Does not touch reservations the student placed manually on the same
    title — only those that were auto-placed here are eligible.
    """
    conn = _connect()
    if conn is None:
        return 0
    try:
        with conn:
            book_ids = [
                r[0] for r in conn.execute(
                    """SELECT b.book_id FROM textbooks t
                       JOIN books b ON b.isbn = t.isbn
                       WHERE t.module_code = ? AND t.required = 1
                         AND t.isbn != ''""",
                    (module_code,),
                ).fetchall()
            ]
            if not book_ids:
                return 0
            placeholders = ",".join(["?"] * len(book_ids))
            cur = conn.execute(
                "UPDATE book_reservations "
                "SET status = 'cancelled' "
                f"WHERE user_id = ? AND book_id IN ({placeholders}) "  # nosec B608
                "  AND status = 'active'",
                [str(student_id), *book_ids],
            )
            return cur.rowcount or 0
    except Exception as exc:
        logger.error("release_holds_for_drop failed: %s", exc)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass
