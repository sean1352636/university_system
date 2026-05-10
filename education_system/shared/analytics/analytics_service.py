"""Cross-system analytics service.

Queries all 4 education system databases (primary, secondary, college,
university) to compute aggregate analytics: total students per system,
transfer rates, average time in each system, retention rates, status
breakdowns, and year-over-year trends.
"""

import csv
import io
import logging
import sqlite3
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


def _default_db_paths():
    """Return a dict of system -> default database Path."""
    shared_dir = Path(__file__).resolve().parent.parent  # .../shared
    edu_root = shared_dir.parent  # .../education_system
    return {
        "university": edu_root / "university_system" / "data" / "db_files" / "student_records.db",
    }


def _table_exists(conn, table_name):
    """Check whether *table_name* exists in the SQLite database."""
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row[0] > 0


def _get_columns(conn, table_name):
    """Return the set of column names for *table_name*."""
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {r[1] for r in rows}


SYSTEM_LABELS = {
    "university": "University",
}

SYSTEM_ORDER = ["primary", "secondary", "college", "university"]


class AnalyticsService:
    """Aggregates analytics across all 4 education system databases."""

    def __init__(self, primary_db=None, secondary_db=None, college_db=None, university_db=None):
        defaults = _default_db_paths()
        self._db_paths = {
            "university": Path(university_db) if university_db else defaults["university"],
        }

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _connect(self, system):
        """Open a read-only connection to a system DB.  Returns None if missing."""
        path = self._db_paths.get(system)
        if not path or not path.exists():
            return None
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        return conn

    def _student_table(self, system):
        """Return the main student table name for a system."""
        return "pupils" if system == "primary" else "students"

    def _id_column(self, system, columns):
        """Return the best ID column name for a student table."""
        if system == "primary":
            return "pupil_id" if "pupil_id" in columns else "id"
        return "student_id" if "student_id" in columns else "id"

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def get_summary(self):
        """Return a summary dict with totals across all systems.

        Keys: total_students, total_active, total_transferred,
              total_graduated, systems (list of per-system dicts).
        """
        total_students = 0
        total_active = 0
        total_transferred = 0
        total_graduated = 0
        systems = []

        for sys_key in SYSTEM_ORDER:
            info = self._count_students(sys_key)
            systems.append(info)
            total_students += info["total"]
            total_active += info["active"]
            total_transferred += info["transferred"]
            total_graduated += info["graduated"]

        return {
            "total_students": total_students,
            "total_active": total_active,
            "total_transferred": total_transferred,
            "total_graduated": total_graduated,
            "systems": systems,
        }

    def get_transfer_rates(self):
        """Return transfer flow data between systems.

        Returns a list of dicts with keys:
            source_system, destination_system, count, rate_pct
        """
        results = []
        for sys_key in SYSTEM_ORDER:
            conn = self._connect(sys_key)
            if not conn:
                continue
            try:
                if not _table_exists(conn, "academic_transfer_history"):
                    continue
                cols = _get_columns(conn, "academic_transfer_history")

                source_col = None
                for c in ("source_system", "from_system", "previous_system"):
                    if c in cols:
                        source_col = c
                        break

                dest_col = None
                for c in ("destination_system", "to_system", "current_system"):
                    if c in cols:
                        dest_col = c
                        break

                if not source_col and not dest_col:
                    continue

                # Count transfers grouped by source -> destination
                if source_col and dest_col:
                    rows = conn.execute(
                        f"SELECT {source_col} AS src, {dest_col} AS dst, COUNT(*) AS cnt "
                        f"FROM academic_transfer_history GROUP BY {source_col}, {dest_col}"
                    ).fetchall()
                elif dest_col:
                    rows = conn.execute(
                        f"SELECT '{sys_key}' AS src, {dest_col} AS dst, COUNT(*) AS cnt "
                        f"FROM academic_transfer_history GROUP BY {dest_col}"
                    ).fetchall()
                else:
                    rows = conn.execute(
                        f"SELECT {source_col} AS src, '{sys_key}' AS dst, COUNT(*) AS cnt "
                        f"FROM academic_transfer_history GROUP BY {source_col}"
                    ).fetchall()

                total = sum(r["cnt"] for r in rows) or 1
                for r in rows:
                    results.append({
                        "source_system": r["src"] or sys_key,
                        "destination_system": r["dst"] or sys_key,
                        "count": r["cnt"],
                        "rate_pct": round(r["cnt"] / total * 100, 1),
                    })
            except Exception as e:
                logger.warning("Error querying transfer rates for %s: %s", sys_key, e)
            finally:
                conn.close()

        # Also count students with previous_system_id as implicit transfers
        for sys_key in SYSTEM_ORDER:
            conn = self._connect(sys_key)
            if not conn:
                continue
            try:
                table = self._student_table(sys_key)
                if not _table_exists(conn, table):
                    continue
                cols = _get_columns(conn, table)
                if "previous_system_id" not in cols:
                    continue

                # Count students who came from another system
                prev_sys_col = None
                for c in ("previous_system", "source_system"):
                    if c in cols:
                        prev_sys_col = c
                        break

                if prev_sys_col:
                    rows = conn.execute(
                        f"SELECT {prev_sys_col} AS src, COUNT(*) AS cnt "
                        f"FROM {table} WHERE previous_system_id IS NOT NULL "
                        f"AND previous_system_id != '' GROUP BY {prev_sys_col}"
                    ).fetchall()
                    for r in rows:
                        # Check if already counted via transfer_history
                        already = any(
                            x["source_system"] == r["src"] and x["destination_system"] == sys_key
                            for x in results
                        )
                        if not already and r["src"]:
                            results.append({
                                "source_system": r["src"],
                                "destination_system": sys_key,
                                "count": r["cnt"],
                                "rate_pct": 0.0,
                            })
                else:
                    cnt = conn.execute(
                        f"SELECT COUNT(*) FROM {table} "
                        f"WHERE previous_system_id IS NOT NULL AND previous_system_id != ''"
                    ).fetchone()[0]
                    if cnt > 0:
                        # Infer source from system order
                        idx = SYSTEM_ORDER.index(sys_key)
                        src = SYSTEM_ORDER[idx - 1] if idx > 0 else "unknown"
                        already = any(
                            x["destination_system"] == sys_key and x["source_system"] == src
                            for x in results
                        )
                        if not already:
                            results.append({
                                "source_system": src,
                                "destination_system": sys_key,
                                "count": cnt,
                                "rate_pct": 0.0,
                            })
            except Exception as e:
                logger.warning("Error querying implicit transfers for %s: %s", sys_key, e)
            finally:
                conn.close()

        return results

    def get_retention_stats(self):
        """Return retention statistics per system.

        Returns a list of dicts with keys:
            system, label, total, active, retained_pct, dropped_out,
            dropout_pct, transferred_out, graduated
        """
        results = []
        for sys_key in SYSTEM_ORDER:
            info = self._count_students(sys_key)
            total = info["total"] or 1
            active = info["active"]
            dropped = info.get("dropped_out", 0)
            results.append({
                "system": sys_key,
                "label": SYSTEM_LABELS.get(sys_key, sys_key),
                "total": info["total"],
                "active": active,
                "retained_pct": round(active / total * 100, 1) if info["total"] > 0 else 0.0,
                "dropped_out": dropped,
                "dropout_pct": round(dropped / total * 100, 1) if info["total"] > 0 else 0.0,
                "transferred_out": info["transferred"],
                "graduated": info["graduated"],
            })
        return results

    def get_year_trends(self):
        """Return year-over-year student count trends per system.

        Returns a list of dicts with keys:
            system, label, year, student_count
        """
        results = []
        for sys_key in SYSTEM_ORDER:
            conn = self._connect(sys_key)
            if not conn:
                continue
            try:
                table = self._student_table(sys_key)
                if not _table_exists(conn, table):
                    continue
                cols = _get_columns(conn, table)

                # Try to find a date column to group by year
                date_col = None
                for c in ("enrollment_date", "enrolled_date", "admission_date",
                           "created_at", "date_enrolled"):
                    if c in cols:
                        date_col = c
                        break

                if date_col:
                    rows = conn.execute(
                        f"SELECT SUBSTR({date_col}, 1, 4) AS yr, COUNT(*) AS cnt "
                        f"FROM {table} WHERE {date_col} IS NOT NULL AND {date_col} != '' "
                        f"GROUP BY yr ORDER BY yr"
                    ).fetchall()
                    for r in rows:
                        yr = r["yr"]
                        if yr and len(yr) == 4 and yr.isdigit():
                            results.append({
                                "system": sys_key,
                                "label": SYSTEM_LABELS.get(sys_key, sys_key),
                                "year": yr,
                                "student_count": r["cnt"],
                            })
                else:
                    # Fallback: just report current total with current year
                    total = conn.execute(
                        f"SELECT COUNT(*) FROM {table}"
                    ).fetchone()[0]
                    results.append({
                        "system": sys_key,
                        "label": SYSTEM_LABELS.get(sys_key, sys_key),
                        "year": str(datetime.now().year),
                        "student_count": total,
                    })
            except Exception as e:
                logger.warning("Error querying year trends for %s: %s", sys_key, e)
            finally:
                conn.close()

        return results

    def export_summary_csv(self):
        """Export the summary data as a CSV string."""
        summary = self.get_summary()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["System", "Total", "Active", "Transferred", "Graduated"])
        for s in summary["systems"]:
            writer.writerow([
                s["label"], s["total"], s["active"],
                s["transferred"], s["graduated"],
            ])
        writer.writerow([])
        writer.writerow(["Overall", summary["total_students"], summary["total_active"],
                         summary["total_transferred"], summary["total_graduated"]])

        # Transfer rates
        writer.writerow([])
        writer.writerow(["Transfer Rates"])
        writer.writerow(["Source", "Destination", "Count", "Rate %"])
        for t in self.get_transfer_rates():
            writer.writerow([
                t["source_system"], t["destination_system"],
                t["count"], t["rate_pct"],
            ])

        # Retention
        writer.writerow([])
        writer.writerow(["Retention Statistics"])
        writer.writerow(["System", "Total", "Active", "Retained %", "Dropped Out", "Dropout %"])
        for r in self.get_retention_stats():
            writer.writerow([
                r["label"], r["total"], r["active"],
                r["retained_pct"], r["dropped_out"], r["dropout_pct"],
            ])

        # Year trends
        writer.writerow([])
        writer.writerow(["Year-over-Year Trends"])
        writer.writerow(["System", "Year", "Student Count"])
        for t in self.get_year_trends():
            writer.writerow([t["label"], t["year"], t["student_count"]])

        return output.getvalue()

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    def _count_students(self, system):
        """Count students by status in a system. Returns a dict."""
        result = {
            "system": system,
            "label": SYSTEM_LABELS.get(system, system),
            "total": 0,
            "active": 0,
            "transferred": 0,
            "graduated": 0,
            "dropped_out": 0,
        }
        conn = self._connect(system)
        if not conn:
            return result
        try:
            table = self._student_table(system)
            if not _table_exists(conn, table):
                return result
            cols = _get_columns(conn, table)

            result["total"] = conn.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]

            if "status" in cols:
                rows = conn.execute(
                    f"SELECT LOWER(status) AS st, COUNT(*) AS cnt "
                    f"FROM {table} WHERE status IS NOT NULL GROUP BY LOWER(status)"
                ).fetchall()
                for r in rows:
                    st = (r["st"] or "").strip()
                    if st in ("active", "enrolled", "current"):
                        result["active"] += r["cnt"]
                    elif st in ("transferred", "transfer", "transferred_out"):
                        result["transferred"] += r["cnt"]
                    elif st in ("graduated", "completed", "passed"):
                        result["graduated"] += r["cnt"]
                    elif st in ("dropped_out", "dropped", "withdrawn", "left", "inactive"):
                        result["dropped_out"] += r["cnt"]
            else:
                # No status column — assume all active
                result["active"] = result["total"]

            return result
        except Exception as e:
            logger.warning("Error counting students for %s: %s", system, e)
            return result
        finally:
            conn.close()
