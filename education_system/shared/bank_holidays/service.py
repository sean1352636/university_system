"""Bank-holiday calendar service.

A tiny single-table store of (date, name, region) entries, used wherever the
codebase needs to know whether a particular date counts as a working day.
The service is read-mostly; ``set_holidays_for_year`` is the bulk-load entry
point used by the seed below.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_REGION = "england_and_wales"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS bank_holidays (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    holiday_date  TEXT    NOT NULL,
    name          TEXT    NOT NULL,
    region        TEXT    NOT NULL DEFAULT 'england_and_wales',
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(holiday_date, region)
);
CREATE INDEX IF NOT EXISTS idx_bank_holidays_date ON bank_holidays(holiday_date);
CREATE INDEX IF NOT EXISTS idx_bank_holidays_region ON bank_holidays(region);
"""

# Hard-coded UK England-and-Wales bank holidays for 2026 and 2027.
# Substitute days are pre-applied (e.g. 26 Dec 2026 falls on a Saturday →
# the substitute holiday is Mon 28 Dec 2026).
_SEED_2026: list[tuple[str, str]] = [
    ("2026-01-01", "New Year's Day"),
    ("2026-04-03", "Good Friday"),
    ("2026-04-06", "Easter Monday"),
    ("2026-05-04", "Early May bank holiday"),
    ("2026-05-25", "Spring bank holiday"),
    ("2026-08-31", "Summer bank holiday"),
    ("2026-12-25", "Christmas Day"),
    ("2026-12-28", "Boxing Day (substitute)"),
]
_SEED_2027: list[tuple[str, str]] = [
    ("2027-01-01", "New Year's Day"),
    ("2027-03-26", "Good Friday"),
    ("2027-03-29", "Easter Monday"),
    ("2027-05-03", "Early May bank holiday"),
    ("2027-05-31", "Spring bank holiday"),
    ("2027-08-30", "Summer bank holiday"),
    ("2027-12-27", "Christmas Day (substitute)"),
    ("2027-12-28", "Boxing Day (substitute)"),
]


def _default_db_path() -> Path:
    """Default to ``shared/data/db_files/bank_holidays.db``."""
    shared_root = Path(__file__).resolve().parent.parent
    db_dir = shared_root / "data" / "db_files"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "bank_holidays.db"


class BankHolidayService:
    """CRUD + lookup for bank holidays."""

    def __init__(self, db_path: str | Path | None = None):
        self._db_path = str(db_path) if db_path else str(_default_db_path())
        self._init_schema()
        self._seed_if_empty()

    # ------------------------------------------------------------------ infra
    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_schema(self) -> None:
        conn = self._conn()
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def _seed_if_empty(self) -> None:
        """Populate the canonical UK seed if the table is empty."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT COUNT(*) AS c FROM bank_holidays").fetchone()
            if row and row["c"] > 0:
                return
            for d, name in (*_SEED_2026, *_SEED_2027):
                conn.execute(
                    "INSERT OR IGNORE INTO bank_holidays "
                    "(holiday_date, name, region) VALUES (?, ?, ?)",
                    (d, name, DEFAULT_REGION),
                )
            conn.commit()
            logger.info("Seeded UK bank holidays for 2026/2027")
        except sqlite3.Error:
            logger.exception("Failed to seed bank holidays")
        finally:
            conn.close()

    # ------------------------------------------------------------------ reads
    def is_holiday(self, when: date | str, region: str = DEFAULT_REGION) -> bool:
        iso = when.isoformat() if isinstance(when, date) else when
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT 1 FROM bank_holidays "
                "WHERE holiday_date = ? AND region = ? LIMIT 1",
                (iso, region),
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def holidays_in_range(
        self,
        start: date | str,
        end: date | str,
        region: str = DEFAULT_REGION,
    ) -> list[dict]:
        s = start.isoformat() if isinstance(start, date) else start
        e = end.isoformat() if isinstance(end, date) else end
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM bank_holidays "
                "WHERE region = ? AND holiday_date BETWEEN ? AND ? "
                "ORDER BY holiday_date",
                (region, s, e),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def list_holidays(
        self,
        *,
        year: int | None = None,
        region: str = DEFAULT_REGION,
    ) -> list[dict]:
        conn = self._conn()
        try:
            if year is None:
                rows = conn.execute(
                    "SELECT * FROM bank_holidays WHERE region = ? "
                    "ORDER BY holiday_date",
                    (region,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM bank_holidays WHERE region = ? "
                    "AND holiday_date BETWEEN ? AND ? "
                    "ORDER BY holiday_date",
                    (region, f"{year}-01-01", f"{year}-12-31"),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def working_days_in_range(
        self,
        start: date | str,
        end: date | str,
        region: str = DEFAULT_REGION,
    ) -> int:
        """Return weekdays in [start, end] minus bank holidays."""
        s = (datetime.strptime(start, "%Y-%m-%d").date()
             if isinstance(start, str) else start)
        e = (datetime.strptime(end, "%Y-%m-%d").date()
             if isinstance(end, str) else end)
        if e < s:
            return 0
        holiday_dates = {h["holiday_date"]
                         for h in self.holidays_in_range(s, e, region=region)}
        days = 0
        cur = s
        while cur <= e:
            if cur.weekday() < 5 and cur.isoformat() not in holiday_dates:
                days += 1
            cur += timedelta(days=1)
        return days

    # ------------------------------------------------------------------ writes
    def add_holiday(
        self, when: date | str, name: str, region: str = DEFAULT_REGION,
    ) -> dict:
        iso = when.isoformat() if isinstance(when, date) else when
        conn = self._conn()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO bank_holidays "
                "(holiday_date, name, region) VALUES (?, ?, ?)",
                (iso, name, region),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM bank_holidays "
                "WHERE holiday_date = ? AND region = ?",
                (iso, region),
            ).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def remove_holiday(self, holiday_id: int) -> bool:
        conn = self._conn()
        try:
            cur = conn.execute(
                "DELETE FROM bank_holidays WHERE id = ?", (holiday_id,)
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()
