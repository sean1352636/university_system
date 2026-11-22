"""Counselling service reports: waiting times and outcomes.

Both are aggregates for the counselling team (no names, no clinical text).

* :func:`wait_times` — for referrals made in a period: days from referral to
  triage and from referral to the first session held or booked (median,
  mean, longest), by priority; and the waiting list now (how many, oldest,
  mean age, by priority, same-day ones still unallocated).
* :func:`outcomes` — for each measure, every episode with both a first and a
  last score (the ``first``-stage score, else the earliest; the
  ``last``-stage score, else the latest after it): mean first, last and
  change, and the share reliably improved, reliably deteriorated, recovered
  and reliably recovered (``outcome_measures.change``).
"""

from __future__ import annotations

import statistics
from datetime import date

from education_system.systems.university.domains.student_support.domain.mental_health import (
    counselling_schema,
    outcome_measures,
)
from education_system.systems.university.domains.student_support.domain.wellbeing.casework import (
    access,
)
from education_system.systems.university.infrastructure.database.db import get_connection

PRIORITY_LABELS = {1: "1 — crisis", 2: "2 — same day", 3: "3 — priority", 4: "4 — routine",
                   None: "untriaged"}


def _days(start, end) -> int | None:
    if not start or not end:
        return None
    return (date.fromisoformat(str(end)[:10]) - date.fromisoformat(str(start)[:10])).days


def _summary(values) -> dict:
    values = [v for v in values if v is not None]
    if not values:
        return {"n": 0, "median": None, "mean": None, "max": None}
    return {"n": len(values), "median": statistics.median(values),
            "mean": round(statistics.mean(values), 1), "max": max(values)}


def _period_clause(date_from, date_to) -> tuple[str, list]:
    clauses, params = [], []
    if date_from:
        clauses.append("substr(r.referred_at, 1, 10) >= ?")
        params.append(str(date_from)[:10])
    if date_to:
        clauses.append("substr(r.referred_at, 1, 10) <= ?")
        params.append(str(date_to)[:10])
    return (" AND ".join(clauses) or "1 = 1"), params


def wait_times(actor, date_from=None, date_to=None) -> dict:
    access.require_counselling_team(actor)
    counselling_schema.ensure()
    where, params = _period_clause(date_from, date_to)
    conn = get_connection()
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT r.referral_id, r.priority, r.referred_at, r.triaged_at, r.status, "
            "r.same_day_due, (SELECT MIN(s.session_date) FROM counselling_sessions s "
            "WHERE s.referral_id = r.referral_id AND COALESCE(s.status, 'booked') "
            f"<> 'cancelled') AS first_session FROM counselling_referrals r WHERE {where}",
            params)]  # nosec B608 - clause built from literals
        waiting = [dict(r) for r in conn.execute(
            "SELECT priority, referred_at, same_day_due, status FROM counselling_referrals "
            "WHERE status IN ('referred', 'waiting')")]
    finally:
        conn.close()
    return {"period": {"from": date_from, "to": date_to}, "referrals": len(rows),
            "to_triage": _summary(_days(r["referred_at"], r["triaged_at"]) for r in rows),
            "to_first_session": _summary(_days(r["referred_at"], r["first_session"])
                                         for r in rows),
            "by_priority": _by_priority(rows),
            "waiting_now": _waiting_now(waiting)}


def _by_priority(rows) -> list[dict]:
    out = []
    for priority in sorted({r["priority"] for r in rows}, key=lambda p: p or 99):
        group = [r for r in rows if r["priority"] == priority]
        out.append({"priority": PRIORITY_LABELS.get(priority, str(priority)),
                    "referrals": len(group),
                    "to_triage": _summary(_days(r["referred_at"], r["triaged_at"])
                                          for r in group),
                    "to_first_session": _summary(_days(r["referred_at"], r["first_session"])
                                                 for r in group)})
    return out


def _waiting_now(rows) -> dict:
    today = date.today().isoformat()
    ages = [_days(r["referred_at"], today) for r in rows]
    groups = {}
    for row, age in zip(rows, ages):
        label = (PRIORITY_LABELS[None] if row["status"] == "referred"
                 else PRIORITY_LABELS.get(row["priority"], str(row["priority"])))
        groups.setdefault(label, []).append(age)
    return {"count": len(rows), "ages": _summary(ages),
            "same_day_unallocated": sum(1 for r in rows if r["same_day_due"]),
            "by_priority": [{"priority": k, **_summary(v)} for k, v in sorted(groups.items())]}


