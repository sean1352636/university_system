"""Safeguarding: what's due, summaries, reports and the CSV export.

The rules and the store are in :mod:`safeguarding`; this is read-only over
them (leads only), apart from the export's audit line.
"""

from __future__ import annotations

import csv
import datetime as _dt
from collections import Counter
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.safeguarding.domain import safeguarding as SG  # registers the tables
from education_system.systems.secondary.modules.safeguarding.domain.safeguarding import (
    NEW,
    SEVERITIES,
    Concern,
    ValidationError,
    _name,
    _require_lead,
    _row,
    _SELECT,
    get,
    is_lead,
    list_actions,
    list_concerns,
    list_referrals,
)
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database


# ── Due ──────────────────────────────────────────────────────────────

def due(*, actor: Principal, today: _dt.date | None = None, within_days: int = 14
        ) -> list[dict[str, Any]]:
    """What needs doing: new reports, urgent ones not passed on, actions due
    in the next *within_days* or overdue, referrals waiting for an outcome
    (over 7 days). Each ``{'due', 'overdue', 'kind', 'concern_id', 'pupil',
    'what', 'action_id'}``, soonest first."""
    _require_lead(actor, "due")
    day = today or _today()
    horizon = (day + _dt.timedelta(days=within_days)).isoformat()
    iso = day.isoformat()
    out: list[dict[str, Any]] = []
    with database.connect() as conn:
        for r in conn.execute(_SELECT + " WHERE c.status = 'New' OR c.needs_phone_call = 1"):
            c = _row(r)
            out.append({"due": c.raised_date, "overdue": c.urgent or c.raised_date < iso,
                        "kind": "Phone the DSL" if c.needs_phone_call else "Triage",
                        "concern_id": c.concern_id, "action_id": None,
                        "pupil": f"{c.pupil_name} ({c.admission_no})",
                        "what": ("URGENT - " if c.urgent else "")
                        + ("no e-mail reached the team - phone the DSL" if c.needs_phone_call
                           else f"New report: {c.category}")})
        for r in conn.execute(
                "SELECT a.*, p.legal_last_name, p.legal_first_name, p.preferred_name, "
                "p.admission_no FROM safeguarding_actions a JOIN safeguarding_concerns c "
                "USING (concern_id) JOIN pupils p ON p.pupil_id = c.pupil_id WHERE "
                "a.due_date IS NOT NULL AND a.completed_date IS NULL AND a.due_date <= ?",
                (horizon,)):
            out.append({"due": r["due_date"], "overdue": r["due_date"] < iso, "kind": "Action",
                        "concern_id": r["concern_id"], "action_id": r["action_id"],
                        "pupil": f"{_name(r)} ({r['admission_no']})",
                        "what": f"{r['action_type']}: {r['summary'][:80]}"
                                + (f" ({r['assigned_to']})" if r["assigned_to"] else "")})
        week = (day - _dt.timedelta(days=7)).isoformat()
        for r in conn.execute(
                "SELECT r.*, p.legal_last_name, p.legal_first_name, p.preferred_name, "
                "p.admission_no FROM safeguarding_referrals r JOIN safeguarding_concerns c "
                "USING (concern_id) JOIN pupils p ON p.pupil_id = c.pupil_id WHERE "
                "r.outcome = 'Pending' AND r.referral_date <= ?", (week,)):
            out.append({"due": r["referral_date"], "overdue": True, "kind": "Referral",
                        "concern_id": r["concern_id"], "action_id": None,
                        "pupil": f"{_name(r)} ({r['admission_no']})",
                        "what": f"Chase {r['agency']} for the outcome"
                                + (f" (ref {r['reference']})" if r["reference"] else "")})
    return sorted(out, key=lambda x: (not x["overdue"], x["due"] or "9999", x["concern_id"]))


# ── Summaries ────────────────────────────────────────────────────────

def concern_summary(concern_id: int, *, actor: Principal) -> dict[str, Any]:
    """The old concern summary: the concern, its actions, count and by type."""
    rec = get(concern_id, actor=actor)
    actions = list_actions(concern_id, actor=actor, log=False)
    return {"concern": rec, "actions": actions, "action_count": len(actions),
            "by_type": dict(Counter(a.action_type for a in actions)),
            "referrals": list_referrals(actor=actor, concern_id=rec.concern_id)}


