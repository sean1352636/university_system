"""Read-only cross-system reporting warehouse.

Each system owns its own SQLite file, so no single connection can answer
"how many learners progressed nursery → university?" or "what's our
headcount across all phases?". This module ATTACHes all five system
databases (read-only) onto one connection, and reads the canonical
``student_journey`` registry for progression/retention — enabling org-wide
questions no single system can answer.

Everything is read-only (databases are attached with ``mode=ro``) and
defensive: a missing system database is skipped, not fatal.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from education_system.platform.kernel.database.paths import (
    AUTH_DB,
    SYSTEM_DB_PATHS,
    SYSTEM_LABELS,
    SYSTEM_ORDER,
)

logger = logging.getLogger(__name__)

# Local student/pupil table per system.
_STUDENT_TABLE = {
    "nursery": "pupils", "primary": "pupils", "secondary": "pupils",
    "sixth_form": "students", "university": "students",
}


class Warehouse:
    """Cross-system read-only aggregation over all attached databases."""

    def __init__(self, db_paths=None, auth_db=None):
        paths = db_paths if db_paths is not None else SYSTEM_DB_PATHS
        self._db_paths = {s: Path(p) for s, p in paths.items()}
        self._order = [s for s in SYSTEM_ORDER if s in self._db_paths]
        self._auth_db = Path(auth_db) if auth_db is not None else Path(AUTH_DB)

    # ------------------------------------------------------------------

    @contextmanager
    def _attached(self):
        """A connection with every existing system DB attached read-only."""
        conn = sqlite3.connect(":memory:", uri=True)
        conn.row_factory = sqlite3.Row
        attached = []
        try:
            for system in self._order:
                path = self._db_paths.get(system)
                if not path or not path.exists():
                    continue
                try:
                    conn.execute(
                        f"ATTACH DATABASE ? AS {system}",
                        (f"file:{path}?mode=ro",))
                    attached.append(system)
                except sqlite3.Error:
                    logger.debug("Could not attach %s (%s)", system, path,
                                 exc_info=True)
            self._attached_systems = attached
            yield conn, attached
        finally:
            conn.close()

    @staticmethod
    def _table_in(conn, alias, table) -> bool:
        try:
            row = conn.execute(
                f"SELECT 1 FROM {alias}.sqlite_master "
                "WHERE type='table' AND name=?", (table,)).fetchone()
            return row is not None
        except sqlite3.Error:
            return False

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------

    def headcount_by_system(self) -> dict:
        """Live local headcount per system (rows in its pupil/student table)."""
        out = {}
        with self._attached() as (conn, attached):
            for system in attached:
                table = _STUDENT_TABLE.get(system)
                if not table or not self._table_in(conn, system, table):
                    continue
                try:
                    n = conn.execute(
                        f"SELECT COUNT(*) FROM {system}.{table}").fetchone()[0]
                except sqlite3.Error:
                    continue
                out[system] = {"label": SYSTEM_LABELS.get(system, system),
                               "headcount": n}
        return out

    def _journey_conn(self):
        conn = sqlite3.connect(f"file:{self._auth_db}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def retention_funnel(self) -> dict:
        """How many journeys have *reached* each phase (slot populated)."""
        slots = {
            "nursery": "nursery_student_id", "primary": "primary_student_id",
            "secondary": "school_student_id", "sixth_form": "college_student_id",
            "university": "university_student_id",
        }
        funnel = {}
        try:
            conn = self._journey_conn()
        except sqlite3.Error:
            return funnel
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM student_journey").fetchone()[0]
            for system in SYSTEM_ORDER:
                col = slots[system]
                n = conn.execute(
                    f"SELECT COUNT(*) FROM student_journey "
                    f"WHERE {col} IS NOT NULL").fetchone()[0]
                funnel[system] = {
                    "label": SYSTEM_LABELS.get(system, system),
                    "reached": n,
                    "pct_of_total": round(100.0 * n / total, 1) if total else 0.0,
                }
        finally:
            conn.close()
        funnel["_total_journeys"] = total
        return funnel

    def progression_rates(self) -> dict:
        """Phase-to-phase conversion: of those who reached phase N, what
        fraction went on to phase N+1."""
        funnel = self.retention_funnel()
        rates = {}
        for i in range(len(SYSTEM_ORDER) - 1):
            a, b = SYSTEM_ORDER[i], SYSTEM_ORDER[i + 1]
            ra = funnel.get(a, {}).get("reached", 0)
            rb = funnel.get(b, {}).get("reached", 0)
            rates[f"{a}->{b}"] = round(100.0 * rb / ra, 1) if ra else 0.0
        return rates

    def summary(self) -> dict:
        """One call for a dashboard: headcounts, retention funnel, rates."""
        with self._attached() as (_conn, attached):
            attached_systems = list(attached)
        return {
            "attached_systems": attached_systems,
            "headcount": self.headcount_by_system(),
            "retention_funnel": self.retention_funnel(),
            "progression_rates": self.progression_rates(),
        }


__all__ = ["Warehouse"]
