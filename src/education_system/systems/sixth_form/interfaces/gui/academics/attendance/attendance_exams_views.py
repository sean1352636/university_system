"""GUI for exam-room registers: sittings, seating plans, marking, sign-off.

Until now these were only reachable from the off-timetable CLI. The
tab is embedded in the Exams Office window; :func:`open_window` also
shows it on its own.
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date, timedelta
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox, simpledialog

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance_exams as exams,
)
from education_system.systems.sixth_form.interfaces.gui.assessment.exams_office.exams_widgets import (
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

_SITTING_FIELDS = [
    FormField("paper_code", "Paper code"),
    FormField("paper_title", "Paper title"),
    FormField("subject", "Subject"),
    FormField("exam_board", "Board"),
    FormField("date", "Date (YYYY-MM-DD)"),
    FormField("start_time", "Start (HH:MM)"),
    FormField("end_time", "End (HH:MM)"),
    FormField("room", "Room"),
    FormField("series", "Series", "readonly", ["", "Summer", "January", "November"]),
    FormField("year", "Year"),
    FormField("notes", "Notes"),
]


def _actor() -> str | None:
    try:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        return access.current().username or None
    except Exception:
        return None


def seating_plan_text(sitting_id: int) -> str:
    return exams.seating_plan_text(sitting_id)


def build_tab(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 6))
    from_var = tk.StringVar(value=(_date.today() - timedelta(days=30)).isoformat())
    to_var = tk.StringVar()
    ttk.Label(bar, text="From:").pack(side="left")
    ttk.Entry(bar, textvariable=from_var, width=11).pack(side="left", padx=(4, 8))
    ttk.Label(bar, text="To:").pack(side="left")
    ttk.Entry(bar, textvariable=to_var, width=11).pack(side="left", padx=(4, 8))

    s_actions = ttk.Frame(parent)
    s_actions.pack(fill="x", pady=(0, 4))
    c_actions = ttk.Frame(parent)
    c_actions.pack(fill="x", pady=(0, 4))
    panes = ttk.PanedWindow(parent, orient="vertical")
    panes.pack(fill="both", expand=True)
    s_holder = ttk.Frame(panes)
    c_holder = ttk.Frame(panes)
    panes.add(s_holder, weight=1)
    panes.add(c_holder, weight=1)
    state: dict = {"sitting": None}

    def refresh() -> None:
        clear(s_holder)
        try:
            rows = exams.list_sittings(date_from=from_var.get().strip() or None,
                                       date_to=to_var.get().strip() or None)
        except ValueError as e:
            ttk.Label(s_holder, text=str(e), foreground=ERROR_FG).pack(anchor="w")
            return
        state["stree"] = tree = table(
            s_holder, [("Date", 90), ("Start", 50), ("End", 50), ("Latest finish", 85),
                       ("Paper", 100), ("Title", 180), ("Room", 90), ("State", 80),
                       ("Invigilator", 200)],
            [(s.date, s.start_time, s.end_time, s.extended_end_time, s.paper_code,
              s.paper_title, s.room, s.state, s.invigilator) for s in rows],
            iids=[s.sitting_id for s in rows], height=8)
        tree.bind("<<TreeviewSelect>>", lambda _e: show_candidates())
        if state["sitting"] and str(state["sitting"]) in tree.get_children():
            tree.selection_set(str(state["sitting"]))
        gui.status_var.set(f"{len(rows)} exam sitting(s)")

    def show_candidates() -> None:
        clear(c_holder)
        sel = state["stree"].selection()
        if not sel:
            return
        sid = int(sel[0])
        state["sitting"] = sid
        summ = exams.summary(sid)
        ttk.Label(c_holder, text=(f"{summ.sitting.label} — entered {summ.entered}, sat "
                                  f"{summ.sat}, absent {summ.absent}, unmarked "
                                  f"{summ.unmarked}"), font=("", 10, "bold")
                  ).pack(anchor="w", pady=(4, 2))
        rows = exams.list_candidates(sid, with_names=True)
        state["ctree"] = table(
            c_holder, [("Seat", 45), ("Cand #", 60), ("Student", 80), ("Name", 160),
                       ("State", 80), ("Arrived", 60), ("Late", 45), ("Extra %", 55),
                       ("Finish", 55), ("Rdr", 35), ("Scr", 35), ("WP", 35),
                       ("Sep. room", 60), ("Rest", 40), ("Flags", 220)],
            [(c.seat, c.candidate_no, c.student_id, c.full_name, c.state or "unmarked",
              c.arrival_time, c.minutes_late, c.extra_time_pct or "", c.finish_time,
              yn(c.reader), yn(c.scribe), yn(c.word_processor), yn(c.separate_room),
              yn(c.rest_breaks), c.arrangement_flags) for c in rows],
            iids=[c.student_id for c in rows], height=10)

    def need_sitting() -> int | None:
        return selected_id(state["stree"], gui.root, "a sitting")

    def need_candidate() -> str | None:
        tree = state.get("ctree")
        sel = tree.selection() if tree else ()
        if not sel:
            messagebox.showinfo("No selection", "Pick a candidate first.", parent=gui.root)
            return None
        return sel[0]

    def after() -> None:
        refresh()
        show_candidates()

    def new() -> None:
        form_dialog(gui.root, "New exam sitting", _SITTING_FIELDS, exams.create_sitting,
                    initial={"date": _date.today().isoformat(), "start_time": "09:00"},
                    on_done=refresh)

    def populate() -> None:
        sid = need_sitting()
        if sid is not None:
            run_action(gui.root, lambda: exams.populate_from_entries(sid),
                       done="{out} candidate(s) added from the exam entries.", then=after)

    def apply_access() -> None:
        sid = need_sitting()
        if sid is not None:
            run_action(gui.root, lambda: exams.apply_access_arrangements(sid),
                       done="{out} candidate(s) have access arrangements.", then=after)

    def plan() -> None:
        sid = need_sitting()
        if sid is not None:
            text_window(gui.root, "Seating plan", seating_plan_text(sid),
                        filename=f"seating_plan_{sid}.txt")

    def mark_all() -> None:
        sid = need_sitting()
        if sid is not None:
            run_action(gui.root, lambda: exams.mark_all_present(sid, actor=_actor()),
                       done="{out} candidate(s) marked present.", then=after)

    def sign() -> None:
        sid = need_sitting()
        if sid is None:
            return
        who = simpledialog.askstring("Sign off", "Invigilator signing the register:",
                                     parent=gui.root)
        if who:
            run_action(gui.root, lambda: exams.sign_off(sid, invigilator=who), then=after)

    def reopen() -> None:
        sid = need_sitting()
        if sid is None:
            return
        why = simpledialog.askstring("Reopen", "Reason for reopening:", parent=gui.root)
        if why:
            run_action(gui.root, lambda: exams.reopen(sid, reason=why, actor=_actor()),
                       then=after)

    def delete() -> None:
        sid = need_sitting()
        if sid is not None and messagebox.askyesno("Delete", "Delete this sitting?",
                                                   parent=gui.root):
            run_action(gui.root, lambda: exams.delete_sitting(sid), then=refresh)

    def report(kind: str) -> None:
        f, t = from_var.get().strip() or None, to_var.get().strip() or None
        if kind == "absent":
            rows = exams.absentees(date_from=f, date_to=t)
            lines = ["ABSENT CANDIDATES", ""] + [
                f"{s.date} {s.paper_code:<10} {c.candidate_no or '':<6} "
                f"{c.full_name or c.student_id:<28} {c.absence_reason or ''}" for s, c in rows]
        elif kind == "report":
            rows = exams.reportable(date_from=f, date_to=t)
            lines = ["REPORTABLE TO THE BOARD (very late / removed)", ""] + [
                f"{s.date} {s.paper_code:<10} {c.candidate_no or '':<6} "
                f"{c.full_name or c.student_id:<28} {c.state} "
                f"{c.minutes_late or ''}" for s, c in rows]
        else:
            rows = exams.unsigned_registers(date_from=f, date_to=t)
            lines = ["REGISTERS NOT SIGNED OFF", ""] + [s.label for s in rows]
        text_window(gui.root, lines[0].title(), "\n".join(lines) + "\n",
                    filename=f"exam_{kind}.txt")

    def mark() -> None:
        sid, stu = need_sitting(), need_candidate()
        if sid is None or stu is None:
            return
        form_dialog(gui.root, f"Mark {stu}",
                    [FormField("state", "State", "readonly", exams.CANDIDATE_STATES),
                     FormField("arrival_time", "Arrival time (HH:MM)"),
                     FormField("departure_time", "Departure time"),
                     FormField("absence_reason", "Absence reason", "readonly",
                               ["", *exams.ABSENCE_REASONS]),
                     FormField("notes", "Notes")],
                    lambda v: exams.mark_candidate(sid, stu, v["state"],
                                                   arrival_time=v["arrival_time"] or None,
                                                   departure_time=v["departure_time"] or None,
                                                   absence_reason=v["absence_reason"] or None,
                                                   notes=v["notes"] or None, actor=_actor()),
                    initial={"state": exams.PRESENT}, on_done=after)

    def seat() -> None:
        sid, stu = need_sitting(), need_candidate()
        if sid is None or stu is None:
            return
        new_seat = simpledialog.askstring("Seat", f"New seat for {stu}:", parent=gui.root)
        if new_seat:
            run_action(gui.root, lambda: exams.seat_candidate(sid, stu, new_seat), then=after)

    def add_candidate() -> None:
        sid = need_sitting()
        if sid is None:
            return
        from education_system.systems.sixth_form.interfaces.gui.assessment.exams_office.exams_widgets import (
            student_choices, student_from_label,
        )
        labels, mapping = student_choices()
        form_dialog(gui.root, "Add candidate",
                    [FormField("student", "Student", "combo", labels, 42),
                     FormField("seat", "Seat"), FormField("candidate_no", "Candidate #")],
                    lambda v: (exams.add_candidate(sid, student_from_label(v["student"], mapping),
                                                   seat=v["seat"] or None,
                                                   candidate_no=v["candidate_no"] or None),
                               exams.apply_access_arrangements(sid)),
                    on_done=after)

    def remove() -> None:
        sid, stu = need_sitting(), need_candidate()
        if sid is not None and stu is not None and messagebox.askyesno(
                "Remove", f"Remove {stu} from this sitting?", parent=gui.root):
            run_action(gui.root, lambda: exams.remove_candidate(sid, stu), then=after)

    def separate_room() -> None:
        sid = need_sitting()
        if sid is None:
            return
        flagged = [c.student_id for c in exams.list_candidates(sid) if c.separate_room]
        tree = state.get("ctree")
        chosen = list(tree.selection()) if tree and tree.selection() else flagged
        if not chosen:
            messagebox.showinfo("Nobody to move", "Select candidates, or none are flagged "
                                "for a separate room.", parent=gui.root)
            return
        room = simpledialog.askstring("Separate room",
                                      f"Move {len(chosen)} candidate(s) to which room?",
                                      parent=gui.root)
        if room:
            run_action(gui.root, lambda: exams.move_candidates_to_room(sid, chosen, room),
                       done="Moved. The new room's sitting is in the list.", then=after)

    ttk.Button(bar, text="Show", command=refresh).pack(side="left")
    for label, cmd in (("New sitting", new), ("Fill from entries", populate),
                       ("Apply access arrangements", apply_access),
                       ("Seating plan…", plan), ("Mark all present", mark_all),
                       ("Sign off…", sign), ("Reopen…", reopen), ("Delete", delete),
                       ("Absentees…", lambda: report("absent")),
                       ("Reportable…", lambda: report("report")),
                       ("Unsigned…", lambda: report("unsigned"))):
        ttk.Button(s_actions, text=label, command=cmd).pack(side="left", padx=(0, 4))
    for label, cmd in (("Mark candidate…", mark), ("Change seat…", seat),
                       ("Add candidate…", add_candidate), ("Remove candidate", remove),
                       ("Move to separate room…", separate_room)):
        ttk.Button(c_actions, text=label, command=cmd).pack(side="left", padx=(0, 4))
    refresh()


def open_window(gui) -> None:
    """Exam registers in their own window."""
    from education_system.platform.delivery.gui import window_sizing
    win = tk.Toplevel(gui.root)
    win.title("Exam Registers & Seating")
    window_sizing.fit(win, "1400x900", (1200, 800))
    frame = ttk.Frame(win, padding=8)
    frame.pack(fill="both", expand=True)

    class _Host:
        root = win
        status_var = gui.status_var
    build_tab(_Host, frame)