def cohort_summary(*, actor: Principal, year_group: int | str | None = None,
                   date_from: str | None = None, date_to: str | None = None) -> dict[str, Any]:
    """The old summary (total, open, by status / severity / category, open
    critical) plus new reports, urgent open and by level of need."""
    rows = list_concerns(actor=actor, year_group=year_group, date_from=date_from,
                         date_to=date_to)
    open_rows = [r for r in rows if r.is_open]
    return {"total": len(rows), "open": len(open_rows),
            "by_status": dict(Counter(r.status for r in rows)),
            "by_severity": dict(Counter(r.severity for r in rows)),
            "by_category": dict(Counter(r.category for r in rows)),
            "by_level": dict(Counter(r.level_of_need or "(not triaged)" for r in rows)),
            "open_critical": sum(1 for r in open_rows if r.severity == "Critical"),
            "new": sum(1 for r in rows if r.status == NEW),
            "urgent_open": sum(1 for r in open_rows if r.urgent),
            "pupils": len({r.pupil_id for r in open_rows})}


def pupils_with_concerns(*, actor: Principal, severity_min: str = "High"
                         ) -> dict[int, list[Concern]]:
    """``{pupil_id: [open concerns]}`` for pupils with at least one open
    concern at *severity_min* or above."""
    if severity_min not in SEVERITIES:
        raise ValidationError([f"Minimum severity must be one of {', '.join(SEVERITIES)}"])
    threshold = SEVERITIES.index(severity_min)
    out: dict[int, list[Concern]] = {}
    for r in list_concerns(actor=actor, open_only=True):
        if SEVERITIES.index(r.severity) >= threshold:
            out.setdefault(r.pupil_id, []).append(r)
    return out


_GROUPS = {"category": lambda c: c.category,
           "level": lambda c: c.level_of_need or "(not triaged)",
           "year": lambda c: f"Year {c.pupil_year}", "severity": lambda c: c.severity,
           "status": lambda c: c.status, "month": lambda c: c.raised_date[:7]}


def analysis(*, actor: Principal, by: str = "category", date_from: str | None = None,
             date_to: str | None = None) -> list[dict[str, Any]]:
    """Concerns grouped: {'group', 'concerns', 'open', 'pupils', 'referred'}."""
    if by not in _GROUPS:
        raise ValidationError([f"Group by one of {', '.join(_GROUPS)}"])
    rows = list_concerns(actor=actor, date_from=date_from, date_to=date_to)
    groups: dict[str, list[Concern]] = {}
    for c in rows:
        groups.setdefault(_GROUPS[by](c), []).append(c)
    return sorted(({"group": g, "concerns": len(v), "open": sum(1 for c in v if c.is_open),
                    "pupils": len({c.pupil_id for c in v}),
                    "referred": sum(1 for c in v if c.referral_body)}
                   for g, v in groups.items()), key=lambda x: (-x["concerns"], x["group"]))


def my_day(*, actor: Principal) -> dict[str, int] | None:
    """For a lead's My Day: new reports, urgent ones and overdue items."""
    if not is_lead(actor):
        return None
    items = due(actor=actor, within_days=0)
    return {"new": sum(1 for x in items if x["kind"] == "Triage"),
            "urgent": sum(1 for x in items if x["kind"] in ("Triage", "Phone the DSL")
                          and x["what"].startswith("URGENT")),
            "overdue": sum(1 for x in items if x["overdue"] and x["kind"] != "Triage")}


# ── Export ───────────────────────────────────────────────────────────

def export_csv(path: str | Path, *, actor: Principal, **filters: Any) -> int:
    """The concern list as CSV (no descriptions, the child's words or notes)."""
    rows = list_concerns(actor=actor, **filters)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "admission_no", "pupil", "year", "raised", "category", "severity",
                    "urgent", "level_of_need", "status", "dsl_reviewer", "review_date",
                    "referral_body", "referral_date", "referral_reference", "closed",
                    "confidential"])
        for c in rows:
            w.writerow([c.concern_id, _safe(c.admission_no), _safe(c.pupil_name), c.pupil_year,
                        c.raised_date, c.category, c.severity, "Y" if c.urgent else "",
                        c.level_of_need or "", c.status, _safe(c.dsl_reviewer),
                        c.review_date or "", c.referral_body or "", c.referral_date or "",
                        _safe(c.referral_reference), c.closed_date or "",
                        "Y" if c.confidential else "N"])
    with database.connect() as conn:
        SG._audit(conn, "export", actor, rows=len(rows))
    activity_log.record("safeguarding.export", principal=actor, rows=len(rows))
    return len(rows)
