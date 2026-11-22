"""Results Day tabs: release & embargo, qualification results, import, history."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox, simpledialog

from education_system.systems.sixth_form.domain.assessment.exam_entries.exam_entries import (
    EXAM_BOARDS,
    SEASONS,
)
from education_system.systems.sixth_form.domain.assessment.exams_office import results_day as rd
from education_system.systems.sixth_form.interfaces.gui.assessment.exams_office.exams_widgets import (
    ERROR_FG,
    FormField,
    SeriesBar,
    clear,
    form_dialog,
    run_action,
    selected_id,
    student_choices,
    student_from_label,
    table,
    yn,
)

logger = logging.getLogger(__name__)


# ── Release & embargo ───────────────────────────────────────────────

def build_release_tab(gui, parent: ttk.Frame) -> None:
    actions = ttk.Frame(parent)
    actions.pack(fill="x", pady=(0, 6))
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)
    info = ttk.Label(parent, text="", foreground="#333")
    info.pack(anchor="w", pady=(4, 0))
    state: dict = {}

    def refresh() -> None:
        clear(holder)
        rows = rd.list_releases()
        state["rows"] = {r.release_id: r for r in rows}
        state["tree"] = table(holder, [("Series", 110), ("Board", 140), ("Results day", 90),
                                       ("Embargo until", 120), ("Released", 130),
                                       ("By", 100), ("Still hidden (papers/quals)", 170),
                                       ("Notes", 200)],
                              [(f"{r.season} {r.year}", r.exam_board or "All boards",
                                r.results_date, r.embargo_until,
                                r.released_at or ("DUE" if r.due else "embargoed"),
                                r.released_by,
                                "{} / {}".format(*rd.embargoed_counts(r.season, r.year)),
                                r.notes) for r in rows],
                              iids=[r.release_id for r in rows], height=10)
        info.configure(text="Imported results are hidden from students until the series "
                            "is released (or the embargo time passes).")

    def schedule() -> None:
        form_dialog(gui.root, "Schedule results day",
                    [FormField("season", "Season", "readonly", SEASONS),
                     FormField("year", "Year"),
                     FormField("exam_board", "Board (blank = all)", "readonly",
                               ["", *EXAM_BOARDS]),
                     FormField("results_date", "Results day (YYYY-MM-DD)"),
                     FormField("embargo_until", f"Embargo until (blank = "
                                                f"{rd.DEFAULT_RELEASE_TIME} that day)"),
                     FormField("notes", "Notes")],
                    rd.schedule_release, on_done=refresh,
                    initial={"season": SEASONS[0]})

    def release() -> None:
        rid = selected_id(state["tree"], gui.root, "a series")
        if rid is None:
            return
        r = state["rows"][rid]
        if not messagebox.askyesno("Release results",
                                   f"Release {r.season} {r.year} "
                                   f"{r.exam_board or '(all boards)'} to students now?",
                                   parent=gui.root):
            return
        run_action(gui.root, lambda: rd.release_series(r.season, r.year,
                                                       r.exam_board or None),
                   done="Released {out[0]} paper result(s) and {out[1]} qualification "
                        "result(s).", then=refresh)

    def release_due() -> None:
        out = run_action(gui.root, rd.release_due, then=refresh)
        if out is not None:
            messagebox.showinfo("Released", f"{len(out)} series released." if out
                                else "Nothing is due for release.", parent=gui.root)

    for label, cmd in (("Schedule results day…", schedule), ("Release selected", release),
                       ("Release everything due", release_due), ("Refresh", refresh)):
        ttk.Button(actions, text=label, command=cmd).pack(side="left", padx=(0, 6))
    refresh()


# ── Qualification results ───────────────────────────────────────────

def build_qualification_tab(gui, parent: ttk.Frame) -> None:
    top = ttk.Frame(parent)
    top.pack(fill="x", pady=(0, 6))
    actions = ttk.Frame(parent)
    actions.pack(fill="x", pady=(0, 6))
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)
    view_var = tk.StringVar(value="Qualification results")
    state: dict = {}

    def refresh() -> None:
        clear(holder)
        try:
            season, year = series.get()
        except ValueError as e:
            ttk.Label(holder, text=str(e), foreground=ERROR_FG).pack(anchor="w")
            return
        if view_var.get() == "Component roll-up":
            rows = rd.component_totals(season, year)
            state["tree"] = table(holder, [("Student", 80), ("Name", 170), ("Board", 120),
                                           ("Entry code", 90), ("Components", 80),
                                           ("With results", 85), ("Total marks", 85),
                                           ("Qualification grade", 120)],
                                  [(t.student_id, t.full_name, t.exam_board, t.entry_code,
                                    t.components_entered, t.components_with_results,
                                    t.total_marks, t.qualification_grade) for t in rows])
            state["rows"] = {}
            return
        rows = rd.list_qualification_results(season=season, year=year, released_only=False)
        state["rows"] = {q.qual_result_id: q for q in rows}
        state["tree"] = table(holder, [("Student", 80), ("Name", 170), ("Board", 120),
                                       ("Entry code", 90), ("Subject", 130),
                                       ("Qual. type", 110), ("Grade", 70), ("Marks", 60),
                                       ("UMS", 50), ("Released", 60), ("Source", 80)],
                              [(q.student_id, q.full_name, q.exam_board, q.entry_code,
                                q.subject, q.qualification_type, q.grade, q.marks, q.ums,
                                yn(q.visible), q.source) for q in rows],
                              iids=[q.qual_result_id for q in rows])
        gui.status_var.set(f"{len(rows)} qualification result(s)")

    series = SeriesBar(top, on_change=refresh)
    ttk.Combobox(top, textvariable=view_var, state="readonly", width=22,
                 values=["Qualification results", "Component roll-up"]).pack(side="left")

    def add() -> None:
        labels, mapping = student_choices()
        season, year = series.get()

        def submit(v: dict) -> None:
            v = dict(v)
            v["student_id"] = student_from_label(v.pop("student"), mapping)
            rd.save_qualification_result(v)

        from education_system.systems.sixth_form.domain.academics.qualifications import (
            grade_scales,
        )
        form_dialog(gui.root, "Qualification result",
                    [FormField("student", "Student", "combo", labels, 42),
                     FormField("exam_board", "Board", "readonly", EXAM_BOARDS),
                     FormField("entry_code", "Entry code"),
                     FormField("season", "Season", "readonly", SEASONS),
                     FormField("year", "Year"),
                     FormField("qualification_type", "Qualification type (blank = "
                               "catalogue)", "readonly", ["", *grade_scales.QUALIFICATION_TYPES]),
                     FormField("grade", "Grade"),
                     FormField("marks", "Total marks"),
                     FormField("ums", "UMS"),
                     FormField("notes", "Notes")],
                    submit, on_done=refresh,
                    initial={"exam_board": EXAM_BOARDS[0], "season": season, "year": year})

    def delete() -> None:
        qid = selected_id(state["tree"], gui.root, "a qualification result")
        if qid is not None and messagebox.askyesno("Delete", "Delete this result?",
                                                   parent=gui.root):
            run_action(gui.root, lambda: rd.delete_qualification_result(qid), then=refresh)

    def history() -> None:
        qid = selected_id(state["tree"], gui.root, "a qualification result")
        if qid is not None:
            _show_history(gui, qual_result_id=qid)

    for label, cmd in (("Add / update", add), ("Delete", delete), ("History…", history)):
        ttk.Button(actions, text=label, command=cmd).pack(side="left", padx=(0, 6))
    refresh()


# ── Import ──────────────────────────────────────────────────────────

def build_import_tab(gui, parent: ttk.Frame) -> None:
    from education_system.systems.sixth_form.interfaces.gui.assessment.exams_office import (
        edi_views,
    )
    edi_views.build_import_panel(gui, parent)


# ── History ─────────────────────────────────────────────────────────

def _show_history(gui, *, result_id: int | None = None,
                  qual_result_id: int | None = None) -> None:
    from education_system.systems.sixth_form.interfaces.gui.assessment.exams_office.exams_widgets import (
        text_window,
    )
    rows = rd.history(result_id=result_id, qual_result_id=qual_result_id)
    lines = ["RESULT HISTORY", ""] + [
        f"{h.changed_at}  {h.old_grade or '—'} → {h.new_grade or '—'}  marks "
        f"{h.old_marks if h.old_marks is not None else '—'} → "
        f"{h.new_marks if h.new_marks is not None else '—'}  {h.reason or ''}  "
        f"({h.changed_by or '?'})" for h in rows]
    if not rows:
        lines.append("(no changes recorded)")
    text_window(gui.root, "Result history", "\n".join(lines) + "\n",
                filename="result_history.txt")


def build_history_tab(gui, parent: ttk.Frame) -> None:
    actions = ttk.Frame(parent)
    actions.pack(fill="x", pady=(0, 6))
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)

    def refresh() -> None:
        clear(holder)
        rows = rd.history()
        table(holder, [("When", 140), ("Paper result #", 100), ("Qual result #", 100),
                       ("Old", 60), ("New", 60), ("Old marks", 70), ("New marks", 70),
                       ("Reason", 380), ("By", 100)],
              [(h.changed_at, h.result_id, h.qual_result_id, h.old_grade, h.new_grade,
                h.old_marks, h.new_marks, h.reason, h.changed_by) for h in rows], height=18)
        gui.status_var.set(f"{len(rows)} grade change(s) recorded")

    def hold() -> None:
        rid = simpledialog.askinteger("Hold result", "Paper result # to put back under "
                                      "embargo:", parent=gui.root)
        if rid:
            until = simpledialog.askstring("Embargo", "Hidden until (YYYY-MM-DD HH:MM, "
                                           "blank = until released):", parent=gui.root)
            run_action(gui.root, lambda: rd.hold_result(rid, embargo_until=until or None),
                       done="Result hidden from students.")

    ttk.Button(actions, text="Refresh", command=refresh).pack(side="left")
    ttk.Button(actions, text="Hold a result…", command=hold).pack(side="left", padx=6)
    refresh()
