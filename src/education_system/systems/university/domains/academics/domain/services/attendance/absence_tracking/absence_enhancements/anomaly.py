"""Anomaly detection: concurrency, shared devices, proxy — #50."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List

from .log import logger


# ===========================================================================
# AnomalyService — #50
# ===========================================================================

class AnomalyService:
    """Detect proxy sign-ins, impossible concurrency, mass identical reasons."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def scan(self) -> List[Dict[str, Any]]:
        new: List[Dict[str, Any]] = []
        new.extend(self._scan_concurrency())
        new.extend(self._scan_shared_devices())
        new.extend(self._scan_mass_identical_reasons())
        try:
            self.conn.commit()
        except sqlite3.Error:
            self.conn.rollback()
            logger.exception("anomaly commit failed")
        logger.info("anomaly scan inserted %d row(s)", len(new))
        return new

    def _scan_concurrency(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        try:
            rows = self.conn.execute(
                """SELECT a.student_id, a.date, GROUP_CONCAT(a.module_code)
                   FROM attendance a
                   WHERE a.status='present'
                   GROUP BY a.student_id, a.date
                   HAVING COUNT(DISTINCT a.module_code) > 1""").fetchall()
        except sqlite3.Error:
            logger.exception("concurrency anomaly scan failed")
            return out
        for sid, d, mods in rows:
            details = f"present in {mods} on {d}"
            try:
                r = self.conn.execute(
                    "INSERT INTO attendance_anomalies"
                    "(kind, student_id, details, severity) "
                    "VALUES('concurrency', ?, ?, 'high')",
                    (sid, details))
                out.append({"id": r.lastrowid, "kind": "concurrency",
                            "student_id": sid, "details": details})
            except sqlite3.Error:
                logger.exception("concurrency insert failed sid=%s", sid)
        return out

    def _scan_shared_devices(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        try:
            cur = self.conn.execute("PRAGMA table_info(attendance_records)")
            ar_cols = {r[1] for r in cur.fetchall()}
        except sqlite3.Error:
            logger.exception("attendance_records PRAGMA failed")
            return out
        if "location_data" not in ar_cols or "student_id" not in ar_cols:
            return out
        try:
            cur = self.conn.execute(
                """SELECT json_extract(location_data, '$.device_id') AS dev,
                          COUNT(DISTINCT student_id),
                          GROUP_CONCAT(DISTINCT student_id)
                   FROM attendance_records
                   WHERE location_data IS NOT NULL
                     AND json_extract(location_data, '$.device_id')
                         IS NOT NULL
                   GROUP BY dev
                   HAVING COUNT(DISTINCT student_id) >= 5""")
        except sqlite3.OperationalError:
            logger.debug("shared_device scan skipped (json1 unavailable)")
            return out
        for dev, n, sids in cur.fetchall():
            details = f"device {dev} used by {n} students: {sids}"
            try:
                r = self.conn.execute(
                    "INSERT INTO attendance_anomalies"
                    "(kind, details, severity) "
                    "VALUES('shared_device', ?, 'high')",
                    (details,))
                out.append({"id": r.lastrowid, "kind": "shared_device",
                            "details": details})
            except sqlite3.Error:
                logger.exception("shared_device insert failed dev=%s", dev)
        return out

    def _scan_mass_identical_reasons(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        try:
            rows = self.conn.execute(
                """SELECT date, reason, COUNT(DISTINCT student_id)
                   FROM attendance
                   WHERE reason IS NOT NULL AND reason != ''
                   GROUP BY date, reason
                   HAVING COUNT(DISTINCT student_id) >= 10""").fetchall()
        except sqlite3.Error:
            logger.exception("mass_proxy scan failed")
            return out
        for d, reason, n in rows:
            details = (f"{n} students share identical reason "
                       f"'{reason[:40]}' on {d}")
            try:
                r = self.conn.execute(
                    "INSERT INTO attendance_anomalies"
                    "(kind, details, severity) "
                    "VALUES('mass_proxy_reason', ?, 'medium')",
                    (details,))
                out.append({"id": r.lastrowid,
                            "kind": "mass_proxy_reason",
                            "details": details})
            except sqlite3.Error:
                logger.exception("mass_proxy insert failed")
        return out


def anomaly_scan(conn) -> List[Dict[str, Any]]:
    return AnomalyService(conn).scan()


__all__ = [
    "AnomalyService",
    "anomaly_scan",
]
