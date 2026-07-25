"""Cross-system student journey service.

Queries every education-system database (nursery, primary, secondary,
sixth-form college, university) to build a unified view of a student's
educational journey. Database locations come from the canonical
``education_system.platform.kernel.database.paths`` registry so this service stays in
step with the rest of the platform.
"""

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from education_system.platform.kernel.database.paths import (
        SYSTEM_DB_PATHS as _DEFAULT_DB_PATHS,
        SYSTEM_ORDER as _SYSTEM_ORDER,
        SYSTEM_LABELS as _SYSTEM_LABELS,
        AUTH_DB as _AUTH_DB,
    )
except Exception:  # pragma: no cover - fallback if registry is unavailable
    _DEFAULT_DB_PATHS = {}
    _SYSTEM_ORDER = ["nursery", "primary", "secondary", "sixth_form", "university"]
    _SYSTEM_LABELS = {}
    _AUTH_DB = None

# Candidate student tables, in preference order.
# The learner table is named differently per system: most use ``students``,
# primary/nursery use ``pupils``. A system has exactly one of these.
_STUDENT_TABLES = ("students", "pupils")

# The cross-system identity registry (auth.db student_journey) tracks these
# stages, in order. Nursery is not part of the statutory journey schema.
_JOURNEY_PIPELINE = ["primary", "secondary", "sixth_form", "university"]

# Per-stage slot columns on student_journey; a stage is "reached" if either
# the pk or the system-specific student id is populated.
_JOURNEY_SLOTS = {
    "primary":    ("primary_pk", "primary_student_id"),
    "secondary":     ("school_pk", "school_student_id"),
    "sixth_form":    ("college_pk", "college_student_id"),
    "university": ("university_pk", "university_student_id"),
}


def _label(system):
    return _SYSTEM_LABELS.get(system, (system or "").title() or system)


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


