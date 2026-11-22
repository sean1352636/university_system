"""Read-only views across every area: the dashboard, what's due, and the
admissions, school places, welfare, exclusions, SEND and transport reports."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from education_system.systems.local_authority.core import dates
from education_system.systems.local_authority.core import records as r
from education_system.systems.local_authority.modules import (
    admissions,
    children,
    exclusions,
    schools,
    send,
    transport,
    welfare,
)


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

    def add(due: date | None, what: str, row: dict, area: str) -> None:
        if due and due <= horizon:
            lid = row.get("learner_id")
            out.append(DueItem(due, what, children.child_name(lid) if lid else "", lid, area))

    for a in r.list_records(admissions.APPLICATIONS, equals={"status": "Received"}):
        add(admissions.decision_due(a), f"Admission decision ({a['round']})", a,
            "applications")
    for ap in r.list_records(admissions.APPEALS, equals={"outcome": "Pending"}):
        add(admissions.hearing_due(ap), "Admission appeal hearing", ap, "appeals")
    for ap in r.list_records(admissions.APPEALS):
        hearing = r.to_date(ap.get("hearing_on"))
        if hearing and ap["outcome"] in ("Upheld", "Dismissed") and not ap.get(
                "letter_sent_on"):
            add(dates.school_day(hearing + timedelta(days=1), 5), "Appeal decision letter",
                ap, "appeals")
    for f in r.list_records(admissions.FAIR_ACCESS):
        if not f.get("on_roll_on") and f["decision"] != "Not eligible":
            add(admissions.fap_target(f), "Fair access: on roll (target)", f, "fair_access")
    for c in r.list_records(welfare.ATTENDANCE_CASES, equals={"status": "Open"}):
        add(r.to_date(c.get("next_review")), "Attendance case review", c, "attendance_cases")
    for pn in r.list_records(welfare.PENALTY_NOTICES, equals={"status": "Issued"}):
        issued = r.to_date(pn["issued_on"])
        add(issued + timedelta(days=28) if issued else None,
            "Penalty notice: paid? (28 days) - else prosecute or withdraw", pn,
            "penalty_notices")
    for e in r.list_records(welfare.EHE, equals={"status": "Active"}):
        add(r.to_date(e.get("next_review")), "EHE annual review", e, "ehe")
        if e.get("consent") == "Requested":
            add(r.to_date(e["notified_on"]), "EHE: decide consent to deregister", e, "ehe")
    for c in r.list_records(welfare.CME, equals={"status": "Open"}):
        got = r.to_date(c["reported_on"])
        add(dates.school_day(got, 10) if got else None, "CME: enquiries outstanding", c,
            "cme")
    for x in r.list_records(exclusions.EXCLUSIONS):
        if x["kind"] == exclusions.KINDS[1] and x.get("outcome") == "Awaiting review":
            add(exclusions.review_due(x), "Governing board review of exclusion", x,
                "exclusions")
        if not x.get("provision_from") and x.get("outcome") != "Withdrawn by school":
            add(exclusions.sixth_day(x), "Full-time provision from day 6", x, "exclusions")
    for q in r.list_records(send.EHC_REQUESTS, equals={"status": "Open"}):
        what, due = send.request_next_step(q)
        add(due, what, q, "ehc_requests")
    for p in r.list_records(send.EHC_PLANS, equals={"status": "Active"}):
        add(r.to_date(p.get("next_review")), "EHC plan annual review", p, "ehc_plans")
        pt = send.phase_transfer_deadline(p)
        add(pt, "EHC plan phase transfer (amended plan final)", p, "ehc_plans")
    for t in r.list_records(send.TRIBUNALS, equals={"outcome": "Pending"}):
        add(r.to_date(t.get("hearing_on")), "SEND tribunal hearing", t, "tribunals")
    for t in r.list_records(transport.TRANSPORT, equals={"status": "Applied"}):
        got = r.to_date(t["applied_on"])
        add(dates.school_day(got, 20) if got else None, "Transport decision", t, "transport")
    for rt in r.list_records(transport.ROUTES, equals={"status": "Active"}):
        ends = r.to_date(rt.get("contract_ends"))
        add(ends - timedelta(days=90) if ends else None,
            f"Re-tender route {rt['code']} (contract ends {dates.uk(ends)})", {}, "routes")
    return sorted(out, key=lambda d: d.due)


def dashboard() -> dict:
    kids = children.active_learners()
    csa = [c for c in kids if children.compulsory_school_age(c)]
    received = r.list_records(admissions.APPLICATIONS, equals={"status": "Received"})
    ys = dates.school_year_start(date.today()).isoformat()
    excl = [x for x in r.list_records(exclusions.EXCLUSIONS) if x["start_date"] >= ys]
    reqs = r.list_records(send.EHC_REQUESTS)
    due = due_items(30)
    return {
        "children": len(kids),
        "not_in_education": sum(1 for c in csa if c["education"] == "Not in education"),
        "ehe": len(r.list_records(welfare.EHE, equals={"status": "Active"})),
        "cme_open": len(r.list_records(welfare.CME, equals={"status": "Open"})),
        "applications_open": len(received),
        "appeals_pending": len(r.list_records(admissions.APPEALS,
                                              equals={"outcome": "Pending"})),
        "attendance_cases": len(r.list_records(welfare.ATTENDANCE_CASES,
                                               equals={"status": "Open"})),
        "suspensions": sum(1 for x in excl if x["kind"] == "Suspension"),
        "exclusions": sum(1 for x in excl if x["kind"] == exclusions.KINDS[1]),
        "ehc_plans": len(r.list_records(send.EHC_PLANS, equals={"status": "Active"})),
        "ehc_open": sum(1 for q in reqs if q["status"] == "Open"),
        "ehc_20_weeks": send_timeliness()["rate"],
        "transport": len(r.list_records(transport.TRANSPORT, equals={"status": "Agreed"})),
        "due": due,
        "overdue": sum(1 for d in due if d.overdue),
    }


def admissions_summary() -> dict[str, Counter]:
    apps = r.list_records(admissions.APPLICATIONS)
    offered = [a for a in apps if a["status"] in ("Offered", "Accepted", "Declined")]
    return {
        "Applications by round": Counter(a["round"] for a in apps),
        "Applications by status": Counter(a["status"] for a in apps),
        "Offers by basis": Counter(a.get("offer_basis") or "?" for a in offered),
        "Late applications": Counter(a["round"] for a in apps if a.get("late")),
        "Appeals by outcome": Counter(x["outcome"] for x in
                                      r.list_records(admissions.APPEALS)),
        "Fair access by category": Counter(x["category"] for x in
                                           r.list_records(admissions.FAIR_ACCESS)),
    }


def first_preference_rate() -> float | None:
    offered = [a for a in r.list_records(admissions.APPLICATIONS)
               if a["round"] != admissions.IN_YEAR and a.get("offer_basis")]
    if not offered:
        return None
    return round(100 * sum(a["offer_basis"] == "1st preference" for a in offered)
                 / len(offered))


@dataclass(frozen=True)
class LinkedItem:
    on: str
    what: str
    learner: str
    learner_id: int | None
    school: str
    status: str
    area: str


def school_notifications() -> list[LinkedItem]:
    """What the linked schools on the platform have sent (attendance
    referrals, exclusions, CME, EHE, EHC needs assessment requests) and the
    school places handed to them, newest first."""
    out: list[LinkedItem] = []

    def add(on, what: str, row: dict, school_id, status, area: str) -> None:
        lid = row.get("learner_id")
        out.append(LinkedItem(str(on or "")[:10], what, children.child_name(lid) if lid else "",
                              lid, schools.school_name(school_id), str(status or ""), area))

    for x in r.list_records(welfare.ATTENDANCE_CASES):
        if x.get("transition_id"):
            add(x.get("referred_on"), "Attendance referral", x, x.get("school_id"),
                f"{x['status']} - {x['stage']}", "attendance_cases")
    for x in r.list_records(exclusions.EXCLUSIONS):
        if x.get("transition_id"):
            add(x.get("notified_on") or x.get("start_date"), x["kind"], x, x.get("school_id"),
                x.get("outcome") or exclusions.KINDS[0], "exclusions")
    for x in r.list_records(welfare.CME):
        if x.get("transition_id"):
            add(x.get("reported_on"), "Child missing education", x, x.get("last_school_id"),
                x["status"], "cme")
    for x in r.list_records(welfare.EHE):
        if x.get("transition_id"):
            add(x.get("notified_on"), "Elective home education", x, x.get("from_school_id"),
                x["status"], "ehe")
    for x in r.list_records(send.EHC_REQUESTS):
        if x.get("transition_id"):
            add(x.get("received_on"), "EHC needs assessment request", x, x.get("setting_id"),
                f"{x['status']} - {x.get('assess_decision') or 'Pending'}", "ehc_requests")
    for x in r.list_records(admissions.APPLICATIONS):
        if x.get("place_transition_id"):
            add(x.get("offered_on"), f"School place handed over ({x['round']})", x,
                x.get("offered_school_id"), x["status"], "applications")
    for x in r.list_records(admissions.FAIR_ACCESS):
        if x.get("place_transition_id"):
            add(x.get("panel_on"), "School place handed over (fair access)", x,
                x.get("school_id"), "On roll" if x.get("on_roll_on") else "Allocated",
                "fair_access")
    return sorted(out, key=lambda i: i.on, reverse=True)


def school_places() -> list[dict]:
    """Per open school: PAN, offers and first preferences this year's rounds."""
    apps = r.list_records(admissions.APPLICATIONS)
    out = []
    for s in schools.open_schools():
        firsts = sum(1 for a in apps if a.get("pref1_id") == s["id"])
        offers = sum(1 for a in apps if a.get("offered_school_id") == s["id"]
                     and a["status"] in ("Offered", "Accepted"))
        out.append({"id": s["id"], "school": s["name"], "phase": s["phase"],
                    "pan": s.get("pan"), "first_prefs": firsts, "offers": offers,
                    "capacity": s.get("capacity"), "on_roll": s.get("on_roll"),
                    "surplus": schools.surplus(s),
                    "over": s.get("pan") is not None and firsts > int(s["pan"])})
    return out


