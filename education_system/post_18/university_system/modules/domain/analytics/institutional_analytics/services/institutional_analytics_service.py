"""Institutional analytics service.

Computes aggregate institutional metrics on demand from the operational
tables in ``student_records.db``. Everything here is read-only: aggregate
SELECTs, no DDL and no writes.

Design notes
------------
* **Schema-tolerant.** Column availability varies across historical
  migrations of this DB, so every section guards on ``_has_column`` /
  ``_table_exists`` and skips (rather than crashes) when a source table or
  column is absent. This also lets the pytest suite seed a minimal DB.
* **Normalised categoricals.** Free-text status values are messy in the
  seed data (``Active``/``active``, ``Graduated``/``graduated``,
  ``Enrolled``/``enrolled``). Statuses are lower-cased and bucketed via
  the classification maps below, so counts don't fragment on case.
* **JSON-friendly output.** Every public method returns plain
  ``dict`` / ``list[dict]`` structures so the same result feeds the CLI,
  the Tk GUI and any REST route without adaptation.
"""
from __future__ import annotations

import re
import sqlite3
from typing import Any, Optional

from education_system.post_18.university_system.infrastructure.database.db import get_connection


class InstitutionalAnalyticsError(Exception):
    """Raised on lookup / validation failures within institutional analytics."""


# --- Student lifecycle status buckets (lower-cased keys) ---------------------
_CURRENT_STATUSES = {"active", "enrolled", "continuing", "registered", "current"}
_COMPLETED_STATUSES = {"graduated", "completed", "awarded", "alumni"}
_ATTRITION_STATUSES = {
    "withdrawn", "withdrew", "suspended", "dropped", "dropout", "deferred",
    "excluded", "inactive", "left", "terminated", "expelled",
}

# --- Module outcome classification ------------------------------------------
_PASS_STATUSES = {"passed", "completed", "complete", "achieved", "credited"}
_FAIL_STATUSES = {"failed", "fail", "referred", "not achieved"}
_PASS_GRADES = {
    "a", "b", "c", "d", "first", "1st", "2:1", "2.1", "2:2", "2.2", "third",
    "3rd", "pass", "merit", "distinction", "credit",
}
_FAIL_GRADES = {"f", "fail", "u", "referred", "e"}
# Numeric grade at or above this (percentage points) counts as a pass.
_NUMERIC_PASS_MARK = 40.0