class JourneyService:
    """Queries all system databases to build a student's educational journey."""

    def __init__(self, db_paths=None, auth_db=None):
        paths = db_paths if db_paths is not None else _DEFAULT_DB_PATHS
        self._db_paths = {sys: Path(p) for sys, p in paths.items()}
        # Preserve the canonical ordering, but include any extra systems too.
        self._order = [s for s in _SYSTEM_ORDER if s in self._db_paths]
        self._order += [s for s in self._db_paths if s not in self._order]
        auth = auth_db if auth_db is not None else _AUTH_DB
        self._auth_db = Path(auth) if auth else None

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _connect(self, system):
        """Open a connection to a system DB. Returns None if DB missing."""
        path = self._db_paths.get(system)
        if not path or not path.exists():
            return None
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _student_table(conn):
        """Return the name of the student/pupil table, or None."""
        for table in _STUDENT_TABLES:
            if _table_exists(conn, table):
                return table
        return None

    @staticmethod
    def _id_column(cols):
        for candidate in ("student_id", "pupil_id", "apprentice_id"):
            if candidate in cols:
                return candidate
        return "id"

    @staticmethod
    def _year_value(row, rk):
        for candidate in ("year_group", "year", "year_of_study"):
            if candidate in rk and row[candidate]:
                return row[candidate]
        return ""

    @staticmethod
    def _status_value(row, rk):
        for candidate in ("status", "send_status"):
            if candidate in rk and row[candidate]:
                return row[candidate]
        return "unknown"

    @staticmethod
    def _dob_value(row, rk):
        for candidate in ("date_of_birth", "dob"):
            if candidate in rk and row[candidate]:
                return row[candidate]
        return ""

    @staticmethod
    def _enrolled_value(row, rk):
        for candidate in (
            "enrollment_date", "enrolled_date", "admission_date",
            "start_date", "registration_datetime", "registration_date",
            "created_at", "created_date",
        ):
            if candidate in rk and row[candidate]:
                return row[candidate]
        return ""

    def _connect_auth(self):
        """Open the shared auth DB (cross-system registry). None if missing."""
        if not self._auth_db or not self._auth_db.exists():
            return None
        conn = sqlite3.connect(str(self._auth_db))
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def get_cohort_flow(self, year=None):
        """Aggregate the cross-system progression funnel from the registry.

        Reads ``student_journey`` (per-stage slots) and
        ``student_journey_transitions`` (recorded moves) in the shared auth DB
        to answer "how many primary leavers reached secondary, where do
        students drop off, and what moves were recorded".

        Args:
            year: Optional cohort year (string/int). Filters journeys by the
                year of ``created_at`` and transitions by ``occurred_at``.

        Returns a dict:
            total_journeys: int
            year: the filter applied (or None)
            available_years: sorted list of years present (newest first)
            stage_presence: [{system, label, count}] for primary->university
            continuation: [{from, to, from_label, to_label, from_count,
                            continued, dropped, rate}] for each adjacent pair
            transitions: [{from_system, to_system, from_label, to_label, count}]
            by_status: {status: count}
            current_distribution: [{system, label, count}] newest-largest first
        """
        result = {
            "total_journeys": 0,
            "year": str(year) if year else None,
            "available_years": [],
            "stage_presence": [],
            "continuation": [],
            "transitions": [],
            "by_status": {},
            "current_distribution": [],
        }

        conn = self._connect_auth()
        if not conn:
            return result
        try:
            if not _table_exists(conn, "student_journey"):
                return result

            cols = _get_columns(conn, "student_journey")
            years = set()
            if "created_at" in cols:
                for r in conn.execute(
                    "SELECT DISTINCT substr(created_at, 1, 4) AS y FROM student_journey "
                    "WHERE created_at IS NOT NULL"
                ):
                    if r["y"]:
                        years.add(r["y"])

            where, params = "", ()
            if year and "created_at" in cols:
                where, params = "WHERE substr(created_at, 1, 4) = ?", (str(year),)
            rows = conn.execute(
                f"SELECT * FROM student_journey {where}", params  # nosec B608
            ).fetchall()
            result["total_journeys"] = len(rows)

            present = {s: 0 for s in _JOURNEY_PIPELINE}
            slot_flags = []
            status_counts, current_counts = {}, {}
            for row in rows:
                rk = row.keys()
                flags = {}
                for system in _JOURNEY_PIPELINE:
                    reached = any(
                        c in rk and row[c] not in (None, "")
                        for c in _JOURNEY_SLOTS[system]
                    )
                    flags[system] = reached
                    if reached:
                        present[system] += 1
                slot_flags.append(flags)

                st = row["status"] if "status" in rk and row["status"] else "unknown"
                status_counts[st] = status_counts.get(st, 0) + 1
                cur = (row["current_system"]
                       if "current_system" in rk and row["current_system"] else "unknown")
                current_counts[cur] = current_counts.get(cur, 0) + 1

            result["stage_presence"] = [
                {"system": s, "label": _label(s), "count": present[s]}
                for s in _JOURNEY_PIPELINE
            ]

            for a, b in zip(_JOURNEY_PIPELINE, _JOURNEY_PIPELINE[1:]):
                from_count = sum(1 for f in slot_flags if f[a])
                continued = sum(1 for f in slot_flags if f[a] and f[b])
                result["continuation"].append({
                    "from": a, "to": b,
                    "from_label": _label(a), "to_label": _label(b),
                    "from_count": from_count,
                    "continued": continued,
                    "dropped": from_count - continued,
                    "rate": round(continued / from_count * 100, 1) if from_count else 0.0,
                })

            result["by_status"] = status_counts
            result["current_distribution"] = [
                {"system": s, "label": _label(s), "count": c}
                for s, c in sorted(current_counts.items(), key=lambda kv: -kv[1])
            ]

            if _table_exists(conn, "student_journey_transitions"):
                tcols = _get_columns(conn, "student_journey_transitions")
                if "occurred_at" in tcols:
                    for r in conn.execute(
                        "SELECT DISTINCT substr(occurred_at, 1, 4) AS y "
                        "FROM student_journey_transitions WHERE occurred_at IS NOT NULL"
                    ):
                        if r["y"]:
                            years.add(r["y"])
                twhere, tparams = "", ()
                if year and "occurred_at" in tcols:
                    twhere, tparams = "WHERE substr(occurred_at, 1, 4) = ?", (str(year),)
                trows = conn.execute(
                    "SELECT from_system, to_system, COUNT(*) AS c "
                    f"FROM student_journey_transitions {twhere} "  # nosec B608
                    "GROUP BY from_system, to_system ORDER BY c DESC",
                    tparams,
                ).fetchall()
                for r in trows:
                    frm = r["from_system"] or "(entry)"
                    to = r["to_system"] or ""
                    result["transitions"].append({
                        "from_system": frm,
                        "to_system": to,
                        "from_label": _label(r["from_system"]) if r["from_system"] else "(entry)",
                        "to_label": _label(to),
                        "count": r["c"],
                    })

            result["available_years"] = sorted(years, reverse=True)
            return result
        except Exception as e:
            logger.warning("Error building cohort flow: %s", e)
            return result
        finally:
            conn.close()

    def get_transition_students(self, from_system=None, to_system=None,
                                year=None, limit=200):
        """List the individual students behind recorded transitions.

        This is the drill-down for the cohort-flow funnel: given a
        ``from_system``/``to_system`` edge (and optionally a cohort *year*),
        return the named students who made that move, newest first.

        Pass ``"(entry)"`` or ``""`` as *from_system* to match initial
        entries (rows with no source system).

        Returns a list of dicts:
            name, journey_id, from_system, to_system, from_label, to_label,
            occurred_at, reason, dob, status, current_system
        """
        result = []
        conn = self._connect_auth()
        if not conn:
            return result
        try:
            if not _table_exists(conn, "student_journey_transitions"):
                return result
            tcols = _get_columns(conn, "student_journey_transitions")
            has_journey = _table_exists(conn, "student_journey")

            select = ("SELECT t.from_system, t.to_system, t.occurred_at, "
                      "t.reason, t.journey_id")
            frm = " FROM student_journey_transitions t"
            if has_journey:
                select += (", j.legal_first_name, j.legal_last_name, "
                           "j.date_of_birth, j.current_system, j.status")
                frm += " LEFT JOIN student_journey j ON j.journey_id = t.journey_id"

            clauses, params = [], []
            if from_system is not None:
                if from_system in ("(entry)", ""):
                    clauses.append("(t.from_system IS NULL OR t.from_system = '')")
                else:
                    clauses.append("t.from_system = ?")
                    params.append(from_system)
            if to_system:
                clauses.append("t.to_system = ?")
                params.append(to_system)
            if year and "occurred_at" in tcols:
                clauses.append("substr(t.occurred_at, 1, 4) = ?")
                params.append(str(year))
            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            params.append(limit)

            rows = conn.execute(
                select + frm + where + " ORDER BY t.occurred_at DESC LIMIT ?",  # nosec B608
                params,
            ).fetchall()

            for r in rows:
                rk = r.keys()
                first = r["legal_first_name"] if "legal_first_name" in rk else None
                last = r["legal_last_name"] if "legal_last_name" in rk else None
                name = f"{first or ''} {last or ''}".strip() or "(unknown)"
                frm_sys = r["from_system"]
                result.append({
                    "name": name,
                    "journey_id": r["journey_id"],
                    "from_system": frm_sys or "(entry)",
                    "to_system": r["to_system"] or "",
                    "from_label": _label(frm_sys) if frm_sys else "(entry)",
                    "to_label": _label(r["to_system"]),
                    "occurred_at": r["occurred_at"] or "",
                    "reason": (r["reason"] or "") if "reason" in rk else "",
                    "dob": r["date_of_birth"] if "date_of_birth" in rk else "",
                    "status": r["status"] if "status" in rk else "",
                    "current_system": r["current_system"] if "current_system" in rk else "",
                })
            return result
        except Exception as e:
            logger.warning("Error listing transition students: %s", e)
            return result
        finally:
            conn.close()

    def search_student(self, name_query):
        """Search for a student across all systems by name.

        Returns a list of dicts, each with keys:
            system, id, student_id, name, status, year_group
        """
        results = []
        if not name_query or not name_query.strip():
            return results

        like_pattern = f"%{name_query.strip()}%"
        for system in self._order:
            results.extend(self._search_system(system, like_pattern))
        return results

    def get_journey(self, student_id=None, system=None, student_name=None):
        """Build the full educational journey for a student.

        The student is first located (by *student_id* within *system*, or by
        *student_name*) to obtain a canonical name; every system is then
        searched by that name and the matching records are assembled into a
        single chronological journey ordered nursery -> university.

        Returns a dict with keys:
            name, student_id, system, stages

        where ``stages`` is a list of per-system stage dicts, each containing:
            system, student_id, name, dob, year_group, status,
            enrolled_date, academic_history
        """
        anchor = None
        if system and student_id:
            anchor = self._query_system(system, student_id=student_id)
        if anchor is None and student_name:
            for sys_key in self._order:
                anchor = self._query_system(sys_key, name=student_name)
                if anchor:
                    break
        if anchor is None and student_id:
            # No system hint — try every system by id.
            for sys_key in self._order:
                anchor = self._query_system(sys_key, student_id=student_id)
                if anchor:
                    break

        if anchor is None:
            return {
                "name": student_name or "",
                "student_id": student_id or "",
                "system": system or "",
                "stages": [],
            }

        name = anchor.get("name", "")
        stages_by_system = {anchor["system"]: anchor}
        if name:
            for sys_key in self._order:
                if sys_key in stages_by_system:
                    continue
                stage = self._query_system(sys_key, name=name)
                if stage:
                    stages_by_system[sys_key] = stage

        order_index = {s: i for i, s in enumerate(self._order)}
        stages = sorted(
            stages_by_system.values(),
            key=lambda s: order_index.get(s["system"], 99),
        )

        return {
            "name": name,
            "student_id": anchor.get("student_id", student_id or ""),
            "system": anchor["system"],
            "stages": stages,
            # Authoritative recorded moves from the registry. These can differ
            # from len(stages): stages are name-matched *appearances* across
            # system DBs (heuristic, may over-match same-named people), whereas
            # transitions are the moves explicitly recorded in the registry.
            "transitions": self.get_student_transitions(name),
        }

    def get_student_transitions(self, student_name):
        """Recorded registry transitions for a student matched by legal name.

        Returns the same dicts as :meth:`get_transition_students`, filtered to
        the named student (case-insensitive), newest first.
        """
        if not student_name or not student_name.strip():
            return []
        target = student_name.strip().lower()
        return [
            t for t in self.get_transition_students(limit=1000)
            if t.get("name", "").strip().lower() == target
        ]

    # ------------------------------------------------------------------
    # per-system search
    # ------------------------------------------------------------------

    def _search_system(self, system, like_pattern):
        results = []
        conn = self._connect(system)
        if not conn:
            return results
        try:
            table = self._student_table(conn)
            if not table:
                return results
            cols = _get_columns(conn, table)
            name_expr = self._name_search_expr(cols)
            if not name_expr:
                return results
            id_col = self._id_column(cols)

            rows = conn.execute(
                f"SELECT * FROM {table} WHERE {name_expr} LIKE ? LIMIT 50",
                (like_pattern,),
            ).fetchall()
            for r in rows:
                rk = r.keys()
                sid = r[id_col] if id_col in rk else (str(r["id"]) if "id" in rk else "")
                results.append({
                    "system": system,
                    "id": r["id"] if "id" in rk else sid,
                    "student_id": sid,
                    "name": self._extract_name(r),
                    "status": self._status_value(r, rk),
                    "year_group": self._year_value(r, rk),
                })
        except Exception as e:
            logger.warning("Error searching %s students: %s", system, e)
        finally:
            conn.close()
        return results

    # ------------------------------------------------------------------
    # per-system detailed query (for journey building)
    # ------------------------------------------------------------------

    def _query_system(self, system, name=None, student_id=None):
        conn = self._connect(system)
        if not conn:
            return None
        try:
            table = self._student_table(conn)
            if not table:
                return None
            cols = _get_columns(conn, table)
            name_expr = self._name_search_expr(cols)
            id_col = self._id_column(cols)

            row = None
            if student_id is not None and student_id != "":
                row = conn.execute(
                    f"SELECT * FROM {table} WHERE {id_col} = ?", (student_id,)
                ).fetchone()
                if not row and id_col != "id" and "id" in cols:
                    row = conn.execute(
                        f"SELECT * FROM {table} WHERE id = ?", (student_id,)
                    ).fetchone()
            elif name and name_expr:
                row = conn.execute(
                    f"SELECT * FROM {table} WHERE {name_expr} LIKE ? LIMIT 1",
                    (f"%{name}%",),
                ).fetchone()

            if not row:
                return None

            rk = row.keys()
            sid = row[id_col] if id_col in rk else (str(row["id"]) if "id" in rk else "")
            return {
                "system": system,
                "student_id": sid,
                "name": self._extract_name(row),
                "dob": self._dob_value(row, rk),
                "year_group": self._year_value(row, rk),
                "status": self._status_value(row, rk),
                "enrolled_date": self._enrolled_value(row, rk),
                "academic_history": self._get_transfer_history(conn, sid),
            }
        except Exception as e:
            logger.warning("Error querying %s student journey: %s", system, e)
            return None
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Transfer history
    # ------------------------------------------------------------------

    def _get_transfer_history(self, conn, student_id):
        """Return academic_transfer_history records for *student_id*, if any."""
        try:
            if not _table_exists(conn, "academic_transfer_history"):
                return []
            cols = _get_columns(conn, "academic_transfer_history")
            id_col = None
            for candidate in ("student_id", "pupil_id", "source_student_id"):
                if candidate in cols:
                    id_col = candidate
                    break
            if not id_col:
                return []

            rows = conn.execute(
                f"SELECT * FROM academic_transfer_history WHERE {id_col} = ? "
                f"ORDER BY rowid",
                (student_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.warning("Error getting transfer history for %s: %s", student_id, e)
            return []

    # ------------------------------------------------------------------
    # Name utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _name_search_expr(columns):
        """Build a SQL expression for a full-name search."""
        if "full_name" in columns:
            return "full_name"
        if "name" in columns:
            return "name"
        if "first_name" in columns and "last_name" in columns:
            return "(first_name || ' ' || last_name)"
        if "forename" in columns and "surname" in columns:
            return "(forename || ' ' || surname)"
        if "first_name" in columns and "surname" in columns:
            return "(first_name || ' ' || surname)"
        if "forename" in columns and "last_name" in columns:
            return "(forename || ' ' || last_name)"
        return None

    @staticmethod
    def _extract_name(row):
        """Extract the student name from a row."""
        rk = row.keys() if hasattr(row, "keys") else []
        if "full_name" in rk and row["full_name"]:
            return row["full_name"]
        if "name" in rk and row["name"]:
            return row["name"]
        parts = []
        for fn in ("first_name", "forename"):
            if fn in rk and row[fn]:
                parts.append(row[fn])
                break
        for ln in ("last_name", "surname"):
            if ln in rk and row[ln]:
                parts.append(row[ln])
                break
        return " ".join(parts) if parts else ""
