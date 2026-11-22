"""Cohort-wide enrolment tools: bulk enrol, progression and end-of-year
rollover (bulk status / tutor changes are in ``enrolment_bulk_actions``)."""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date
from tkinter import ttk

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.sixth_form.domain.admissions.enrolments import enrolments as data
from education_system.systems.sixth_form.domain.admissions.enrolments.enrolments import (
    DEFAULT_STATUS,
    YEAR_GROUPS,
)
from education_system.systems.sixth_form.domain.learners.students import students as student_data

from .enrolment_common import (
    _clear,
    _default_academic_year,
    _heading,
    _next_academic_year,
    _report_bulk,
    _year_choices,
    back_to_directory,
    describe_error,
    show_error,
)
from .enrolment_pickers import TutorGroupPicker, students_for_picker
from .enrolment_rollover_views import open_return_intentions, open_rollover_history

logger = logging.getLogger(__name__)


def open_bulk_enrol(gui) -> None:
    """Feature #1 — enrol several students into one shared year/status."""
    frame = _clear(gui)
    _heading(frame, "Bulk Enrol Students")

    students = students_for_picker()
    if not students:
        ttk.Label(frame, text="No students on the roll yet — add a student first.",
                  foreground="#a33").pack(anchor="w")
        ttk.Button(frame, text="Back to Enrolments",
                   command=lambda: back_to_directory(gui)).pack(anchor="w", pady=(8, 0))
        return

    ttk.Label(
        frame,
        text="Select students (Ctrl/Shift-click), set the shared details, then Enrol.",
        foreground="#555",
    ).pack(anchor="w", pady=(0, 6))

    body = ttk.Frame(frame)
    body.pack(anchor="w", fill="x")

    left = ttk.Frame(body)
    left.pack(side="left", padx=(0, 16))
    lb = tk.Listbox(left, selectmode="extended", height=14, width=40,
                    exportselection=False)
    lbs = ttk.Scrollbar(left, orient="vertical", command=lb.yview)
    lb.configure(yscrollcommand=lbs.set)
    lb.pack(side="left")
    lbs.pack(side="left", fill="y")
    idx_to_sid: dict[int, str] = {}
    for i, s in enumerate(students):
        lb.insert("end", f"{s.student_id} — {s.full_name}")
        idx_to_sid[i] = s.student_id

    form = ttk.Frame(body)
    form.pack(side="left", anchor="n")
    year_var = tk.StringVar(value=_default_academic_year())
    yg_var = tk.StringVar(value=str(YEAR_GROUPS[0]))
    tg_var = tk.StringVar()
    sd_var = tk.StringVar(value=date.today().isoformat())
    status_var = tk.StringVar(value=DEFAULT_STATUS)

    def frow(r: int, label: str, widget: tk.Widget) -> None:
        ttk.Label(form, text=label).grid(row=r, column=0, sticky="e", padx=(0, 8), pady=4)
        widget.grid(row=r, column=1, sticky="ew", pady=4)

    frow(0, "Academic year *", ttk.Combobox(
        form, textvariable=year_var, values=_year_choices(),
        state="readonly", width=10))
    frow(1, "Year group *", ttk.Combobox(
        form, textvariable=yg_var, values=[str(y) for y in YEAR_GROUPS],
        state="readonly", width=8))
    tg_picker = TutorGroupPicker(form, tg_var, int(yg_var.get()))
    frow(2, "Tutor group", tg_picker)
    yg_var.trace_add("write", lambda *_: (tg_var.set(""), tg_picker.set_year_group(
        int(yg_var.get()) if yg_var.get() else None)))
    frow(3, "Start date", ttk.Entry(form, textvariable=sd_var))
    frow(4, "Status *", ttk.Combobox(
        form, textvariable=status_var, values=list(data.CREATE_STATUSES),
        state="readonly", width=16))
    ttk.Label(form, text="Only learners on roll are listed.",
              foreground="#777").grid(row=5, column=0, columnspan=2, sticky="w")

    def run() -> None:
        sel = lb.curselection()
        if not sel:
            messagebox.showinfo("No students", "Select at least one student.",
                                parent=gui.root)
            return
        ok: list[str] = []
        fail: list[str] = []
        for i in sel:
            sid = idx_to_sid[i]
            payload = {
                "student_id": sid,
                "academic_year": year_var.get(),
                "year_group": yg_var.get(),
                "tutor_group": tg_var.get(),
                "start_date": sd_var.get(),
                "status": status_var.get(),
                "notes": None,
            }
            try:
                data.create_enrolment(payload)
                ok.append(sid)
            except Exception as exc:  # reported per learner
                fail.append(f"{sid}: {describe_error(exc)}")
        _report_bulk(gui, "Bulk enrol", ok, fail)

    bar = ttk.Frame(frame)
    bar.pack(anchor="w", pady=(12, 0))
    ttk.Button(bar, text="Enrol Selected", command=run).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Cancel",
               command=lambda: back_to_directory(gui)).pack(side="left")
    gui.status_var.set("Bulk enrol")