def _pairs(rows) -> dict:
    """``{(referral_id, measure): (first_total, last_total)}`` per episode."""
    by_key: dict = {}
    for row in rows:
        by_key.setdefault((row["referral_id"], row["measure"]), []).append(row)
    pairs = {}
    for key, scores in by_key.items():
        scores.sort(key=lambda r: (r["recorded_at"], r["measure_id"]))
        firsts = [r for r in scores if r["stage"] == "first"] or scores[:1]
        first = firsts[0]
        later = [r for r in scores if r["measure_id"] != first["measure_id"]
                 and r["recorded_at"] >= first["recorded_at"]]
        lasts = [r for r in later if r["stage"] == "last"] or later[-1:]
        if lasts:
            pairs[key] = (first["total"], lasts[-1]["total"])
    return pairs


def _pct(part, whole):
    return round(100.0 * part / whole, 1) if whole else None


def outcomes(actor, date_from=None, date_to=None) -> dict:
    access.require_counselling_team(actor)
    counselling_schema.ensure()
    where, params = _period_clause(date_from, date_to)
    conn = get_connection()
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT m.measure_id, m.referral_id, m.measure, m.stage, m.total, m.recorded_at "
            "FROM counselling_measures m JOIN counselling_referrals r ON "
            f"r.referral_id = m.referral_id WHERE {where}", params)]  # nosec B608
    finally:
        conn.close()
    pairs = _pairs(rows)
    report = {"period": {"from": date_from, "to": date_to}, "measures": []}
    for code in outcome_measures.MEASURES:
        changes = [outcome_measures.change(code, first, last)
                   for (_rid, measure), (first, last) in pairs.items() if measure == code]
        report["measures"].append(_measure_summary(code, changes,
                                                   sum(1 for r in rows if r["measure"] == code)))
    return report


def _measure_summary(code, changes, completed) -> dict:
    n = len(changes)
    cases = [c for c in changes if c["case_at_start"]]
    return {
        "measure": code, "forms_completed": completed, "paired_episodes": n,
        "mean_first": round(statistics.mean(c["first"] for c in changes), 1) if n else None,
        "mean_last": round(statistics.mean(c["last"] for c in changes), 1) if n else None,
        "mean_change": round(statistics.mean(c["change"] for c in changes), 1) if n else None,
        "reliably_improved_pct": _pct(sum(c["category"] == "reliably improved"
                                          for c in changes), n),
        "reliably_deteriorated_pct": _pct(sum(c["category"] == "reliably deteriorated"
                                              for c in changes), n),
        "cases_at_start": len(cases),
        "recovered_pct": _pct(sum(c["recovered"] for c in cases), len(cases)),
        "reliable_recovery_pct": _pct(sum(c["reliable_recovery"] for c in cases), len(cases)),
    }


def as_text(wait: dict, outcome: dict) -> str:
    """Both reports as plain text (CLI and the GUI's text view)."""
    def s(stats):
        if not stats["n"]:
            return "no data"
        return f"n={stats['n']}, median {stats['median']} d, mean {stats['mean']} d, " \
               f"longest {stats['max']} d"
    lines = ["COUNSELLING WAITING TIMES",
             f"Referrals in period: {wait['referrals']}",
             f"  Referral → triage:        {s(wait['to_triage'])}",
             f"  Referral → first session: {s(wait['to_first_session'])}"]
    for group in wait["by_priority"]:
        lines.append(f"  Priority {group['priority']}: {group['referrals']} referrals; "
                     f"triage {s(group['to_triage'])}; first session "
                     f"{s(group['to_first_session'])}")
    now = wait["waiting_now"]
    lines += ["", f"Waiting now: {now['count']} ({s(now['ages'])}); same-day still "
                  f"unallocated: {now['same_day_unallocated']}"]
    lines += [f"  {g['priority']}: {g['n']} waiting, oldest {g['max']} d"
              for g in now["by_priority"]]
    lines += ["", "COUNSELLING OUTCOMES"]
    for m in outcome["measures"]:
        if not m["paired_episodes"]:
            lines.append(f"{m['measure']}: {m['forms_completed']} forms, no paired "
                         "first/last scores yet")
            continue
        lines.append(
            f"{m['measure']}: {m['paired_episodes']} paired episodes; mean "
            f"{m['mean_first']} → {m['mean_last']} (change {m['mean_change']}); reliably "
            f"improved {m['reliably_improved_pct']}%, deteriorated "
            f"{m['reliably_deteriorated_pct']}%; of {m['cases_at_start']} above caseness, "
            f"recovered {m['recovered_pct']}%, reliably recovered "
            f"{m['reliable_recovery_pct']}%")
    return "\n".join(lines)
