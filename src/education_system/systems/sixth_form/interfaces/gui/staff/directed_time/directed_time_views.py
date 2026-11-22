"""Tkinter window: staff timetables, teaching load, who is free, and
directed-time budgets."""

from __future__ import annotations

import logging
from datetime import date as _date
from education_system.platform.delivery.gui.parented_dialogs import messagebox

from education_system.systems.sixth_form.domain.academics.timetable import (
    staff_timetable as tt_data,
)
from education_system.systems.sixth_form.domain.staff import staff as _staff
from education_system.systems.sixth_form.domain.staff.directed_time import (
    directed_time as data,
)
from education_system.systems.sixth_form.interfaces.gui.operations._ops_ui import (
    Field,
    SummaryTab,
    TableTab,
    form_dialog,
    make_window,
    option_key,
    staff_options,
)

logger = logging.getLogger(__name__)

_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri")
_PERIODS = tuple(f"P{p}" for p in range(1, 7))

_BAL_TAGS = {
    "over": ("#ffd1d1", "#8c0d0d"),
    "near": ("#fff7e6", "#7a5800"),
    "none": ("#eeeeee", "#444444"),
}
_ACT_TAGS = {
    data.CANCELLED: ("#eeeeee", "#777777"),
    data.PLANNED: ("#e6f0ff", "#1a3f8c"),
}


def _hours(v: float | None) -> str:
    return "" if v is None else f"{v:,.2f}".rstrip("0").rstrip(".")


