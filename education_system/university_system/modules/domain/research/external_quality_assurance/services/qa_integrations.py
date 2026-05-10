"""Cross-module integration helpers for External QA.

This module is the home for everything that touches *other* parts of
the system: scheduled jobs, webhooks, REST/outbox, AI hooks, evidence
bundling, GDPR redaction, and cross-system aggregation.

All entry points are best-effort and log on failure — the EQA module
must never break a sibling module's flow.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
import zipfile
from datetime import date, datetime, timedelta
from typing import Any, Optional

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.domain.research.external_quality_assurance.services import (
    qa_service as qa,
)

logger = logging.getLogger(__name__)


# =====================================================================
# #12 — Nightly B3 snapshot
# =====================================================================

def b3_nightly_job() -> int:
    """Snapshot B3 for the current academic year. Returns metric count.

    Wire into the existing maintenance scheduler with a daily cron::

        from .qa_integrations import b3_nightly_job
        threading.Thread(target=lambda: b3_nightly_job(), daemon=True).start()
    """
    year = date.today().year
    try:
        return qa.record_b3_snapshot(year)
    except Exception:
        logger.exception("b3_nightly_job failed for year %s", year)
        return 0


# =====================================================================
# #13 — Deadline watcher
# =====================================================================

def eqa_deadline_watcher(threshold_days: int = 14) -> list[dict]:
    """Return submissions and APP milestones whose due-date is within
    ``threshold_days``. Caller decides how to surface (toast, email, etc.).
    """
    qa.init_db()
    cutoff = (date.today() + timedelta(days=threshold_days)).isoformat()
    today = date.today().isoformat()
    out: list[dict] = []
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, framework, submission_year, submission_date, status "
            "FROM qa_submissions "
            "WHERE submission_date IS NOT NULL "
            "AND submission_date BETWEEN ? AND ? "
            "AND status NOT IN ('submitted','accepted')",
            (today, cutoff),
        ).fetchall()
        for r in rows:
            out.append({"kind": "submission", **dict(r)})
        rows = conn.execute(
            "SELECT id, plan_year, milestone_text, target_date, achieved "
            "FROM ofs_app_milestones "
            "WHERE target_date IS NOT NULL "
            "AND target_date BETWEEN ? AND ? "
            "AND achieved = 0",
            (today, cutoff),
        ).fetchall()
        for r in rows:
            out.append({"kind": "milestone", **dict(r)})
    return out


# =====================================================================
# #14 — Auto-publish KPIs whenever EQA tables change
# =====================================================================

def auto_publish_kpis_on_change() -> int:
    """Convenience: recompute & publish all EQA KPIs. Hooked from
    sign-off (8.117.137) and exposed for callers that mutate EQA tables
    via custom scripts."""
    try:
        return qa.record_external_qa_kpis()
    except Exception:
        logger.exception("auto_publish_kpis_on_change failed")
        return 0


# =====================================================================
# #16 — Webhook dispatch
# =====================================================================

_QA_EVENTS = (
    "qa.submission_created", "qa.submission_updated",
    "qa.submission_signed_off",
    "qa.b3_snapshot_recorded",
    "qa.app_milestone_created", "qa.app_milestone_updated",
    "qa.impact_case_created", "qa.impact_case_updated",
    "qa.tef_narrative_added", "qa.environment_statement_added",
    "qa.export_written",
)


def dispatch_qa_webhook(event_type: str, payload: dict,
                          system_key: str = "university") -> int:
    """Fan ``event_type`` out to subscribers via the existing webhook
    service. Returns the queued-delivery count (0 on best-effort fail)."""
    try:
        from education_system.shared.webhooks.webhook_service import WebhookService
    except Exception:
        return 0
    try:
        return WebhookService().dispatch(event_type, payload, system_key=system_key)
    except Exception:
        logger.exception("dispatch_qa_webhook(%s) failed", event_type)
        return 0


# =====================================================================
# #17 — Outbox event for offline-sync
# =====================================================================

def enqueue_qa_outbox(event_type: str, payload: dict) -> bool:
    """Push an event onto the offline-sync outbox so satellite installs
    converge. Best-effort — silently no-ops if the outbox subsystem
    isn't installed."""
    try:
        from education_system.shared.offline_sync import outbox  # type: ignore
    except Exception:
        return False
    try:
        outbox.enqueue(event_type, payload)  # type: ignore[attr-defined]
        return True
    except Exception:
        logger.exception("enqueue_qa_outbox(%s) failed", event_type)
        return False


