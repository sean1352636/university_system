"""Access grants driven by absence state — #46.

Records that a student may reach a session resource (a lecture recording,
say) because their absence was approved. Named ``lms_*`` for historical
reasons and unrelated to the retired internal LMS: it is keyed on
``module_code`` + ``session_date`` and owned by absence tracking, whose
own schema creates the table.

The optional push into ``services.lms.lms_core`` is gone with that
package — it was guarded by ``hasattr(_lms, "grant_access")`` and that
attribute never existed, so it had never done anything.
"""

from __future__ import annotations

import sqlite3

from .log import logger


# ===========================================================================
# LmsSyncService — #46
# ===========================================================================

class LmsSyncService:
    """Mirror approved absence requests as LMS access grants."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def grant_for_absence(self, student_id: str, module_code: str,
                          session_date: str,
                          resource: str = "lecture_recording",
                          reason: str = "approved absence") -> None:
        try:
            self.conn.execute(
                """INSERT OR IGNORE INTO lms_access_grants
                     (student_id, module_code, session_date, resource,
                      granted, reason)
                   VALUES(?,?,?,?,1,?)""",
                (student_id, module_code, session_date, resource, reason))
            self.conn.commit()
        except sqlite3.Error:
            self.conn.rollback()
            logger.exception("LMS grant insert failed sid=%s mc=%s",
                             student_id, module_code)
            return

    def sync_approved_requests(self) -> int:
        try:
            cur = self.conn.execute(
                """SELECT r.id, r.student_id, r.module_code, r.date
                   FROM absence_requests r
                   LEFT JOIN lms_access_grants g
                       ON g.student_id = r.student_id
                      AND g.module_code = r.module_code
                      AND g.session_date = r.date
                   WHERE r.status = 'approved' AND g.id IS NULL""")
            rows = cur.fetchall()
        except sqlite3.Error:
            logger.exception("lms sync query failed")
            return 0
        n = 0
        for _id, sid, mod, d in rows:
            self.grant_for_absence(sid, mod, d)
            n += 1
        logger.info("LMS sync mirrored %d grant(s)", n)
        return n


def lms_on_absence(conn, student_id, module_code, session_date,
                   resource: str = "lecture_recording",
                   reason: str = "approved absence") -> None:
    LmsSyncService(conn).grant_for_absence(
        student_id, module_code, session_date, resource, reason)


def lms_sync_approved_requests(conn) -> int:
    return LmsSyncService(conn).sync_approved_requests()


__all__ = [
    "LmsSyncService",
    "lms_on_absence",
    "lms_sync_approved_requests",
]
