"""CLI flows for staff exit interviews (HR)."""

from __future__ import annotations

import logging
from typing import Callable

from education_system.systems.sixth_form.domain.staff.staff_hr import (
    exit_interviews as data,
)
from education_system.systems.sixth_form.interfaces.cli.operations._ops_cli import (
    ask,
    ask_int,
    choose,
    choose_many,
    pause,
    pick_staff,
    run_menu,
    table,
    yes_no,
)

logger = logging.getLogger(__name__)


def _show(rows) -> None:
    table(["#", "Staff", "Department", "Leaving", "Status", "Main reason",
           "Going to", "Avg"],
          [(i.interview_id, i.staff_name, i.department, i.leaving_date,
            i.status, i.primary_reason, i.destination, i.average_rating)
           for i in rows])


def _answers(existing=None) -> dict:
    g = (lambda k: getattr(existing, k) or "") if existing else (lambda k: "")
    status = choose("Status", data.STATUSES,
                    default=g("status") or data.SCHEDULED)
    out: dict = {"status": status}
    if status == data.DECLINED:
        out["notes"] = ask("Notes", default=g("notes"))
        return out
    if status == data.COMPLETED or yes_no("Record answers now?"):
        out["primary_reason"] = choose("Main reason", data.REASONS,
                                       default=g("primary_reason") or None)
        out["other_reasons"] = choose_many(
            "Other reasons", data.REASONS,
            existing.other_reasons if existing else [])
        out["destination"] = choose("Going to", data.DESTINATIONS,
                                    default=g("destination") or None,
                                    allow_blank=True)
        out["destination_detail"] = ask("Destination detail",
                                        default=g("destination_detail"))
        print("  Ratings 1 (very poor) – 5 (very good); blank = skip")
        ratings = dict(existing.ratings) if existing else {}
        for area in data.FEEDBACK_AREAS:
            raw = ask(f"  {area}", default=str(ratings.get(area, "")))
            if raw:
                ratings[area] = raw
        out["ratings"] = ratings
        out["went_well"] = ask("What we did well", default=g("went_well"))
        out["could_improve"] = ask("What we should change",
                                   default=g("could_improve"))
        out["would_recommend"] = choose("Would recommend us", data.ANSWERS,
                                        allow_blank=True)
        out["would_return"] = choose("Would consider returning",
                                     data.ANSWERS, allow_blank=True)
        out["interview_date"] = ask("Interview date (YYYY-MM-DD)",
                                    default=g("interview_date"))
        out["method"] = choose("Method", data.METHODS, allow_blank=True)
    if yes_no("Set the interviewer?", default=not existing):
        out["interviewer_id"] = pick_staff()
    out["notes"] = ask("Notes", default=g("notes"))
    return out


def new_flow() -> None:
    sid = pick_staff()
    leaving = ask("Leaving date (blank = from staff record)")
    iv = data.create_interview({"staff_id": sid, "leaving_date": leaving,
                                **_answers()})
    print(f"\n  ✓ Exit interview #{iv.interview_id} for {iv.staff_name} "
          f"({iv.status})")
    pause()


def edit_flow() -> None:
    iv = data.get_interview(ask_int("Interview #"))
    iv = data.update_interview(iv.interview_id, _answers(iv))
    print(f"\n  ✓ Updated ({iv.status})")
    pause()


def list_flow() -> None:
    year = ask("Academic year (e.g. 2025/26, blank = all)")
    _show(data.list_interviews(academic_year=year or None))
    pause()


def view_flow() -> None:
    iv = data.get_interview(ask_int("Interview #"))
    print(f"\n  {iv.staff_name} ({iv.job_role}, {iv.department}) — leaving "
          f"{iv.leaving_date}, {iv.status}")
    print(f"  Main reason:   {iv.primary_reason or '—'}")
    print(f"  Other reasons: {', '.join(iv.other_reasons) or '—'}")
    print(f"  Going to:      {iv.destination or '—'} "
          f"{iv.destination_detail or ''}")
    for a in data.FEEDBACK_AREAS:
        if a in iv.ratings:
            print(f"    {a:<28} {iv.ratings[a]}")
    print(f"  Did well: {iv.went_well or '—'}")
    print(f"  Change:   {iv.could_improve or '—'}")
    print(f"  Recommend: {iv.would_recommend or '—'}; return: "
          f"{iv.would_return or '—'}")
    print(f"  Interviewer: {iv.interviewer_name or '—'} "
          f"{iv.interview_date or ''} {iv.method or ''}")
    pause()


def leavers_flow() -> None:
    table(["Staff id", "Name", "Role", "Department", "Leaving", "Known from"],
          [(lv.staff_id, lv.staff_name, lv.job_role, lv.department,
            lv.leaving_date, lv.source)
           for lv in data.leavers_without_interview()])
    pause()


def report_flow() -> None:
    year = ask("Academic year (e.g. 2025/26, blank = all)")
    r = data.report(academic_year=year or None)
    print(f"\n  Interviews {r.interviews}: {r.completed} completed, "
          f"{r.declined} declined")
    if r.average_service_years is not None:
        print(f"  Average service: {r.average_service_years} years")
    for title, d in (("Main reasons", r.primary_reasons),
                     ("All reasons given", r.reasons),
                     ("Destinations", r.destinations),
                     ("Would recommend", r.would_recommend)):
        print(f"\n  {title}:")
        for k, v in d.items():
            print(f"    {k:<40} {v}")
    print("\n  Average ratings (1-5):")
    for a in data.FEEDBACK_AREAS:
        if a in r.area_averages:
            print(f"    {a:<28} {r.area_averages[a]}")
    pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Leavers without interview", leavers_flow),
    ("New exit interview",        new_flow),
    ("Edit / complete interview", edit_flow),
    ("List interviews",           list_flow),
    ("View interview",            view_flow),
    ("─" * 6,                     lambda: None),
    ("Reasons report",            report_flow),
]


def run() -> None:
    data.init_db()
    run_menu("Staff Exit Interviews", _MENU)


def exit_interviews_menu() -> None:
    """Entry point for the main CLI menu."""
    run()


def dispatch(label: str) -> bool:
    if label != "Exit Interviews":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Exit interviews CLI crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        pause()
    return True