def open_directed_time_window(parent=None) -> None:
    data.init_db()
    win, nb = make_window(parent, "Staff Timetables & Directed Time")
    tabs: list = []

    def refresh_all(_tab=None) -> None:
        for t in tabs:
            t.refresh()

    staff_list = staff_options()

    # ── Staff timetable grid ──
    def grid_loader(f):
        sid = option_key(f.get("staff"))
        if not sid:
            return []
        grid = tt_data.staff_grid(sid)
        rows = []
        for p in range(1, 7):
            cells = []
            for d in range(1, 6):
                lessons = grid.get((d, p), [])
                cells.append(" / ".join(
                    f"{ls.label}{' ' + ls.room if ls.room else ''}"
                    f"{' *' if ls.inherited else ''}" for ls in lessons))
            clash = any(len(grid.get((d, p), [])) > 1 for d in range(1, 6))
            rows.append((p, (f"P{p}", *cells), ("over",) if clash else ()))
        return rows

    tabs.append(TableTab(
        nb, "Staff Timetable",
        [("p", "Period", 70)] + [(d.lower(), d, 230) for d in _DAYS],
        grid_loader,
        filters=[Field("staff", "Staff", "combo", staff_list, width=36)],
        actions=[], tag_colours=_BAL_TAGS))

    # ── Teaching load ──
    def load_loader(f):
        rows = tt_data.teaching_loads(include_zero=bool(f.get("zero")),
                                      department=f.get("dept"))
        return [(ld.staff_id,
                 (ld.staff_id, ld.name, ld.role, ld.department,
                  f"{ld.fte_percent:g}%", ld.periods, _hours(ld.hours),
                  ld.available_periods, ld.non_contact_periods,
                  "" if ld.contact_ratio is None else f"{ld.contact_ratio}%",
                  len(ld.groups),
                  ", ".join(f"{_DAYS[d - 1]} P{p}"
                            for d, p in ld.double_booked)),
                 ("over",) if ld.double_booked else ())
                for ld in rows]

    def show_free_periods(tab):
        sid = tab.selected()
        if not sid:
            return
        cells = tt_data.free_periods(sid)
        by_day: dict[int, list[str]] = {}
        for d, p in cells:
            by_day.setdefault(d, []).append(f"P{p}")
        messagebox.showinfo(
            "Free periods",
            "\n".join(f"{_DAYS[d - 1]}: {', '.join(v)}"
                      for d, v in sorted(by_day.items())) or "None",
            parent=win)

    depts = list(_staff.DEPARTMENTS)
    tabs.append(TableTab(
        nb, "Teaching Load",
        [("id", "Staff ID", 90), ("name", "Name", 170), ("role", "Role", 140),
         ("dept", "Department", 130), ("fte", "FTE", 60),
         ("periods", "Periods/wk", 80), ("hours", "Hours/wk", 75),
         ("avail", "Available", 75), ("nc", "Non-contact", 85),
         ("ratio", "Contact %", 75), ("groups", "Groups", 60),
         ("clash", "Double-booked", 160)],
        load_loader,
        filters=[Field("dept", "Department", "combo", depts, width=18),
                 Field("zero", "Include staff with no lessons", "check")],
        actions=[("Free periods", show_free_periods)],
        tag_colours=_BAL_TAGS))

    # ── Who is free ──
    def free_loader(f):
        day = f.get("day")
        period = f.get("period")
        if not day or not period:
            return []
        rows = tt_data.free_staff(day, period, on_date=f.get("date") or None,
                                  teaching_roles_only=not f.get("all"))
        return [(r.staff_id,
                 (r.staff_id, r.name, r.role, r.department,
                  r.lessons_that_day, r.lessons_this_week), ())
                for r in rows]

    tabs.append(TableTab(
        nb, "Who's Free",
        [("id", "Staff ID", 90), ("name", "Name", 200), ("role", "Role", 160),
         ("dept", "Department", 160), ("day", "Lessons that day", 120),
         ("week", "Lessons this week", 120)],
        free_loader,
        filters=[Field("day", "Day", "combo", _DAYS, width=6),
                 Field("period", "Period", "combo", _PERIODS, width=5),
                 Field("date", "On date (YYYY-MM-DD)", width=11),
                 Field("all", "All roles", "check")],
        actions=[]))

    # ── Unassigned lessons ──
    def unmatched_loader(_f):
        return [(ls.slot_id,
                 (ls.slot_id, _DAYS[ls.day - 1] if 1 <= ls.day <= 5
                  else ls.day, f"P{ls.period}", ls.label, ls.subject,
                  ls.room, ls.teacher_text or "(no teacher)",
                  "course" if ls.inherited else "group"), ())
                for ls in tt_data.unmatched_lessons()]

    tabs.append(TableTab(
        nb, "Unmatched Lessons",
        [("slot", "Slot", 60), ("day", "Day", 60), ("p", "Period", 60),
         ("grp", "Group", 180), ("subj", "Subject", 150),
         ("room", "Room", 80), ("teacher", "Teacher text", 200),
         ("from", "Teacher from", 100)],
        unmatched_loader, actions=[]))

    # ── Budgets ──
    budget_fields = [
        Field("contracted_hours", "Contracted directed hours (full time)"),
        Field("fte_percent", "FTE % (blank = from Staff HR)"),
        Field("allocated_hours", "Allocated hours (blank = contracted × FTE)"),
        Field("teaching_weeks", "Teaching weeks"),
        Field("include_teaching", "Count timetabled teaching", "check"),
        Field("include_cpd", "Count CPD attended", "check"),
        Field("notes", "Notes", "text"),
    ]

    def _bal_row(b):
        tag = ("none" if not b.has_budget else "over" if b.over
               else "near" if (b.percent_used or 0) >= data.NEAR_LIMIT_PERCENT
               else "")
        return (b.staff_id,
                (b.staff_id, b.name, b.academic_year, _hours(b.allocated),
                 _hours(b.teaching), _hours(b.logged), _hours(b.planned),
                 _hours(b.parents_evenings), _hours(b.cpd), _hours(b.cover),
                 _hours(b.used), _hours(b.remaining),
                 "" if b.percent_used is None else f"{b.percent_used}%"),
                (tag,) if tag else ())

    def budgets_loader(f):
        return [_bal_row(b) for b in data.balances(f.get("year") or None)]

    def _year(tab) -> str:
        return tab.filters().get("year") or data.current_academic_year()

    def new_budget(tab):
        v = form_dialog(win, "New directed-time budget", [
            Field("staff", "Staff", "combo", staff_list, required=True,
                  width=40),
            Field("academic_year", "Academic year", required=True),
        ] + budget_fields, {
            "academic_year": _year(tab),
            "contracted_hours": f"{data.FULL_TIME_DIRECTED_HOURS:g}",
            "teaching_weeks": data.DEFAULT_TEACHING_WEEKS,
            "include_teaching": True, "include_cpd": True})
        if v:
            v["staff_id"] = option_key(v.pop("staff"))
            for k in ("fte_percent", "allocated_hours"):
                if not v.get(k):
                    v.pop(k, None)
            data.create_budget(v)
            refresh_all()

    def _selected_budget(tab):
        sid = tab.selected()
        if not sid:
            return None
        b = data.budget_for(sid, _year(tab))
        if b is None:
            messagebox.showwarning("No budget",
                                   "That person has no budget for the year.",
                                   parent=win)
        return b

    def edit_budget(tab):
        b = _selected_budget(tab)
        if not b:
            return
        v = form_dialog(win, f"Budget — {b.staff_name or b.staff_id} "
                        f"{b.academic_year}", budget_fields, vars(b))
        if v:
            data.update_budget(b.budget_id, v)
            refresh_all()

    def delete_budget(tab):
        b = _selected_budget(tab)
        if b and messagebox.askyesno(
                "Delete", "Remove this budget? Logged activities are kept.",
                parent=win):
            data.delete_budget(b.budget_id)
            refresh_all()

    def default_budgets(tab):
        year = _year(tab)
        if not messagebox.askyesno(
                "Default budgets",
                f"Give every teaching member of staff without a budget for "
                f"{year} the standard {data.FULL_TIME_DIRECTED_HOURS:g} h "
                "pro-rata by their HR FTE?", parent=win):
            return
        made = data.create_default_budgets(year)
        messagebox.showinfo("Default budgets",
                            f"Created {len(made)} budget(s).", parent=win)
        refresh_all()

    def breakdown(tab):
        sid = tab.selected()
        if not sid:
            return
        items = data.directed_items(sid, _year(tab))
        lines = [f"{i.date or '—':<10}  {i.source:<16} {i.status:<9} "
                 f"{_hours(i.hours):>7} h  {i.title}" for i in items]
        bal = data.balance(sid, _year(tab))
        lines += ["", f"Used {_hours(bal.used)} of {_hours(bal.allocated)} h;"
                  f" remaining {_hours(bal.remaining)} h"]
        messagebox.showinfo(f"Directed time — {bal.name}",
                            "\n".join(lines) or "Nothing recorded",
                            parent=win)

    bal_cols = [
        ("id", "Staff ID", 85), ("name", "Name", 160), ("year", "Year", 65),
        ("alloc", "Allocated", 75), ("teach", "Teaching", 70),
        ("logged", "Logged", 65), ("planned", "of which planned", 105),
        ("pe", "Parents' eve.", 85), ("cpd", "CPD", 55),
        ("cover", "Cover", 55), ("used", "Used", 65),
        ("rem", "Remaining", 75), ("pct", "% used", 65)]
    tabs.append(TableTab(
        nb, "Budgets", bal_cols, budgets_loader,
        filters=[Field("year", "Academic year (2026/27)", width=9)],
        actions=[("New budget", new_budget), ("Edit", edit_budget),
                 ("Breakdown", breakdown), ("Delete", delete_budget),
                 ("Default budgets for all", default_budgets)],
        on_double=breakdown, tag_colours=_BAL_TAGS))

    # ── Activities ──
    act_fields = [
        Field("activity_date", "Date (YYYY-MM-DD)", required=True),
        Field("category", "Category", "combo", data.CATEGORIES,
              required=True),
        Field("title", "Title", required=True, width=44),
        Field("hours", "Hours each time", required=True),
        Field("occurrences", "Occurrences (e.g. 38 for a weekly duty)"),
        Field("status", "Status", "combo", data.ACTIVITY_STATUSES,
              required=True),
        Field("notes", "Notes", "text"),
    ]

    def acts_loader(f):
        rows = data.list_activities(
            staff_id=option_key(f.get("staff")),
            academic_year=f.get("year") or None,
            category=f.get("category"), status=f.get("status"))
        return [(a.activity_id,
                 (a.activity_id, a.staff_id, a.staff_name, a.activity_date,
                  a.category, a.title, _hours(a.hours), a.occurrences,
                  _hours(a.total_hours), a.status, a.recorded_by),
                 (a.status,) if a.status in _ACT_TAGS else ())
                for a in rows]

    act_defaults = {"activity_date": _date.today().isoformat(),
                    "category": data.DEFAULT_CATEGORY, "occurrences": 1,
                    "status": data.PLANNED}

    def log_act(tab):
        v = form_dialog(win, "Log directed time", [
            Field("staff", "Staff", "combo", staff_list, required=True,
                  width=40)] + act_fields, act_defaults)
        if v:
            v["staff_id"] = option_key(v.pop("staff"))
            data.log_activity(v)
            refresh_all()

    def log_many(tab):
        v = form_dialog(win, "Log for several people", [
            Field("staff", "Staff", "multi", staff_list)] + act_fields,
            act_defaults)
        if v:
            ids = [option_key(s) for s in v.pop("staff")]
            made = data.log_activity_for_many(ids, v)
            messagebox.showinfo("Logged", f"Logged for {len(made)} people.",
                                parent=win)
            refresh_all()

    def edit_act(tab):
        aid = tab.selected()
        if not aid:
            return
        a = data.get_activity(int(aid))
        v = form_dialog(win, f"Edit activity #{a.activity_id}", act_fields,
                        vars(a))
        if v:
            data.update_activity(a.activity_id, v)
            refresh_all()

    def set_status(status):
        def run(tab):
            aid = tab.selected()
            if aid:
                data.set_activity_status(int(aid), status)
                refresh_all()
        return run

    def delete_act(tab):
        aid = tab.selected()
        if aid and messagebox.askyesno("Delete", "Delete this activity?",
                                       parent=win):
            data.delete_activity(int(aid))
            refresh_all()

    tabs.append(TableTab(
        nb, "Activities",
        [("id", "ID", 50), ("sid", "Staff ID", 85), ("name", "Name", 150),
         ("date", "Date", 85), ("cat", "Category", 120),
         ("title", "Title", 230), ("hours", "Hours", 55),
         ("occ", "Times", 50), ("total", "Total h", 65),
         ("status", "Status", 85), ("by", "Recorded by", 120)],
        acts_loader,
        filters=[Field("staff", "Staff", "combo", staff_list, width=26),
                 Field("year", "Year", width=8),
                 Field("category", "Category", "combo", data.CATEGORIES,
                       width=14),
                 Field("status", "Status", "combo", data.ACTIVITY_STATUSES,
                       width=10)],
        actions=[("Log activity", log_act), ("Log for several", log_many),
                 ("Edit", edit_act),
                 ("Mark completed", set_status(data.COMPLETED)),
                 ("Cancel", set_status(data.CANCELLED)),
                 ("Delete", delete_act)],
        on_double=edit_act, tag_colours=_ACT_TAGS))

    # ── Over-allocation ──
    def over_loader(f):
        over, near = data.over_allocation_report(f.get("year") or None)
        return [_bal_row(b) for b in over + near]

    def missing_loader(f):
        return [(s.staff_id, (s.staff_id, s.full_name, s.role, s.department,
                              s.employment_status), ())
                for s in data.staff_without_budget(f.get("year") or None)]

    tabs.append(TableTab(
        nb, "Over-allocation", bal_cols, over_loader,
        filters=[Field("year", "Academic year", width=9)],
        actions=[("Breakdown", breakdown)], tag_colours=_BAL_TAGS))
    tabs.append(TableTab(
        nb, "No Budget",
        [("id", "Staff ID", 90), ("name", "Name", 220), ("role", "Role", 170),
         ("dept", "Department", 170), ("status", "Employment", 120)],
        missing_loader,
        filters=[Field("year", "Academic year", width=9)],
        actions=[("Default budgets for all", default_budgets)]))

    def render():
        year = data.current_academic_year()
        rows = data.balances(year)
        over, near = data.over_allocation_report(year)
        loads = tt_data.teaching_loads()
        lines = [f"Directed time {year}", "",
                 f"  Budgets set:            {len(rows)}",
                 f"  Allocated hours:        "
                 f"{_hours(sum(b.allocated for b in rows))}",
                 f"  Used hours:             "
                 f"{_hours(sum(b.used for b in rows))}",
                 f"  Over budget:            {len(over)}",
                 f"  At {data.NEAR_LIMIT_PERCENT:g}%+ of budget:     "
                 f"{len(near)}",
                 f"  Teaching staff without a budget: "
                 f"{len(data.staff_without_budget(year))}",
                 "", "Timetable",
                 f"  Staff with lessons:     {len(loads)}",
                 f"  Periods taught / week:  {sum(ld.periods for ld in loads)}",
                 f"  Double-booked staff:    "
                 f"{sum(1 for ld in loads if ld.double_booked)}",
                 f"  Unmatched lessons:      "
                 f"{len(tt_data.unmatched_lessons())}"]
        return lines

    tabs.append(SummaryTab(nb, render))