class InstitutionalAnalyticsService:
    """Read-only aggregate analytics over the institution's operational data."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path

    # --------------------------------------------------------------- plumbing
    def _conn(self) -> sqlite3.Connection:
        conn = get_connection(self.db_path) if self.db_path else get_connection()
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        return row is not None

    @staticmethod
    def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
        try:
            return {r[1] for r in conn.execute(f"PRAGMA table_info('{table}')").fetchall()}
        except sqlite3.Error:
            return set()

    @classmethod
    def _has_column(cls, conn: sqlite3.Connection, table: str, column: str) -> bool:
        return column in cls._columns(conn, table)

    @staticmethod
    def _pct(part: float, whole: float) -> Optional[float]:
        if not whole:
            return None
        return round(part / whole * 100, 2)

    @staticmethod
    def _norm(value: Any) -> str:
        return str(value).strip().lower() if value is not None else ""

    @classmethod
    def _classify_student_status(cls, status: Any) -> str:
        s = cls._norm(status)
        if s in _COMPLETED_STATUSES:
            return "completed"
        if s in _ATTRITION_STATUSES:
            return "attrition"
        if s in _CURRENT_STATUSES:
            return "current"
        return "other"

    @classmethod
    def _classify_module_outcome(cls, status: Any, grade: Any) -> str:
        """Return 'pass' | 'fail' | 'in_progress' | 'unknown' for one enrolment."""
        g = cls._norm(grade)
        if g:
            num = cls._numeric_grade(g)
            if num is not None:
                return "pass" if num >= _NUMERIC_PASS_MARK else "fail"
            if g in _PASS_GRADES:
                return "pass"
            if g in _FAIL_GRADES:
                return "fail"
        s = cls._norm(status)
        if s in _PASS_STATUSES:
            return "pass"
        if s in _FAIL_STATUSES:
            return "fail"
        if s in _CURRENT_STATUSES:
            return "in_progress"
        return "unknown"

    @staticmethod
    def _numeric_grade(grade: str) -> Optional[float]:
        m = re.fullmatch(r"\s*(\d{1,3}(?:\.\d+)?)\s*%?\s*", grade)
        if not m:
            return None
        try:
            val = float(m.group(1))
        except ValueError:
            return None
        return val if 0 <= val <= 100 else None

    # ============================================================ ENROLMENT
    def enrollment_summary(self) -> dict[str, Any]:
        """Head-count, active/graduated split, and breakdown by course."""
        conn = self._conn()
        try:
            if not self._table_exists(conn, "students"):
                raise InstitutionalAnalyticsError("students table not present")
            rows = conn.execute("SELECT * FROM students").fetchall()
            has_course = self._has_column(conn, "students", "course")
            total = len(rows)
            buckets: dict[str, int] = {"current": 0, "completed": 0,
                                       "attrition": 0, "other": 0}
            by_status: dict[str, int] = {}
            by_course: dict[str, int] = {}
            for r in rows:
                status = r["status"] if "status" in r.keys() else None
                buckets[self._classify_student_status(status)] += 1
                key = self._norm(status) or "unknown"
                by_status[key] = by_status.get(key, 0) + 1
                if has_course:
                    course = (r["course"] or "unknown") if r["course"] is not None else "unknown"
                    by_course[course] = by_course.get(course, 0) + 1
            return {
                "total_students": total,
                "current": buckets["current"],
                "completed": buckets["completed"],
                "attrition": buckets["attrition"],
                "other": buckets["other"],
                "by_status": _sorted_counts(by_status),
                "by_course": _sorted_counts(by_course),
            }
        finally:
            conn.close()

    # ========================================================== DEMOGRAPHICS
    def demographics(self) -> dict[str, Any]:
        """Gender split, age stats and UCAS-tariff stats where available."""
        conn = self._conn()
        try:
            if not self._table_exists(conn, "students"):
                raise InstitutionalAnalyticsError("students table not present")
            cols = self._columns(conn, "students")
            rows = conn.execute("SELECT * FROM students").fetchall()
            by_gender: dict[str, int] = {}
            ages: list[float] = []
            tariffs: list[float] = []
            gpas: list[float] = []
            for r in rows:
                keys = r.keys()
                if "gender" in cols:
                    by_gender_key = self._norm(r["gender"]) or "unspecified"
                    by_gender[by_gender_key] = by_gender.get(by_gender_key, 0) + 1
                if "age" in cols and r["age"] is not None:
                    _append_num(ages, r["age"])
                if "ucas_tariff" in cols and r["ucas_tariff"] is not None:
                    _append_num(tariffs, r["ucas_tariff"])
                if "gpa" in keys and r["gpa"] is not None:
                    _append_num(gpas, r["gpa"])
            return {
                "by_gender": _sorted_counts(by_gender),
                "age": _describe(ages),
                "ucas_tariff": _describe(tariffs),
                "gpa": _describe(gpas),
            }
        finally:
            conn.close()

    # ============================================================ RETENTION
    def retention_metrics(self) -> dict[str, Any]:
        """Retention / attrition / completion rates, overall and per course."""
        conn = self._conn()
        try:
            if not self._table_exists(conn, "students"):
                raise InstitutionalAnalyticsError("students table not present")
            has_course = self._has_column(conn, "students", "course")
            rows = conn.execute("SELECT * FROM students").fetchall()
            total = len(rows)

            def _blank() -> dict[str, int]:
                return {"total": 0, "current": 0, "completed": 0,
                        "attrition": 0, "other": 0}

            overall = _blank()
            per_course: dict[str, dict[str, int]] = {}
            for r in rows:
                status = r["status"] if "status" in r.keys() else None
                bucket = self._classify_student_status(status)
                overall["total"] += 1
                overall[bucket] += 1
                if has_course:
                    course = (r["course"] or "unknown") if r["course"] is not None else "unknown"
                    pc = per_course.setdefault(course, _blank())
                    pc["total"] += 1
                    pc[bucket] += 1

            def _rates(b: dict[str, int]) -> dict[str, Any]:
                t = b["total"]
                # Retention = still enrolled OR successfully completed.
                retained = b["current"] + b["completed"]
                return {
                    **b,
                    "retention_rate": self._pct(retained, t),
                    "attrition_rate": self._pct(b["attrition"], t),
                    "completion_rate": self._pct(b["completed"], t),
                }

            course_rates = [
                {"course": c, **_rates(b)}
                for c, b in sorted(per_course.items(),
                                   key=lambda kv: kv[1]["total"], reverse=True)
            ]
            return {
                "total_students": total,
                "overall": _rates(overall),
                "by_course": course_rates,
            }
        finally:
            conn.close()

    # ==================================================== MODULE PERFORMANCE
    def module_performance(self, limit: Optional[int] = None) -> dict[str, Any]:
        """Per-module enrolment volume, pass rate and in-progress counts."""
        conn = self._conn()
        try:
            if not self._table_exists(conn, "student_modules"):
                raise InstitutionalAnalyticsError("student_modules table not present")
            cols = self._columns(conn, "student_modules")
            code_col = "module_code" if "module_code" in cols else (
                "module_id" if "module_id" in cols else None)
            if code_col is None:
                raise InstitutionalAnalyticsError(
                    "student_modules has no module_code/module_id column")
            name_col = "module_name" if "module_name" in cols else None
            has_grade = "grade" in cols
            has_status = "status" in cols

            rows = conn.execute("SELECT * FROM student_modules").fetchall()

            agg: dict[str, dict[str, Any]] = {}
            totals = {"enrolments": 0, "pass": 0, "fail": 0,
                      "in_progress": 0, "unknown": 0}
            for r in rows:
                code = r[code_col] or "unknown"
                entry = agg.setdefault(code, {
                    "module_code": code,
                    "module_name": r[name_col] if name_col else None,
                    "enrolments": 0, "pass": 0, "fail": 0,
                    "in_progress": 0, "unknown": 0,
                })
                if name_col and entry["module_name"] is None and r[name_col]:
                    entry["module_name"] = r[name_col]
                outcome = self._classify_module_outcome(
                    r["status"] if has_status else None,
                    r["grade"] if has_grade else None,
                )
                entry["enrolments"] += 1
                entry[outcome] += 1
                totals["enrolments"] += 1
                totals[outcome] += 1

            modules = []
            for entry in agg.values():
                graded = entry["pass"] + entry["fail"]
                entry["pass_rate"] = self._pct(entry["pass"], graded)
                modules.append(entry)
            modules.sort(key=lambda m: m["enrolments"], reverse=True)
            if limit is not None and limit > 0:
                modules = modules[:limit]

            graded_total = totals["pass"] + totals["fail"]
            return {
                "module_count": len(agg),
                "totals": {
                    **totals,
                    "overall_pass_rate": self._pct(totals["pass"], graded_total),
                },
                "modules": modules,
            }
        finally:
            conn.close()

    # ======================================================= COURSE CAPACITY
    def course_capacity(self) -> dict[str, Any]:
        """Fill rate (enrolment vs capacity) per course and institution-wide."""
        conn = self._conn()
        try:
            if not self._table_exists(conn, "courses"):
                raise InstitutionalAnalyticsError("courses table not present")
            cols = self._columns(conn, "courses")
            if "current_enrollment" not in cols or "max_enrollment" not in cols:
                raise InstitutionalAnalyticsError(
                    "courses table lacks enrolment/capacity columns")
            name_col = "course_name" if "course_name" in cols else (
                "name" if "name" in cols else None)
            code_col = "course_code" if "course_code" in cols else (
                "code" if "code" in cols else "id")
            rows = conn.execute("SELECT * FROM courses").fetchall()
            courses = []
            tot_enrolled = tot_capacity = 0
            for r in rows:
                enrolled = _to_int(r["current_enrollment"])
                capacity = _to_int(r["max_enrollment"])
                tot_enrolled += enrolled
                tot_capacity += capacity
                courses.append({
                    "course_code": r[code_col] if code_col in r.keys() else None,
                    "course_name": r[name_col] if name_col else None,
                    "enrolled": enrolled,
                    "capacity": capacity,
                    "available": max(capacity - enrolled, 0),
                    "fill_rate": self._pct(enrolled, capacity),
                    "at_capacity": capacity > 0 and enrolled >= capacity,
                })
            courses.sort(key=lambda c: (c["fill_rate"] is None, -(c["fill_rate"] or 0)))
            return {
                "course_count": len(courses),
                "total_enrolled": tot_enrolled,
                "total_capacity": tot_capacity,
                "overall_fill_rate": self._pct(tot_enrolled, tot_capacity),
                "courses_at_capacity": sum(1 for c in courses if c["at_capacity"]),
                "courses": courses,
            }
        finally:
            conn.close()

    # ========================================================= FINANCIAL
    def financial_summary(self) -> dict[str, Any]:
        """Collected revenue (by method / month) and outstanding fees."""
        conn = self._conn()
        try:
            result: dict[str, Any] = {}
            # --- Payments -----------------------------------------------
            if self._table_exists(conn, "payments"):
                pcols = self._columns(conn, "payments")
                has_status = "status" in pcols
                # Only completed payments count as collected revenue.
                cond = "lower(status)='completed'" if has_status else "1=1"
                total = conn.execute(
                    f"SELECT COALESCE(SUM(amount),0) FROM payments WHERE {cond}"
                ).fetchone()[0]
                count = conn.execute(
                    f"SELECT COUNT(*) FROM payments WHERE {cond}"
                ).fetchone()[0]
                by_method: dict[str, float] = {}
                if "payment_method" in pcols:
                    for r in conn.execute(
                        f"SELECT payment_method m, COALESCE(SUM(amount),0) s "
                        f"FROM payments WHERE {cond} GROUP BY lower(payment_method)"
                    ).fetchall():
                        by_method[self._norm(r["m"]) or "unknown"] = round(r["s"] or 0, 2)
                by_month: dict[str, float] = {}
                if "payment_date" in pcols:
                    for r in conn.execute(
                        f"SELECT substr(payment_date,1,7) ym, "
                        f"COALESCE(SUM(amount),0) s FROM payments "
                        f"WHERE {cond} AND payment_date IS NOT NULL "
                        f"GROUP BY ym ORDER BY ym"
                    ).fetchall():
                        if r["ym"]:
                            by_month[r["ym"]] = round(r["s"] or 0, 2)
                result["revenue"] = {
                    "collected_total": round(total or 0, 2),
                    "payment_count": count,
                    "by_method": dict(sorted(by_method.items(),
                                             key=lambda kv: kv[1], reverse=True)),
                    "by_month": by_month,
                }
            # --- Outstanding fees ---------------------------------------
            if self._table_exists(conn, "student_fees"):
                fcols = self._columns(conn, "student_fees")
                if "status" in fcols and "amount" in fcols:
                    outstanding = conn.execute(
                        "SELECT COALESCE(SUM(amount),0) FROM student_fees "
                        "WHERE lower(status) NOT IN ('paid','waived','cancelled')"
                    ).fetchone()[0]
                    waived = conn.execute(
                        "SELECT COALESCE(SUM(amount),0) FROM student_fees "
                        "WHERE lower(status)='waived'"
                    ).fetchone()[0]
                    by_fee_status: dict[str, float] = {}
                    for r in conn.execute(
                        "SELECT status s, COALESCE(SUM(amount),0) a "
                        "FROM student_fees GROUP BY lower(status)"
                    ).fetchall():
                        by_fee_status[self._norm(r["s"]) or "unknown"] = round(r["a"] or 0, 2)
                    result["fees"] = {
                        "outstanding_total": round(outstanding or 0, 2),
                        "waived_total": round(waived or 0, 2),
                        "by_status": by_fee_status,
                    }
            # --- Account balances ---------------------------------------
            if self._table_exists(conn, "student_finance_accounts"):
                acols = self._columns(conn, "student_finance_accounts")
                if "balance" in acols:
                    row = conn.execute(
                        "SELECT COUNT(*) n, COALESCE(SUM(balance),0) s "
                        "FROM student_finance_accounts"
                    ).fetchone()
                    result["accounts"] = {
                        "account_count": row["n"],
                        "total_balance": round(row["s"] or 0, 2),
                    }
            if not result:
                raise InstitutionalAnalyticsError("no finance tables present")
            return result
        finally:
            conn.close()

    # ============================================================ OVERVIEW
    def institutional_overview(self) -> dict[str, Any]:
        """Headline figures across every section, for a one-glance dashboard.

        Each section is computed independently; a section that fails (e.g.
        its source table is absent) is reported under ``errors`` rather than
        sinking the whole overview.
        """
        overview: dict[str, Any] = {}
        errors: dict[str, str] = {}

        sections = {
            "enrollment": self.enrollment_summary,
            "retention": self.retention_metrics,
            "demographics": self.demographics,
            "modules": self.module_performance,
            "capacity": self.course_capacity,
            "finance": self.financial_summary,
        }
        for name, fn in sections.items():
            try:
                overview[name] = fn()
            except InstitutionalAnalyticsError as exc:
                errors[name] = str(exc)
            except sqlite3.Error as exc:  # pragma: no cover - defensive
                errors[name] = f"db error: {exc}"

        # Distil the headline numbers callers most often want up top.
        enr = overview.get("enrollment", {})
        ret = overview.get("retention", {}).get("overall", {})
        cap = overview.get("capacity", {})
        mod = overview.get("modules", {}).get("totals", {})
        fin = overview.get("finance", {})
        headline = {
            "total_students": enr.get("total_students"),
            "active_students": enr.get("current"),
            "retention_rate": ret.get("retention_rate"),
            "attrition_rate": ret.get("attrition_rate"),
            "overall_fill_rate": cap.get("overall_fill_rate"),
            "module_pass_rate": mod.get("overall_pass_rate"),
            "revenue_collected": fin.get("revenue", {}).get("collected_total"),
            "fees_outstanding": fin.get("fees", {}).get("outstanding_total"),
        }
        return {"headline": headline, "sections": overview, "errors": errors}


# ------------------------------------------------------------------ helpers
def _sorted_counts(counts: dict[str, int]) -> list[dict[str, Any]]:
    """Turn a {label: count} map into a descending list of {label, count}."""
    return [
        {"label": k, "count": v}
        for k, v in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    ]


def _append_num(bucket: list[float], value: Any) -> None:
    try:
        bucket.append(float(value))
    except (TypeError, ValueError):
        pass


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _describe(values: list[float]) -> dict[str, Any]:
    """Small numeric summary that tolerates an empty sample."""
    if not values:
        return {"count": 0, "min": None, "max": None, "avg": None}
    return {
        "count": len(values),
        "min": round(min(values), 2),
        "max": round(max(values), 2),
        "avg": round(sum(values) / len(values), 2),
    }
