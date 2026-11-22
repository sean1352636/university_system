"""Exams Office tab: invigilator pool, allocations, cover check, printable rota."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox

from education_system.systems.sixth_form.domain.assessment.exams_office import invigilation
from education_system.systems.sixth_form.interfaces.gui.assessment.exams_office.exams_widgets import (
    guarded,
    ERROR_FG,
    FormField,
    clear,
    form_dialog,
    run_action,
    selected_id,
    table,
    text_window,
    yn,
)

logger = logging.getLogger(__name__)

_INV_FIELDS = [
    FormField("name", "Name"),
    FormField("staff_id", "Staff ID (optional)"),
    FormField("email", "Email"),
    FormField("phone", "Phone"),
    FormField("trained_on", "Trained on (YYYY-MM-DD)"),
    FormField("can_read_scribe", "Trained reader / scribe", "check"),
    FormField("is_active", "Active", "check"),
    FormField("notes", "Notes"),
]


def build_tab(gui, parent: ttk.Frame) -> None:
    nb = ttk.Notebook(parent)
    nb.pack(fill="both", expand=True)
    pool_tab = ttk.Frame(nb, padding=6)
    rota_tab = ttk.Frame(nb, padding=6)
    nb.add(pool_tab, text="Invigilator pool")
    nb.add(rota_tab, text="Rota & cover")
    state: dict = {}

    # Pool -----------------------------------------------------------
    actions = ttk.Frame(pool_tab)
    actions.pack(fill="x", pady=(0, 6))
    holder = ttk.Frame(pool_tab)
    holder.pack(fill="both", expand=True)

    @guarded(gui.root)
    def refresh_pool() -> None:
        clear(holder)
        rows = invigilation.list_invigilators(active_only=False)
        state["pool"] = {i.invigilator_id: i for i in rows}
        state["ptree"] = table(holder, [("Name", 180), ("Staff ID", 80), ("Email", 200),
                                        ("Phone", 110), ("Trained", 90),
                                        ("Reader/scribe", 90), ("Active", 60),
                                        ("Notes", 200)],
                               [(i.name, i.staff_id, i.email, i.phone, i.trained_on,
                                 yn(i.can_read_scribe), yn(i.is_active), i.notes)
                                for i in rows], iids=[i.invigilator_id for i in rows])

    @guarded(gui.root)
    def add() -> None:
        form_dialog(gui.root, "Add invigilator", _INV_FIELDS, invigilation.save_invigilator,
                    initial={"is_active": True}, on_done=refresh_pool)

    @guarded(gui.root)
    def add_staff() -> None:
        from education_system.systems.sixth_form.domain.staff import staff as _staff
        people = _staff.list_staff(active_only=True)
        labels = [f"{s.staff_id} — {s.first_name} {s.last_name}" for s in people]
        form_dialog(gui.root, "Add from staff directory",
                    [FormField("who", "Staff member", "readonly", labels, 42)],
                    lambda v: invigilation.add_from_staff(v["who"].split(" — ")[0]),
                    on_done=refresh_pool)

    @guarded(gui.root)
    def edit() -> None:
        iid = selected_id(state["ptree"], gui.root, "an invigilator")
        if iid is None:
            return
        form_dialog(gui.root, "Edit invigilator", _INV_FIELDS,
                    lambda v: invigilation.save_invigilator(v, invigilator_id=iid),
                    initial=vars(state["pool"][iid]), on_done=refresh_pool)

    @guarded(gui.root)
    def delete() -> None:
        iid = selected_id(state["ptree"], gui.root, "an invigilator")
        if iid is not None and messagebox.askyesno(
                "Delete", "Delete this invigilator and all their allocations? "
                "(Untick Active instead to keep the history.)", parent=gui.root):
            run_action(gui.root, lambda: invigilation.delete_invigilator(iid),
                       then=refresh_pool)

    for label, cmd in (("Add", add), ("Add from staff…", add_staff), ("Edit", edit),
                       ("Delete", delete), ("Refresh", refresh_pool)):
        ttk.Button(actions, text=label, command=cmd).pack(side="left", padx=(0, 6))

    # Rota -----------------------------------------------------------
    bar = ttk.Frame(rota_tab)
    bar.pack(fill="x", pady=(0, 6))
    from_var, to_var = tk.StringVar(), tk.StringVar()
    ttk.Label(bar, text="From:").pack(side="left")
    ttk.Entry(bar, textvariable=from_var, width=11).pack(side="left", padx=(4, 8))
    ttk.Label(bar, text="To:").pack(side="left")
    ttk.Entry(bar, textvariable=to_var, width=11).pack(side="left", padx=(4, 8))
    r_actions = ttk.Frame(rota_tab)
    r_actions.pack(fill="x", pady=(0, 6))
    r_holder = ttk.Frame(rota_tab)
    r_holder.pack(fill="both", expand=True)
    r_info = ttk.Label(rota_tab, text="", foreground=ERROR_FG, wraplength=900,
                       justify="left")
    r_info.pack(anchor="w", pady=(4, 0))

    @guarded(gui.root)
    def refresh_rota() -> None:
        clear(r_holder)
        try:
            rows = invigilation.cover_report(date_from=from_var.get().strip() or None,
                                             date_to=to_var.get().strip() or None)
            clashes = invigilation.conflicts(date_from=from_var.get().strip() or None,
                                             date_to=to_var.get().strip() or None)
        except ValueError as e:
            ttk.Label(r_holder, text=str(e), foreground=ERROR_FG).pack(anchor="w")
            return
        state["cover"] = {c.sitting.sitting_id: c for c in rows}
        state["rtree"] = table(r_holder, [("Date", 90), ("Time", 100), ("Room", 100),
                                          ("Paper", 100), ("Cands", 50), ("Need", 45),
                                          ("Have", 45), ("Rdr/scr need", 80),
                                          ("Rdr/scr have", 80), ("Status", 80),
                                          ("Invigilators", 300)],
                               [(c.sitting.date,
                                 f"{c.sitting.start_time}-"
                                 f"{c.sitting.extended_end_time or c.sitting.end_time or ''}",
                                 c.sitting.room, c.sitting.paper_code, c.candidates,
                                 c.required, c.allocated, c.facilitators_needed,
                                 c.facilitators_allocated, "OK" if c.ok else "SHORT",
                                 ", ".join(f"{a.invigilator_name} ({a.role})"
                                           for a in c.allocations))
                                for c in rows], iids=[c.sitting.sitting_id for c in rows])
        r_info.configure(text="Double-booked: " + "; ".join(
            f"{k.invigilator_name}: {k.first.label} / {k.second.label}" for k in clashes)
            if clashes else "")
        short = sum(1 for c in rows if not c.ok)
        gui.status_var.set(f"{len(rows)} sitting(s), {short} short of cover, "
                           f"{len(clashes)} conflict(s)")

    @guarded(gui.root)
    def allocate() -> None:
        sid = selected_id(state["rtree"], gui.root, "a sitting")
        if sid is None:
            return
        pool = invigilation.list_invigilators()
        labels = [f"{i.invigilator_id}: {i.name}" for i in pool]
        from education_system.systems.sixth_form.domain.academics.attendance import (
            attendance_exams as _exams,
        )
        cands = ["", *[c.student_id for c in _exams.list_candidates(sid)
                       if c.reader or c.scribe]]
        form_dialog(gui.root, "Allocate invigilator",
                    [FormField("inv", "Invigilator", "readonly", labels, 40),
                     FormField("role", "Role", "readonly", invigilation.ROLES),
                     FormField("student_id", "For candidate (reader/scribe)", "readonly",
                               cands),
                     FormField("notes", "Notes")],
                    lambda v: invigilation.allocate(
                        sid, int(v["inv"].split(":")[0]) if v["inv"] else 0,
                        role=v["role"], student_id=v["student_id"] or None,
                        notes=v["notes"]),
                    initial={"role": "Invigilator"}, on_done=refresh_rota)

    @guarded(gui.root)
    def unallocate() -> None:
        sid = selected_id(state["rtree"], gui.root, "a sitting")
        if sid is None:
            return
        allocs = state["cover"][sid].allocations
        if not allocs:
            messagebox.showinfo("Nobody allocated", "No invigilators on this sitting.",
                                parent=gui.root)
            return
        labels = [f"{a.allocation_id}: {a.invigilator_name} ({a.role})" for a in allocs]
        form_dialog(gui.root, "Remove invigilator",
                    [FormField("a", "Allocation", "readonly", labels, 40)],
                    lambda v: invigilation.unallocate(int(v["a"].split(":")[0])),
                    on_done=refresh_rota)

    @guarded(gui.root)
    def rota() -> None:
        text_window(gui.root, "Invigilation rota",
                    invigilation.printable_rota(date_from=from_var.get().strip() or None,
                                                date_to=to_var.get().strip() or None),
                    filename="invigilation_rota.txt")

    ttk.Button(bar, text="Show", command=refresh_rota).pack(side="left")
    ttk.Label(bar, text=f"Ratio: 1 invigilator per "
                        f"{invigilation.CANDIDATES_PER_INVIGILATOR} candidates",
              foreground="#555").pack(side="left", padx=12)
    for label, cmd in (("Allocate…", allocate), ("Remove…", unallocate),
                       ("Printable rota…", rota)):
        ttk.Button(r_actions, text=label, command=cmd).pack(side="left", padx=(0, 6))

    refresh_pool()
    refresh_rota()
