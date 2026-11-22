"""Absence quota answers for the chatbot — #49."""

from __future__ import annotations

import math
import sqlite3
from typing import Optional

from .log import logger


# ===========================================================================
# ChatbotService — #49
# ===========================================================================

class ChatbotService:
    """Computes per-module / per-student remaining-absences quota."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def absence_quota(self, student_id: str,
                      module_code: Optional[str] = None,
                      threshold_pct: float = 75.0) -> str:
        if module_code:
            return self._single_module(student_id, module_code, threshold_pct)
        return self._all_modules(student_id, threshold_pct)

    def _single_module(self, sid: str, mc: str, threshold_pct: float) -> str:
        try:
            row = self.conn.execute(
                """SELECT COUNT(*),
                          SUM(CASE WHEN status='present' THEN 1 ELSE 0 END),
                          SUM(CASE WHEN status='absent'  THEN 1 ELSE 0 END)
                   FROM attendance
                   WHERE student_id=? AND module_code=?""",
                (sid, mc)).fetchone() or (0, 0, 0)
        except sqlite3.Error:
            logger.exception("quota single fetch failed sid=%s mc=%s",
                             sid, mc)
            return f"Could not load attendance for {mc}."
        total, present, absent = row
        if not total:
            return f"No attendance recorded yet for {mc}."
        pct = 100.0 * (present or 0) / total
        max_absences = math.floor(total * (1 - threshold_pct / 100.0))
        remaining = max(0, max_absences - (absent or 0))
        return (f"{mc}: {pct:.1f}% attended. "
                f"Threshold {threshold_pct:.0f}% → you can miss "
                f"{remaining} more session(s) before falling below.")

    def _all_modules(self, sid: str, threshold_pct: float) -> str:
        try:
            rows = self.conn.execute(
                """SELECT module_code,
                          COUNT(*),
                          SUM(CASE WHEN status='present' THEN 1 ELSE 0 END),
                          SUM(CASE WHEN status='absent'  THEN 1 ELSE 0 END)
                   FROM attendance
                   WHERE student_id=?
                   GROUP BY module_code""", (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("quota all fetch failed sid=%s", sid)
            return "Could not load attendance."
        lines = []
        for mod, total, present, absent in rows:
            if not total:
                continue
            max_abs = math.floor(total * (1 - threshold_pct / 100.0))
            rem = max(0, max_abs - (absent or 0))
            pct = 100.0 * (present or 0) / total
            lines.append(f"  • {mod}: {pct:.0f}% — {rem} more misses OK")
        if not lines:
            return "No attendance recorded yet."
        return "Attendance quota remaining:\n" + "\n".join(lines)


def chatbot_absence_quota(conn, student_id: str,
                          module_code: Optional[str] = None,
                          threshold_pct: float = 75.0) -> str:
    return ChatbotService(conn).absence_quota(
        student_id, module_code, threshold_pct)


__all__ = [
    "ChatbotService",
    "chatbot_absence_quota",
]
