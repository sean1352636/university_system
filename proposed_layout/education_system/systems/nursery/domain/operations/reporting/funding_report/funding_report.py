"""Domain layer for the Funding Report (Nursery System).

A computed, read-only report. It owns no table of its own — it aggregates the two
funding tables: ``funded_hours_records`` (the detailed funded-entitlement records
behind each child's place) and ``funding_claims`` (the claims made to the local
authority for those funded hours). Produces an entitlement breakdown, a claims
detail list and roll-up totals by status and funding period.

Follows the 4-layer pattern: computation + SQLite access here, CLI in
``funding_report_cli.py``, Tk GUI in ``funding_report_views.py``.
"""

from __future__ import annotations

import csv
import datetime as _dt
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from education_system.systems.nursery.infrastructure import paths
from education_system.systems.nursery.infrastructure.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Funding Report"
CATEGORY = "Compliance & Reports"


@dataclass
class EntitlementRow:
    entitlement: str
    children: int
    funded_hours_pw_total: float
    additional_hours_total: float


@dataclass
class ClaimRow:
    claim_id: str
    pupil_name: str
    funding_period: str | None
    entitlement: str | None
    funded_hours: float
    weeks: float
    hourly_rate: float
    claim_amount: float
    status: str
    headcount_date: str | None
    submitted_date: str | None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for funding report")
        raise


# ── Reads / computation ──────────────────────────────────────────────────────

def entitlement_breakdown() -> list[EntitlementRow]:
    """Per-entitlement roll-up over active ``funded_hours_records``."""
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT entitlement, "
                "COUNT(DISTINCT pupil_id) AS children, "
                "COALESCE(SUM(funded_hours_pw), 0) AS funded_total, "
                "COALESCE(SUM(additional_hours), 0) AS additional_total "
                "FROM funded_hours_records WHERE status = 'active' "
                "GROUP BY entitlement ORDER BY entitlement").fetchall()
    except sqlite3.Error:
        logger.exception("entitlement_breakdown failed")
        raise
    return [
        EntitlementRow(
            entitlement=r["entitlement"] or "-",
            children=int(r["children"] or 0),
            funded_hours_pw_total=float(r["funded_total"] or 0),
            additional_hours_total=float(r["additional_total"] or 0),
        )
        for r in rows
    ]


def list_claims() -> list[ClaimRow]:
    """All funding claims with the child's name, newest headcount first."""
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT c.claim_id, c.funding_period, c.entitlement, "
                "c.funded_hours, c.weeks, c.hourly_rate, c.claim_amount, "
                "c.status, c.headcount_date, c.submitted_date, "
                "p.first_name, p.last_name "
                "FROM funding_claims c "
                "LEFT JOIN pupils p ON p.pupil_id = c.pupil_id "
                "ORDER BY c.headcount_date DESC, c.claim_id").fetchall()
    except sqlite3.Error:
        logger.exception("list_claims failed")
        raise
    out: list[ClaimRow] = []
    for r in rows:
        fn, ln = r["first_name"], r["last_name"]
        name = f"{fn or ''} {ln or ''}".strip() if (fn or ln) else "(unknown)"
        out.append(ClaimRow(
            claim_id=r["claim_id"], pupil_name=name,
            funding_period=r["funding_period"], entitlement=r["entitlement"],
            funded_hours=float(r["funded_hours"] or 0),
            weeks=float(r["weeks"] or 0),
            hourly_rate=float(r["hourly_rate"] or 0),
            claim_amount=float(r["claim_amount"] or 0),
            status=r["status"], headcount_date=r["headcount_date"],
            submitted_date=r["submitted_date"],
        ))
    return out


def claims_summary() -> dict[str, object]:
    """Totals over ``funding_claims``: by status, by period and headlines."""
    _ensure_schema()
    try:
        with connect() as conn:
            by_status_rows = conn.execute(
                "SELECT status, COUNT(*) AS n, "
                "COALESCE(SUM(claim_amount), 0) AS amt "
                "FROM funding_claims GROUP BY status").fetchall()
            by_period_rows = conn.execute(
                "SELECT funding_period, COUNT(*) AS n, "
                "COALESCE(SUM(claim_amount), 0) AS amt "
                "FROM funding_claims GROUP BY funding_period "
                "ORDER BY funding_period").fetchall()
    except sqlite3.Error:
        logger.exception("claims_summary failed")
        raise
    by_status = {
        (r["status"] or "-"): {"count": int(r["n"]), "amount": float(r["amt"])}
        for r in by_status_rows
    }
    by_period = {
        (r["funding_period"] or "-"): {
            "count": int(r["n"]), "amount": float(r["amt"])}
        for r in by_period_rows
    }
    total_amount = sum(v["amount"] for v in by_status.values())
    submitted_amount = by_status.get("submitted", {}).get("amount", 0.0)
    draft_amount = by_status.get("draft", {}).get("amount", 0.0)
    return {
        "by_status": by_status,
        "by_period": by_period,
        "total_amount": total_amount,
        "submitted_amount": submitted_amount,
        "draft_amount": draft_amount,
    }


def summary() -> dict[str, object]:
    """Headline roll-up across funded hours records and claims."""
    _ensure_schema()
    try:
        with connect() as conn:
            funded = conn.execute(
                "SELECT COUNT(DISTINCT pupil_id) AS children, "
                "COALESCE(SUM(funded_hours_pw), 0) AS funded_total, "
                "COALESCE(SUM(additional_hours), 0) AS additional_total "
                "FROM funded_hours_records WHERE status = 'active'").fetchone()
    except sqlite3.Error:
        logger.exception("summary failed")
        raise
    cs = claims_summary()
    by_status: dict = cs["by_status"]  # type: ignore[assignment]
    claims_count = sum(v["count"] for v in by_status.values())
    return {
        "active_funded_children": int(funded["children"] or 0),
        "total_funded_hours_pw": float(funded["funded_total"] or 0),
        "total_additional_hours_pw": float(funded["additional_total"] or 0),
        "claims_count": claims_count,
        "total_claim_amount": cs["total_amount"],
        "submitted_amount": cs["submitted_amount"],
        "draft_amount": cs["draft_amount"],
    }


# ── Export ───────────────────────────────────────────────────────────────────

def export_csv(path: str | Path | None = None) -> dict[str, object]:
    """Write the claims detail list to CSV; return path + row count."""
    rows = list_claims()
    if path is None:
        paths.ensure_directories()
        path = paths.DATA_DIR / (
            f"funding_report_{_dt.date.today().isoformat()}.csv")
    path = Path(path)
    headers = ["claim_id", "child", "funding_period", "entitlement",
               "funded_hours", "weeks", "hourly_rate", "claim_amount",
               "status", "headcount_date", "submitted_date"]
    try:
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(headers)
            for r in rows:
                w.writerow([
                    r.claim_id, r.pupil_name, r.funding_period or "",
                    r.entitlement or "", r.funded_hours, r.weeks,
                    r.hourly_rate, r.claim_amount, r.status,
                    r.headcount_date or "", r.submitted_date or "",
                ])
    except OSError as e:
        logger.exception("Could not write funding CSV to %s", path)
        raise OSError(f"Could not write report — {e}") from e
    return {"path": str(path), "row_count": len(rows)}