def welfare_summary() -> dict[str, Counter]:
    cases = r.list_records(welfare.ATTENDANCE_CASES, equals={"status": "Open"})
    return {
        "Open attendance cases by stage": Counter(c["stage"] for c in cases),
        "Open cases by absence band": Counter(welfare.absence_band(c.get("attendance_pct"))
                                              or "Not recorded" for c in cases),
        "Penalty notices by status": Counter(p["status"] for p in
                                             r.list_records(welfare.PENALTY_NOTICES)),
        "Children missing education": Counter(c["status"] for c in
                                              r.list_records(welfare.CME)),
        "Home education suitability": Counter(e["suitability"] for e in
                                              r.list_records(welfare.EHE,
                                                             equals={"status": "Active"})),
        "Education of children of compulsory school age": Counter(
            c["education"] for c in children.active_learners()
            if children.compulsory_school_age(c)),
    }


def exclusions_summary() -> dict[str, Counter]:
    ys = dates.school_year_start(date.today()).isoformat()
    rows = [x for x in r.list_records(exclusions.EXCLUSIONS) if x["start_date"] >= ys]
    names = {s["id"]: s["name"] for s in r.list_records(schools.SCHOOLS)}
    days: Counter = Counter()
    for x in rows:
        if x["kind"] == "Suspension":
            days[names.get(x["school_id"], "?")] += float(x.get("days") or 0)
    return {
        "This school year by type": Counter(x["kind"] for x in rows),
        "By reason": Counter(x["reason"] for x in rows),
        "Permanent exclusions by school": Counter(names.get(x["school_id"], "?") for x in rows
                                                  if x["kind"] == exclusions.KINDS[1]),
        "Suspension days by school": days,
        "Exclusion reviews": Counter(x.get("outcome") or "" for x in rows
                                     if x["kind"] == exclusions.KINDS[1]),
    }


