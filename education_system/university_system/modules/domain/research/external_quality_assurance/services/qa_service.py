"""Service layer for external quality assurance (OfS / TEF / REF).

All compute / CRUD / export logic lives here. The GUI (``qa_dashboard_gui``)
and the analytics counterpart (``modules/domain/analytics/external_qa_kpis``)
are thin wrappers over these functions.
"""

from __future__ import annotations

import csv
import json
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional

from education_system.university_system.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FRAMEWORKS = ("OfS", "TEF", "REF")

QA_STATUSES = ("draft", "in_review", "submitted", "accepted", "rejected")

OFS_B3_METRICS = ("continuation", "completion", "progression")

TEF_SECTIONS = (
    "student_experience",
    "student_outcomes",
    "provider_context",
    "educational_gain",
)

# Sample REF Units of Assessment — REF 2021 had 34. We keep a small
# starter list and the GUI lets you type any code.
REF_UOAS = (
    "UOA11", "UOA12", "UOA13", "UOA14", "UOA15", "UOA16", "UOA17",
    "UOA18", "UOA19", "UOA20", "UOA21", "UOA22", "UOA23", "UOA24",
)

REF_IMPACT_STATUSES = ("draft", "in_review", "submitted", "withdrawn")


# ---------------------------------------------------------------------------
# Schema (idempotent)
# ---------------------------------------------------------------------------

_DDL = [
    """CREATE TABLE IF NOT EXISTS qa_submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        framework TEXT NOT NULL,
        submission_year INTEGER NOT NULL,
        submission_date TEXT,
        status TEXT NOT NULL DEFAULT 'draft',
        assigned_to INTEGER,
        notes TEXT,
        signed_off_by INTEGER,
        signed_off_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (framework, submission_year)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_qa_sub_status ON qa_submissions(status)",
    """CREATE TABLE IF NOT EXISTS ofs_b3_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cohort_year INTEGER NOT NULL,
        course TEXT,
        metric_type TEXT NOT NULL,
        value_pct REAL NOT NULL,
        numerator INTEGER NOT NULL,
        denominator INTEGER NOT NULL,
        computed_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (cohort_year, course, metric_type)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_ofs_b3_cohort ON ofs_b3_metrics(cohort_year)",
    "CREATE INDEX IF NOT EXISTS idx_ofs_b3_metric ON ofs_b3_metrics(metric_type)",
    """CREATE TABLE IF NOT EXISTS ofs_app_milestones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_year INTEGER NOT NULL,
        milestone_text TEXT NOT NULL,
        target_value REAL,
        target_date TEXT,
        current_value REAL,
        achieved INTEGER NOT NULL DEFAULT 0,
        achieved_date TEXT,
        owner_id INTEGER,
        notes TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS idx_ofs_app_year ON ofs_app_milestones(plan_year)",
    "CREATE INDEX IF NOT EXISTS idx_ofs_app_achieved ON ofs_app_milestones(achieved)",
    """CREATE TABLE IF NOT EXISTS ofs_protection_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        version TEXT NOT NULL,
        in_force_from TEXT NOT NULL,
        in_force_to TEXT,
        plan_text TEXT NOT NULL,
        approved_by INTEGER,
        approved_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (version)
    )""",
    """CREATE TABLE IF NOT EXISTS tef_provider_narratives (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        submission_year INTEGER NOT NULL,
        section TEXT NOT NULL,
        narrative_text TEXT NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        drafted_by INTEGER,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (submission_year, section, version)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_tef_narr_year ON tef_provider_narratives(submission_year)",
    """CREATE TABLE IF NOT EXISTS ref_impact_cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uoa TEXT NOT NULL,
        title TEXT NOT NULL,
        summary TEXT,
        lead_author_id INTEGER,
        status TEXT NOT NULL DEFAULT 'draft',
        reach_significance TEXT,
        beneficiaries TEXT,
        evidence_links TEXT,
        quality_rating TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS idx_ref_impact_uoa ON ref_impact_cases(uoa)",
    "CREATE INDEX IF NOT EXISTS idx_ref_impact_status ON ref_impact_cases(status)",
    """CREATE TABLE IF NOT EXISTS ref_environment_statements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uoa TEXT NOT NULL,
        narrative_text TEXT NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        drafted_by INTEGER,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (uoa, version)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_ref_env_uoa ON ref_environment_statements(uoa)",
]