# =====================================================================
# #22 — Cross-system aggregator
# =====================================================================

def aggregate_qa_across_systems() -> dict:
    """Combine ``get_qa_summary_dict`` snapshots from every subsystem.
    Each subsystem is expected to expose a ``get_qa_summary_dict`` in
    the same import path; missing subsystems are skipped."""
    out: dict[str, Any] = {}
    candidates = [
        ("university",
         "education_system.university_system.modules.domain.research."
         "external_quality_assurance.services.qa_service"),
    ]
    import importlib
    for sys_key, modpath in candidates:
        try:
            mod = importlib.import_module(modpath)
            getter = getattr(mod, "get_qa_summary_dict", None)
            if callable(getter):
                out[sys_key] = getter()
        except Exception:
            continue
    return out


# =====================================================================
# #23 — AI-drafted TEF narrative
# =====================================================================

def draft_tef_narrative(section: str, year: int,
                          save: bool = True) -> str:
    """Use the chatbot integration to draft a TEF narrative for
    ``section`` based on B3 snapshots for ``year``. If ``save`` and a
    draft is produced, persist as a new ``tef_provider_narratives``
    version. Returns the draft text (empty string on failure)."""
    snaps = qa.list_b3_snapshots(cohort_year=year)
    indicator_text = "; ".join(
        f"{s['metric_type']}={s['value_pct']}%" for s in snaps
        if s.get("course") in (None, "") and s.get("value_pct", -1) >= 0
    ) or "no B3 data on file"
    prompt = (
        f"Draft a TEF '{section}' provider narrative for academic year "
        f"{year}/{(year + 1) % 100:02d}. Tie the argument to these "
        f"indicators where possible: {indicator_text}. Keep it under "
        f"600 words, formal register."
    )
    try:
        from education_system.university_system.modules.shared.cli.chatbot_integration import (
            run_completion,  # type: ignore
        )
        text = run_completion(prompt) or ""
    except Exception:
        logger.exception("draft_tef_narrative: chatbot unavailable")
        text = ""
    if save and text:
        try:
            qa.add_tef_narrative(year, section, text)
        except Exception:
            logger.exception("draft_tef_narrative: save failed")
    return text


# =====================================================================
# #24 — Cluster recent alerts into APP milestone candidates
# =====================================================================

def suggest_app_milestones_from_alerts(alerts: list[dict],
                                         max_candidates: int = 5) -> list[dict]:
    """Group alerts by ``metric`` (or ``category`` / ``type``); each
    cluster of >=3 becomes a candidate milestone the user can
    promote via :func:`qa.promote_alert_to_app_milestone`."""
    buckets: dict[str, list[dict]] = {}
    for a in alerts:
        key = (a.get("metric") or a.get("category") or a.get("type")
               or "uncategorised")
        buckets.setdefault(key, []).append(a)
    candidates: list[dict] = []
    for key, group in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
        if len(group) < 3:
            continue
        candidates.append({
            "title": f"Address {key} risk in {len(group)} students",
            "description": f"Aggregated from {len(group)} predictive alerts",
            "metric": key,
            "_alert_ids": [a.get("id") for a in group if a.get("id")],
        })
        if len(candidates) >= max_candidates:
            break
    return candidates


# =====================================================================
# #25 — RAG risk score for B3 grid
# =====================================================================

