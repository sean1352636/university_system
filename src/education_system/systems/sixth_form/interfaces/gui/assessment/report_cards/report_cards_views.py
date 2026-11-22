"""Staff GUI for Sixth Form report cards.

:class:`ReportCardsPanel` is a four-tab notebook that can sit in its own
window (:func:`open_report_cards_window`, the "Report Cards" entry) or
inside another window's notebook (:func:`add_report_cards_tab`, used by
the Grades Report window):

* **Periods & Templates** — set up report periods and templates, and
  generate the cards for a period.
* **Comment Entry** — a teacher's lines for their own classes (leads can
  show every line), plus tutor comments for their tutees.
* **Completion** — per-learner and per-teacher progress, for chasing.
* **Review & Publish** — the head of sixth form's comment, approve or
  return, publish through the bulk operation, render files.

Who may do what is decided by the domain module (``report_cards``); the
screen just reports its refusals.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox, simpledialog
from typing import Any, Callable

from education_system.platform.delivery.gui import window_sizing
from education_system.systems.sixth_form.domain.assessment.report_cards import (
    report_cards as data,
)
from education_system.platform.delivery.gui.parented_dialogs import make_toplevel

logger = logging.getLogger(__name__)


def _principal():
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return access.current()


def _table(parent, columns, *, height: int = 12) -> ttk.Treeview:
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings",
                        height=height)
    for key, title, width in columns:
        tree.heading(key, text=title)
        tree.column(key, width=width, anchor="w")
    bar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=bar.set)
    tree.pack(side="left", fill="both", expand=True)
    bar.pack(side="right", fill="y")
    return tree


def _d(v: Any) -> str:
    return "—" if v in (None, "") else str(v)


class _PeriodPicker(ttk.Frame):
    """A period combobox that calls back when the choice changes."""

    def __init__(self, parent, on_change: Callable[[], None]) -> None:
        super().__init__(parent)
        ttk.Label(self, text="Report period:").pack(side="left")
        self.var = tk.StringVar()
        self.box = ttk.Combobox(self, textvariable=self.var, state="readonly", width=40)
        self.box.pack(side="left", padx=4)
        self._map: dict[str, int] = {}
        self.var.trace_add("write", lambda *_: on_change())
        self.reload()

    def reload(self) -> None:
        current = self.var.get()
        self._map = {f"{p.label} ({p.status})": p.period_id for p in data.list_periods()}
        self.box.configure(values=list(self._map))
        if current in self._map:
            return
        if self._map:
            self.var.set(next(iter(self._map)))

    @property
    def period_id(self) -> int | None:
        return self._map.get(self.var.get())


class ReportCardsPanel:
    """The report-card workflow, built into ``parent``."""

    def __init__(self, parent: tk.Misc) -> None:
        data.init_db()
        self.parent = parent
        self.nb = ttk.Notebook(parent)
        self.nb.pack(fill="both", expand=True)
        self._build_setup()
        self._build_entry()
        self._build_completion()
        self._build_review()

    def _err(self, title: str, exc: Exception) -> None:
        messagebox.showerror(title, str(exc), parent=self.parent)

    def _reload_pickers(self) -> None:
        for p in (self.entry_pick, self.comp_pick, self.rev_pick):
            p.reload()

    # ── Periods & templates ──────────────────────────────────────────

    def _build_setup(self) -> None:
        f = ttk.Frame(self.nb, padding=8)
        self.nb.add(f, text="Periods & Templates")
        pbox = ttk.LabelFrame(f, text="Report periods", padding=6)
        pbox.pack(fill="both", expand=True)
        bar = ttk.Frame(pbox)
        bar.pack(fill="x", pady=(0, 4))
        self.period_tree = _table(pbox, (
            ("id", "#", 40), ("label", "Label", 200), ("year", "Year", 90),
            ("start", "Start", 100), ("end", "End", 100), ("due", "Comments due", 110),
            ("template", "Template", 220), ("status", "Status", 90)), height=8)
        for text, cmd in (("New…", self._new_period), ("Edit…", self._edit_period),
                          ("Generate cards", self._generate),
                          ("Open", lambda: self._period_status(data.PERIOD_OPEN)),
                          ("Close entry", lambda: self._period_status(data.PERIOD_CLOSED)),
                          ("Delete", self._delete_period)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=(0, 4))

        tbox = ttk.LabelFrame(f, text="Templates", padding=6)
        tbox.pack(fill="both", expand=True, pady=(8, 0))
        tbar = ttk.Frame(tbox)
        tbar.pack(fill="x", pady=(0, 4))
        self.template_tree = _table(tbox, (
            ("id", "#", 40), ("name", "Name", 240), ("sections", "Sections", 520),
            ("effort", "Effort scale", 260), ("attitude", "Attitude scale", 260)),
            height=5)
        ttk.Button(tbar, text="New…", command=lambda: self._template_dialog(None)).pack(
            side="left")
        ttk.Button(tbar, text="Edit…", command=self._edit_template).pack(side="left", padx=4)
        self._refresh_setup()

    def _refresh_setup(self) -> None:
        templates = {t.template_id: t for t in data.list_templates()}
        self.period_tree.delete(*self.period_tree.get_children())
        for p in data.list_periods():
            t = templates.get(p.template_id)
            self.period_tree.insert("", "end", iid=str(p.period_id), values=(
                p.period_id, p.label, _d(p.academic_year), p.start_date, p.end_date,
                _d(p.comments_due), t.name if t else p.template_id, p.status))
        self.template_tree.delete(*self.template_tree.get_children())
        for t in templates.values():
            secs = [label for flag, label in (
                ("include_attendance", "attendance"), ("include_current_grade", "current"),
                ("include_target_grade", "target"), ("include_predicted_grade", "predicted"),
                ("include_effort", "effort"), ("include_attitude", "attitude"),
                ("include_subject_comments", "subject comments"),
                ("include_tutor_comment", "tutor"), ("include_hosf_comment", "HoSF"))
                if getattr(t, flag)]
            self.template_tree.insert("", "end", iid=str(t.template_id), values=(
                t.template_id, t.name, ", ".join(secs), " | ".join(t.effort_scale),
                " | ".join(t.attitude_scale)))

    def _selected_period(self) -> int | None:
        sel = self.period_tree.selection()
        return int(sel[0]) if sel else None

    def _period_dialog(self, existing=None) -> dict | None:
        templates = data.list_templates()
        names = [t.name for t in templates] or [data.DEFAULT_TEMPLATE_NAME]
        win = make_toplevel(self.parent)
        win.title("Report period")
        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)
        fields = (("label", "Label (e.g. 2025/26 Autumn)"), ("academic_year", "Academic year"),
                  ("start_date", "Start (YYYY-MM-DD)"), ("end_date", "End (YYYY-MM-DD)"),
                  ("comments_due", "Comments due (YYYY-MM-DD)"))
        vars_ = {}
        for r, (k, label) in enumerate(fields):
            ttk.Label(frm, text=label).grid(row=r, column=0, sticky="w", pady=2)
            v = tk.StringVar(value=(getattr(existing, k) or "") if existing else "")
            ttk.Entry(frm, textvariable=v, width=36).grid(row=r, column=1, pady=2)
            vars_[k] = v
        ttk.Label(frm, text="Template").grid(row=len(fields), column=0, sticky="w")
        tvar = tk.StringVar()
        ttk.Combobox(frm, textvariable=tvar, values=names, state="readonly",
                     width=34).grid(row=len(fields), column=1, pady=2)
        if existing:
            tvar.set(next((t.name for t in templates
                           if t.template_id == existing.template_id), names[0]))
        else:
            tvar.set(names[0])
        out: dict = {}

        def ok() -> None:
            out.update({k: v.get().strip() for k, v in vars_.items()})
            t = next((t for t in templates if t.name == tvar.get()), None)
            out["template_id"] = t.template_id if t else None
            win.destroy()
        ttk.Button(frm, text="Save", command=ok).grid(row=len(fields) + 1, column=1,
                                                      sticky="e", pady=(8, 0))
        win.transient(self.parent.winfo_toplevel())
        self.parent.wait_window(win)
        return out or None

    def _new_period(self) -> None:
        vals = self._period_dialog()
        if not vals:
            return
        try:
            data.create_period(vals, by=_principal())
        except data.ValidationError as e:
            return self._err("New period", e)
        self._refresh_setup()
        self._reload_pickers()

    def _edit_period(self) -> None:
        pid = self._selected_period()
        if pid is None:
            return
        vals = self._period_dialog(data.get_period(pid))
        if not vals:
            return
        try:
            data.update_period(pid, vals, by=_principal())
        except data.ValidationError as e:
            return self._err("Edit period", e)
        self._refresh_setup()
        self._reload_pickers()

    def _generate(self) -> None:
        pid = self._selected_period()
        if pid is None:
            messagebox.showinfo("Generate", "Choose a period first.", parent=self.parent)
            return
        try:
            res = data.generate_cards(pid, by=_principal())
        except data.ValidationError as e:
            return self._err("Generate cards", e)
        messagebox.showinfo("Generate cards",
                            f"{res['created']} new cards, {res['lines_added']} subject "
                            f"lines added, {res['skipped']} skipped (approved or unknown).",
                            parent=self.parent)

    def _period_status(self, status: str) -> None:
        pid = self._selected_period()
        if pid is None:
            return
        try:
            data.set_period_status(pid, status, by=_principal())
        except data.ValidationError as e:
            return self._err("Period", e)
        self._refresh_setup()
        self._reload_pickers()

    def _delete_period(self) -> None:
        pid = self._selected_period()
        if pid is None or not messagebox.askyesno(
                "Delete period", "Delete this period and all its draft cards?",
                parent=self.parent):
            return
        try:
            data.delete_period(pid, by=_principal())
        except data.ValidationError as e:
            return self._err("Delete period", e)
        self._refresh_setup()
        self._reload_pickers()

    def _edit_template(self) -> None:
        sel = self.template_tree.selection()
        if sel:
            self._template_dialog(data.get_template(int(sel[0])))

    def _template_dialog(self, existing) -> None:
        win = make_toplevel(self.parent)
        win.title("Report template")
        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)
        name = tk.StringVar(value=existing.name if existing else "")
        ttk.Label(frm, text="Name").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=name, width=50).grid(row=0, column=1, sticky="w")
        flags = {}
        for r, (flag, label) in enumerate((
                ("include_attendance", "Attendance %"),
                ("include_current_grade", "Current grade"),
                ("include_target_grade", "Target grade"),
                ("include_predicted_grade", "Predicted grade"),
                ("include_effort", "Effort"), ("include_attitude", "Attitude"),
                ("include_subject_comments", "Teacher comment per subject"),
                ("include_tutor_comment", "Tutor comment"),
                ("include_hosf_comment", "Head of sixth form comment")), 1):
            v = tk.BooleanVar(value=getattr(existing, flag) if existing else True)
            ttk.Checkbutton(frm, text=label, variable=v).grid(row=r, column=1, sticky="w")
            flags[flag] = v
        row = len(flags) + 1
        scales = {}
        for i, (key, label, default) in enumerate((
                ("effort_scale", "Effort scale (one per line)",
                 existing.effort_scale if existing else data.DEFAULT_EFFORT_SCALE),
                ("attitude_scale", "Attitude scale (one per line)",
                 existing.attitude_scale if existing else data.DEFAULT_ATTITUDE_SCALE))):
            ttk.Label(frm, text=label).grid(row=row + i, column=0, sticky="nw", pady=4)
            t = tk.Text(frm, width=48, height=4)
            t.insert("1.0", "\n".join(default))
            t.grid(row=row + i, column=1, sticky="w", pady=4)
            scales[key] = t
        ttk.Label(frm, text="Comment length limit").grid(row=row + 2, column=0, sticky="w")
        cmax = tk.StringVar(value=str(existing.comment_max_chars if existing
                                      else data.DEFAULT_COMMENT_MAX))
        ttk.Entry(frm, textvariable=cmax, width=8).grid(row=row + 2, column=1, sticky="w")
        ttk.Label(frm, text="Intro text").grid(row=row + 3, column=0, sticky="nw")
        intro = tk.Text(frm, width=48, height=3)
        intro.insert("1.0", (existing.intro_text or "") if existing else "")
        intro.grid(row=row + 3, column=1, sticky="w")

        def save() -> None:
            payload = {"name": name.get(), "intro_text": intro.get("1.0", "end"),
                       "comment_max_chars": cmax.get(),
                       **{k: v.get() for k, v in flags.items()},
                       **{k: t.get("1.0", "end") for k, t in scales.items()}}
            try:
                if existing:
                    data.update_template(existing.template_id, payload, by=_principal())
                else:
                    data.create_template(payload, by=_principal())
            except data.ValidationError as e:
                messagebox.showerror("Template", str(e), parent=win)
                return
            win.destroy()
            self._refresh_setup()
        ttk.Button(frm, text="Save", command=save).grid(row=row + 4, column=1, sticky="e",
                                                        pady=(8, 0))

    # ── Comment entry ────────────────────────────────────────────────

    def _build_entry(self) -> None:
        f = ttk.Frame(self.nb, padding=8)
        self.nb.add(f, text="Comment Entry")
        top = ttk.Frame(f)
        top.pack(fill="x")
        self.entry_pick = _PeriodPicker(top, self._refresh_entry)
        self.entry_pick.pack(side="left")
        self.all_lines = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Show every line (report leads)",
                        variable=self.all_lines,
                        command=self._refresh_entry).pack(side="left", padx=10)
        ttk.Button(top, text="Refresh", command=self._refresh_entry).pack(side="left")

        panes = ttk.Panedwindow(f, orient="horizontal")
        panes.pack(fill="both", expand=True, pady=(6, 0))
        left, right = ttk.Frame(panes), ttk.Frame(panes, padding=(8, 0, 0, 0))
        panes.add(left, weight=3)
        panes.add(right, weight=2)
        lbox = ttk.LabelFrame(left, text="My subject lines", padding=4)
        lbox.pack(fill="both", expand=True)
        self.line_tree = _table(lbox, (
            ("subject", "Subject", 150), ("student", "Learner", 170),
            ("grade", "Current", 70), ("effort", "Effort", 110),
            ("attitude", "Attitude", 120), ("done", "Comment", 70),
            ("status", "Card", 80)), height=14)
        tbox = ttk.LabelFrame(left, text="My tutees (tutor comment)", padding=4)
        tbox.pack(fill="both", expand=True, pady=(6, 0))
        self.tutee_tree = _table(tbox, (("student", "Learner", 220),
                                        ("done", "Tutor comment", 120),
                                        ("status", "Card", 100)), height=6)

        form = ttk.LabelFrame(right, text="Entry", padding=8)
        form.pack(fill="both", expand=True)
        self.form_title = tk.StringVar(value="Select a line or a tutee")
        ttk.Label(form, textvariable=self.form_title, font=("", 11, "bold"),
                  wraplength=420).pack(anchor="w")
        row = ttk.Frame(form)
        row.pack(fill="x", pady=4)
        self.grade_var, self.effort_var, self.att_var = (tk.StringVar(), tk.StringVar(),
                                                         tk.StringVar())
        ttk.Label(row, text="Current grade").grid(row=0, column=0, sticky="w")
        self.grade_box = ttk.Combobox(row, textvariable=self.grade_var, width=14)
        self.grade_box.grid(row=0, column=1, sticky="w", padx=4)
        ttk.Label(row, text="Effort").grid(row=1, column=0, sticky="w")
        self.effort_box = ttk.Combobox(row, textvariable=self.effort_var,
                                       state="readonly", width=30)
        self.effort_box.grid(row=1, column=1, sticky="w", padx=4)
        ttk.Label(row, text="Attitude").grid(row=2, column=0, sticky="w")
        self.att_box = ttk.Combobox(row, textvariable=self.att_var, state="readonly",
                                    width=30)
        self.att_box.grid(row=2, column=1, sticky="w", padx=4)
        ttk.Label(form, text="Comment").pack(anchor="w")
        self.comment = tk.Text(form, wrap="word", height=12)
        self.comment.pack(fill="both", expand=True)
        self.count_var = tk.StringVar(value="")
        ttk.Label(form, textvariable=self.count_var, foreground="#7f8c8d").pack(anchor="e")
        self.comment.bind("<KeyRelease>", lambda _e: self.count_var.set(
            f"{len(self.comment.get('1.0', 'end').strip())} characters"))
        ttk.Button(form, text="Save", command=self._save_entry).pack(anchor="e", pady=4)
        self._editing: tuple[str, int] | None = None
        self.line_tree.bind("<<TreeviewSelect>>", lambda _e: self._pick_line())
        self.tutee_tree.bind("<<TreeviewSelect>>", lambda _e: self._pick_tutee())
        self._lines: dict[int, Any] = {}
        self._refresh_entry()

    def _refresh_entry(self) -> None:
        if not hasattr(self, "line_tree"):
            return
        self.line_tree.delete(*self.line_tree.get_children())
        self.tutee_tree.delete(*self.tutee_tree.get_children())
        pid = self.entry_pick.period_id
        if pid is None:
            return
        p = _principal()
        try:
            lines = data.lines_for_teacher(pid, by=p, all_lines=self.all_lines.get())
        except data.ValidationError as e:
            self.all_lines.set(False)
            self._err("Comment entry", e)
            lines = data.lines_for_teacher(pid, by=p)
        self._lines = {tl.line.line_id: tl for tl in lines}
        for tl in lines:
            ln = tl.line
            self.line_tree.insert("", "end", iid=str(ln.line_id), values=(
                ln.subject, tl.student_name, _d(ln.current_grade), _d(ln.effort),
                _d(ln.attitude), "yes" if ln.comment else "—", tl.card_status))
        for c in data.cards_for_tutor(pid, by=p):
            self.tutee_tree.insert("", "end", iid=str(c.card_id), values=(
                c.student_name or c.student_id, "yes" if c.tutor_comment else "—",
                c.status))

    def _set_comment(self, text: str | None) -> None:
        self.comment.delete("1.0", "end")
        self.comment.insert("1.0", text or "")
        self.count_var.set(f"{len((text or '').strip())} characters")

    def _pick_line(self) -> None:
        sel = self.line_tree.selection()
        if not sel:
            return
        tl = self._lines.get(int(sel[0]))
        if tl is None:
            return
        ln = tl.line
        period = data.get_period(self.entry_pick.period_id)
        tmpl = data.get_template(period.template_id) if period else None
        from education_system.systems.sixth_form.domain.academics.qualifications import (
            grade_scales as _gs,
        )
        self.grade_box.configure(values=list(_gs.grades_for(ln.qualification_type)),
                                 state="normal")
        self.effort_box.configure(values=list(tmpl.effort_scale) if tmpl else [],
                                  state="readonly")
        self.att_box.configure(values=list(tmpl.attitude_scale) if tmpl else [],
                               state="readonly")
        self.grade_var.set(ln.current_grade or "")
        self.effort_var.set(ln.effort or "")
        self.att_var.set(ln.attitude or "")
        self._set_comment(ln.comment)
        self.form_title.set(f"{ln.subject} — {tl.student_name}   "
                            f"(target {_d(ln.target_grade)}, predicted "
                            f"{_d(ln.predicted_grade)})")
        self._editing = ("line", ln.line_id)

    def _pick_tutee(self) -> None:
        sel = self.tutee_tree.selection()
        if not sel:
            return
        card = data.get_card(int(sel[0]))
        if card is None:
            return
        for box in (self.grade_box, self.effort_box, self.att_box):
            box.configure(state="disabled")
        self.grade_var.set("")
        self.effort_var.set("")
        self.att_var.set("")
        self._set_comment(card.tutor_comment)
        self.form_title.set(f"Tutor comment — {card.student_name or card.student_id}")
        self._editing = ("tutor", card.card_id)

    def _save_entry(self) -> None:
        if self._editing is None:
            return
        kind, ident = self._editing
        text = self.comment.get("1.0", "end").strip()
        try:
            if kind == "line":
                data.save_subject_entry(ident, current_grade=self.grade_var.get(),
                                        effort=self.effort_var.get(),
                                        attitude=self.att_var.get(), comment=text,
                                        by=_principal())
            else:
                data.save_tutor_comment(ident, text, by=_principal())
        except data.ValidationError as e:
            return self._err("Save", e)
        self._refresh_entry()
        try:
            tree = self.line_tree if kind == "line" else self.tutee_tree
            tree.selection_set(str(ident))
        except tk.TclError:
            pass

    # ── Completion ───────────────────────────────────────────────────

    def _build_completion(self) -> None:
        f = ttk.Frame(self.nb, padding=8)
        self.nb.add(f, text="Completion")
        top = ttk.Frame(f)
        top.pack(fill="x")
        self.comp_pick = _PeriodPicker(top, self._refresh_completion)
        self.comp_pick.pack(side="left")
        ttk.Button(top, text="Refresh", command=self._refresh_completion).pack(
            side="left", padx=6)
        self.comp_summary = tk.StringVar()
        ttk.Label(top, textvariable=self.comp_summary).pack(side="left", padx=10)
        panes = ttk.Panedwindow(f, orient="horizontal")
        panes.pack(fill="both", expand=True, pady=(6, 0))
        left, right = ttk.Frame(panes), ttk.Frame(panes)
        panes.add(left, weight=3)
        panes.add(right, weight=1)
        self.comp_tree = _table(left, (("student", "Learner", 200),
                                       ("status", "Card", 90),
                                       ("progress", "Progress", 260),
                                       ("missing", "Outstanding", 520)))
        self.teacher_tree = _table(right, (("teacher", "Teacher", 160),
                                           ("done", "Done", 60), ("owed", "Outstanding", 90)))
        self._refresh_completion()

    def _refresh_completion(self) -> None:
        if not hasattr(self, "comp_tree"):
            return
        self.comp_tree.delete(*self.comp_tree.get_children())
        self.teacher_tree.delete(*self.teacher_tree.get_children())
        pid = self.comp_pick.period_id
        if pid is None:
            self.comp_summary.set("")
            return
        for c in data.completion(pid):
            self.comp_tree.insert("", "end", values=(
                c.student_name or c.student_id, c.status, c.label,
                "; ".join(c.missing) or "complete"))
        for t in data.teacher_progress(pid):
            self.teacher_tree.insert("", "end", values=(t.teacher, t.lines_done,
                                                        t.outstanding))
        s = data.period_summary(pid)
        self.comp_summary.set(f"{s['complete']}/{s['cards']} complete · "
                              f"{s['approved']} approved · {s['published']} published")

    # ── Review & publish ─────────────────────────────────────────────

    def _build_review(self) -> None:
        f = ttk.Frame(self.nb, padding=8)
        self.nb.add(f, text="Review & Publish")
        top = ttk.Frame(f)
        top.pack(fill="x")
        self.rev_pick = _PeriodPicker(top, self._refresh_review)
        self.rev_pick.pack(side="left")
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=6)
        for text, cmd in (
                ("Refresh", self._refresh_review),
                ("HoSF comment…", self._hosf_comment),
                ("Submit for review", lambda: self._card_action(data.submit_for_review)),
                ("Return for changes…", self._return_card),
                ("Approve", lambda: self._card_action(data.approve)),
                ("Approve all complete", self._approve_all),
                ("Reopen", lambda: self._card_action(data.reopen)),
                ("Update data", lambda: self._card_action(data.refresh_card_data)),
                ("Publish approved", self._publish),
                ("Unpublish…", self._unpublish),
                ("Save files…", self._render)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=(0, 4))
        panes = ttk.Panedwindow(f, orient="horizontal")
        panes.pack(fill="both", expand=True)
        left, right = ttk.Frame(panes), ttk.Frame(panes)
        panes.add(left, weight=2)
        panes.add(right, weight=3)
        self.rev_tree = _table(left, (("student", "Learner", 200),
                                      ("status", "Status", 90),
                                      ("note", "Review note", 260)))
        self.preview = tk.Text(right, wrap="word", state="disabled", padx=8, pady=8)
        self.preview.pack(fill="both", expand=True)
        self.rev_tree.bind("<<TreeviewSelect>>", lambda _e: self._preview_card())
        self._refresh_review()

    def _refresh_review(self) -> None:
        if not hasattr(self, "rev_tree"):
            return
        self.rev_tree.delete(*self.rev_tree.get_children())
        pid = self.rev_pick.period_id
        if pid is None:
            return
        for c in data.list_cards(pid):
            self.rev_tree.insert("", "end", iid=str(c.card_id), values=(
                c.student_name or c.student_id, c.status, _d(c.review_note)))

    def _selected_cards(self) -> list[int]:
        return [int(i) for i in self.rev_tree.selection()]

    def _preview_card(self) -> None:
        ids = self._selected_cards()
        if not ids:
            return
        card = data.get_card(ids[0])
        text = data.render_text(card) if card else ""
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)
        self.preview.configure(state="disabled")

    def _card_action(self, fn) -> None:
        ids = self._selected_cards()
        if not ids:
            messagebox.showinfo("Report cards", "Select one or more learners.",
                                parent=self.parent)
            return
        problems = []
        for cid in ids:
            try:
                fn(cid, by=_principal())
            except data.ValidationError as e:
                card = data.get_card(cid)
                problems.append(f"{(card.student_name if card else cid)}: {e}")
        self._refresh_review()
        if problems:
            messagebox.showwarning("Report cards", "\n".join(problems[:20]),
                                   parent=self.parent)

    def _hosf_comment(self) -> None:
        ids = self._selected_cards()
        if len(ids) != 1:
            messagebox.showinfo("HoSF comment", "Select one learner.", parent=self.parent)
            return
        card = data.get_card(ids[0])
        text = simpledialog.askstring(
            "Head of sixth form comment", f"Comment for {card.student_name}:",
            initialvalue=card.hosf_comment or "", parent=self.parent)
        if text is None:
            return
        try:
            data.save_hosf_comment(card.card_id, text, by=_principal())
        except data.ValidationError as e:
            return self._err("HoSF comment", e)
        self._refresh_review()
        self.rev_tree.selection_set(str(card.card_id))

    def _return_card(self) -> None:
        note = simpledialog.askstring("Return for changes", "What needs changing?",
                                      parent=self.parent)
        if not note:
            return
        self._card_action(lambda cid, by: data.return_for_changes(cid, note, by=by))

    def _approve_all(self) -> None:
        pid = self.rev_pick.period_id
        if pid is None:
            return
        try:
            n, problems = data.approve_all_complete(pid, by=_principal())
        except data.ValidationError as e:
            return self._err("Approve", e)
        self._refresh_review()
        msg = f"{n} report(s) approved."
        if problems:
            msg += f"\n\nNot approved ({len(problems)}):\n" + "\n".join(problems[:15])
        messagebox.showinfo("Approve", msg, parent=self.parent)

    def _publish(self) -> None:
        pid = self.rev_pick.period_id
        if pid is None:
            return
        ids = self._selected_cards()
        students = None
        if ids:
            students = [data.get_card(i).student_id for i in ids]
        if not messagebox.askyesno(
                "Publish", "Publish the " + ("selected" if ids else "approved")
                + " reports to learners and parents?", parent=self.parent):
            return
        try:
            res = data.publish(pid, student_ids=students, by=_principal())
        except data.ValidationError as e:
            return self._err("Publish", e)
        msg = f"Published {res.success_count} of {res.target_count}."
        if res.failures:
            msg += "\n\n" + "\n".join(f"{s}: {r}" for s, r in res.failures[:15])
        messagebox.showinfo("Publish", msg, parent=self.parent)
        self._refresh_review()
        self._reload_pickers()

    def _unpublish(self) -> None:
        pid = self.rev_pick.period_id
        if pid is None:
            return
        ids = self._selected_cards()
        students = [data.get_card(i).student_id for i in ids] if ids else None
        if not messagebox.askyesno(
                "Unpublish", "Withdraw the " + ("selected" if ids else "published")
                + " reports from the portals?", parent=self.parent):
            return
        try:
            res = data.unpublish(pid, student_ids=students, by=_principal())
        except data.ValidationError as e:
            return self._err("Unpublish", e)
        messagebox.showinfo("Unpublish", f"Withdrew {res.success_count}.",
                            parent=self.parent)
        self._refresh_review()
        self._reload_pickers()

    def _render(self) -> None:
        pid = self.rev_pick.period_id
        if pid is None:
            return
        fmt = simpledialog.askstring(
            "Save files", "Format: html, txt or pdf"
            + ("" if data.pdf_available() else " (pdf needs reportlab)"),
            initialvalue="html", parent=self.parent)
        if not fmt:
            return
        try:
            files = data.render_period(pid, fmt=fmt.strip().lower(), by=_principal())
        except data.ValidationError as e:
            return self._err("Save files", e)
        where = files[0].parent if files else data.OUTPUT_DIR
        messagebox.showinfo("Save files", f"Wrote {len(files)} file(s) to\n{where}",
                            parent=self.parent)


def add_report_cards_tab(nb: ttk.Notebook, *, text: str = "Report Cards") -> ReportCardsPanel:
    """Add the report-card workflow as a tab of an existing notebook."""
    frame = ttk.Frame(nb, padding=4)
    nb.add(frame, text=text)
    return ReportCardsPanel(frame)


def open_report_cards_window(parent=None) -> None:
    """Standalone window — the "Report Cards" menu entry."""
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title("Report Cards")
    window_sizing.fit(win, "1400x900", (1200, 800))
    frame = ttk.Frame(win, padding=10)
    frame.pack(fill="both", expand=True)
    ReportCardsPanel(frame)