def init_db() -> None:
    with get_connection() as conn:
        for stmt in _DDL:
            conn.execute(stmt)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today() -> str:
    return date.today().isoformat()


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

def _audit(action: str, resource_type: str = "qa", resource_id: Optional[str] = None,
           details: Optional[dict] = None) -> None:
    try:
        from education_system.university_system.infrastructure.security.audit_helpers import (
            safe_log_security_event,
        )
        actor = None
        try:
            from education_system.university_system.infrastructure.shared_context import get_auth
            a = get_auth()
            if a and getattr(a, "current_user", None):
                u = a.current_user
                actor = str(
                    (u.get("id") or u.get("user_id") or "") if isinstance(u, dict)
                    else (getattr(u, "id", "") or "")
                )
        except Exception:
            pass
        safe_log_security_event(
            action=f"qa.{action}", user_id=actor,
            resource_type=resource_type, resource_id=resource_id,
            details=details or {},
        )
    except Exception:
        pass


# ===========================================================================
# Submissions tracker
# ===========================================================================

def upsert_submission(framework: str, submission_year: int, status: str = "draft",
                      assigned_to: Optional[int] = None, notes: Optional[str] = None) -> int:
    if framework not in FRAMEWORKS:
        raise ValueError(f"unknown framework {framework}")
    init_db()
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM qa_submissions WHERE framework = ? AND submission_year = ?",
            (framework, submission_year),
        ).fetchone()
        if existing:
            sid = existing[0] if isinstance(existing, tuple) else existing["id"]
            conn.execute(
                "UPDATE qa_submissions SET status=?, assigned_to=?, notes=?, updated_at=? WHERE id=?",
                (status, assigned_to, notes, _now(), sid),
            )
            _audit("submission_updated", resource_id=str(sid),
                   details={"framework": framework, "year": submission_year, "status": status})
            return sid
        cur = conn.execute(
            """INSERT INTO qa_submissions
               (framework, submission_year, status, assigned_to, notes)
               VALUES (?, ?, ?, ?, ?)""",
            (framework, submission_year, status, assigned_to, notes),
        )
        new_id = cur.lastrowid
    _audit("submission_created", resource_id=str(new_id),
           details={"framework": framework, "year": submission_year})
    return new_id