def _names() -> dict[str, str]:
    try:
        return {s.student_id: s.full_name for s in student_data.list_students()}
    except Exception:  # noqa: BLE001 — ids are shown instead
        logger.exception("Could not build student name map")
        return {}


def _rollover_text(result, *, dry_run: bool, names: dict[str, str]) -> str:
    """Human-readable RolloverResult: what (would have) happened and why
    each skipped learner was left alone."""
    def who(sid: str) -> str:
        return f"{sid} {names.get(sid, '')}".rstrip()

    verb = "Would" if dry_run else "Did"
    lines = [f"{'Preview' if dry_run else 'Result'}: {result.from_year} → "
             f"{result.to_year}", ""]
    lines.append(f"{verb} complete {len(result.completed)} Year 13 leaver(s)")
    lines += [f"  • {who(s)}" for s in result.completed]
    lines.append(f"{verb} progress {len(result.progressed)} Year 12 learner(s) "
                 f"into Year 13 for {result.to_year}")
    lines += [f"  • {who(s)}" for s in result.progressed]
    lines.append(f"Skipped {len(result.skipped)}")
    lines += [f"  • {who(s)}: {why}" for s, why in result.skipped]
    if result.failed:
        lines.append(f"Failed {len(result.failed)}")
        lines += [f"  • {who(s)}: {why}" for s, why in result.failed]
    if result.aim_problems:
        lines.append(f"Learning aim problems {len(result.aim_problems)}")
        lines += [f"  • {p}" for p in result.aim_problems]
    if result.run_id is not None:
        lines += ["", f"Recorded as rollover run #{result.run_id} — it can be "
                      "undone from Rollover History."]
    return "\n".join(lines)


