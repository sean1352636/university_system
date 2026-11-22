"""Read-only views across every area: the dashboard figures, what's due,
the SEN register summary, provision costs and CSV export."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from education_system.systems.special_education.core import dates
from education_system.systems.special_education.core import records as r
from education_system.systems.special_education.modules import (
    ehcp, funding, learners, people, provision, support_plans,
)


@dataclass(frozen=True)
class DueItem:
    due: date
    what: str
    learner: str
    learner_id: int | None
    area: str           # menu key of the page that holds it

    @property
    def overdue(self) -> bool:
        return self.due < date.today()


def due_items(within_days: int = 30) -> list[DueItem]:
    """Everything due in the next *within_days* days, plus anything overdue."""
    horizon = date.today() + timedelta(days=within_days)
    out: list[DueItem] = []

    def add(due: date | None, what: str, row: dict, area: str) -> None:
        if due and due <= horizon:
            out.append(DueItem(due, what, row.get("learner_name") or "", row.get("learner_id"),
                               area))

    for row in r.list_records(support_plans.PLANS, equals={"status": "Active"}):
        add(r.to_date(row.get("review_date")), "Support plan review", row, "support_plans")
    for row in ehcp.open_plans():
        nxt = ehcp.next_deadline(row)
        if nxt:
            add(nxt.due, f"EHCP: {nxt.what}", row, "ehcps")
    for row in r.list_records(ehcp.ADVICE):
        if not row.get("received_on"):
            add(r.to_date(row.get("due_on")), f"{row['advice_type']} advice due", row,
                "ehcp_advice")
    for row in r.list_records(ehcp.REVIEWS):
        meeting = r.to_date(row.get("meeting_date"))
        if meeting and not row.get("report_sent"):
            add(dates.add_weeks(meeting, ehcp.REPORT_WEEKS), "Annual review report to LA", row,
                "annual_reviews")
    for row in r.list_records(provision.HEALTH_PLANS, equals={"status": "Active"}):
        add(r.to_date(row.get("review_date")), f"{row['plan_type']} review", row, "health_plans")
    for row in r.list_records(provision.EQUIPMENT, equals={"status": "In use"}):
        add(r.to_date(row.get("review_date")), f"Equipment review: {row['item']}", row,
            "equipment")
    for row in r.list_records(people.MEETINGS):
        nxt = r.to_date(row.get("next_meeting"))
        if nxt and nxt >= date.today():
            add(nxt, f"{row['meeting_type']} meeting", row, "meetings")
    return sorted(out, key=lambda d: d.due)


def dashboard() -> dict:
    active = learners.active_learners()
    status = Counter(x["sen_status"] for x in active)
    open_ehcps = ehcp.open_plans()
    assessing = [x for x in open_ehcps if not x.get("final_date")]
    overdue_ehcp = [x for x in assessing if (n := ehcp.next_deadline(x)) and n.overdue]
    live = r.list_records(provision.PROVISION, equals={"status": "Active"})
    due = due_items(30)
    return {
        "on_register": len([x for x in active if x["sen_status"] != "No longer SEN"]),
        "sen_support": status.get("SEN Support", 0),
        "ehcp": status.get("EHCP", 0),
        "assessing": len(assessing),
        "assessing_overdue": len(overdue_ehcp),
        "provisions": len(live),
        "provision_hours": sum(x.get("hours_per_week") or 0 for x in live),
        "due": due,
        "overdue": sum(1 for d in due if d.overdue),
    }


def register_summary() -> dict[str, Counter]:
    """Active register counts by SEN status, primary need and year group."""
    rows = [x for x in learners.active_learners() if x["sen_status"] != "No longer SEN"]
    return {
        "SEN status": Counter(x["sen_status"] for x in rows),
        "Primary need": Counter((x.get("primary_need") or "Not recorded").split(" - ")[0]
                                for x in rows),
        "Year group": Counter(x.get("year_group") or "Not recorded" for x in rows),
    }


def provision_costs() -> list[dict]:
    """Per learner: active provision hours and weekly cost, and agreed funding a year."""
    by: dict[int, dict] = {}
    for row in r.list_records(provision.PROVISION, equals={"status": "Active"}):
        item = by.setdefault(row["learner_id"], {"learner": row["learner_name"], "items": 0,
                                                 "hours": 0.0, "weekly": 0.0, "funding": 0.0})
        item["items"] += 1
        item["hours"] += row.get("hours_per_week") or 0
        item["weekly"] += row.get("cost_per_week") or 0
    for row in r.list_records(funding.FUNDING, equals={"status": "Agreed"}):
        item = by.setdefault(row["learner_id"], {"learner": row["learner_name"], "items": 0,
                                                 "hours": 0.0, "weekly": 0.0, "funding": 0.0})
        item["funding"] += row.get("amount_per_year") or 0
    return sorted(by.values(), key=lambda x: -x["weekly"])


def export_csv(rt: r.RecordType, path: str | Path, rows: list[dict] | None = None) -> int:
    """Write *rows* (default: every record of *rt*) to *path*. Returns rows written."""
    rows = r.list_records(rt) if rows is None else rows
    cols = [f for f in rt.fields if f.kind not in ("learner", "ref")]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        out = csv.writer(fh)
        head = (["Learner"] if rt.learner_field else []) + [f.label for f in cols]
        out.writerow(head + [label for label, _ in rt.computed])
        for row in rows:
            line = ([row.get("learner_name") or ""] if rt.learner_field else [])
            line += [r.fmt(f, row.get(f.name)) if f.kind != "long" else (row.get(f.name) or "")
                     for f in cols]
            out.writerow(line + [fn(row) for _, fn in rt.computed])
    return len(rows)
