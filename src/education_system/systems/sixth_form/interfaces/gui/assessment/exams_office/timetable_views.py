"""Exams Office tab: board timetable, candidate clashes, contingency days."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox, simpledialog

from education_system.systems.sixth_form.domain.assessment.exam_entries.exam_entries import (
    EXAM_BOARDS,
    SEASONS,
)
from education_system.systems.sixth_form.domain.assessment.exams_office import timetable
from education_system.systems.sixth_form.domain.assessment.exams_office.boards import SESSIONS
from education_system.systems.sixth_form.interfaces.gui.assessment.exams_office.exams_widgets import (
    guarded,
    ERROR_FG,
    FormField,
    SeriesBar,
    clear,
    form_dialog,
    run_action,
    selected_id,
    table,
    text_window,
)

logger = logging.getLogger(__name__)

_PAPER_FIELDS = [
    FormField("exam_board", "Board", "readonly", EXAM_BOARDS),
    FormField("season", "Season", "readonly", SEASONS),
    FormField("year", "Year"),
    FormField("component_code", "Component (paper) code"),
    FormField("entry_code", "Entry code (blank = from catalogue)"),
    FormField("title", "Title"),
    FormField("exam_date", "Date (YYYY-MM-DD)"),
    FormField("session", "Session", "readonly", SESSIONS),
    FormField("start_time", "Start time (blank = session start)"),
    FormField("duration_minutes", "Duration (minutes, blank = catalogue)"),
    FormField("notes", "Notes"),
]


def build_tab(gui, parent: ttk.Frame) -> None:
    top = ttk.Frame(parent)
    top.pack(fill="x", pady=(0, 6))
    nb = ttk.Notebook(parent)
    nb.pack(fill="both", expand=True)
    papers_tab = ttk.Frame(nb, padding=6)
    clash_tab = ttk.Frame(nb, padding=6)
    cont_tab = ttk.Frame(nb, padding=6)
    nb.add(papers_tab, text="Timetable")
    nb.add(clash_tab, text="Candidate clashes")
    nb.add(cont_tab, text="Contingency days")
    state: dict = {}

    @guarded(gui.root)
    def refresh_all() -> None:
        refresh_papers()
        refresh_clashes()
        refresh_contingency()

    series = SeriesBar(top, on_change=refresh_all)

    # Timetable ------------------------------------------------------
    p_actions = ttk.Frame(papers_tab)
    p_actions.pack(fill="x", pady=(0, 6))
    p_holder = ttk.Frame(papers_tab)
    p_holder.pack(fill="both", expand=True)
    p_info = ttk.Label(papers_tab, text="", foreground=ERROR_FG, wraplength=900,
                       justify="left")
    p_info.pack(anchor="w", pady=(4, 0))

    @guarded(gui.root)
    def refresh_papers() -> None:
        clear(p_holder)
        try:
            season, year = series.get()
            rows = timetable.list_papers(season=season, year=year)
            missing = timetable.unscheduled_entries(season, year)
        except ValueError as e:
            ttk.Label(p_holder, text=str(e), foreground=ERROR_FG).pack(anchor="w")
            return
        state["papers"] = {p.timetable_id: p for p in rows}
        state["ptree"] = table(p_holder, [("Date", 90), ("Sess", 45), ("Start", 50),
                                          ("End", 50), ("Board", 120), ("Entry", 70),
                                          ("Component", 100), ("Title", 220),
                                          ("Mins", 50), ("Candidates", 80)],
                               [(p.exam_date, p.session, p.start_time, p.end_time,
                                 p.exam_board, p.entry_code, p.component_code, p.title,
                                 p.duration_minutes, len(timetable.entries_for_paper(p)))
                                for p in rows], iids=[p.timetable_id for p in rows])
        p_info.configure(text=("Entered but not timetabled: " + ", ".join(
            f"{c} ({b}, {n})" for b, c, n in missing)) if missing else "")
        gui.status_var.set(f"{len(rows)} paper(s) timetabled")

    @guarded(gui.root)
    def add_paper() -> None:
        season, year = series.get()
        form_dialog(gui.root, "Timetable a paper", _PAPER_FIELDS, timetable.save_paper,
                    initial={"exam_board": EXAM_BOARDS[0], "season": season,
                             "year": year, "session": "AM"}, on_done=refresh_all)

    @guarded(gui.root)
    def edit_paper() -> None:
        tid = selected_id(state["ptree"], gui.root, "a paper")
        if tid is None:
            return
        form_dialog(gui.root, "Edit timetabled paper", _PAPER_FIELDS,
                    lambda v: timetable.save_paper(v, timetable_id=tid),
                    initial=vars(state["papers"][tid]), on_done=refresh_all)

    @guarded(gui.root)
    def delete_paper() -> None:
        tid = selected_id(state["ptree"], gui.root, "a paper")
        if tid is not None and messagebox.askyesno("Delete", "Remove this paper from the "
                                                   "timetable?", parent=gui.root):
            run_action(gui.root, lambda: timetable.delete_paper(tid), then=refresh_all)

    @guarded(gui.root)
    def make_sitting() -> None:
        tid = selected_id(state["ptree"], gui.root, "a paper")
        if tid is None:
            return
        room = simpledialog.askstring("Room", "Room for this sitting:", parent=gui.root)
        if not room:
            return
        run_action(gui.root, lambda: timetable.create_sitting(tid, room=room),
                   done="Sitting created and filled from the entries, with access "
                        "arrangements applied. See the Sittings & seating tab.")

    @guarded(gui.root)
    def print_timetable() -> None:
        season, year = series.get()
        lines = [f"EXAM TIMETABLE — {season} {year}", ""]
        for p in timetable.list_papers(season=season, year=year):
            lines.append(f"{p.exam_date} {p.session} {p.start_time}-{p.end_time}  "
                         f"{p.exam_board:<18} {p.component_code:<10} {p.title or ''}")
        for c in timetable.list_contingency(season=season, year=year):
            lines.append(f"{c.exam_date} {c.session or 'all day'}  CONTINGENCY DAY")
        text_window(gui.root, "Exam timetable", "\n".join(lines) + "\n",
                    filename=f"timetable_{season}{year}.txt")

    for label, cmd in (("Add paper", add_paper), ("Edit", edit_paper),
                       ("Delete", delete_paper), ("Create sitting…", make_sitting),
                       ("Print timetable…", print_timetable)):
        ttk.Button(p_actions, text=label, command=cmd).pack(side="left", padx=(0, 6))

    # Clashes --------------------------------------------------------
    c_actions = ttk.Frame(clash_tab)
    c_actions.pack(fill="x", pady=(0, 6))
    unresolved_var = tk.BooleanVar(value=False)
    c_holder = ttk.Frame(clash_tab)
    c_holder.pack(fill="both", expand=True)

    @guarded(gui.root)
    def refresh_clashes() -> None:
        clear(c_holder)
        try:
            season, year = series.get()
            rows = timetable.candidate_clashes(season, year,
                                               unresolved_only=unresolved_var.get())
        except ValueError as e:
            ttk.Label(c_holder, text=str(e), foreground=ERROR_FG).pack(anchor="w")
            return
        state["clashes"] = rows
        state["ctree"] = table(c_holder, [("Date", 90), ("Sess", 45), ("Student", 80),
                                          ("Name", 160), ("Papers", 220),
                                          ("Total mins (incl. extra)", 140),
                                          ("Resolution", 300), ("Supervisor", 120)],
                               [(c.exam_date, c.session, c.student_id, c.full_name,
                                 ", ".join(p.component_code for p in c.papers),
                                 f"{c.total_minutes}" + (" — too long for one session"
                                                         if c.needs_move else ""),
                                 c.resolution.method if c.resolution else "UNRESOLVED",
                                 c.resolution.supervisor if c.resolution else "")
                                for c in rows], iids=list(range(len(rows))))
        open_n = sum(1 for c in rows if not c.resolved)
        gui.status_var.set(f"{len(rows)} clash(es), {open_n} unresolved")

    @guarded(gui.root)
    def resolve() -> None:
        idx = selected_id(state["ctree"], gui.root, "a clash")
        if idx is None:
            return
        c = state["clashes"][idx]
        season, year = series.get()
        papers = {f"{p.timetable_id}: {p.component_code}": p.timetable_id for p in c.papers}
        r = c.resolution

        def submit(v: dict) -> None:
            v = dict(v)
            moved = v.pop("moved", "")
            v["moved_timetable_id"] = papers.get(moved)
            timetable.resolve_clash({**v, "student_id": c.student_id, "season": season,
                                     "year": year, "exam_date": c.exam_date,
                                     "session": c.session})

        form_dialog(gui.root, f"Resolve clash — {c.student_id} {c.exam_date} {c.session}",
                    [FormField("method", "Method", "readonly", timetable.RESOLUTION_METHODS, 52),
                     FormField("moved", "Paper moved", "readonly", ["", *papers]),
                     FormField("moved_to_date", "Moved to date"),
                     FormField("moved_to_session", "Moved to session", "readonly",
                               ["", *SESSIONS]),
                     FormField("moved_to_time", "Moved to time"),
                     FormField("supervisor", "Supervisor"),
                     FormField("notes", "Notes", "text")],
                    submit, on_done=refresh_clashes,
                    initial=vars(r) if r else {"moved_to_date": c.exam_date,
                                               "moved_to_session": "PM"},
                    note=f"Papers: {', '.join(p.label for p in c.papers)}. "
                         f"Total time incl. extra time: {c.total_minutes} min.")

    @guarded(gui.root)
    def unresolve() -> None:
        idx = selected_id(state["ctree"], gui.root, "a clash")
        if idx is None:
            return
        r = state["clashes"][idx].resolution
        if r and messagebox.askyesno("Remove", "Remove this resolution?", parent=gui.root):
            run_action(gui.root, lambda: timetable.delete_resolution(r.resolution_id),
                       then=refresh_clashes)

    ttk.Button(c_actions, text="Record resolution…", command=resolve).pack(side="left")
    ttk.Button(c_actions, text="Remove resolution", command=unresolve).pack(side="left",
                                                                            padx=6)
    ttk.Checkbutton(c_actions, text="Unresolved only", variable=unresolved_var,
                    command=refresh_clashes).pack(side="left", padx=12)

    # Contingency ----------------------------------------------------
    k_actions = ttk.Frame(cont_tab)
    k_actions.pack(fill="x", pady=(0, 6))
    k_holder = ttk.Frame(cont_tab)
    k_holder.pack(fill="both", expand=True)

    @guarded(gui.root)
    def refresh_contingency() -> None:
        clear(k_holder)
        try:
            season, year = series.get()
        except ValueError:
            return
        rows = timetable.list_contingency(season=season, year=year)
        state["ktree"] = table(k_holder, [("Date", 100), ("Session", 80), ("Notes", 400)],
                               [(c.exam_date, c.session or "All day", c.notes) for c in rows],
                               iids=[c.contingency_id for c in rows], height=8)

    @guarded(gui.root)
    def add_contingency() -> None:
        season, year = series.get()
        form_dialog(gui.root, "Contingency day",
                    [FormField("exam_date", "Date"),
                     FormField("session", "Session (blank = all day)", "readonly",
                               ["", *SESSIONS]),
                     FormField("notes", "Notes")],
                    lambda v: timetable.save_contingency({**v, "season": season,
                                                          "year": year}),
                    on_done=refresh_contingency,
                    note="JCQ keeps one contingency day per series free of exams.")

    @guarded(gui.root)
    def delete_contingency() -> None:
        cid = selected_id(state["ktree"], gui.root, "a contingency day")
        if cid is not None:
            run_action(gui.root, lambda: timetable.delete_contingency(cid),
                       then=refresh_contingency)

    ttk.Button(k_actions, text="Add contingency day", command=add_contingency).pack(side="left")
    ttk.Button(k_actions, text="Delete", command=delete_contingency).pack(side="left", padx=6)

    refresh_all()
