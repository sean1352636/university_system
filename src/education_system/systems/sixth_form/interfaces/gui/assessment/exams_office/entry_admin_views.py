"""Exam Entries tabs: entry codes & components, deadlines & fees, amendments."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox

from education_system.systems.sixth_form.domain.assessment.exam_entries.exam_entries import (
    EXAM_BOARDS,
    SEASONS,
)
from education_system.systems.sixth_form.domain.assessment.exams_office import entry_admin
from education_system.systems.sixth_form.interfaces.gui.assessment.exams_office.exams_widgets import (
    ERROR_FG,
    FormField,
    SeriesBar,
    clear,
    default_year,
    form_dialog,
    money,
    run_action,
    selected_id,
    student_choices,
    student_from_label,
    table,
    text_window,
)

logger = logging.getLogger(__name__)


def _qual_types() -> list[str]:
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        grade_scales,
    )
    return ["", *grade_scales.QUALIFICATION_TYPES]


def _subjects() -> list[str]:
    try:
        from education_system.systems.sixth_form.domain.academics.subjects import (
            subjects as _subjects_mod,
        )
        return _subjects_mod.get_active_names()
    except Exception:
        logger.exception("Could not load subjects")
        return []


# ── Entry codes & components ────────────────────────────────────────

def build_components_tab(gui, parent: ttk.Frame) -> None:
    filt = ttk.Frame(parent)
    filt.pack(fill="x", pady=(0, 6))
    board_var = tk.StringVar()
    ttk.Label(filt, text="Board:").pack(side="left")
    ttk.Combobox(filt, textvariable=board_var, values=["", *EXAM_BOARDS],
                 state="readonly", width=18).pack(side="left", padx=(4, 10))
    actions = ttk.Frame(parent)
    actions.pack(fill="x", pady=(0, 6))
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)
    state: dict = {}

    fields = [
        FormField("exam_board", "Board", "readonly", EXAM_BOARDS),
        FormField("entry_code", "Entry (qualification) code"),
        FormField("entry_title", "Entry title"),
        FormField("qualification_type", "Qualification type", "readonly", _qual_types()),
        FormField("component_code", "Component code"),
        FormField("component_title", "Component title"),
        FormField("duration_minutes", "Duration (minutes)"),
        FormField("entry_fee", "Entry fee per component (£)"),
        FormField("is_active", "Active", "check"),
        FormField("notes", "Notes"),
    ]

    def refresh() -> None:
        clear(holder)
        try:
            rows = entry_admin.list_components(exam_board=board_var.get() or None)
        except ValueError as e:
            ttk.Label(holder, text=str(e), foreground=ERROR_FG).pack(anchor="w")
            return
        state["rows"] = {c.component_id: c for c in rows}
        state["tree"] = table(holder, [("Board", 120), ("Entry code", 90), ("Entry title", 180),
                                       ("Qual. type", 120), ("Component", 100),
                                       ("Component title", 200), ("Mins", 50), ("Fee", 70),
                                       ("Active", 50)],
                              [(c.exam_board, c.entry_code, c.entry_title,
                                c.qualification_type, c.component_code, c.component_title,
                                c.duration_minutes, money(c.entry_fee),
                                "Yes" if c.is_active else "No") for c in rows],
                              iids=[c.component_id for c in rows])
        gui.status_var.set(f"{len(rows)} component(s) in the catalogue")

    def add() -> None:
        form_dialog(gui.root, "Add component", fields, entry_admin.save_component,
                    initial={"exam_board": board_var.get() or EXAM_BOARDS[0],
                             "is_active": True}, on_done=refresh)

    def edit() -> None:
        cid = selected_id(state["tree"], gui.root, "a component")
        if cid is None:
            return
        c = state["rows"][cid]
        form_dialog(gui.root, "Edit component", fields, entry_admin.save_component,
                    initial=vars(c), on_done=refresh)

    def delete() -> None:
        cid = selected_id(state["tree"], gui.root, "a component")
        if cid is None or not messagebox.askyesno("Delete", "Remove this component from "
                                                  "the catalogue?", parent=gui.root):
            return
        run_action(gui.root, lambda: entry_admin.delete_component(cid), then=refresh)

    def enter_option() -> None:
        labels, mapping = student_choices()
        form_dialog(
            gui.root, "Enter candidate for a whole option",
            [FormField("student", "Student", "combo", labels, 42),
             FormField("exam_board", "Board", "readonly", EXAM_BOARDS),
             FormField("entry_code", "Entry code"),
             FormField("subject", "Subject", "combo", _subjects()),
             FormField("season", "Season", "readonly", SEASONS),
             FormField("year", "Year"),
             FormField("candidate_no", "Candidate # (blank = from student record)"),
             FormField("tier", "Tier", "readonly", ["", "Higher", "Foundation"])],
            lambda v: messagebox.showinfo("Entered", "{} component entr(y/ies) created.".format(
                len(entry_admin.enter_for_option(
                    student_id=student_from_label(v["student"], mapping),
                    exam_board=v["exam_board"], entry_code=v["entry_code"],
                    subject=v["subject"], season=v["season"], year=v["year"],
                    candidate_no=v["candidate_no"] or None, tier=v["tier"] or None))),
                parent=gui.root),
            initial={"exam_board": board_var.get() or EXAM_BOARDS[0],
                     "season": SEASONS[0], "year": default_year()},
            note="Creates one exam entry for every active component of the entry code.")

    ttk.Button(filt, text="Show", command=refresh).pack(side="left")
    for label, cmd in (("Add component", add), ("Edit", edit), ("Delete", delete),
                       ("Enter candidate for option…", enter_option),
                       ("Refresh", refresh)):
        ttk.Button(actions, text=label, command=cmd).pack(side="left", padx=(0, 6))
    refresh()


# ── Deadlines & fees ────────────────────────────────────────────────

_DEADLINE_FIELDS = [
    FormField("exam_board", "Board", "readonly", EXAM_BOARDS),
    FormField("season", "Season", "readonly", SEASONS),
    FormField("year", "Year"),
    FormField("entry_deadline", "Entry deadline (YYYY-MM-DD)"),
    FormField("final_late_deadline", "Final late deadline"),
    FormField("late_fee", "Late fee per entry (£)"),
    FormField("very_late_fee", "Very late fee per entry (£)"),
    FormField("amendment_deadline", "Amendment deadline"),
    FormField("amendment_fee", "Amendment fee (£)"),
    FormField("withdrawal_deadline", "Withdrawal deadline"),
    FormField("withdrawal_fee", "Withdrawal fee (£)"),
    FormField("notes", "Notes"),
]


def build_deadlines_tab(gui, parent: ttk.Frame) -> None:
    actions = ttk.Frame(parent)
    actions.pack(fill="x", pady=(0, 6))
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)
    calc_bar = ttk.LabelFrame(parent, text="Late-fee calculator", padding=6)
    calc_bar.pack(fill="x", pady=(8, 0))
    series = SeriesBar(calc_bar)
    state: dict = {}

    def refresh() -> None:
        clear(holder)
        rows = entry_admin.list_deadlines()
        state["rows"] = {d.deadline_id: d for d in rows}
        state["tree"] = table(holder, [("Board", 120), ("Series", 110), ("Entry", 90),
                                       ("Final late", 90), ("Late £", 60),
                                       ("Very late £", 70), ("Amend by", 90),
                                       ("Amend £", 60), ("Withdraw by", 90),
                                       ("Withdraw £", 70)],
                              [(d.exam_board, f"{d.season} {d.year}", d.entry_deadline,
                                d.final_late_deadline, money(d.late_fee),
                                money(d.very_late_fee), d.amendment_deadline,
                                money(d.amendment_fee), d.withdrawal_deadline,
                                money(d.withdrawal_fee)) for d in rows],
                              iids=[d.deadline_id for d in rows], height=8)

    def add() -> None:
        form_dialog(gui.root, "Series deadlines & fees", _DEADLINE_FIELDS,
                    entry_admin.save_deadlines,
                    initial={"exam_board": EXAM_BOARDS[0], "season": SEASONS[0],
                             "year": default_year()}, on_done=refresh)

    def edit() -> None:
        did = selected_id(state["tree"], gui.root, "a series")
        if did is None:
            return
        form_dialog(gui.root, "Series deadlines & fees", _DEADLINE_FIELDS,
                    entry_admin.save_deadlines, initial=vars(state["rows"][did]),
                    on_done=refresh)

    def delete() -> None:
        did = selected_id(state["tree"], gui.root, "a series")
        if did is not None and messagebox.askyesno("Delete", "Delete these deadlines?",
                                                   parent=gui.root):
            run_action(gui.root, lambda: entry_admin.delete_deadlines(did), then=refresh)

    def calendar() -> None:
        items = entry_admin.deadline_calendar()
        lines = ["ENTRY DEADLINE CALENDAR", ""]
        for i in items:
            when = (f"in {i.days_left} day(s)" if i.days_left >= 0
                    else f"{-i.days_left} day(s) ago")
            fee = f"  (fee after: £{i.fee:.2f})" if i.fee else ""
            lines.append(f"{i.date}  {i.exam_board:<18} {i.season} {i.year}  "
                         f"{i.kind:<20} {when}{fee}")
        if not items:
            lines.append("(no deadlines recorded)")
        text_window(gui.root, "Entry deadline calendar", "\n".join(lines) + "\n",
                    filename="entry_deadlines.txt")

    def calculate() -> None:
        try:
            season, year = series.get()
            lines_ = entry_admin.late_fee_calculator(season=season, year=year)
        except ValueError as e:
            messagebox.showerror("Cannot calculate", str(e), parent=gui.root)
            return
        names = {}
        try:
            from education_system.systems.sixth_form.domain.assessment.exams_office import store
            names = store.student_names()
        except Exception:
            logger.exception("names")
        out = [f"LATE / AMENDMENT / WITHDRAWAL FEES — {season} {year}", ""]
        total = 0.0
        for f in lines_:
            total += f.fee
            out.append(f"{f.on_date}  {f.student_id:<10} {names.get(f.student_id, ''):<24} "
                       f"{(f.paper_code or ''):<10} {f.what:<18} £{f.fee:8.2f}")
        out += ["", f"TOTAL  £{total:.2f}  ({len(lines_)} charge(s))"]
        text_window(gui.root, "Late-fee calculator", "\n".join(out) + "\n",
                    filename=f"late_fees_{season}{year}.txt")

    ttk.Button(calc_bar, text="Calculate fees owed", command=calculate).pack(side="left")
    for label, cmd in (("Add / update series", add), ("Edit", edit), ("Delete", delete),
                       ("Deadline calendar…", calendar), ("Refresh", refresh)):
        ttk.Button(actions, text=label, command=cmd).pack(side="left", padx=(0, 6))
    refresh()


# ── Amendment history ───────────────────────────────────────────────

def build_amendments_tab(gui, parent: ttk.Frame) -> None:
    filt = ttk.Frame(parent)
    filt.pack(fill="x", pady=(0, 6))
    sid_var = tk.StringVar()
    action_var = tk.StringVar()
    ttk.Label(filt, text="Student:").pack(side="left")
    ttk.Entry(filt, textvariable=sid_var, width=12).pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="Action:").pack(side="left")
    ttk.Combobox(filt, textvariable=action_var, values=["", *entry_admin.AMENDMENT_ACTIONS],
                 state="readonly", width=12).pack(side="left", padx=(4, 10))
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)

    def refresh() -> None:
        clear(holder)
        rows = entry_admin.list_amendments(student_id=sid_var.get().strip() or None,
                                           action=action_var.get() or None)
        table(holder, [("When", 130), ("Entry", 50), ("Student", 80), ("Board", 110),
                       ("Paper", 90), ("Series", 100), ("Action", 80), ("Fee", 60),
                       ("Changes", 380), ("Reason", 140), ("By", 80)],
              [(a.amended_at, a.entry_id, a.student_id, a.exam_board, a.paper_code,
                f"{a.season or ''} {a.year or ''}", a.action, money(a.fee), a.changes,
                a.reason, a.amended_by) for a in rows], height=18)
        gui.status_var.set(f"{len(rows)} amendment record(s)")

    ttk.Button(filt, text="Show", command=refresh).pack(side="left")
    refresh()