def list_submissions(framework: Optional[str] = None) -> list[dict]:
    init_db()
    with get_connection() as conn:
        if framework:
            rows = conn.execute(
                "SELECT * FROM qa_submissions WHERE framework = ? ORDER BY submission_year DESC",
                (framework,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM qa_submissions ORDER BY framework, submission_year DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def sign_off_submission(submission_id: int, signed_off_by: int) -> bool:
    init_db()
    with get_connection() as conn:
        cur = conn.execute(
            """UPDATE qa_submissions
               SET status='submitted', signed_off_by=?, signed_off_at=?, submission_date=?
               WHERE id = ? AND status != 'submitted'""",
            (signed_off_by, _now(), _today(), submission_id),
        )
        ok = cur.rowcount > 0
    if ok:
        _audit("submission_signed_off", resource_id=str(submission_id),
               details={"signed_off_by": signed_off_by})
    return ok


# ===========================================================================
# OfS — B3 metrics
# ===========================================================================

def _has_table(conn, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def compute_b3_metrics(cohort_year: int, course: Optional[str] = None) -> dict:
    """Compute the three B3 indicators for a cohort year.

    * **Continuation**: of students who enrolled in ``cohort_year``, the
      proportion still ``status='Active'``/``Enrolled`` after one year.
    * **Completion**: of the same cohort, the proportion whose status is
      now ``'completed'`` / ``'graduated'``.
    * **Progression**: stub — proper progression-into-graduate-employment
      data is held in HESA Graduate Outcomes, not in this system. We
      return a sentinel value (``-1``) so the metric exists but the GUI
      can render it as "n/a".

    Returns a dict like ``{"continuation": (pct, num, denom), …}``.
    """
    init_db()
    metrics: dict[str, tuple[float, int, int]] = {}
    with get_connection() as conn:
        params: list[Any] = []
        cohort_filter = (
            "strftime('%Y', COALESCE(enrollment_date, registration_datetime)) = ?"
        )
        params.append(str(cohort_year))
        if course:
            cohort_filter += " AND course = ?"
            params.append(course)

        cohort_size = conn.execute(
            f"SELECT COUNT(*) FROM students WHERE {cohort_filter}", params,
        ).fetchone()[0] or 0

        if cohort_size == 0:
            return {m: (0.0, 0, 0) for m in OFS_B3_METRICS}

        cont_count = conn.execute(
            f"SELECT COUNT(*) FROM students "
            f"WHERE {cohort_filter} AND LOWER(status) IN ('active','enrolled')",
            params,
        ).fetchone()[0] or 0

        comp_count = conn.execute(
            f"SELECT COUNT(*) FROM students "
            f"WHERE {cohort_filter} AND LOWER(status) IN ('completed','graduated')",
            params,
        ).fetchone()[0] or 0

        metrics["continuation"] = (
            round(100.0 * cont_count / cohort_size, 2), cont_count, cohort_size,
        )
        metrics["completion"] = (
            round(100.0 * comp_count / cohort_size, 2), comp_count, cohort_size,
        )
        metrics["progression"] = (-1.0, 0, cohort_size)
    return metrics


def record_b3_snapshot(cohort_year: int, course: Optional[str] = None) -> int:
    """Compute B3 for the cohort and write a snapshot row per metric. Returns
    the number of metrics persisted."""
    init_db()
    metrics = compute_b3_metrics(cohort_year, course=course)
    n = 0
    with get_connection() as conn:
        for metric_type, (pct, num, denom) in metrics.items():
            conn.execute(
                """INSERT INTO ofs_b3_metrics
                   (cohort_year, course, metric_type, value_pct, numerator, denominator, computed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(cohort_year, course, metric_type) DO UPDATE SET
                     value_pct = excluded.value_pct,
                     numerator = excluded.numerator,
                     denominator = excluded.denominator,
                     computed_at = excluded.computed_at""",
                (cohort_year, course, metric_type, pct, num, denom, _now()),
            )
            n += 1
    _audit("b3_snapshot_recorded",
           details={"cohort_year": cohort_year, "course": course, "metrics": list(metrics)})
    return n


def list_b3_snapshots(cohort_year: Optional[int] = None) -> list[dict]:
    init_db()
    with get_connection() as conn:
        if cohort_year is not None:
            rows = conn.execute(
                "SELECT * FROM ofs_b3_metrics WHERE cohort_year = ? "
                "ORDER BY course, metric_type", (cohort_year,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM ofs_b3_metrics "
                "ORDER BY cohort_year DESC, course, metric_type",
            ).fetchall()
        return [dict(r) for r in rows]


def export_ofs_return(year: int, out_path: str) -> int:
    """Write a CSV with all B3 snapshot rows for ``year``. Returns row count."""
    rows = list_b3_snapshots(cohort_year=year)
    fields = ("cohort_year", "course", "metric_type", "value_pct",
              "numerator", "denominator", "computed_at")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    _audit("ofs_export_written", details={"year": year, "rows": len(rows), "path": out_path})
    return len(rows)


# ===========================================================================
# OfS — APP milestones (CRUD)
# ===========================================================================

def list_app_milestones(plan_year: Optional[int] = None) -> list[dict]:
    init_db()
    with get_connection() as conn:
        if plan_year is not None:
            rows = conn.execute(
                "SELECT * FROM ofs_app_milestones WHERE plan_year = ? "
                "ORDER BY achieved, target_date", (plan_year,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM ofs_app_milestones ORDER BY plan_year DESC, target_date"
            ).fetchall()
        return [dict(r) for r in rows]


def create_app_milestone(plan_year: int, milestone_text: str,
                          target_value: Optional[float] = None,
                          target_date: Optional[str] = None,
                          owner_id: Optional[int] = None,
                          notes: Optional[str] = None) -> int:
    init_db()
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO ofs_app_milestones
               (plan_year, milestone_text, target_value, target_date, owner_id, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (plan_year, milestone_text, target_value, target_date, owner_id, notes),
        )
        new_id = cur.lastrowid
    _audit("app_milestone_created", resource_id=str(new_id),
           details={"plan_year": plan_year, "milestone": milestone_text[:60]})
    return new_id


def update_app_milestone(milestone_id: int, **fields: Any) -> bool:
    if not fields:
        return False
    allowed = {
        "milestone_text", "target_value", "target_date", "current_value",
        "achieved", "achieved_date", "owner_id", "notes",
    }
    sets, params = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k == "achieved":
            v = 1 if v else 0
        sets.append(f"{k} = ?")
        params.append(v)
    if not sets:
        return False
    sets.append("updated_at = ?")
    params.append(_now())
    params.append(milestone_id)
    init_db()
    with get_connection() as conn:
        cur = conn.execute(
            f"UPDATE ofs_app_milestones SET {', '.join(sets)} WHERE id = ?", params,
        )
        ok = cur.rowcount > 0
    if ok:
        _audit("app_milestone_updated", resource_id=str(milestone_id), details=fields)
    return ok


def delete_app_milestone(milestone_id: int) -> bool:
    init_db()
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM ofs_app_milestones WHERE id = ?", (milestone_id,))
        ok = cur.rowcount > 0
    if ok:
        _audit("app_milestone_deleted", resource_id=str(milestone_id))
    return ok


# ===========================================================================
# OfS — Protection plans (versioned)
# ===========================================================================

def list_protection_plans() -> list[dict]:
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM ofs_protection_plans ORDER BY in_force_from DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def create_protection_plan(version: str, in_force_from: str, plan_text: str,
                            in_force_to: Optional[str] = None,
                            approved_by: Optional[int] = None) -> int:
    init_db()
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO ofs_protection_plans
               (version, in_force_from, in_force_to, plan_text, approved_by, approved_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (version, in_force_from, in_force_to, plan_text,
             approved_by, _now() if approved_by else None),
        )
        new_id = cur.lastrowid
    _audit("protection_plan_created", resource_id=str(new_id),
           details={"version": version, "in_force_from": in_force_from})
    return new_id


# ===========================================================================
# TEF — provider narratives
# ===========================================================================

def list_tef_narratives(submission_year: Optional[int] = None) -> list[dict]:
    init_db()
    with get_connection() as conn:
        if submission_year is not None:
            rows = conn.execute(
                "SELECT * FROM tef_provider_narratives "
                "WHERE submission_year = ? ORDER BY section, version DESC",
                (submission_year,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tef_provider_narratives "
                "ORDER BY submission_year DESC, section, version DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def add_tef_narrative(submission_year: int, section: str, narrative_text: str,
                       drafted_by: Optional[int] = None) -> int:
    if section not in TEF_SECTIONS:
        raise ValueError(f"unknown TEF section {section}; valid: {TEF_SECTIONS}")
    init_db()
    with get_connection() as conn:
        latest = conn.execute(
            "SELECT MAX(version) FROM tef_provider_narratives "
            "WHERE submission_year = ? AND section = ?",
            (submission_year, section),
        ).fetchone()[0]
        next_version = (latest or 0) + 1
        cur = conn.execute(
            """INSERT INTO tef_provider_narratives
               (submission_year, section, narrative_text, version, drafted_by)
               VALUES (?, ?, ?, ?, ?)""",
            (submission_year, section, narrative_text, next_version, drafted_by),
        )
        new_id = cur.lastrowid
    _audit("tef_narrative_added", resource_id=str(new_id),
           details={"year": submission_year, "section": section, "version": next_version})
    return new_id


def export_tef_submission(year: int, out_path: str) -> int:
    """Write a JSON file shaped for TEF: latest narrative per section,
    plus any computed indicator metrics. Returns total sections written."""
    payload: dict[str, Any] = {
        "submission_year": year,
        "generated_at": _now(),
        "indicators": compute_tef_indicators(year),
        "narratives": {},
    }
    rows = list_tef_narratives(submission_year=year)
    seen: set[str] = set()
    for r in rows:
        if r["section"] in seen:
            continue
        seen.add(r["section"])
        payload["narratives"][r["section"]] = {
            "version": r["version"],
            "text": r["narrative_text"],
            "drafted_at": r.get("created_at"),
        }
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    _audit("tef_export_written", details={"year": year, "path": out_path})
    return len(seen)


def compute_tef_indicators(year: Optional[int] = None) -> dict:
    """Best-effort derivation of TEF indicators from existing data.

    NSS data isn't held in this system, so the student-experience metric
    is reported as ``"n/a (NSS feed not configured)"``. The student-
    outcomes line piggybacks on whatever B3 snapshots exist for the
    most recent cohort year on file."""
    init_db()
    out: dict[str, Any] = {
        "student_experience": "n/a (NSS feed not configured)",
    }
    with get_connection() as conn:
        latest = conn.execute(
            "SELECT MAX(cohort_year) FROM ofs_b3_metrics"
        ).fetchone()[0]
    if not latest:
        out["student_outcomes"] = "n/a (no B3 snapshots)"
        return out
    snaps = list_b3_snapshots(cohort_year=latest)
    cont = next((s["value_pct"] for s in snaps if s["metric_type"] == "continuation"
                 and s.get("course") in (None, "")), None)
    comp = next((s["value_pct"] for s in snaps if s["metric_type"] == "completion"
                 and s.get("course") in (None, "")), None)
    out["student_outcomes"] = {
        "cohort_year": latest,
        "continuation_pct": cont,
        "completion_pct": comp,
    }
    return out


# ===========================================================================
# REF — impact cases (CRUD)
# ===========================================================================

def list_impact_cases(uoa: Optional[str] = None) -> list[dict]:
    init_db()
    with get_connection() as conn:
        if uoa:
            rows = conn.execute(
                "SELECT * FROM ref_impact_cases WHERE uoa = ? ORDER BY title",
                (uoa,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM ref_impact_cases ORDER BY uoa, title"
            ).fetchall()
        return [dict(r) for r in rows]


def create_impact_case(uoa: str, title: str, summary: Optional[str] = None,
                        lead_author_id: Optional[int] = None,
                        reach_significance: Optional[str] = None,
                        beneficiaries: Optional[str] = None) -> int:
    init_db()
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO ref_impact_cases
               (uoa, title, summary, lead_author_id, status,
                reach_significance, beneficiaries)
               VALUES (?, ?, ?, ?, 'draft', ?, ?)""",
            (uoa, title, summary, lead_author_id, reach_significance, beneficiaries),
        )
        new_id = cur.lastrowid
    _audit("impact_case_created", resource_id=str(new_id),
           details={"uoa": uoa, "title": title})
    return new_id


def update_impact_case(case_id: int, **fields: Any) -> bool:
    if not fields:
        return False
    allowed = {"title", "summary", "lead_author_id", "status",
               "reach_significance", "beneficiaries", "evidence_links",
               "quality_rating"}
    sets, params = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        sets.append(f"{k} = ?")
        params.append(v)
    if not sets:
        return False
    sets.append("updated_at = ?")
    params.append(_now())
    params.append(case_id)
    init_db()
    with get_connection() as conn:
        cur = conn.execute(
            f"UPDATE ref_impact_cases SET {', '.join(sets)} WHERE id = ?", params,
        )
        ok = cur.rowcount > 0
    if ok:
        _audit("impact_case_updated", resource_id=str(case_id), details=fields)
    return ok


def delete_impact_case(case_id: int) -> bool:
    init_db()
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM ref_impact_cases WHERE id = ?", (case_id,))
        ok = cur.rowcount > 0
    if ok:
        _audit("impact_case_deleted", resource_id=str(case_id))
    return ok


# ===========================================================================
# REF — environment statements (versioned)
# ===========================================================================

def list_environment_statements(uoa: Optional[str] = None) -> list[dict]:
    init_db()
    with get_connection() as conn:
        if uoa:
            rows = conn.execute(
                "SELECT * FROM ref_environment_statements WHERE uoa = ? "
                "ORDER BY version DESC", (uoa,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM ref_environment_statements "
                "ORDER BY uoa, version DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def add_environment_statement(uoa: str, narrative_text: str,
                               drafted_by: Optional[int] = None) -> int:
    init_db()
    with get_connection() as conn:
        latest = conn.execute(
            "SELECT MAX(version) FROM ref_environment_statements WHERE uoa = ?",
            (uoa,),
        ).fetchone()[0]
        next_version = (latest or 0) + 1
        cur = conn.execute(
            """INSERT INTO ref_environment_statements
               (uoa, narrative_text, version, drafted_by) VALUES (?, ?, ?, ?)""",
            (uoa, narrative_text, next_version, drafted_by),
        )
        new_id = cur.lastrowid
    _audit("environment_statement_added", resource_id=str(new_id),
           details={"uoa": uoa, "version": next_version})
    return new_id


# ===========================================================================
# REF — UoA summary + export
# ===========================================================================

def compute_uoa_summary(uoa: str) -> dict:
    """Return aggregate stats for a Unit of Assessment, joining the
    pre-existing ``research_outputs`` table."""
    init_db()
    out = {
        "uoa": uoa, "outputs_total": 0, "outputs_submitted": 0,
        "open_access_pct": 0.0, "avg_quality": None,
        "impact_cases": 0, "environment_statement_versions": 0,
    }
    with get_connection() as conn:
        if _has_table(conn, "research_outputs"):
            r = conn.execute(
                """SELECT
                     COUNT(*) AS total,
                     SUM(CASE WHEN ref_submitted = 1 THEN 1 ELSE 0 END) AS submitted,
                     SUM(CASE WHEN open_access = 1 THEN 1 ELSE 0 END) AS oa,
                     AVG(CAST(REPLACE(quality_rating, '*', '') AS REAL)) AS avg_q
                   FROM research_outputs
                   WHERE uoa = ?""", (uoa,),
            ).fetchone()
            total = (r[0] if isinstance(r, tuple) else r["total"]) or 0
            submitted = (r[1] if isinstance(r, tuple) else r["submitted"]) or 0
            oa = (r[2] if isinstance(r, tuple) else r["oa"]) or 0
            avg_q = r[3] if isinstance(r, tuple) else r["avg_q"]
            out["outputs_total"] = total
            out["outputs_submitted"] = submitted
            out["open_access_pct"] = round(100.0 * oa / total, 2) if total else 0.0
            out["avg_quality"] = round(avg_q, 2) if avg_q else None
        out["impact_cases"] = conn.execute(
            "SELECT COUNT(*) FROM ref_impact_cases WHERE uoa = ?", (uoa,),
        ).fetchone()[0]
        out["environment_statement_versions"] = conn.execute(
            "SELECT COUNT(*) FROM ref_environment_statements WHERE uoa = ?", (uoa,),
        ).fetchone()[0]
    return out


def export_ref_submission(uoa: str, out_path: str) -> int:
    """CSV containing the UoA's outputs (from research_outputs), impact
    cases, and the latest environment statement. Returns total rows."""
    init_db()
    rows: list[dict] = []
    with get_connection() as conn:
        if _has_table(conn, "research_outputs"):
            for r in conn.execute(
                """SELECT 'output' AS kind, id, title,
                          venue AS detail, quality_rating, open_access
                   FROM research_outputs WHERE uoa = ?""", (uoa,),
            ).fetchall():
                rows.append(dict(r) if not isinstance(r, tuple) else {
                    "kind": r[0], "id": r[1], "title": r[2],
                    "detail": r[3], "quality_rating": r[4], "open_access": r[5],
                })
        for c in list_impact_cases(uoa=uoa):
            rows.append({
                "kind": "impact_case", "id": c["id"], "title": c["title"],
                "detail": (c.get("summary") or "")[:200],
                "quality_rating": c.get("quality_rating"), "open_access": "",
            })
        for e in list_environment_statements(uoa=uoa)[:1]:
            rows.append({
                "kind": "environment", "id": e["id"],
                "title": f"Environment statement v{e['version']}",
                "detail": (e.get("narrative_text") or "")[:200],
                "quality_rating": "", "open_access": "",
            })

    fields = ("kind", "id", "title", "detail", "quality_rating", "open_access")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    _audit("ref_export_written", details={"uoa": uoa, "rows": len(rows), "path": out_path})
    return len(rows)


# ===========================================================================
# KPIs
# ===========================================================================

def compute_external_qa_kpis() -> list[dict]:
    """Return KPI dicts ready for ``KPIManager.record_kpi``."""
    init_db()
    out: list[dict] = []
    with get_connection() as conn:
        # Latest cohort B3 metrics — institution-wide rows (course IS NULL)
        latest = conn.execute(
            "SELECT MAX(cohort_year) FROM ofs_b3_metrics WHERE course IS NULL"
        ).fetchone()[0]
        if latest:
            for mt in OFS_B3_METRICS:
                row = conn.execute(
                    "SELECT value_pct FROM ofs_b3_metrics "
                    "WHERE cohort_year = ? AND course IS NULL AND metric_type = ?",
                    (latest, mt),
                ).fetchone()
                if not row:
                    continue
                pct = row[0] if isinstance(row, tuple) else row["value_pct"]
                if pct is None or pct < 0:
                    continue
                out.append({
                    "kpi_name": f"OfS B3 {mt} % ({latest} cohort)",
                    "kpi_category": "external_qa",
                    "current_value": float(pct), "target_value": 90.0,
                    "period": "annual", "trend": "",
                })

        # APP milestone progress
        total_ms = conn.execute("SELECT COUNT(*) FROM ofs_app_milestones").fetchone()[0] or 0
        achieved_ms = conn.execute(
            "SELECT COUNT(*) FROM ofs_app_milestones WHERE achieved = 1"
        ).fetchone()[0] or 0
        if total_ms:
            out.append({
                "kpi_name": "APP milestones achieved %",
                "kpi_category": "external_qa",
                "current_value": round(100.0 * achieved_ms / total_ms, 2),
                "target_value": 100.0, "period": "monthly", "trend": "",
            })

        # REF coverage — % of UoAs with any output rows + at least one impact case
        if _has_table(conn, "research_outputs"):
            uoas_with_outputs = conn.execute(
                "SELECT COUNT(DISTINCT uoa) FROM research_outputs WHERE uoa IS NOT NULL"
            ).fetchone()[0] or 0
            uoas_with_impact = conn.execute(
                "SELECT COUNT(DISTINCT uoa) FROM ref_impact_cases"
            ).fetchone()[0] or 0
            out.append({
                "kpi_name": "REF UoAs with outputs",
                "kpi_category": "external_qa",
                "current_value": float(uoas_with_outputs),
                "target_value": float(len(REF_UOAS)),
                "period": "annual", "trend": "",
            })
            out.append({
                "kpi_name": "REF UoAs with impact cases",
                "kpi_category": "external_qa",
                "current_value": float(uoas_with_impact),
                "target_value": float(len(REF_UOAS)),
                "period": "annual", "trend": "",
            })

        # Submission readiness — % of frameworks with an active submission
        # row for the current calendar year
        this_year = date.today().year
        ready = conn.execute(
            "SELECT COUNT(DISTINCT framework) FROM qa_submissions "
            "WHERE submission_year = ?", (this_year,),
        ).fetchone()[0] or 0
        out.append({
            "kpi_name": f"Frameworks with active {this_year} submission",
            "kpi_category": "external_qa",
            "current_value": float(ready), "target_value": float(len(FRAMEWORKS)),
            "period": "annual", "trend": "",
        })
    return out


def record_external_qa_kpis() -> int:
    try:
        from education_system.university_system.modules.shared.services.analytics.analytics_dashboard_core import (
            KPIManager,
        )
    except Exception:
        return 0
    n = 0
    for k in compute_external_qa_kpis():
        try:
            KPIManager.record_kpi(
                kpi_name=k["kpi_name"], kpi_category=k["kpi_category"],
                current_value=k["current_value"], target_value=k.get("target_value"),
                period=k.get("period", "annual"), trend=k.get("trend", ""),
            )
            n += 1
        except Exception as exc:
            logger.warning("KPI record failed for %s: %s", k["kpi_name"], exc)
    return n


__all__ = [
    "FRAMEWORKS", "QA_STATUSES", "OFS_B3_METRICS", "TEF_SECTIONS",
    "REF_UOAS", "REF_IMPACT_STATUSES",
    "init_db",
    "upsert_submission", "list_submissions", "sign_off_submission",
    "compute_b3_metrics", "record_b3_snapshot", "list_b3_snapshots",
    "export_ofs_return",
    "list_app_milestones", "create_app_milestone",
    "update_app_milestone", "delete_app_milestone",
    "list_protection_plans", "create_protection_plan",
    "list_tef_narratives", "add_tef_narrative",
    "compute_tef_indicators", "export_tef_submission",
    "list_impact_cases", "create_impact_case",
    "update_impact_case", "delete_impact_case",
    "list_environment_statements", "add_environment_statement",
    "compute_uoa_summary", "export_ref_submission",
    "compute_external_qa_kpis", "record_external_qa_kpis",
]
