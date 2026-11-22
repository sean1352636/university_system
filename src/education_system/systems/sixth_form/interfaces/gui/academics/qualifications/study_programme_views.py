"""Study Programme windows for the Sixth Form GUI.

* :func:`open_study_programme` — one learner's programme, opened from the
  Student Profile / Directory "Study Programme" button. Tabs: Learning
  Aims, Change History, Prior Attainment, Condition of Funding, Planned
  Hours, Option Choices, Identifiers.
* :func:`open_option_blocks` — define each year's option blocks (from the
  Subjects window).
* :func:`open_programme_reports` — college-wide condition-of-funding,
  funding band, withdrawal (qualifying period) and aims reports (from the
  Subjects and Courses windows).

All data goes through ``domain/academics/qualifications``.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk
from education_system.systems.sixth_form.interfaces.gui._sidebar import SidebarBook
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from typing import Any, Callable

from education_system.platform.delivery.gui import window_sizing
from education_system.systems.sixth_form.domain.academics.qualifications import (
    grade_scales,
    identifiers,
    learning_aims,
    option_blocks,
    prior_attainment,
    study_programme,
)
from education_system.systems.sixth_form.domain.learners.students import students

logger = logging.getLogger(__name__)

_ERRORS = (ValueError,)   # every module's ValidationError is a ValueError


def _me() -> str:
    """Signed-in username, for 'recorded by' / default approver."""
    try:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        return access.current().username or ""
    except Exception:
        return ""


def _current_year() -> str:
    return learning_aims.academic_year_for(_dt.date.today().isoformat()) or ""


def _subject_names() -> list[str]:
    try:
        from education_system.systems.sixth_form.domain.academics.subjects import (
            subjects as _subjects,
        )
        return _subjects.get_active_names()
    except Exception:
        return list(students.A_LEVEL_SUBJECTS)


def _window(parent: tk.Misc, title: str) -> tk.Toplevel:
    win = tk.Toplevel(parent)
    win.title(title)
    window_sizing.fit(win, "1400x900", (1200, 800))
    win.transient(parent.winfo_toplevel())
    return win


def _table(parent: tk.Misc, cols: list[tuple[str, str, int]],
           height: int = 14) -> ttk.Treeview:
    """Treeview + scrollbar filling the rest of ``parent`` (pack the action
    bar before calling this)."""
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True, pady=(4, 4))
    tree = ttk.Treeview(frame, columns=[c[0] for c in cols], show="headings",
                        height=height)
    for key, text, width in cols:
        tree.heading(key, text=text)
        tree.column(key, width=width, anchor="w")
    vs = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vs.set)
    tree.pack(side="left", fill="both", expand=True)
    vs.pack(side="right", fill="y")
    return tree


def _fill(tree: ttk.Treeview, rows: list[tuple[str, tuple]]) -> None:
    tree.delete(*tree.get_children())
    for iid, values in rows:
        tree.insert("", "end", iid=iid,
                    values=tuple("—" if v in (None, "") else v for v in values))


def _selected(tree: ttk.Treeview, win: tk.Misc, what: str = "a row") -> str | None:
    sel = tree.selection()
    if not sel:
        messagebox.showinfo("No selection", f"Select {what} first.", parent=win)
        return None
    return sel[0]


def _form(parent: tk.Misc, title: str,
          fields: list[tuple[str, str, Any, Any]]) -> dict[str, str] | None:
    """Small modal form. ``fields``: (key, label, default, choices|None).

    ``choices`` may be a list (readonly combobox), ``"edit"`` + list via a
    tuple ("edit", [...]) for an editable combobox, or None for an entry.
    Returns the values, or None if cancelled.
    """
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.transient(parent.winfo_toplevel())
    dlg.grab_set()
    body = ttk.Frame(dlg, padding=12)
    body.pack(fill="both", expand=True)
    vars_: dict[str, tk.StringVar] = {}
    for row, (key, label, default, choices) in enumerate(fields):
        ttk.Label(body, text=label).grid(row=row, column=0, sticky="e",
                                         padx=(0, 8), pady=3)
        var = tk.StringVar(value="" if default is None else str(default))
        vars_[key] = var
        if isinstance(choices, tuple) and choices and choices[0] == "edit":
            w = ttk.Combobox(body, textvariable=var, values=list(choices[1]),
                             width=34)
        elif choices is not None:
            w = ttk.Combobox(body, textvariable=var, values=list(choices),
                             state="readonly", width=34)
        else:
            w = ttk.Entry(body, textvariable=var, width=36)
        w.grid(row=row, column=1, sticky="w", pady=3)
    result: dict[str, Any] = {}

    def ok() -> None:
        result.update({k: v.get().strip() for k, v in vars_.items()})
        dlg.destroy()

    bar = ttk.Frame(body)
    bar.grid(row=len(fields), column=0, columnspan=2, sticky="e", pady=(10, 0))
    ttk.Button(bar, text="OK", command=ok).pack(side="left", padx=4)
    ttk.Button(bar, text="Cancel", command=dlg.destroy).pack(side="left")
    dlg.wait_window()
    return result or None


def _run(win: tk.Misc, fn: Callable[[], Any], ok_message: str | None = None,
         after: Callable[[], None] | None = None) -> Any:
    try:
        out = fn()
    except _ERRORS as e:
        messagebox.showerror("Cannot save", str(e), parent=win)
        return None
    except Exception as e:
        logger.exception("Study programme action failed")
        messagebox.showerror("Error", f"Unexpected error: {e}", parent=win)
        return None
    if ok_message:
        messagebox.showinfo("Done", ok_message, parent=win)
    if after:
        after()
    return out


# ════════════════════════════════════════════════════════════════════
# One learner's study programme
# ════════════════════════════════════════════════════════════════════

def open_study_programme(parent: tk.Misc, student_id: str) -> tk.Toplevel | None:
    student = students.get_student(student_id)
    if student is None:
        messagebox.showerror("Not found", f"No student with id {student_id}",
                             parent=parent)
        return None
    win = _window(parent, f"Study Programme — {student.full_name} ({student_id})")
    ttk.Label(win, text=f"Study Programme — {student.full_name} ({student_id})",
              font=("", 15, "bold")).pack(anchor="w", padx=12, pady=(10, 4))
    nb = SidebarBook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    refreshers: list[Callable[[], None]] = []

    def refresh_all() -> None:
        for r in refreshers:
            try:
                r()
            except Exception:
                logger.exception("Study programme tab refresh failed")

    refreshers.append(_aims_tab(nb, win, student_id, refresh_all))
    refreshers.append(_history_tab(nb, win, student_id))
    refreshers.append(_prior_tab(nb, win, student_id, refresh_all))
    refreshers.append(_cof_tab(nb, win, student_id, refresh_all))
    refreshers.append(_hours_tab(nb, win, student_id))
    refreshers.append(_choices_tab(nb, win, student_id, refresh_all))
    _identifiers_tab(nb, win, student_id)
    refresh_all()
    return win


# ── Learning aims ──────────────────────────────────────────────────

def _aim_fields(aim: learning_aims.LearningAim | None = None,
                *, new: bool = True) -> list[tuple[str, str, Any, Any]]:
    today = _dt.date.today().isoformat()
    fields: list[tuple[str, str, Any, Any]] = []
    if new:
        fields += [
            ("qualification_type", "Qualification type *",
             grade_scales.DEFAULT_QUALIFICATION_TYPE,
             list(grade_scales.QUALIFICATION_TYPES)),
            ("subject", "Subject *", "", ("edit", _subject_names())),
        ]
    fields += [
        ("awarding_body", "Awarding body", aim.awarding_body if aim else "",
         ("edit", list(learning_aims.AWARDING_BODIES))),
        ("aim_code", "Aim / QAN code", aim.aim_code if aim else "", None),
        ("start_date", "Start date * (YYYY-MM-DD)",
         aim.start_date if aim else today, None),
        ("planned_end_date", "Planned end date",
         aim.planned_end_date if aim else "", None),
        ("planned_hours", "Planned hours (this year)",
         aim.planned_hours if aim and aim.planned_hours is not None else "", None),
        ("is_core_aim", "Core aim?", "Yes" if aim and aim.is_core_aim else "No",
         ["No", "Yes"]),
        ("notes", "Notes", aim.notes if aim else "", None),
    ]
    return fields


def _clean_aim(values: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = dict(values)
    out["is_core_aim"] = values.get("is_core_aim") == "Yes"
    return out


def _aims_tab(nb: ttk.Notebook, win: tk.Misc, sid: str,
              refresh_all: Callable[[], None]) -> Callable[[], None]:
    tab = ttk.Frame(nb, padding=8)
    nb.add(tab, text="Learning Aims")
    ttk.Label(tab, foreground="#555", text=(
        "Every qualification on the learner's programme. The A-level subject "
        "slots on the student record mirror the first three active A-level "
        "aims. Withdrawals and course changes record a reason, approver and "
        "the funding qualifying-period check.")).pack(anchor="w")
    bar = ttk.Frame(tab)
    bar.pack(fill="x", pady=(6, 0))
    status = ttk.Label(tab, foreground="#555")
    status.pack(side="bottom", anchor="w")
    tree = _table(tab, [
        ("id", "#", 50), ("type", "Qualification", 170), ("subject", "Subject", 170),
        ("board", "Board", 90), ("code", "Aim code", 90), ("start", "Start", 90),
        ("end", "Planned end", 90), ("status", "Status", 90),
        ("left", "Left on", 90), ("hours", "Hours", 60), ("core", "Core", 50),
        ("qp", "Qualifying period", 200),
    ])

    def refresh() -> None:
        aims = learning_aims.list_aims(sid)
        rows = []
        for a in aims:
            chk = learning_aims.qualifying_check_for(a)
            if chk.withdrawn_before_qualifying:
                qp = f"NOT met ({chk.days_in_learning}/{chk.qualifying_days} days)"
            elif chk.met:
                qp = f"Met ({chk.qualifying_days}-day rule)"
            else:
                qp = f"Due {chk.qualifying_date} ({chk.days_in_learning}/{chk.qualifying_days})"
            rows.append((str(a.aim_id), (
                a.aim_id, a.qualification_type, a.subject, a.awarding_body,
                a.aim_code, a.start_date, a.planned_end_date, a.status,
                a.withdrawal_date or a.actual_end_date, a.planned_hours,
                "Yes" if a.is_core_aim else "", qp)))
        _fill(tree, rows)
        active = [a for a in aims if a.is_active]
        status.configure(text=f"{len(active)} active aim(s), {len(aims)} in total. "
                              f"Mirrored slots: {', '.join(students.get_student(sid).subjects) or '—'}")

    def add() -> None:
        v = _form(win, "Add learning aim", _aim_fields())
        if v:
            _run(win, lambda: learning_aims.add_aim(sid, _clean_aim(v),
                                                    recorded_by=_me()),
                 after=refresh_all)

    def edit() -> None:
        aid = _selected(tree, win, "an aim")
        if not aid:
            return
        aim = learning_aims.get_aim(int(aid))
        v = _form(win, f"Edit aim #{aid} — {aim.label}", _aim_fields(aim, new=False))
        if v:
            _run(win, lambda: learning_aims.update_aim(int(aid), _clean_aim(v),
                                                       recorded_by=_me()),
                 after=refresh_all)

    def withdraw() -> None:
        aid = _selected(tree, win, "an aim")
        if not aid:
            return
        aim = learning_aims.get_aim(int(aid))
        v = _form(win, f"Withdraw — {aim.label}", [
            ("effective_date", "Last day in learning *", _dt.date.today().isoformat(), None),
            ("reason", "Reason *", "", None),
            ("approved_by", "Approved by *", _me(), None),
            ("status", "Record as", "Withdrawn", ["Withdrawn", "Transferred"]),
        ])
        if not v:
            return
        chk = _run(win, lambda: learning_aims.withdraw_aim(
            int(aid), effective_date=v["effective_date"], reason=v["reason"],
            approved_by=v["approved_by"], recorded_by=_me(), status=v["status"]),
            after=refresh_all)
        if chk is not None:
            messagebox.showinfo("Withdrawn", (
                f"{aim.label} withdrawn after {chk.days_in_learning} day(s) "
                f"in learning.\n\nFunding qualifying period ({chk.qualifying_days} "
                f"days): {'met' if chk.met else 'NOT met — withdrawn before qualifying period'}"),
                parent=win)

    def change() -> None:
        aid = _selected(tree, win, "an aim")
        if not aid:
            return
        aim = learning_aims.get_aim(int(aid))
        v = _form(win, f"Course change — from {aim.label}", [
            ("new_qualification_type", "New qualification type",
             aim.qualification_type, list(grade_scales.QUALIFICATION_TYPES)),
            ("new_subject", "New subject *", "", ("edit", _subject_names())),
            ("effective_date", "Starts new aim on *", _dt.date.today().isoformat(), None),
            ("reason", "Reason *", "", None),
            ("approved_by", "Approved by *", _me(), None),
            ("new_awarding_body", "New awarding body", aim.awarding_body or "",
             ("edit", list(learning_aims.AWARDING_BODIES))),
            ("new_aim_code", "New aim code", "", None),
            ("new_planned_end_date", "New planned end", aim.planned_end_date or "", None),
        ])
        if not v:
            return
        out = _run(win, lambda: learning_aims.change_aim(
            int(aid), recorded_by=_me(), **v), after=refresh_all)
        if out is not None:
            new, chk = out
            messagebox.showinfo("Course changed", (
                f"{aim.label} closed as Transferred; {new.label} starts "
                f"{new.start_date}.\n\nOld aim qualifying period: "
                f"{'met' if chk.met else 'NOT met'} ({chk.days_in_learning}/"
                f"{chk.qualifying_days} days)."), parent=win)

    def complete() -> None:
        aid = _selected(tree, win, "an aim")
        if not aid:
            return
        aim = learning_aims.get_aim(int(aid))
        v = _form(win, f"Complete — {aim.label}", [
            ("end_date", "Actual end date", aim.planned_end_date or
             _dt.date.today().isoformat(), None)])
        if v:
            _run(win, lambda: learning_aims.complete_aim(
                int(aid), end_date=v["end_date"], recorded_by=_me()),
                after=refresh_all)

    def delete() -> None:
        aid = _selected(tree, win, "an aim")
        if not aid:
            return
        if messagebox.askyesno("Delete aim", "Delete this aim as entered in "
                               "error? (Real withdrawals must use Withdraw.)",
                               parent=win):
            _run(win, lambda: learning_aims.delete_aim(int(aid)), after=refresh_all)

    def check() -> None:
        aid = _selected(tree, win, "an aim")
        if not aid:
            return
        c = learning_aims.qualifying_check(int(aid))
        messagebox.showinfo("Funding qualifying period", (
            f"Start: {c.start_date}\nPlanned end: {c.planned_end_date or '—'}"
            f"\nPlanned length: {c.planned_length_days or '—'} days\n"
            f"Qualifying period: {c.qualifying_days} days (counts from "
            f"{c.qualifying_date})\nIn learning: {c.days_in_learning} days "
            f"(to {c.end_date_used})\n\nMet: {'Yes' if c.met else 'No'}"
            + ("\nWithdrawn before qualifying period." if c.withdrawn_before_qualifying else "")),
            parent=win)

    for text, cmd in (("Add aim", add), ("Edit", edit), ("Course change", change),
                      ("Withdraw", withdraw), ("Complete", complete),
                      ("Qualifying check", check),
                      ("Delete (entered in error)", delete),
                      ("Refresh", refresh_all)):
        ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=(0, 6))
    return refresh


def _history_tab(nb: ttk.Notebook, win: tk.Misc, sid: str) -> Callable[[], None]:
    tab = ttk.Frame(nb, padding=8)
    nb.add(tab, text="Change History")
    tree = _table(tab, [
        ("when", "Recorded", 140), ("aim", "Aim #", 60), ("action", "Action", 100),
        ("eff", "Effective", 90), ("from", "From", 180), ("to", "To", 180),
        ("reason", "Reason", 220), ("approver", "Approved by", 110),
        ("qp", "Qualifying", 120),
    ])

    def refresh() -> None:
        rows = []
        for h in learning_aims.aim_history(student_id=sid):
            qp = ("" if h.qualifying_met is None else
                  ("Met" if h.qualifying_met else
                   f"NOT met ({h.days_in_learning}/{h.qualifying_days})"))
            rows.append((str(h.change_id), (
                h.recorded_at, h.aim_id, h.action, h.effective_date,
                h.from_detail, h.to_detail, h.reason, h.approved_by, qp)))
        _fill(tree, rows)
    return refresh


# ── Prior attainment ───────────────────────────────────────────────

def _prior_tab(nb: ttk.Notebook, win: tk.Misc, sid: str,
               refresh_all: Callable[[], None]) -> Callable[[], None]:
    tab = ttk.Frame(nb, padding=8)
    nb.add(tab, text="Prior Attainment")
    summary = ttk.Label(tab, font=("", 11, "bold"))
    summary.pack(anchor="w")
    bar = ttk.Frame(tab)
    bar.pack(fill="x", pady=(6, 0))
    tree = _table(tab, [
        ("subject", "Subject", 220), ("grade", "Grade", 70), ("system", "Scale", 70),
        ("points", "Points", 70), ("kind", "Kind", 130), ("year", "Year", 70),
        ("board", "Board", 120), ("notes", "Notes", 260),
    ])

    def refresh() -> None:
        pa = prior_attainment.prior_attainment(sid)
        summary.configure(text=(
            f"Average GCSE point score: "
            f"{pa.average_point_score if pa.average_point_score is not None else '—'}"
            f"  ({pa.gcse_count:g} GCSE(s))     Best English: "
            f"{pa.best_english_grade or '—'}     Best maths: {pa.best_maths_grade or '—'}"))
        _fill(tree, [(str(r.result_id), (
            r.subject, r.grade, r.grade_system, r.points, r.kind, r.year,
            r.exam_board, r.notes)) for r in pa.results])

    def add() -> None:
        v = _form(win, "Add GCSE result", [
            ("subject", "Subject *", "", ("edit", [
                "English Language", "English Literature", "Mathematics",
                *_subject_names()])),
            ("grade", "Grade * (9-1 or A*-G)", "", None),
            ("grade_system", "Scale", "9-1", list(prior_attainment.GRADE_SYSTEMS)),
            ("kind", "Kind", "GCSE", list(prior_attainment.QUALIFICATION_KINDS)),
            ("year", "Year", str(_dt.date.today().year), None),
            ("exam_board", "Board", "", ("edit", list(prior_attainment.EXAM_BOARDS))),
            ("notes", "Notes", "", None),
        ])
        if v:
            _run(win, lambda: prior_attainment.add_result(sid, v), after=refresh_all)

    def delete() -> None:
        rid = _selected(tree, win, "a result")
        if rid and messagebox.askyesno("Delete", "Delete this GCSE result?",
                                       parent=win):
            _run(win, lambda: prior_attainment.delete_result(int(rid)),
                 after=refresh_all)

    ttk.Button(bar, text="Add GCSE", command=add).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Delete", command=delete).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Refresh", command=refresh).pack(side="left")
    return refresh


# ── Condition of funding ───────────────────────────────────────────

def _cof_tab(nb: ttk.Notebook, win: tk.Misc, sid: str,
             refresh_all: Callable[[], None]) -> Callable[[], None]:
    tab = ttk.Frame(nb, padding=12)
    nb.add(tab, text="Condition of Funding")
    ttk.Label(tab, foreground="#555", wraplength=1100, justify="left", text=(
        "Learners without grade 4 (or C) in English / maths must study it: a "
        "GCSE if they hold grade 3, a GCSE or Functional Skills if grade 2 or "
        "below. Check against the current ESFA funding guidance.")).pack(anchor="w")
    holder = ttk.Frame(tab)
    holder.pack(fill="x", pady=8)

    def refresh() -> None:
        for w in holder.winfo_children():
            w.destroy()
        fc = prior_attainment.funding_condition(sid)
        for i, a in enumerate(fc.areas):
            box = ttk.LabelFrame(holder, text=a.area, padding=8)
            box.grid(row=0, column=i, sticky="nsew", padx=(0, 10))
            colour = "#1a7f37" if a.compliant else "#b42318"
            ttk.Label(box, text=a.status, foreground=colour, wraplength=520,
                      font=("", 11, "bold")).pack(anchor="w")
            ttk.Label(box, text=f"Best prior grade: {a.best_grade or 'none recorded'}"
                                f"   Requirement: {a.requirement}").pack(anchor="w")
            if a.aim_label:
                att = (f"{a.resit_attendance_pct}% of {a.resit_sessions} session(s)"
                       if a.resit_attendance_pct is not None else "no register marks yet")
                ttk.Label(box, text=f"Aim: {a.aim_label} — attendance {att}").pack(anchor="w")
            row = ttk.Frame(box)
            row.pack(anchor="w", pady=(6, 0))
            area = a.area
            ttk.Button(row, text="Record exemption",
                       command=lambda area=area: exempt(area)).pack(side="left", padx=(0, 6))
            if a.exemption:
                ttk.Label(box, text=f"Exemption agreed by {a.exemption.agreed_by} "
                                    f"on {a.exemption.agreed_on}").pack(anchor="w")
                ttk.Button(row, text="Clear exemption",
                           command=lambda area=area: clear(area)).pack(side="left")
        holder.columnconfigure(0, weight=1)
        holder.columnconfigure(1, weight=1)

    def exempt(area: str) -> None:
        v = _form(win, f"{area} exemption", [
            ("reason", "Reason *", "", None),
            ("agreed_by", "Agreed by *", _me(), None)])
        if v:
            _run(win, lambda: prior_attainment.set_exemption(sid, area, **v),
                 after=refresh_all)

    def clear(area: str) -> None:
        if messagebox.askyesno("Clear", f"Clear the {area} exemption?", parent=win):
            _run(win, lambda: prior_attainment.clear_exemption(sid, area),
                 after=refresh_all)

    return refresh


# ── Planned hours ──────────────────────────────────────────────────

def _hours_tab(nb: ttk.Notebook, win: tk.Misc, sid: str) -> Callable[[], None]:
    tab = ttk.Frame(nb, padding=8)
    nb.add(tab, text="Planned Hours")
    bar = ttk.Frame(tab)
    bar.pack(fill="x")
    year_var = tk.StringVar(value=_current_year())
    weeks_var = tk.StringVar(value=str(study_programme.TEACHING_WEEKS))
    hn_var = tk.BooleanVar(value=False)
    ttk.Label(bar, text="Funding year:").pack(side="left")
    ttk.Entry(bar, textvariable=year_var, width=9).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="Teaching weeks:").pack(side="left")
    ttk.Entry(bar, textvariable=weeks_var, width=5).pack(side="left", padx=(4, 12))
    ttk.Checkbutton(bar, text="High needs", variable=hn_var).pack(side="left")
    totals = ttk.Label(tab, font=("", 11, "bold"))
    totals.pack(anchor="w", pady=(6, 0))
    ttk.Label(tab, text="Qualification hours", font=("", 10, "bold")).pack(anchor="w")
    aims_tree = _table(tab, [
        ("aim", "Aim", 280), ("weekly", "Timetabled h/week", 120),
        ("annual", "Timetabled h/year", 120), ("planned", "Planned hours", 110),
        ("source", "From", 90), ("counted", "Counts", 70)], height=8)
    nq_bar = ttk.Frame(tab)
    nq_bar.pack(fill="x")
    ttk.Label(nq_bar, text="Non-qualification hours", font=("", 10, "bold")).pack(side="left")
    nq_tree = _table(tab, [("cat", "Category", 200), ("hours", "Hours", 80),
                           ("notes", "Notes", 400)], height=5)

    def refresh() -> None:
        try:
            weeks = int(weeks_var.get() or study_programme.TEACHING_WEEKS)
            ph = study_programme.planned_hours(sid, year_var.get().strip() or None,
                                               teaching_weeks=weeks,
                                               high_needs=hn_var.get())
        except _ERRORS as e:
            totals.configure(text=str(e))
            return
        age = ph.age_on_31_august
        totals.configure(text=(
            f"{ph.academic_year}: {ph.qualification_hours:g} qualification + "
            f"{ph.non_qualification_hours:g} non-qualification = "
            f"{ph.total_hours:g} planned hours  →  {ph.band}"
            f"   (age on 31 Aug: {age if age is not None else 'unknown'})"))
        _fill(aims_tree, [(str(a.aim.aim_id), (
            a.aim.label + ("" if a.aim.is_active else f" [{a.aim.status}]"),
            a.timetabled_weekly_hours, a.timetabled_annual_hours,
            a.planned_hours, a.source,
            "Yes" if a.counted else "No (before QP)")) for a in ph.aims])
        _fill(nq_tree, [(str(n.entry_id), (n.category, n.hours, n.notes))
                        for n in ph.non_qualification])

    def add_nq() -> None:
        v = _form(win, "Non-qualification hours", [
            ("category", "Category", "Tutorial", list(study_programme.NON_QUAL_CATEGORIES)),
            ("hours", "Hours *", "", None), ("notes", "Notes", "", None)])
        if v:
            _run(win, lambda: study_programme.set_non_qual_hours(
                sid, year_var.get().strip(), v["category"], v["hours"], v["notes"]),
                after=refresh)

    def del_nq() -> None:
        eid = _selected(nq_tree, win, "an hours row")
        if eid:
            _run(win, lambda: study_programme.delete_non_qual_hours(int(eid)),
                 after=refresh)

    def bands() -> None:
        messagebox.showinfo("16-19 funding bands", "\n".join(
            f"{b}: {lo}{'+' if hi is None else f'-{hi}'} hours — {who}"
            for b, lo, hi, who in study_programme.FUNDING_BANDS)
            + "\n\nCheck against the current ESFA funding guidance.", parent=win)

    ttk.Button(bar, text="Recalculate", command=refresh).pack(side="left", padx=(12, 6))
    ttk.Button(bar, text="Band table", command=bands).pack(side="left")
    ttk.Button(nq_bar, text="Add / set hours", command=add_nq).pack(side="left", padx=(12, 6))
    ttk.Button(nq_bar, text="Delete", command=del_nq).pack(side="left")
    return refresh


# ── Option choices ─────────────────────────────────────────────────

def _choices_tab(nb: ttk.Notebook, win: tk.Misc, sid: str,
                 refresh_all: Callable[[], None]) -> Callable[[], None]:
    tab = ttk.Frame(nb, padding=8)
    nb.add(tab, text="Option Choices")
    top = ttk.Frame(tab)
    top.pack(fill="x")
    years = option_blocks.list_years() or [_current_year()]
    year_var = tk.StringVar(value=years[0])
    ttk.Label(top, text="Academic year:").pack(side="left")
    year_cb = ttk.Combobox(top, textvariable=year_var, values=years, width=10)
    year_cb.pack(side="left", padx=(4, 12))
    picks = ttk.Frame(tab)
    picks.pack(fill="x", pady=6)
    msg = ttk.Label(tab, foreground="#555", wraplength=1100, justify="left")
    msg.pack(anchor="w")
    bar = ttk.Frame(tab)
    bar.pack(fill="x", pady=(4, 0))
    tree = _table(tab, [("block", "Block", 60), ("subject", "Subject", 220),
                        ("status", "Status", 90), ("aim", "Aim #", 70),
                        ("chosen", "Chosen", 150), ("applied", "Applied", 150)],
                  height=8)
    choice_vars: dict[str, tk.StringVar] = {}

    def build() -> None:
        for w in picks.winfo_children():
            w.destroy()
        choice_vars.clear()
        try:
            pattern = option_blocks.blocks(year_var.get().strip())
            current = {c.block_letter: c.subject for c in
                       option_blocks.list_choices(sid, year_var.get().strip())}
        except _ERRORS as e:
            msg.configure(text=str(e))
            return
        if not pattern:
            msg.configure(text="No option blocks defined for this year — set them "
                               "up in Subjects → Option Blocks.")
        for col, letter in enumerate(sorted(pattern)):
            ttk.Label(picks, text=f"Block {letter}").grid(row=0, column=col, padx=6)
            var = tk.StringVar(value=current.get(letter, ""))
            choice_vars[letter] = var
            ttk.Combobox(picks, textvariable=var, values=["", *pattern[letter]],
                         state="readonly", width=20).grid(row=1, column=col, padx=6)
        _fill(tree, [(str(c.choice_id), (c.block_letter, c.subject, c.status,
                                         c.aim_id, c.chosen_at, c.applied_at))
                     for c in option_blocks.list_choices(sid, year_var.get().strip())])

    def chosen() -> dict[str, str]:
        return {k: v.get() for k, v in choice_vars.items()}

    def validate() -> None:
        chk = _run(win, lambda: option_blocks.validate_choices(
            year_var.get().strip(), chosen(), student_id=sid))
        if chk is not None:
            msg.configure(text=("Valid. " if chk.ok else "Problems: " + "; ".join(chk.errors) + ". ")
                          + ("Notes: " + "; ".join(chk.warnings) if chk.warnings else ""))

    def save() -> None:
        chk = _run(win, lambda: option_blocks.save_choices(
            sid, year_var.get().strip(), chosen()))
        if chk is not None:
            msg.configure(text=("Saved." if chk.ok else "Not saved: " + "; ".join(chk.errors))
                          + (" " + "; ".join(chk.warnings) if chk.warnings else ""))
            build()

    def apply() -> None:
        if not messagebox.askyesno("Apply choices",
                                   "Create learning aims from the pending choices?",
                                   parent=win):
            return
        made = _run(win, lambda: option_blocks.apply_choices(
            sid, year_var.get().strip(), recorded_by=_me()), after=refresh_all)
        if made is not None:
            msg.configure(text=f"{len(made)} new aim(s) created.")

    def place() -> None:
        v = _form(win, "Place subjects in blocks", [
            ("subjects", "Subjects (comma separated)", "", None)])
        if not v:
            return
        assignment, reasons = option_blocks.find_block_assignment(
            year_var.get().strip(), [s for s in v["subjects"].split(",")])
        if assignment is None:
            msg.configure(text="; ".join(reasons))
            return
        for letter, var in choice_vars.items():
            var.set(assignment.get(letter, ""))
        msg.configure(text="Placed: " + ", ".join(f"{b}={s}" for b, s in assignment.items())
                      + " — Save to keep.")

    year_cb.bind("<<ComboboxSelected>>", lambda _e: build())
    ttk.Button(top, text="Load", command=build).pack(side="left")
    for text, cmd in (("Validate", validate), ("Save choices", save),
                      ("Auto-place subjects", place),
                      ("Apply as learning aims", apply)):
        ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=(0, 6))
    return build


# ── Identifiers ────────────────────────────────────────────────────

def _identifiers_tab(nb: ttk.Notebook, win: tk.Misc, sid: str) -> None:
    tab = ttk.Frame(nb, padding=12)
    nb.add(tab, text="Identifiers")
    s = students.get_student(sid)
    vars_ = {k: tk.StringVar(value=getattr(s, k) or "")
             for k in ("uln", "uci", "candidate_number")}
    for row, (key, label, hint) in enumerate((
            ("uln", "ULN", "10 digits, LRS check digit verified"),
            ("uci", "UCI", "13 characters — format checked only; the JCQ check "
                           "character is NOT verified"),
            ("candidate_number", "Candidate number", "4 digits"))):
        ttk.Label(tab, text=label).grid(row=row, column=0, sticky="e", padx=(0, 8), pady=4)
        ttk.Entry(tab, textvariable=vars_[key], width=20).grid(row=row, column=1, sticky="w")
        ttk.Label(tab, text=hint, foreground="#555").grid(row=row, column=2, sticky="w", padx=8)
    result = ttk.Label(tab)
    result.grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 0))

    def check_uln() -> None:
        u = vars_["uln"].get().strip()
        ok = identifiers.is_valid_uln(u)
        result.configure(text=f"ULN {u}: {'valid' if ok else 'INVALID'}",
                         foreground="#1a7f37" if ok else "#b42318")

    def save() -> None:
        out = _run(win, lambda: students.set_identifiers(
            sid, uln=vars_["uln"].get(), uci=vars_["uci"].get(),
            candidate_number=vars_["candidate_number"].get()), "Identifiers saved.")
        if out is not None:
            for k in vars_:
                vars_[k].set(getattr(out, k) or "")

    bar = ttk.Frame(tab)
    bar.grid(row=3, column=1, sticky="w", pady=(8, 0))
    ttk.Button(bar, text="Save", command=save).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Check ULN", command=check_uln).pack(side="left")


# ════════════════════════════════════════════════════════════════════
# Option blocks (college-wide)
# ════════════════════════════════════════════════════════════════════

def open_option_blocks(parent: tk.Misc) -> tk.Toplevel:
    win = _window(parent, "Option Blocks")
    body = ttk.Frame(win, padding=10)
    body.pack(fill="both", expand=True)
    ttk.Label(body, text="Option Blocks", font=("", 15, "bold")).pack(anchor="w")
    ttk.Label(body, foreground="#555", text=(
        "Subjects in the same block are taught at the same time: a learner "
        "takes at most one subject per block.")).pack(anchor="w")
    bar = ttk.Frame(body)
    bar.pack(fill="x", pady=6)
    years = option_blocks.list_years() or [_current_year()]
    year_var = tk.StringVar(value=years[0])
    ttk.Label(bar, text="Academic year:").pack(side="left")
    ycb = ttk.Combobox(bar, textvariable=year_var, values=years, width=10)
    ycb.pack(side="left", padx=(4, 12))
    tree = _table(body, [("block", "Block", 60), ("subject", "Subject", 240),
                         ("type", "Qualification", 180), ("cap", "Capacity", 80),
                         ("chosen", "Chosen by", 90)])

    def refresh() -> None:
        try:
            rows = option_blocks.block_uptake(year_var.get().strip())
        except _ERRORS as e:
            messagebox.showerror("Option blocks", str(e), parent=win)
            return
        _fill(tree, [(str(e.entry_id), (e.block_letter, e.subject,
                                        e.qualification_type, e.capacity, n))
                     for e, n in rows])
        ycb.configure(values=option_blocks.list_years() or [year_var.get()])

    def add() -> None:
        v = _form(win, "Add subject to block", [
            ("block_letter", "Block *", "A", list(option_blocks.BLOCK_LETTERS)),
            ("subject", "Subject *", "", ("edit", _subject_names())),
            ("qualification_type", "Qualification type", "",
             ["", *grade_scales.QUALIFICATION_TYPES]),
            ("capacity", "Capacity", "", None)])
        if v:
            _run(win, lambda: option_blocks.add_block_subject(
                year_var.get().strip(), v["block_letter"], v["subject"],
                qualification_type=v["qualification_type"] or None,
                capacity=v["capacity"]), after=refresh)

    def remove() -> None:
        eid = _selected(tree, win, "a block entry")
        if eid:
            _run(win, lambda: option_blocks.remove_block_subject(int(eid)), after=refresh)

    def copy() -> None:
        v = _form(win, "Copy blocks", [("to_year", "Copy this year's blocks to", "", None)])
        if v:
            n = _run(win, lambda: option_blocks.copy_blocks(year_var.get().strip(),
                                                            v["to_year"]))
            if n is not None:
                messagebox.showinfo("Copied", f"{n} block entr(ies) copied.", parent=win)

    def clash() -> None:
        v = _form(win, "Check a subject combination", [
            ("subjects", "Subjects (comma separated)", "", None)])
        if not v:
            return
        assignment, reasons = option_blocks.find_block_assignment(
            year_var.get().strip(), v["subjects"].split(","))
        messagebox.showinfo("Combination", (
            "Fits: " + ", ".join(f"block {b} = {s}" for b, s in assignment.items())
            if assignment else "\n".join(reasons)), parent=win)

    ycb.bind("<<ComboboxSelected>>", lambda _e: refresh())
    for text, cmd in (("Load", refresh), ("Add subject", add), ("Remove", remove),
                      ("Copy to year", copy), ("Check combination", clash)):
        ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=(0, 6))
    refresh()
    return win


# ════════════════════════════════════════════════════════════════════
# College-wide programme reports
# ════════════════════════════════════════════════════════════════════

def open_programme_reports(parent: tk.Misc, *, tab: str | None = None) -> tk.Toplevel:
    win = _window(parent, "Study Programme Reports")
    nb = SidebarBook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    def student_click(tree: ttk.Treeview) -> None:
        sel = tree.selection()
        if sel:
            open_study_programme(win, sel[0].split("|")[0])

    # Condition of funding
    cof = ttk.Frame(nb, padding=8)
    nb.add(cof, text="Condition of Funding")
    cbar = ttk.Frame(cof)
    cbar.pack(fill="x")
    only_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(cbar, text="Non-compliant only", variable=only_var).pack(side="left")
    csum = ttk.Label(cof, foreground="#555")
    csum.pack(anchor="w")
    ctree = _table(cof, [("sid", "Student", 90), ("name", "Name", 180),
                         ("eng", "English", 380), ("mat", "Maths", 380),
                         ("att", "Resit attendance", 140)])

    def cof_refresh() -> None:
        rows = prior_attainment.compliance_report(only_non_compliant=only_var.get())
        out = []
        for r in rows:
            c = r.condition
            att = ", ".join(f"{a.area} {a.resit_attendance_pct}%" for a in c.areas
                            if a.resit_attendance_pct is not None)
            out.append((r.student_id, (r.student_id, r.student_name, c.english.status,
                                       c.maths.status, att)))
        _fill(ctree, out)
        csum.configure(text=f"{len(rows)} learner(s) listed.")

    ttk.Button(cbar, text="Run", command=cof_refresh).pack(side="left", padx=8)
    ttk.Button(cbar, text="Open learner", command=lambda: student_click(ctree)).pack(side="left")

    # Funding bands
    bands = ttk.Frame(nb, padding=8)
    nb.add(bands, text="Planned Hours & Bands")
    bbar = ttk.Frame(bands)
    bbar.pack(fill="x")
    byear = tk.StringVar(value=_current_year())
    ttk.Label(bbar, text="Funding year:").pack(side="left")
    ttk.Entry(bbar, textvariable=byear, width=9).pack(side="left", padx=(4, 8))
    bsum = ttk.Label(bands, foreground="#555")
    bsum.pack(anchor="w")
    btree = _table(bands, [("sid", "Student", 90), ("name", "Name", 200),
                           ("age", "Age 31 Aug", 80), ("qual", "Qualification h", 110),
                           ("nq", "Non-qual h", 90), ("total", "Total h", 80),
                           ("band", "Band", 80), ("aims", "Aims", 400)])

    def bands_refresh() -> None:
        try:
            rows = study_programme.band_report(byear.get().strip() or None)
        except _ERRORS as e:
            messagebox.showerror("Bands", str(e), parent=win)
            return
        _fill(btree, [(r.student_id, (
            r.student_id, r.student_name, r.hours.age_on_31_august,
            r.hours.qualification_hours, r.hours.non_qualification_hours,
            r.hours.total_hours, r.hours.band,
            ", ".join(a.aim.label for a in r.hours.aims if a.counted)))
            for r in rows])
        counts = study_programme.band_counts(rows)
        bsum.configure(text="  ".join(f"{b}: {n}" for b, n in counts.items())
                       + "   (bands must be checked against current ESFA guidance)")

    ttk.Button(bbar, text="Run", command=bands_refresh).pack(side="left", padx=8)
    ttk.Button(bbar, text="Open learner", command=lambda: student_click(btree)).pack(side="left")

    # Withdrawals / qualifying period
    wd = ttk.Frame(nb, padding=8)
    nb.add(wd, text="Withdrawals & Qualifying Period")
    wbar = ttk.Frame(wd)
    wbar.pack(fill="x")
    before_var = tk.BooleanVar(value=False)
    wyear = tk.StringVar(value="")
    ttk.Label(wbar, text="Academic year (blank = all):").pack(side="left")
    ttk.Entry(wbar, textvariable=wyear, width=9).pack(side="left", padx=(4, 8))
    ttk.Checkbutton(wbar, text="Withdrawn before qualifying period only",
                    variable=before_var).pack(side="left")
    wsum = ttk.Label(wd, foreground="#555")
    wsum.pack(anchor="w")
    wtree = _table(wd, [("sid", "Student", 90), ("name", "Name", 170),
                        ("aim", "Aim", 230), ("status", "Status", 90),
                        ("start", "Start", 90), ("left", "Last day", 90),
                        ("days", "Days", 60), ("qp", "QP days", 60),
                        ("met", "Qualified", 80), ("reason", "Reason", 220),
                        ("by", "Approved by", 110)])

    def wd_refresh() -> None:
        rows = learning_aims.withdrawals(academic_year=wyear.get().strip() or None,
                                         only_before_qualifying=before_var.get())
        _fill(wtree, [(f"{r.aim.student_id}|{r.aim.aim_id}", (
            r.aim.student_id, r.student_name, r.aim.label, r.aim.status,
            r.aim.start_date, r.aim.withdrawal_date, r.check.days_in_learning,
            r.check.qualifying_days, "Yes" if r.check.met else "NO",
            r.aim.withdrawal_reason, r.approved_by)) for r in rows])
        wsum.configure(text=f"{len(rows)} withdrawn / transferred aim(s); "
                            f"{sum(1 for r in rows if r.check.withdrawn_before_qualifying)} "
                            "before the qualifying period.")

    ttk.Button(wbar, text="Run", command=wd_refresh).pack(side="left", padx=8)
    ttk.Button(wbar, text="Open learner", command=lambda: student_click(wtree)).pack(side="left")

    # Aims by qualification
    aims = ttk.Frame(nb, padding=8)
    nb.add(aims, text="Aims by Qualification")
    abar = ttk.Frame(aims)
    abar.pack(fill="x")
    atree = _table(aims, [("type", "Qualification", 220), ("subject", "Subject", 240),
                          ("active", "Active", 80), ("withdrawn", "Withdrawn", 90),
                          ("completed", "Completed", 90), ("transferred", "Transferred", 90)])

    def aims_refresh() -> None:
        n = learning_aims.backfill_all()
        tally: dict[tuple[str, str], dict[str, int]] = {}
        for a in learning_aims.list_all_aims(status=None):
            t = tally.setdefault((a.qualification_type, a.subject),
                                 {s: 0 for s in learning_aims.STATUSES})
            t[a.status] = t.get(a.status, 0) + 1
        _fill(atree, [(f"{k[0]}|{k[1]}", (k[0], k[1], v["Active"], v["Withdrawn"],
                                          v["Completed"], v["Transferred"]))
                      for k, v in sorted(tally.items())])
        if n:
            messagebox.showinfo("Backfill", f"{n} aim(s) backfilled from subject slots.",
                                parent=win)

    ttk.Button(abar, text="Run (backfills any learner not yet converted)",
               command=aims_refresh).pack(side="left")

    order = {"cof": 0, "bands": 1, "withdrawals": 2, "aims": 3}
    if tab in order:
        nb.select(order[tab])
    return win
