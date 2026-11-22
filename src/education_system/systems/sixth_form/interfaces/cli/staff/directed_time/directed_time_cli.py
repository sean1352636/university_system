"""CLI flows: staff timetables, teaching load, who is free, directed time."""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Callable

from education_system.systems.sixth_form.domain.academics.timetable import (
    staff_timetable as tt_data,
)
from education_system.systems.sixth_form.domain.staff.directed_time import (
    directed_time as data,
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

_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri")


def _h(v: float | None) -> str:
    return "" if v is None else f"{v:,.2f}".rstrip("0").rstrip(".")


def _year() -> str:
    return ask("Academic year", default=data.current_academic_year())


# ── Timetables ──────────────────────────────────────────────────────

def staff_timetable() -> None:
    sid = pick_staff()
    grid = tt_data.staff_grid(sid)
    rows = []
    for p in range(1, 7):
        rows.append([f"P{p}"] + [
            " / ".join(f"{ls.label}{' ' + ls.room if ls.room else ''}"
                       for ls in grid.get((d, p), []))
            for d in range(1, 6)])
    table(["Period", *_DAYS], rows)
    ld = tt_data.teaching_load(sid)
    print(f"\n  {ld.periods} period(s), {_h(ld.hours)} h a week; "
          f"{ld.non_contact_periods} non-contact of {ld.available_periods} "
          f"(FTE {ld.fte_percent:g}%)")
    if ld.double_booked:
        print("  Double-booked: " + ", ".join(
            f"{_DAYS[d - 1]} P{p}" for d, p in ld.double_booked))
    pause()


def teaching_loads() -> None:
    rows = tt_data.teaching_loads(include_zero=yes_no(
        "Include staff with no lessons?"))
    table(["ID", "Name", "Role", "FTE", "Periods", "Hours", "Avail.",
           "Non-contact", "Contact %", "Double-booked"],
          [(ld.staff_id, ld.name, ld.role, f"{ld.fte_percent:g}%",
            ld.periods, _h(ld.hours), ld.available_periods,
            ld.non_contact_periods,
            "" if ld.contact_ratio is None else f"{ld.contact_ratio}%",
            len(ld.double_booked)) for ld in rows])
    pause()


def whos_free() -> None:
    day = choose("Day", _DAYS)
    period = ask_int("Period (1-6)")
    on = ask("On date (YYYY-MM-DD, blank = any week)")
    rows = tt_data.free_staff(day, period, on_date=on or None,
                              teaching_roles_only=not yes_no(
                                  "Include non-teaching roles?"))
    table(["ID", "Name", "Role", "Department", "Lessons that day",
           "Lessons/week"],
          [(r.staff_id, r.name, r.role, r.department, r.lessons_that_day,
            r.lessons_this_week) for r in rows])
    pause()


def unmatched() -> None:
    table(["Slot", "Day", "Period", "Group", "Teacher text"],
          [(ls.slot_id, _DAYS[ls.day - 1] if 1 <= ls.day <= 5 else ls.day,
            f"P{ls.period}", ls.label, ls.teacher_text or "(none)")
           for ls in tt_data.unmatched_lessons()])
    pause()


# ── Budgets ─────────────────────────────────────────────────────────

def _show_balances(rows) -> None:
    table(["ID", "Name", "Allocated", "Teaching", "Logged", "Parents' ev.",
           "CPD", "Cover", "Used", "Remaining", "% used"],
          [(b.staff_id, b.name, _h(b.allocated), _h(b.teaching),
            _h(b.logged), _h(b.parents_evenings), _h(b.cpd), _h(b.cover),
            _h(b.used), _h(b.remaining),
            "" if b.percent_used is None else f"{b.percent_used}%")
           for b in rows])


def list_balances() -> None:
    _show_balances(data.balances(_year()))
    pause()


def my_balance() -> None:
    sid = pick_staff()
    year = _year()
    items = data.directed_items(sid, year)
    table(["Date", "Source", "Category", "Status", "Hours", "Title"],
          [(i.date, i.source, i.category, i.status, _h(i.hours), i.title)
           for i in items])
    b = data.balance(sid, year)
    print(f"\n  Allocated {_h(b.allocated)} h · used {_h(b.used)} h · "
          f"remaining {_h(b.remaining)} h"
          + ("  ** OVER BUDGET **" if b.over else ""))
    pause()


def _budget_answers(b=None) -> dict:
    return {
        "contracted_hours": ask(
            "Contracted directed hours (full time)",
            default=_h(b.contracted_hours) if b
            else f"{data.FULL_TIME_DIRECTED_HOURS:g}"),
        "fte_percent": ask("FTE % (blank = from Staff HR)",
                           default=_h(b.fte_percent) if b else "") or None,
        "allocated_hours": ask("Allocated hours (blank = contracted × FTE)")
        or None,
        "teaching_weeks": ask_int("Teaching weeks", default=b.teaching_weeks
                                  if b else data.DEFAULT_TEACHING_WEEKS),
        "include_teaching": yes_no("Count timetabled teaching?",
                                   default=b.include_teaching if b else True),
        "include_cpd": yes_no("Count CPD attended?",
                              default=b.include_cpd if b else True),
        "notes": ask("Notes", default=(b.notes or "") if b else ""),
    }


def new_budget() -> None:
    sid = pick_staff()
    payload = {"staff_id": sid, "academic_year": _year(), **_budget_answers()}
    payload = {k: v for k, v in payload.items() if v is not None}
    b = data.create_budget(payload)
    print(f"\n  ✓ Budget {_h(b.allocated_hours)} h for {b.staff_id} "
          f"{b.academic_year}")
    pause()


def _pick_budget():
    year = _year()
    rows = data.list_budgets(academic_year=year)
    label = choose("Budget", [f"{b.budget_id} — {b.staff_id} "
                              f"{b.staff_name or ''} ({_h(b.allocated_hours)} h)"
                              for b in rows])
    if label is None:
        raise ValueError("No budgets for that year")
    return data.get_budget(int(label.split(" — ")[0]))


def edit_budget() -> None:
    b = _pick_budget()
    out = data.update_budget(b.budget_id, {
        k: v for k, v in _budget_answers(b).items() if v is not None})
    print(f"\n  ✓ Now {_h(out.allocated_hours)} h")
    pause()


def delete_budget() -> None:
    b = _pick_budget()
    if yes_no("Delete this budget (activities are kept)?"):
        data.delete_budget(b.budget_id)
        print("\n  ✓ Deleted")
    pause()


def default_budgets() -> None:
    year = _year()
    if yes_no(f"Create standard budgets for teaching staff without one in "
              f"{year}?", default=True):
        made = data.create_default_budgets(year)
        print(f"\n  ✓ Created {len(made)} budget(s)")
    pause()


def over_allocation() -> None:
    over, near = data.over_allocation_report(_year())
    print("\n  Over budget:")
    _show_balances(over)
    print(f"\n  At {data.NEAR_LIMIT_PERCENT:g}% or more:")
    _show_balances(near)
    pause()


def no_budget() -> None:
    table(["ID", "Name", "Role", "Department"],
          [(s.staff_id, s.full_name, s.role, s.department)
           for s in data.staff_without_budget(_year())])
    pause()


# ── Activities ──────────────────────────────────────────────────────

def _activity_answers(a=None) -> dict:
    return {
        "activity_date": ask("Date (YYYY-MM-DD)",
                             default=a.activity_date if a
                             else _dt.date.today().isoformat()),
        "category": choose("Category", data.CATEGORIES,
                           default=a.category if a
                           else data.DEFAULT_CATEGORY),
        "title": ask("Title", default=a.title if a else "", required=True),
        "hours": ask("Hours each time", default=_h(a.hours) if a else "",
                     required=True),
        "occurrences": ask_int("Occurrences", default=a.occurrences
                               if a else 1),
        "status": choose("Status", data.ACTIVITY_STATUSES,
                         default=a.status if a else data.PLANNED),
        "notes": ask("Notes", default=(a.notes or "") if a else ""),
    }


def log_activity() -> None:
    sid = pick_staff()
    a = data.log_activity({"staff_id": sid, **_activity_answers()})
    print(f"\n  ✓ Logged {_h(a.total_hours)} h for {a.staff_id}")
    pause()


def log_for_many() -> None:
    from education_system.systems.sixth_form.domain.staff import staff as _sf
    people = [f"{s.staff_id} — {s.full_name}"
              for s in _sf.list_staff(active_only=True)]
    chosen = choose_many("Staff", people)
    made = data.log_activity_for_many([c.split(" — ")[0] for c in chosen],
                                      _activity_answers())
    print(f"\n  ✓ Logged for {len(made)} people")
    pause()


def list_activities() -> None:
    sid = ask("Staff id (blank = all you can see)")
    rows = data.list_activities(staff_id=sid or None,
                                academic_year=_year())
    table(["ID", "Staff", "Date", "Category", "Title", "Hours", "Times",
           "Total", "Status"],
          [(a.activity_id, a.staff_name or a.staff_id, a.activity_date,
            a.category, a.title, _h(a.hours), a.occurrences,
            _h(a.total_hours), a.status) for a in rows])
    pause()


def _pick_activity():
    sid = ask("Staff id (blank = all)")
    rows = data.list_activities(staff_id=sid or None)
    label = choose("Activity", [f"{a.activity_id} — {a.activity_date} "
                                f"{a.staff_id} {a.title} ({a.status})"
                                for a in rows[:60]])
    if label is None:
        raise ValueError("No activities")
    return data.get_activity(int(label.split(" — ")[0]))


def edit_activity() -> None:
    a = _pick_activity()
    data.update_activity(a.activity_id, _activity_answers(a))
    print("\n  ✓ Updated")
    pause()


def complete_activity() -> None:
    a = _pick_activity()
    data.set_activity_status(a.activity_id, data.COMPLETED)
    print("\n  ✓ Marked completed")
    pause()


def cancel_activity() -> None:
    a = _pick_activity()
    data.set_activity_status(a.activity_id, data.CANCELLED)
    print("\n  ✓ Cancelled")
    pause()


def delete_activity() -> None:
    a = _pick_activity()
    if yes_no("Delete this activity?"):
        data.delete_activity(a.activity_id)
        print("\n  ✓ Deleted")
    pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Staff timetable",          staff_timetable),
    ("Teaching load",            teaching_loads),
    ("Who is free",              whos_free),
    ("Unmatched lessons",        unmatched),
    ("─" * 6,                    lambda: None),
    ("Directed time balances",   list_balances),
    ("One person's directed time", my_balance),
    ("Over-allocation report",   over_allocation),
    ("Teaching staff with no budget", no_budget),
    ("─" * 6,                    lambda: None),
    ("Log activity",             log_activity),
    ("Log for several people",   log_for_many),
    ("List activities",          list_activities),
    ("Edit activity",            edit_activity),
    ("Mark activity completed",  complete_activity),
    ("Cancel activity",          cancel_activity),
    ("Delete activity",          delete_activity),
    ("─" * 6,                    lambda: None),
    ("New budget",               new_budget),
    ("Edit budget",              edit_budget),
    ("Delete budget",            delete_budget),
    ("Default budgets for all",  default_budgets),
]


def run() -> None:
    run_menu("Staff Timetables & Directed Time", _MENU)


def directed_time_menu() -> None:
    """Entry point for the main CLI menu."""
    run()