def risk_score_for_b3(metric: str, value_pct: float) -> str:
    """Return ``"green"`` / ``"amber"`` / ``"red"`` for a B3 cell.
    Thresholds reflect OfS B3 institution-wide minimums (continuation
    80%, completion 75%, progression 60%) widely used as benchmarks."""
    if value_pct is None or value_pct < 0:
        return "n/a"
    floors = {"continuation": (80.0, 90.0),
              "completion": (75.0, 85.0),
              "progression": (60.0, 75.0)}
    lo, hi = floors.get(metric, (60.0, 80.0))
    if value_pct < lo:
        return "red"
    if value_pct < hi:
        return "amber"
    return "green"


# =====================================================================
# #26 — Evidence pack ZIP
# =====================================================================

def eqa_evidence_pack(submission_id: int, output_path: str) -> str:
    """Bundle audit log, CSV/JSON exports, and HESA cross-references
    into a single ZIP suitable for a regulator data request. Returns
    the path written."""
    qa.init_db()
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with get_connection() as conn:
        sub = conn.execute(
            "SELECT * FROM qa_submissions WHERE id = ?", (submission_id,),
        ).fetchone()
        if not sub:
            raise ValueError(f"submission {submission_id} not found")
        sub_d = dict(sub)
        audits = conn.execute(
            "SELECT * FROM security_events "
            "WHERE resource_type = 'qa' AND resource_id = ? ORDER BY id",
            (str(submission_id),),
        ).fetchall() if _table_exists(conn, "security_events") else []
        audits = [dict(r) for r in audits]
    hesa_links = qa.list_hesa_links(submission_id)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("submission.json", json.dumps(sub_d, indent=2, default=str))
        z.writestr("audit_log.json", json.dumps(audits, indent=2, default=str))
        z.writestr("hesa_links.json", json.dumps(hesa_links, indent=2, default=str))
        if sub_d["framework"] == "OfS":
            buf = io.StringIO()
            year = sub_d["submission_year"]
            qa.export_ofs_return(year, _temp_csv := os.path.join(
                os.path.dirname(output_path) or ".", f"_ofs_{year}.csv"))
            with open(_temp_csv, "r", encoding="utf-8") as fh:
                z.writestr(f"ofs_b3_{year}.csv", fh.read())
            os.remove(_temp_csv)
    qa._audit("evidence_pack_built", resource_id=str(submission_id),
              details={"path": output_path})
    return output_path


def _table_exists(conn, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone() is not None


# =====================================================================
# #27 — GDPR redaction
# =====================================================================

def gdpr_redact_qa(user_id: int) -> int:
    """When the GDPR module deletes a user, scrub identifying foreign
    keys in EQA tables. Returns count of rows touched. Records a
    redaction audit event."""
    qa.init_db()
    n = 0
    with get_connection() as conn:
        for table, col in (
            ("qa_submissions", "assigned_to"),
            ("qa_submissions", "signed_off_by"),
            ("ofs_app_milestones", "owner_id"),
            ("ofs_protection_plans", "approved_by"),
            ("tef_provider_narratives", "drafted_by"),
            ("ref_impact_cases", "lead_author_id"),
            ("ref_environment_statements", "drafted_by"),
        ):
            try:
                cur = conn.execute(
                    f"UPDATE {table} SET {col} = NULL WHERE {col} = ?",
                    (user_id,),
                )
                n += cur.rowcount or 0
            except Exception:
                logger.exception("gdpr_redact_qa: %s.%s failed", table, col)
    qa._audit("gdpr_redacted", details={"user_id": user_id, "rows": n})
    return n


__all__ = [
    "b3_nightly_job", "eqa_deadline_watcher", "auto_publish_kpis_on_change",
    "dispatch_qa_webhook", "enqueue_qa_outbox",
    "aggregate_qa_across_systems",
    "draft_tef_narrative", "suggest_app_milestones_from_alerts",
    "risk_score_for_b3",
    "eqa_evidence_pack", "gdpr_redact_qa",
]