def send_timeliness() -> dict:
    """Final EHC plans issued within 20 weeks (excluding exceptions isn't modelled)."""
    done = [q for q in r.list_records(send.EHC_REQUESTS) if q.get("final_issued_on")]
    on_time = [q for q in done if (r.to_date(q["final_issued_on"]) -
                                   r.to_date(q["received_on"])).days <= send.FINAL_WEEKS * 7]
    return {"issued": len(done), "on_time": len(on_time),
            "rate": round(100 * len(on_time) / len(done)) if done else None}


def send_summary() -> dict[str, Counter]:
    plans = r.list_records(send.EHC_PLANS, equals={"status": "Active"})
    names = {s["id"]: s["phase"] for s in r.list_records(schools.SCHOOLS)}
    return {
        "Active plans by primary need": Counter(p.get("primary_need") or "Not recorded"
                                                for p in plans),
        "Active plans by setting type": Counter(names.get(p.get("setting_id"), "Not named")
                                                for p in plans),
        "Assessment decisions": Counter(q["assess_decision"] for q in
                                        r.list_records(send.EHC_REQUESTS)),
        "Tribunal outcomes": Counter(t["outcome"] for t in r.list_records(send.TRIBUNALS)),
    }


def high_needs_cost() -> float:
    return round(sum(float(t["annual_amount"]) for t in send.live_topups()), 2)


def export_csv(rt: r.RecordType, path: str | Path, rows: list[dict] | None = None) -> int:
    """Write *rows* (default: every record of *rt*) to *path*. Returns rows written."""
    rows = r.list_records(rt) if rows is None else rows
    cols = [f for f in rt.fields if f.kind not in ("learner", "ref")]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        out = csv.writer(fh)
        head = (["Child"] if rt.learner_field else []) + [f.label for f in cols]
        out.writerow(head + [label for label, _ in rt.computed])
        for row in rows:
            line = ([row.get("learner_name") or ""] if rt.learner_field else [])
            line += [r.fmt(f, row.get(f.name)) if f.kind != "long" else (row.get(f.name) or "")
                     for f in cols]
            out.writerow(line + [fn(row) for _, fn in rt.computed])
    return len(rows)
