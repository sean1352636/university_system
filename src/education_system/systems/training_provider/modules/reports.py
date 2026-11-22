"""Read-only views across every area: the dashboard, what's due, session fill,
achievement, certificate expiry, aged debt and quality."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from education_system.systems.training_provider.core import records as r
from education_system.systems.training_provider.modules import (
    assessment,
    clients,
    courses,
    finance,
    learners,
    quality,
    sessions,
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

    def add(due: date | None, what: str, area: str, who: str = "",
            learner_id: int | None = None) -> None:
        if due and due <= horizon:
            out.append(DueItem(due, what, who, learner_id, area))

    for s in sessions.upcoming(within_days):
        start = r.to_date(s["start_date"])
        label = sessions.session_label(s)
        course = r.get(courses.COURSES, s["course_id"])
        if not s.get("trainer_id"):
            add(start, f"{label}: no trainer assigned", "sessions")
        booked = sessions.taken(s["id"])
        if course.get("min_delegates") and booked < int(course["min_delegates"]):
            add(start - timedelta(days=sessions.CHARGE_50_DAYS) if start else None,
                f"{label}: under-booked ({booked}/{course['min_delegates']} minimum) - "
                "run or cancel", "sessions")
        if s["status"] == "Planned":
            add(start - timedelta(days=14) if start else None, f"{label}: confirm session",
                "sessions")
    for s in r.list_records(sessions.SESSIONS):
        end = r.to_date(s["end_date"])
        if s["status"] in sessions.LIVE and end and end < date.today():
            add(end, f"{sessions.session_label(s)}: finished - take the last register and "
                     "mark Completed", "sessions")
    for t in r.list_records(courses.TRAINERS, equals={"status": "Active"}):
        add(courses.dbs_due(t), f"DBS renewal: {t['name']}", "trainers")
        last = quality.latest_observation(t["id"])
        if last and last.get("next_due"):
            add(r.to_date(last["next_due"]), f"Observation due: {t['name']}", "observations")
    for a in r.list_records(courses.APPROVALS):
        t = r.get(courses.TRAINERS, a["trainer_id"])
        if t and t["status"] == "Active":
            add(r.to_date(a.get("expires_on")), f"Trainer approval expires: {t['name']}",
                "trainer_approvals")
    for c in assessment.expiring(max(within_days, assessment.RENEW_DAYS)):
        add(assessment.renewal_due(c), f"Certificate {c['cert_no']} renewal (expires "
                                       f"{c['expires_on']})", "certificates",
            c.get("learner_name") or "", c["learner_id"])
    for f in r.list_records(quality.FEEDBACK, equals={"status": "Open"}):
        add(quality.response_due(f), "Complaint response", "feedback",
            f.get("learner_name") or "", f.get("learner_id"))
    for inv in r.list_records(finance.INVOICES, equals={"status": "Sent"}):
        if finance.outstanding(inv) > 0:
            add(r.to_date(inv["due_on"]), f"Invoice {inv['invoice_no']} payment "
                                          f"(£{finance.outstanding(inv):,.2f})", "invoices")
    for con in r.list_records(clients.CONTRACTS, equals={"status": "Active"}):
        end = r.to_date(con["end_date"])
        add(end - timedelta(days=60) if end else None,
            f"Contract renewal: {con['title']}", "contracts")
    return sorted(out, key=lambda d: d.due)


def dashboard() -> dict:
    today = date.today()
    month_start = today.replace(day=1)
    upcoming = sessions.upcoming(30)
    places = sum(int(s["capacity"]) for s in upcoming)
    booked = sum(sessions.taken(s["id"]) for s in upcoming)
    this_month = [b for b in r.list_records(sessions.BOOKINGS)
                  if (r.to_date(b.get("booked_on")) or today) >= month_start]
    due = due_items(30)
    return {
        "learners": len(learners.active_learners()),
        "clients": len(r.list_records(clients.CLIENTS, equals={"status": "Active"})),
        "sessions_30": len(upcoming),
        "fill": round(100 * booked / places) if places else None,
        "waiting": sum(sessions.waiting(s["id"]) for s in upcoming),
        "bookings_month": len(this_month),
        "booked_value_month": round(sum(sessions.chargeable(b) for b in this_month), 2),
        "achievement": achievement_rate(),
        "certs_expiring": len(assessment.expiring(90)),
        "uninvoiced": round(sum(x[3] for x in finance.payers_to_invoice()), 2),
        "outstanding": round(sum(finance.aged_debt().values()), 2),
        "overdue_debt": round(sum(finance.outstanding(i)
                                  for i in finance.overdue_invoices()), 2),
        "complaints_open": sum(1 for f in r.list_records(quality.FEEDBACK,
                                                         equals={"status": "Open"})
                               if f["kind"] == "Complaint"),
        "rating": quality.average_rating(),
        "due": due,
        "overdue": sum(1 for d in due if d.overdue),
    }


def session_fill(days: int = 90) -> list[dict]:
    out = []
    for s in sessions.upcoming(days):
        course = r.get(courses.COURSES, s["course_id"])
        n = sessions.taken(s["id"])
        out.append({"id": s["id"], "session": sessions.session_label(s),
                    "title": course["title"], "start": s["start_date"],
                    "booked": n, "capacity": int(s["capacity"]),
                    "waiting": sessions.waiting(s["id"]),
                    "fill": round(100 * n / int(s["capacity"])),
                    "under": bool(course.get("min_delegates")) and
                    n < int(course["min_delegates"]),
                    "status": s["status"]})
    return out


def achievement_rate() -> float | None:
    """% of learners finishing an accredited session (Attended or a result)
    who passed."""
    done = passed = 0
    for row in achievement():
        done += row["finished"]
        passed += row["passed"]
    return round(100 * passed / done) if done else None


def achievement() -> list[dict]:
    """Per accredited course: learners finished, passed, rate."""
    by_course: dict[int, dict] = {}
    for b in r.list_records(sessions.BOOKINGS):
        if b["status"] not in ("Attended", "Did not attend"):
            continue
        s = r.get(sessions.SESSIONS, b["session_id"])
        course = r.get(courses.COURSES, s["course_id"])
        if course["kind"] != courses.KINDS[0]:
            continue
        row = by_course.setdefault(course["id"], {"course": courses.course_label(course),
                                                  "finished": 0, "passed": 0})
        row["finished"] += 1
        res = assessment.latest_result(b["learner_id"], s["id"])
        if res and res["outcome"] in assessment.PASSES:
            row["passed"] += 1
    out = list(by_course.values())
    for row in out:
        row["rate"] = round(100 * row["passed"] / row["finished"]) if row["finished"] else None
    return sorted(out, key=lambda x: x["course"])


def booking_summary() -> dict[str, Counter]:
    rows = r.list_records(sessions.BOOKINGS)
    names = {c["id"]: c["name"] for c in r.list_records(clients.CLIENTS)}
    by_course: Counter = Counter()
    for b in rows:
        s = r.get(sessions.SESSIONS, b["session_id"])
        c = r.get(courses.COURSES, s["course_id"]) if s else None
        if c and b["status"] in sessions.PLACE_TAKEN:
            by_course[c["code"]] += 1
    return {
        "Bookings by status": Counter(b["status"] for b in rows),
        "Places by course": by_course,
        "Places by client": Counter(names.get(b.get("client_id"), "Self-funded")
                                    for b in rows if b["status"] in sessions.PLACE_TAKEN),
        "Learners by funding": Counter(x["funding"] for x in learners.active_learners()),
    }


def revenue_by_month(months: int = 12) -> list[tuple[str, float, float]]:
    """(YYYY-MM, invoiced total, payments received) for recent months."""
    inv: Counter = Counter()
    got: Counter = Counter()
    for i in r.list_records(finance.INVOICES):
        if i["status"] == "Sent":
            inv[i["issued_on"][:7]] += float(i["total"] or 0)
    for p in r.list_records(finance.PAYMENTS):
        got[p["paid_on"][:7]] += float(p["amount"] or 0)
    keys = sorted(set(inv) | set(got), reverse=True)[:months]
    return [(k, round(inv[k], 2), round(got[k], 2)) for k in sorted(keys)]


def quality_summary() -> dict:
    obs = r.list_records(quality.OBSERVATIONS)
    latest = {}
    for o in obs:   # newest first
        latest.setdefault(o["trainer_id"], o)
    fb = r.list_records(quality.FEEDBACK)
    return {
        "Latest observation grade per trainer": Counter(o["grade"] for o in latest.values()),
        "IQA decisions": Counter(x["decision"] for x in r.list_records(quality.IQA_SAMPLES)),
        "Feedback by type": Counter(f["kind"] for f in fb),
        "Ratings": Counter(f"{f['rating']} star" for f in fb if f.get("rating")),
        "sample_rate": quality.sample_rate(),
        "rating": quality.average_rating(),
    }


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
