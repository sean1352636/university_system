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

from education_system.paths import (
    PLATFORM_AUTH_DB,
    SYSTEM_DB_PATHS,
    SYSTEM_LABELS,
    SYSTEM_LEARNER_TABLE,
    SYSTEM_ORDER,
)

logger = logging.getLogger(__name__)

# Local learner table per system. Derived from the one registry rather than
# restated here — apprenticeships keeps ``apprentices``, so the old "pupils
# for K-12, students for everyone else" rule no longer holds.
_STUDENT_TABLE = {s: t for s, (t, _id) in SYSTEM_LEARNER_TABLE.items()}


class Warehouse:
    """Cross-system read-only aggregation over all attached databases."""

    def __init__(self, db_paths=None, auth_db=None):
        paths = db_paths if db_paths is not None else SYSTEM_DB_PATHS
        self._db_paths = {s: Path(p) for s, p in paths.items()}
        self._order = [s for s in SYSTEM_ORDER if s in self._db_paths]
        self._auth_db = Path(auth_db) if auth_db is not None else Path(PLATFORM_AUTH_DB)

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

    def _slot_columns(self, conn) -> dict[str, str]:
        """``{system: student-id column}`` for the slots this DB actually has.

        Read from ``identity_service.SYSTEM_SLOTS`` so all seven systems are
        covered. The local table used to stop at five while ``SYSTEM_ORDER``
        grew to seven, so the funnel raised KeyError on ``fe_college``.
        """
        from education_system.platform.cross_system.identity_service import SYSTEM_SLOTS
        have = {r[1] for r in conn.execute("PRAGMA table_info(student_journey)")}
        return {s: col for s, (_pk, col) in SYSTEM_SLOTS.items() if col in have}

    def retention_funnel(self) -> dict:
        """How many journeys have *reached* each phase (slot populated)."""
        funnel = {}
        try:
            conn = self._journey_conn()
        except sqlite3.Error:
            return funnel
        try:
            slots = self._slot_columns(conn)
            total = conn.execute(
                "SELECT COUNT(*) FROM student_journey").fetchone()[0]
            for system in SYSTEM_ORDER:
                col = slots.get(system)
                n = conn.execute(
                    f"SELECT COUNT(*) FROM student_journey "  # nosec B608
                    f"WHERE {col} IS NOT NULL").fetchone()[0] if col else 0
                funnel[system] = {
                    "label": SYSTEM_LABELS.get(system, system),
                    "reached": n,
                    "pct_of_total": round(100.0 * n / total, 1) if total else 0.0,
                }
        finally:
            conn.close()
        funnel["_total_journeys"] = total
        return funnel

    #: The moves learners actually make. SYSTEM_ORDER is a reading order,
    #: not a chain — FE college and apprenticeships sit beside sixth form —
    #: so pairing neighbours in it reported "sixth_form -> fe_college" as a
    #: progression and lost "sixth_form -> university" entirely.
    PROGRESSION_PAIRS: tuple[tuple[str, str], ...] = (
        ("nursery", "primary"),
        ("primary", "secondary"),
        ("secondary", "sixth_form"),
        ("secondary", "fe_college"),
        ("secondary", "apprenticeships"),
        ("sixth_form", "university"),
        ("sixth_form", "apprenticeships"),
        ("fe_college", "university"),
        ("fe_college", "apprenticeships"),
        ("apprenticeships", "university"),
    )

    def progression_rates(self) -> dict:
        """Of the journeys that reached phase A, the % that also reached B."""
        rates = {f"{a}->{b}": 0.0 for a, b in self.PROGRESSION_PAIRS}
        try:
            conn = self._journey_conn()
        except sqlite3.Error:
            return rates
        try:
            slots = self._slot_columns(conn)
            for a, b in self.PROGRESSION_PAIRS:
                ca, cb = slots.get(a), slots.get(b)
                if not ca or not cb:
                    continue
                ra = conn.execute(
                    f"SELECT COUNT(*) FROM student_journey WHERE {ca} IS NOT NULL"  # nosec B608
                ).fetchone()[0]
                both = conn.execute(
                    f"SELECT COUNT(*) FROM student_journey "  # nosec B608
                    f"WHERE {ca} IS NOT NULL AND {cb} IS NOT NULL").fetchone()[0]
                rates[f"{a}->{b}"] = round(100.0 * both / ra, 1) if ra else 0.0
        except sqlite3.Error:
            logger.debug("Progression rates unavailable", exc_info=True)
        finally:
            conn.close()
        return rates

    def progression_statistics(self, year=None) -> dict:
        """All-systems progression flow, boundaries and destination outcomes."""
        from education_system.platform.features.analytics.journey_analytics import (
            progression_statistics,
        )
        return progression_statistics(year=year, db_path=str(self._auth_db))

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
