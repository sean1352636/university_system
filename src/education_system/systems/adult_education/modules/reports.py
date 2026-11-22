"""Read-only views across every area: the dashboard, what's due, and the
enrolment, attendance, funding, fees, achievement and destination reports."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from education_system.systems.adult_education.core import dates
from education_system.systems.adult_education.core import records as r
from education_system.systems.adult_education.modules import (
    courses, enrolments, funding, learners, progress, support,
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

    def add(due: date | None, what: str, row: dict, area: str, who: str | None = None) -> None:
        if due and due <= horizon:
            out.append(DueItem(due, what, who if who is not None else
                               (row.get("learner_name") or ""), row.get("learner_id"), area))

    for row in r.list_records(learners.IDENTITY, equals={"status": "Verified"}):
        add(r.to_date(row.get("expiry_date")), f"ID expires: {row['document_type']}", row,
            "identity_checks")
    for row in r.list_records(progress.GOALS):
        if row["status"] not in progress.CLOSED:
            add(r.to_date(row.get("target_date")), f"Goal target: {row['title']}", row, "goals")
    for row in r.list_records(support.SUPPORT, equals={"status": "Active"}):
        add(r.to_date(row.get("review_date")), f"Support review: {row['need']}", row,
            "support_plans")
    for row in r.list_records(support.FEEDBACK, equals={"status": "Open"}):
        if row["kind"] in ("Complaint", "Appeal"):
            add(r.to_date(row["received_on"]) + timedelta(days=support.COMPLAINT_RESPONSE_DAYS),
                f"{row['kind']} reply: {row['about']}", row, "feedback")
    for row in r.list_records(enrolments.ENQUIRIES):
        if row["status"] not in ("Enrolled", "Closed"):
            add(r.to_date(row.get("follow_up")), "Enquiry follow-up", row, "enquiries",
                who=row["name"])
    for row in r.list_records(courses.TUTORS, equals={"status": "Active"}):
        checked = r.to_date(row.get("dbs_date"))
        due = dates.add_months(checked, 12 * courses.DBS_RENEWAL_YEARS) if checked else date.today()
        add(due, f"Tutor DBS {'renewal' if checked else 'check missing'}: {row['name']}", row,
            "tutors", who="")
    for row in r.list_records(courses.CLASSES):
        if row["status"] in ("Planned", "Open for enrolment"):
            add(r.to_date(row.get("start_date")), f"Class starts: {courses.class_label(row)}",
                row, "classes", who="")
    return sorted(out, key=lambda d: d.due)


def _recent_attendance(days: int = 30) -> float | None:
    since = (date.today() - timedelta(days=days)).isoformat()
    marks = [m["mark"] for m in r.list_records(enrolments.ATTENDANCE)
             if m["session_date"] >= since]
    return round(100 * sum(m in enrolments.PRESENT for m in marks) / len(marks)) if marks else None


def outstanding() -> list[dict]:
    out = []
    for row in r.list_records(enrolments.ENROLMENTS):
        if row["status"] in ("Enrolled", "Completed", "Withdrawn"):
            bal = enrolments.balance(row)
            if bal > 0:
                out.append({**row, "balance": bal})
    return sorted(out, key=lambda x: -x["balance"])


def dashboard() -> dict:
    active = [x for x in learners.active_learners() if x["status"] == "Active"]
    live = [c for c in r.list_records(courses.CLASSES)
            if c["status"] in ("Open for enrolment", "Running")]
    places = sum(c["capacity"] or 0 for c in live)
    enrolled = [e for e in r.list_records(enrolments.ENROLMENTS) if e["status"] == "Enrolled"]
    waiting = len(r.list_records(enrolments.ENROLMENTS, equals={"status": "Waiting list"}))
    owed = outstanding()
    due = due_items(30)
    return {
        "active_learners": len(active),
        "enquiries": sum(1 for x in learners.active_learners() if x["status"] == "Enquiry"),
        "classes": len(live), "places": places, "enrolled": len(enrolled), "waiting": waiting,
        "attendance": _recent_attendance(),
        "owed": sum(x["balance"] for x in owed), "owed_count": len(owed),
        "due": due, "overdue": sum(1 for d in due if d.overdue),
    }


def enrolment_summary() -> list[dict]:
    """Per class: places, enrolled, waiting, withdrawn, completed."""
    counts: dict[int, Counter] = {}
    for e in r.list_records(enrolments.ENROLMENTS):
        counts.setdefault(e["class_id"], Counter())[e["status"]] += 1
    out = []
    for c in r.list_records(courses.CLASSES):
        n = counts.get(c["id"], Counter())
        out.append({"class": courses.class_label(c), "status": c["status"],
                    "places": c["capacity"] or 0, "enrolled": n["Enrolled"] + n["Completed"],
                    "waiting": n["Waiting list"], "withdrawn": n["Withdrawn"],
                    "completed": n["Completed"]})
    return out


def attendance_report() -> list[dict]:
    """Per enrolled learner with marks: attendance %, lowest first."""
    out = []
    for e in r.list_records(enrolments.ENROLMENTS):
        if e["status"] not in ("Enrolled", "Completed"):
            continue
        rate = enrolments.attendance_rate(e)
        if rate is not None:
            klass = r.get(courses.CLASSES, e["class_id"])
            out.append({"learner": e["learner_name"], "learner_id": e["learner_id"],
                        "class": courses.class_label(klass) if klass else "", "rate": rate})
    return sorted(out, key=lambda x: x["rate"])


def funding_summary() -> dict[str, Counter]:
    return {
        "Assessment outcomes": Counter(x["outcome"] for x in
                                       r.list_records(funding.ELIGIBILITY)),
        "Enrolments by funding": Counter(x.get("funding") or "Not set" for x in
                                         r.list_records(enrolments.ENROLMENTS)
                                         if x["status"] != "Waiting list"),
    }


def achievement() -> list[dict]:
    """Per course: completers (leavers), achieved, and the achievement rate."""
    by: dict[int, Counter] = {}
    for e in r.list_records(enrolments.ENROLMENTS):
        if e["status"] in ("Completed", "Withdrawn"):
            klass = r.get(courses.CLASSES, e["class_id"])
            if klass:
                c = by.setdefault(klass["course_id"], Counter())
                c["leavers"] += 1
                c["achieved"] += e["outcome"] == "Achieved"
                c["withdrawn"] += e["status"] == "Withdrawn"
    out = []
    for cid, c in by.items():
        course = r.get(courses.COURSES, cid) or {}
        out.append({"course": f"{course.get('code', '')} {course.get('title', '')}",
                    "leavers": c["leavers"], "achieved": c["achieved"],
                    "withdrawn": c["withdrawn"],
                    "rate": round(100 * c["achieved"] / c["leavers"])})
    return sorted(out, key=lambda x: x["rate"])


def destinations_summary() -> Counter:
    latest: dict[int, str] = {}
    for row in sorted(r.list_records(progress.DESTINATIONS), key=lambda x: x["recorded_on"]):
        latest[row["learner_id"]] = row["destination"]
    return Counter(latest.values())


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