def _rollover_screen(gui, *, title: str, intro: str, run_label: str,
                     complete_year13: bool, choose_steps: bool) -> None:
    """Shared screen for the progression wizard and end-of-year rollover.

    Both go through ``enrolments.rollover``: Preview is a dry run that
    lists every learner and the reason anyone is skipped (withdrawn,
    pending, not on roll, already enrolled next year); Run does it."""
    frame = _clear(gui)
    _heading(frame, title)
    ttk.Label(frame, text=intro, foreground="#555", wraplength=900,
              justify="left").pack(anchor="w", pady=(0, 6))

    src_var = tk.StringVar(value=_default_academic_year())
    tgt_var = tk.StringVar(value=_next_academic_year(src_var.get()))
    y13_var = tk.BooleanVar(value=complete_year13)
    y12_var = tk.BooleanVar(value=True)
    intent_var = tk.BooleanVar(value=False)

    row = ttk.Frame(frame)
    row.pack(anchor="w", pady=(0, 6))
    ttk.Label(row, text="Academic year ending:").pack(side="left")
    ttk.Combobox(row, textvariable=src_var, values=_year_choices(),
                 state="readonly", width=10).pack(side="left", padx=(4, 8))
    ttk.Label(row, text="New year:").pack(side="left")
    tgt_box = ttk.Combobox(row, textvariable=tgt_var, state="readonly", width=10,
                           values=_year_choices(tgt_var.get()))
    tgt_box.pack(side="left", padx=(4, 8))

    def _src_changed(*_a) -> None:
        nxt = _next_academic_year(src_var.get().strip())
        tgt_box.configure(values=_year_choices(nxt))
        tgt_var.set(nxt)
    src_var.trace_add("write", _src_changed)
    if choose_steps:
        ttk.Checkbutton(row, text="Complete Year 13 leavers",
                        variable=y13_var).pack(side="left", padx=(8, 4))
        ttk.Checkbutton(row, text="Progress Year 12 → 13",
                        variable=y12_var).pack(side="left", padx=(4, 8))
    row2 = ttk.Frame(frame)
    row2.pack(anchor="w", pady=(0, 6))
    ttk.Checkbutton(
        row2, variable=intent_var,
        text="Require re-enrolment confirmation (only Year 12s recorded as "
             "Returning move up)").pack(side="left")
    intent_label = ttk.Label(row2, foreground="#555")
    intent_label.pack(side="left", padx=(12, 0))

    def _intent_summary(*_a) -> None:
        try:
            counts = data.reintention_summary(src_var.get().strip())
        except Exception as exc:  # noqa: BLE001 — shown in place
            intent_label.configure(text=f"(intentions not read: {exc})")
            return
        intent_label.configure(text="Year 12 intentions — " + ", ".join(
            f"{k}: {v}" for k, v in counts.items()))
    src_var.trace_add("write", _intent_summary)
    _intent_summary()

    # Bottom bar before the expanding report (pack-order rule).
    bar = ttk.Frame(frame)
    bar.pack(side="bottom", anchor="w", pady=(8, 0))
    holder = ttk.Frame(frame)
    holder.pack(fill="both", expand=True)
    text = tk.Text(holder, wrap="word", height=18)
    sb = ttk.Scrollbar(holder, orient="vertical", command=text.yview)
    text.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    text.pack(side="left", fill="both", expand=True)

    def show(msg: str) -> None:
        text.configure(state="normal")
        text.delete("1.0", "end")
        text.insert("1.0", msg)
        text.configure(state="disabled")

    def call(dry_run: bool):
        return data.rollover(
            src_var.get().strip(), tgt_var.get().strip() or None,
            complete_year13=bool(y13_var.get()),
            progress_year12=bool(y12_var.get()),
            require_intention=bool(intent_var.get()), dry_run=dry_run)

    def preview() -> None:
        try:
            result = call(True)
        except Exception as exc:  # ValidationError / AccessDenied / DB
            show(f"Cannot preview: {describe_error(exc)}")
            return
        show(_rollover_text(result, dry_run=True, names=_names()))

    def run() -> None:
        try:
            plan = call(True)
        except Exception as exc:
            show_error(gui.root, title, exc)
            return
        if not plan.completed and not plan.progressed:
            show(_rollover_text(plan, dry_run=True, names=_names()))
            messagebox.showinfo("Nothing to do", "No learner would be completed "
                                "or progressed; see the reasons listed.",
                                parent=gui.root)
            return
        if not messagebox.askyesno(
                f"Confirm {title.lower()}",
                f"Complete {len(plan.completed)} leaver(s) and progress "
                f"{len(plan.progressed)} learner(s) to {plan.to_year}? "
                f"{len(plan.skipped)} will be skipped.", parent=gui.root):
            return
        try:
            result = call(False)
        except Exception as exc:
            show_error(gui.root, title, exc)
            return
        show(_rollover_text(result, dry_run=False, names=_names()))
        summary = (f"{len(result.completed)} completed, "
                   f"{len(result.progressed)} progressed, "
                   f"{len(result.skipped)} skipped, {len(result.failed)} failed"
                   + (f", {len(result.aim_problems)} aim problem(s)"
                      if result.aim_problems else "")
                   + (f" (run #{result.run_id})." if result.run_id else "."))
        (messagebox.showwarning if result.failed or result.aim_problems
         else messagebox.showinfo)(
            title, summary + "\n\nThe full list is shown on the screen.",
            parent=gui.root)
        gui.status_var.set(f"{title}: {summary}")

    ttk.Button(row, text="Preview", command=preview).pack(side="left")
    ttk.Button(bar, text=run_label, command=run,
               state="normal" if data.can_write() else "disabled"
               ).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Rollover History",
               command=lambda: open_rollover_history(gui)
               ).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Return Intentions",
               command=lambda: open_return_intentions(gui, src_var.get().strip())
               ).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Back to Directory",
               command=lambda: back_to_directory(gui)).pack(side="left")
    preview()
    gui.status_var.set(title)


def open_progression_wizard(gui) -> None:
    """Roll enrolled Year 12s forward into Year 13 next year (Year 13s
    are left alone)."""
    _rollover_screen(
        gui, title="Year 12 → 13 Progression Wizard", run_label="Run Progression",
        complete_year13=False, choose_steps=False,
        intro="Gives every enrolled, on-roll Year 12 learner a Year 13 "
              "enrolment for the new year, with the tutor group moved up "
              "(12A → 13A). Preview lists everyone and why anyone is skipped.")


def open_end_of_year_rollover(gui) -> None:
    """Complete Year 13 leavers and progress Year 12 into 13."""
    _rollover_screen(
        gui, title="End-of-Year Rollover", run_label="Run Rollover",
        complete_year13=True, choose_steps=True,
        intro="Marks enrolled Year 13 leavers as Completed and progresses "
              "Year 12 into Year 13 for the next academic year. Learners who "
              "are withdrawn, pending, not on roll, recorded as not returning "
              "or already enrolled next year are skipped with the reason; "
              "one-year programmes are completed instead. Each run is "
              "recorded and can be undone from Rollover History.")


