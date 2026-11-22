"""OIA case statistics for academic appeals.

What the OIA's annual return and a Senate report ask about: appeals received,
open and closed, by stage, grounds and outcome, the upheld rate, reviews,
the share closed within the OIA's 90-day expectation, the average time to
close, and how many Completion of Procedures letters were issued.
"""

from __future__ import annotations

import csv
import io
from datetime import date
from typing import Any

from education_system.systems.university.application.cases.appeals import UPHELD, _date
from education_system.systems.university.infrastructure.database.db import get_connection


def _days(start, end) -> int | None:
    a, b = _date(start, "start"), _date(end, "end")
    return (b - a).days if a and b else None


def statistics(date_from=None, date_to=None) -> dict:
    """OIA-style case statistics for appeals submitted in the period (staff check
    is the caller's: :func:`appeals.statistics`)."""
    lo = (_date(date_from, "From") or date(1900, 1, 1)).isoformat()
    hi = (_date(date_to, "To") or date(9999, 12, 31)).isoformat()
    with get_connection() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM academic_appeals WHERE substr(submitted_at, 1, 10) BETWEEN ? AND ?",
            (lo, hi))]
    closed = [r for r in rows if r["closed_at"]]
    decided = [r for r in rows if r["outcome"] in ("upheld", "partly_upheld", "not_upheld")]
    durations = [d for d in (_days(r["submitted_at"], r["closed_at"]) for r in closed)
                 if d is not None]
    on_time = [r for r in closed if r["closed_at"][:10] <= (r["target_close_date"] or "9999")]

    def count(key):
        out: dict[str, int] = {}
        for r in rows:
            out[str(r[key] or "pending")] = out.get(str(r[key] or "pending"), 0) + 1
        return out
    return {
        "period": {"from": lo, "to": hi}, "received": len(rows), "closed": len(closed),
        "open": len(rows) - len(closed), "late_submissions": sum(r["late"] for r in rows),
        "by_stage": count("stage"), "by_grounds": count("grounds"), "by_outcome": count("outcome"),
        "upheld_rate": round(100 * sum(r["outcome"] in UPHELD for r in decided) / len(decided), 1)
        if decided else None,
        "reviews_requested": sum(1 for r in rows if r["review_requested_at"]),
        "closed_within_90_days_pct": round(100 * len(on_time) / len(closed), 1) if closed else None,
        "average_days_to_close": round(sum(durations) / len(durations), 1) if durations else None,
        "cop_letters_issued": sum(1 for r in rows if r["cop_issued_at"]),
    }


def statistics_rows(stats: dict) -> list[tuple[str, str, Any]]:
    """``(section, item, value)`` rows for a table, CSV or text report."""
    out = [("Period", "From", stats["period"]["from"]), ("Period", "To", stats["period"]["to"])]
    for key in ("received", "open", "closed", "late_submissions", "reviews_requested",
                "upheld_rate", "closed_within_90_days_pct", "average_days_to_close",
                "cop_letters_issued"):
        value = stats[key]
        out.append(("Summary", key.replace("_", " "), "—" if value is None else value))
    for section in ("by_stage", "by_grounds", "by_outcome"):
        out += [(section.replace("_", " ").title(), k.replace("_", " "), v)
                for k, v in sorted(stats[section].items())]
    return out


def statistics_csv(stats: dict) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Section", "Item", "Value"])
    writer.writerows(statistics_rows(stats))
    return buffer.getvalue()


def statistics_text(stats: dict) -> str:
    lines, section = ["Academic appeals — OIA case statistics"], None
    for sec, item, value in statistics_rows(stats):
        if sec != section:
            lines += ["", sec]
            section = sec
        lines.append(f"  {item:<32} {value}")
    return "\n".join(lines) + "\n"
