"""Read-only views across every area: the dashboard, what's due, and the roll,
attendance, behaviour, placement cost and outcome reports."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from education_system.systems.alternative_provision.core import dates
from education_system.systems.alternative_provision.core import records as r
from education_system.systems.alternative_provision.modules import (
    attendance,
    behaviour,
    commissioning,
    learners,
    learning,
    placements,
    referrals,
    reintegration,
    safeguarding,
)

INVOICE_TERMS_DAYS = 30


@dataclass(frozen=True)
class DueItem:
    due: date
    what: str
    learner: str
    learner_id: int | None
    area: str

    @property
    def overdue(self) -> bool:
        return self.due < date.today()


def due_items(within_days: int = 30) -> list[DueItem]:
    """Everything due in the next *within_days* days, plus anything overdue."""
    horizon = date.today() + timedelta(days=within_days)
    out: list[DueItem] = []

    def add(due: date | None, what: str, row: dict, area: str, who: str | None = None) -> None:
        if due and due <= horizon:
            out.append(DueItem(due, what, who if who is not None else
                               (row.get("learner_name") or ""), row.get("learner_id"), area))

    for row in r.list_records(referrals.REFERRALS):
        due = referrals.sixth_day(row)
        if (due and row["status"] not in ("Declined", "Withdrawn")
                and not referrals.has_active_placement(row["learner_id"], due)):
            add(due, "Sixth-day provision must start", row, "referrals")
        if row["status"] in ("New", "Triage"):
            received = r.to_date(row["received"])
            add(dates.school_day(received, 5) if received else None, "Referral decision",
                row, "referrals")
    for row in placements.active_placements():
        add(r.to_date(row.get("next_review")), "Placement review", row, "placement_reviews")
        if float(row.get("hours_per_week") or 0) < placements.FULL_TIME_HOURS:
            add(r.to_date(row.get("part_time_review")), "Part-time timetable review", row,
                "placements")
        planned = r.to_date(row.get("planned_end"))
        add(planned, "Placement planned to end", row, "placements")
    for row in r.list_records(placements.PROVIDERS, equals={"status": "Active"}):
        due = placements.qa_due(row)
        if due:
            add(due, f"QA visit: {row['name']}", row, "providers", who="")
    for row in r.list_records(referrals.RISK_ASSESSMENTS, equals={"status": "Current"}):
        add(r.to_date(row.get("review_date")), f"Risk assessment review ({row['overall']})",
            row, "risk_assessments")
    for row in r.list_records(learning.PLANS, equals={"status": "Active"}):
        add(r.to_date(row.get("review_date")), f"{row['kind']} review", row, "plans")
    for row in r.list_records(safeguarding.CONCERNS, equals={"status": "Open"}):
        if not row.get("dsl_reviewed_by"):
            raised = r.to_date(row["raised_on"])
            add(raised + timedelta(days=1) if raised else None, "DSL review of a concern",
                row, "safeguarding")
    for row in r.list_records(safeguarding.MISSING):
        due = safeguarding.interview_due(row)
        if due and not row.get("interview_on"):
            add(due.date(), "Return interview (72 hours)", row, "missing_episodes")
    for row in r.list_records(behaviour.INCIDENTS):
        if row.get("reasonable_force") and not row.get("parent_informed"):
            on = r.to_date(row["incident_date"])
            add(on, "Tell parents about use of force", row, "incidents")
    for row in r.list_records(behaviour.SUSPENSIONS, equals={"kind": "Suspension",
                                                             "status": "Confirmed"}):
        if not row.get("reintegration_meeting"):
            add(r.to_date(row.get("return_date")), "Reintegration meeting after suspension",
                row, "suspensions")
    for row in r.list_records(reintegration.REINTEGRATION, equals={"status": "Completed"}):
        done = int(row.get("follow_ups_done") or 0)
        ups = reintegration.follow_ups(row)
        if done < len(ups):
            add(ups[done], f"{reintegration.FOLLOW_UP_WEEKS[done]}-week reintegration "
                           "follow-up", row, "reintegration")
    for row in commissioning.outstanding():
        sent = r.to_date(row.get("sent_on"))
        add(sent + timedelta(days=INVOICE_TERMS_DAYS) if sent else None,
            f"Invoice {row['invoice_no']} payment", row, "invoices")
    for row in r.list_records(learning.QUALIFICATIONS_RT, equals={"status": "Entered"}):
        add(r.to_date(row.get("exam_date")), f"Exam: {row['qualification']} {row['subject']}",
            row, "qualifications")
    return sorted(out, key=lambda d: d.due)


def persistent_absentees() -> list[dict]:
    """Pupils on roll attending under 90% this school year."""
    out = []
    since = (date.today() - dates.school_year_start(date.today())).days
    for pupil in learners.on_roll():
        rate = attendance.rate(pupil["id"], days=since)
        if rate is not None and rate < attendance.PERSISTENT_ABSENCE:
            out.append({**pupil, "rate": rate})
    return sorted(out, key=lambda x: x["rate"])


def dashboard() -> dict:
    on_roll = learners.on_roll()
    open_refs = [x for x in r.list_records(referrals.REFERRALS) if x["status"] in referrals.OPEN]
    active = placements.active_placements()
    due = due_items(30)
    ys = dates.school_year_start(date.today())
    sus = [x for x in r.list_records(behaviour.SUSPENSIONS)
           if x["status"] != "Withdrawn" and (r.to_date(x["start_date"]) or ys) >= ys]
    return {
        "on_roll": len(on_roll),
        "referrals_open": len(open_refs),
        "day6_overdue": sum(1 for d in due if d.overdue and d.what.startswith("Sixth-day")),
        "placements": len(active),
        "part_time": sum(1 for p in active
                         if float(p.get("hours_per_week") or 0) < placements.FULL_TIME_HOURS),
        "attendance": attendance.rate(days=30),
        "persistent_absence": len(persistent_absentees()),
        "incidents_open": len(r.list_records(behaviour.INCIDENTS, equals={"status": "Open"})),
        "concerns_open": len(r.list_records(safeguarding.CONCERNS, equals={"status": "Open"})),
        "suspensions": len(sus),
        "suspension_days": sum(float(x.get("days") or 0) for x in sus),
        "exclusions": sum(1 for x in sus if x["kind"] == "Permanent exclusion"),
        "due": due,
        "overdue": sum(1 for d in due if d.overdue),
    }


def roll_summary() -> dict[str, Counter]:
    pupils = learners.on_roll()
    refs = r.list_records(referrals.REFERRALS, equals={"status": "Accepted"})
    providers = {p["id"]: p["name"] for p in r.list_records(placements.PROVIDERS)}
    return {
        "Year group": Counter(p["year_group"] for p in pupils),
        "SEN": Counter(p["sen_status"] for p in pupils),
        "Social care": Counter(p.get("social_care") or "None known" for p in pupils),
        "Looked after / pupil premium / FSM": Counter(
            label for p in pupils for label, key in
            (("Looked after", "looked_after"), ("Pupil premium", "pupil_premium"),
             ("Free school meals", "free_school_meals")) if p.get(key)),
        "Reason referred (accepted referrals)": Counter(x["reason"] for x in refs),
        "Placed with": Counter(providers.get(p["provider_id"], "?")
                               for p in placements.active_placements()),
    }


def attendance_report() -> list[dict]:
    since = (date.today() - dates.school_year_start(date.today())).days
    out = []
    for pupil in learners.on_roll():
        rate = attendance.rate(pupil["id"], days=since)
        out.append({"learner_id": pupil["id"], "learner": learners.pupil_label(pupil),
                    "rate": rate, "last_30": attendance.rate(pupil["id"], days=30),
                    "persistent": rate is not None and rate < attendance.PERSISTENT_ABSENCE})
    return sorted(out, key=lambda x: (x["rate"] is None, x["rate"] or 0))


def behaviour_summary() -> dict[str, Counter]:
    ys = dates.school_year_start(date.today()).isoformat()
    incidents = [x for x in r.list_records(behaviour.INCIDENTS) if x["incident_date"] >= ys]
    sus = [x for x in r.list_records(behaviour.SUSPENSIONS)
           if x["start_date"] >= ys and x["status"] != "Withdrawn"]
    days = Counter()
    for x in sus:
        if x["kind"] == "Suspension":
            days[x["learner_name"] or "?"] += float(x.get("days") or 0)
    return {
        "Incidents this year by type": Counter(x["kind"] for x in incidents),
        "Incidents by severity": Counter(x["severity"] for x in incidents),
        "Reasonable force used": Counter("Force used" for x in incidents
                                         if x.get("reasonable_force")),
        "Suspensions / exclusions by reason": Counter(x["reason"] for x in sus),
        "Suspension days per pupil": days,
    }


def placement_costs() -> list[dict]:
    providers = {p["id"]: p["name"] for p in r.list_records(placements.PROVIDERS)}
    out = []
    for p in placements.active_placements():
        out.append({"learner_id": p["learner_id"], "learner": p["learner_name"],
                    "provider": providers.get(p["provider_id"], "?"),
                    "hours": float(p.get("hours_per_week") or 0),
                    "commissioned_by": p.get("commissioned_by") or "",
                    "weekly": placements.weekly_cost(p)})
    return sorted(out, key=lambda x: -x["weekly"])


def outcomes() -> dict[str, Counter]:
    plans = r.list_records(reintegration.REINTEGRATION)
    return {
        "Reintegration plans": Counter(x["status"] for x in plans),
        "Latest destination per pupil": Counter(reintegration.latest_destinations().values()),
        "Placements ended": Counter(x.get("end_reason") or "Not given" for x in
                                    r.list_records(placements.PLACEMENTS,
                                                   equals={"status": "Ended"})),
    }


def reintegration_rate() -> float | None:
    plans = [x for x in r.list_records(reintegration.REINTEGRATION)
             if x["status"] in ("Completed", "Broke down")]
    if not plans:
        return None
    return round(100 * sum(x["status"] == "Completed" for x in plans) / len(plans))


def export_csv(rt: r.RecordType, path: str | Path, rows: list[dict] | None = None) -> int:
    """Write *rows* (default: every record of *rt*) to *path*. Returns rows written."""
    rows = r.list_records(rt) if rows is None else rows
    cols = [f for f in rt.fields if f.kind not in ("learner", "ref")]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        out = csv.writer(fh)
        head = (["Pupil"] if rt.learner_field else []) + [f.label for f in cols]
        out.writerow(head + [label for label, _ in rt.computed])
        for row in rows:
            line = ([row.get("learner_name") or ""] if rt.learner_field else [])
            line += [r.fmt(f, row.get(f.name)) if f.kind != "long" else (row.get(f.name) or "")
                     for f in cols]
            out.writerow(line + [fn(row) for _, fn in rt.computed])
    return len(rows)
