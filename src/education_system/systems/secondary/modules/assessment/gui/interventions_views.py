"""Interventions screen.

The old Intervention Tracking window is the first tab, with its toolbar
(Year / Status / Type with Apply, New, Edit, Status, Reviews, Summary,
Delete, Refresh) and columns (ID, Pupil, Yr, Subj, Type, Start, Led by,
Freq, Status, Outcome); its Reviews window keeps Add review / Delete
selected / Refresh and the columns ID, Date, Reviewer, Att %, On-track,
Notes, Next action. Added: Sessions, Group…, Refresh grade, History,
Export CSV, Open pupil and the Programme / grade columns.

New tabs: Who needs one? (suggestions from the school's data), Due for
review, and Impact. The rules are in :mod:`modules.assessment.domain.interventions`.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui.parented_dialogs import (
    filedialog,
    make_toplevel,
    messagebox,
)
from education_system.systems.secondary.modules.assessment.domain import interventions as IV
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
YEARS = ("7", "8", "9", "10", "11")
_ERRORS = (IV.ValidationError, IV.PermissionDenied, IV.NotFound)


_problems = W.problems


def _tree(parent, columns, height: int = 16, select: str = "browse") -> ttk.Treeview:
    return W.tree(parent, columns, height=height, select=select,
                  stretch={"pupil", "notes", "reason", "group"}, tags=W.STANDARD_TAGS)


_text_window = W.text_window
_form = W.form_dialog


def _subjects() -> list[str]:
    try:
        return [s.code for s in S.list_subjects()]
    except Exception:  # noqa: BLE001 - the list is a convenience
        logger.exception("subject list")
        return []


class InterventionsPage:
    TABS = ("Interventions", "Who needs one?", "Due for review", "Impact")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        self.editor = IV.is_editor(principal)
        activity_log.record("interventions.view")
        ttk.Label(parent, text="Intervention Tracking", font=("", 16, "bold")).pack(anchor="w")
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(
            anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._built: set[str] = set()
        self.book.select(self.TABS.index(state.get("tab", "Interventions")))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    def _top(self):
        return self.parent.winfo_toplevel()

    def _err(self, title: str, e: Exception) -> None:
        messagebox.showerror(title, _problems(e), parent=self._top())

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        build = {"Interventions": (self._build_list, self.refresh),
                 "Who needs one?": (self._build_suggest, self.refresh_suggest),
                 "Due for review": (self._build_due, self.refresh_due),
                 "Impact": (self._build_impact, self.refresh_impact)}[name]
        if name not in self._built:
            self._built.add(name)
            build[0](self.tabs[name])
        build[1]()

    def _button(self, bar, text: str, command, editor_only: bool = False) -> None:
        b = ttk.Button(bar, text=text, command=command)
        if editor_only and not self.editor:
            b.state(["disabled"])
        b.pack(side="left", padx=2)

    # ── Interventions (old window) ───────────────────────────────────

    def _build_list(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.year = tk.StringVar(value=self.state.get("year", ""))
        self.status = tk.StringVar(value=self.state.get("status", ""))
        self.itype = tk.StringVar(value=self.state.get("type", ""))
        self.mine = tk.BooleanVar(value=self.state.get("mine", False))
        for label, var, values, width in (("Year:", self.year, ["", *YEARS], 5),
                                          ("Status:", self.status,
                                           ["", *IV.INTERVENTION_STATUSES], 10),
                                          ("Type:", self.itype,
                                           ["", *IV.INTERVENTION_TYPES], 14)):
            ttk.Label(bar, text=label).pack(side="left", padx=(0, 4))
            ttk.Combobox(bar, textvariable=var, values=values, state="readonly",
                         width=width).pack(side="left", padx=(0, 6))
        ttk.Checkbutton(bar, text="Mine", variable=self.mine).pack(side="left", padx=(0, 6))
        self._button(bar, "Apply", self.refresh)
        self._button(bar, "New", self.new)
        self._button(bar, "Edit", self.edit)
        self._button(bar, "Status", self.change_status)
        self._button(bar, "Reviews", self.reviews)
        self._button(bar, "Summary", self.summary)
        self._button(bar, "Delete", self.delete, True)
        self._button(bar, "Refresh", self.refresh)
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(0, 6))
        self._button(bar2, "Sessions", self.sessions)
        self._button(bar2, "Group…", self.new_group)
        self._button(bar2, "Group register…", self.group_register)
        self._button(bar2, "Refresh grade", self.refresh_grade)
        self._button(bar2, "History", self.history)
        self._button(bar2, "Export CSV…", self.export)
        if self.open_pupil:
            self._button(bar2, "Open pupil", self.open_selected)
        self.tree = _tree(tab, [
            ("id", "ID", 50), ("pupil", "Pupil", 180), ("year", "Yr", 35),
            ("subj", "Subj", 60), ("type", "Type", 100), ("start", "Start", 85),
            ("led", "Led by", 120), ("freq", "Freq", 85), ("status", "Status", 75),
            ("outcome", "Outcome", 85), ("prog", "Programme", 120),
            ("grades", "Base→Cur (Tgt)", 110)])
        self.tree.bind("<Double-1>", lambda _e: self.edit())
        self.rows: dict[str, IV.Intervention] = {}

    def refresh(self) -> None:
        y, st, ty = self.year.get(), self.status.get(), self.itype.get()
        self.state.update(year=y, status=st, type=ty, mine=self.mine.get())
        lead = self.principal.username if self.mine.get() else None
        self.tree.delete(*self.tree.get_children())
        try:
            rows = IV.list_interventions(year_group=y or None, status=st or None,
                                         intervention_type=ty or None, lead=lead)
        except _ERRORS as e:
            self._err("Interventions", e)
            return
        self.rows = {}
        for r in rows:
            self.rows[str(r.intervention_id)] = r
            grades = (f"{r.baseline_grade or '-'}→{r.current_grade or '-'}"
                      f" ({r.target_grade or '-'})") if r.subject_id else ""
            tag = ("good",) if r.outcome == "Successful" else (
                ("bad",) if r.outcome == "Unsuccessful" else (
                    ("muted",) if not r.is_open else ()))
            self.tree.insert("", "end", iid=str(r.intervention_id), tags=tag, values=(
                r.intervention_id, f"{r.admission_no} {r.pupil_name}", r.pupil_year,
                r.subject_code or "", r.intervention_type, r.start_date, r.led_by or "",
                r.frequency, r.status, r.outcome or "", r.programme or "", grades))
        s = IV.cohort_summary(year_group=y or None, status=st or None,
                              intervention_type=ty or None, lead=lead)
        self.summary_var.set(f"{s['total']} intervention(s) for {s['pupils']} pupil(s) · "
                             f"{s['open']} open")
        activity_log.record("interventions.list", results=len(rows))

    def _selected(self, title: str) -> IV.Intervention | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo(title, "Select an intervention first.", parent=self._top())
            return None
        return self.rows.get(sel[0])

    def open_selected(self) -> None:
        r = self._selected("Open pupil")
        if r and self.open_pupil:
            self.open_pupil(r.pupil_id)

    def _fields(self, r: IV.Intervention | None, *, pupil: bool = True) -> list:
        g = (lambda k, d=None: getattr(r, k) if r else d)
        f = []
        if pupil:
            f.append(("pupil", "Pupil ID", r.admission_no if r else "", None))
        f += [("subject", "Subject", g("subject_code", ""), ("edit", ["", *_subjects()])),
              ("intervention_type", "Type", g("intervention_type", IV.DEFAULT_TYPE),
               IV.INTERVENTION_TYPES),
              ("programme", "Programme / group", g("programme", ""),
               ("edit", ["", *IV.programmes()])),
              ("reason", "Reason", g("reason", ""), None),
              ("start_date", "Start date", g("start_date", IV._today().isoformat()), None),
              ("end_date", "End date", g("end_date", ""), None)]
        if r is None:
            f.append(("status", "Status", "Planned", ("Planned", "Active")))
        f += [("led_by", "Led by", g("led_by", self.principal.username),
               ("edit", IV.staff_names())),
              ("location", "Location", g("location", ""), None),
              ("frequency", "Frequency", g("frequency", IV.DEFAULT_FREQUENCY), IV.FREQUENCIES),
              ("baseline_grade", "Baseline grade", g("baseline_grade", ""), None),
              ("target_grade", "Target grade", g("target_grade", ""), None),
              ("current_grade", "Current grade", g("current_grade", ""), None)]
        if r is not None:
            f.append(("outcome", "Outcome", g("outcome", ""), ["", *IV.OUTCOMES]))
        f += [("goal", "Goal", g("goal", ""), "text"), ("notes", "Notes", g("notes", ""),
                                                        "text")]
        return f

    _GRADE_NOTE = ("Leave the grades blank to fill them from the pupil's target grade and "
                   "newest assessment-point or gradebook grade in the subject.")

    def new(self) -> None:
        def save(v):
            r = IV.create(v, actor=self.principal)
            self.refresh()
            self.tree.selection_set(str(r.intervention_id))
        _form(self.parent, "New intervention", self._fields(None), save,
              note=self._GRADE_NOTE)

    def edit(self) -> None:
        r = self._selected("Edit intervention")
        if r is None:
            return

        def save(v):
            IV.update(r.intervention_id, v, actor=self.principal)
            self.refresh()
        _form(self.parent, f"Edit #{r.intervention_id} - {r.pupil_name}",
              self._fields(r, pupil=False), save,
              note="Use Status to move it through the workflow.")

    def new_group(self) -> None:
        def save(v):
            refs = [x for x in v.pop("pupils").replace(",", " ").split() if x]
            from education_system.systems.secondary.modules.pupils.domain import pupils as P
            ids, missing = [], []
            for ref in refs:
                p = P.get_pupil(int(ref)) if ref.isdigit() else P.find_by_reference(ref)
                (ids.append(p.pupil_id) if p else missing.append(ref))
            if missing:
                raise IV.ValidationError([f"No pupil {m}" for m in missing])
            res = IV.create_many(ids, v, actor=self.principal)
            self.refresh()
            msg = f"Started {len(res['created'])} intervention(s)."
            if res["skipped"]:
                msg += "\n\nSkipped:\n" + "\n".join(f"• {k}: {w}"
                                                    for k, w in res["skipped"].items())
            messagebox.showinfo("Group intervention", msg, parent=self._top())
        fields = [("pupils", "Pupils (admission nos)", "", "text"),
                  *self._fields(None, pupil=False)]
        _form(self.parent, "Group intervention", fields, save,
              note="The same intervention for several pupils - give it a programme name so "
                   "you can register the group's sessions together.")

    def change_status(self) -> None:
        r = self._selected("Status")
        if r is None:
            return
        moves = sorted(IV.MOVES[r.status], key=IV.INTERVENTION_STATUSES.index)

        def save(v):
            IV.set_status(r.intervention_id, v["status"], actor=self.principal,
                          outcome=v["outcome"] or None, notes=v["notes"] or None)
            self.refresh()
        _form(self.parent, f"Status - {r.pupil_name}",
              [("status", "New status", moves[0] if moves else "", moves),
               ("outcome", "Outcome (required if Complete / Cancelled)", "",
                ["", *IV.OUTCOMES]),
               ("notes", "Note", "", "text")], save,
              note=f"Currently {r.status}. Closing it sets the end date and refreshes the "
                   f"current grade.")

    def refresh_grade(self) -> None:
        r = self._selected("Refresh grade")
        if r is None:
            return
        try:
            new = IV.refresh_grade(r.intervention_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Refresh grade", e)
            return
        self.refresh()
        messagebox.showinfo("Refresh grade", f"Current grade: {new.current_grade}"
                            + (f" (target {new.target_grade})" if new.target_grade else ""),
                            parent=self._top())

    def summary(self) -> None:
        sel = self.tree.selection()
        if sel and sel[0] in self.rows:
            s = IV.intervention_summary(self.rows[sel[0]].intervention_id)
            iv = s["intervention"]
            ss = s["sessions"]
            lines = [f"#{iv.intervention_id}  {iv.admission_no} {iv.pupil_name} (Y"
                     f"{iv.pupil_year})", f"{iv.intervention_type}"
                     + (f" in {iv.subject_name}" if iv.subject_name else "")
                     + (f" · {iv.programme}" if iv.programme else ""),
                     f"Status {iv.status}" + (f" · outcome {iv.outcome}" if iv.outcome else ""),
                     f"{iv.start_date} → {iv.end_date or 'ongoing'} · {iv.frequency} · led by "
                     f"{iv.led_by or '-'}", ""]
            if iv.subject_id:
                ch = s["grade_change"]
                lines.append(f"Grades: baseline {iv.baseline_grade or '-'}, current "
                             f"{iv.current_grade or '-'}, target {iv.target_grade or '-'}"
                             + (f" (change {ch:+g})" if ch is not None else ""))
            lines += [f"Sessions: {ss['ran']} run, {ss['Present']} present, {ss['Late']} late,"
                      f" {ss['Absent']} absent, {ss['Cancelled']} cancelled"
                      + (f" - {ss['pct']}% attendance" if ss["pct"] is not None else ""),
                      f"Reviews: {s['review_count']} ({s['on_track']} on track, "
                      f"{s['off_track']} off track)"
                      + (f", average attendance {s['avg_attendance']}%"
                         if s["avg_attendance"] is not None else "")]
            if iv.goal:
                lines += ["", "Goal:", iv.goal]
            _text_window(self.parent, "Intervention summary", "\n".join(lines))
            return
        y = self.year.get() or None
        s = IV.cohort_summary(year_group=y)
        lines = [f"Cohort summary{' - Year ' + y if y else ''}",
                 f"{s['total']} intervention(s), {s['open']} open, {s['pupils']} pupil(s)", ""]
        for title, key in (("By status", "by_status"), ("By type", "by_type"),
                           ("By outcome", "by_outcome")):
            lines.append(title + ":")
            lines += [f"  {k:<18} {v}" for k, v in sorted(s[key].items())] or ["  -"]
        _text_window(self.parent, "Cohort summary", "\n".join(lines))

    def delete(self) -> None:
        r = self._selected("Delete")
        if r is None:
            return
        if not messagebox.askyesno("Delete", f"Delete intervention #{r.intervention_id} for "
                                   f"{r.pupil_name} with its reviews and sessions?",
                                   parent=self._top()):
            return
        try:
            IV.delete(r.intervention_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Delete", e)
            return
        self.refresh()

    def history(self) -> None:
        r = self._selected("History")
        if r is None:
            return
        rows = IV.history(r.intervention_id)
        _text_window(self.parent, "History", "\n".join(
            f"{h['at']}  {h['actor']:<14} {h['action']:<14} "
            f"{', '.join(f'{k}={v}' for k, v in h['detail'].items())}" for h in rows)
            or "No changes recorded.")

    def export(self) -> None:
        path = filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            initialfile="interventions.csv")
        if not path:
            return
        n = IV.export_csv(path, actor=self.principal, year_group=self.year.get() or None,
                          status=self.status.get() or None,
                          intervention_type=self.itype.get() or None)
        messagebox.showinfo("Export", f"Exported {n} intervention(s).", parent=self._top())

    # ── Reviews window (old) ─────────────────────────────────────────

    def reviews(self) -> None:
        r = self._selected("Reviews")
        if r is None:
            return
        win = make_toplevel(self._top())
        win.title(f"Reviews - #{r.intervention_id} {r.pupil_name}")
        win.geometry("860x420")
        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)
        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=(0, 6))
        tree = _tree(frm, [("id", "ID", 50), ("date", "Date", 90), ("rev", "Reviewer", 120),
                           ("att", "Att %", 60), ("on", "On-track", 70),
                           ("notes", "Notes", 260), ("next", "Next action", 180)], height=12)

        def load() -> None:
            tree.delete(*tree.get_children())
            for rv in IV.list_reviews(r.intervention_id):
                tree.insert("", "end", iid=str(rv.review_id),
                            tags=() if rv.on_track else ("bad",), values=(
                                rv.review_id, rv.review_date, rv.reviewer or "",
                                "" if rv.attendance_pct is None else f"{rv.attendance_pct:g}",
                                "Yes" if rv.on_track else "No", rv.progress_notes or "",
                                rv.next_action or ""))

        def add() -> None:
            def save(v):
                IV.add_review(r.intervention_id, v, actor=self.principal)
                load()
            _form(win, "Add review",
                  [("review_date", "Review date", IV._today().isoformat(), None),
                   ("reviewer", "Reviewer", self.principal.username, None),
                   ("attendance_pct", "Attendance %", "", None),
                   ("on_track", "On-track", True, "check"),
                   ("next_action", "Next action", "", None),
                   ("progress_notes", "Progress notes", "", "text")], save,
                  note="Leave Attendance % blank to use the sessions registered so far.")

        def remove() -> None:
            sel = tree.selection()
            if not sel or not messagebox.askyesno("Delete review", "Delete the selected "
                                                  "review?", parent=win):
                return
            try:
                IV.delete_review(int(sel[0]), actor=self.principal)
            except _ERRORS as e:
                messagebox.showerror("Delete review", _problems(e), parent=win)
            load()

        for text, cmd in (("Add review", add), ("Delete selected", remove),
                          ("Refresh", load)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        load()

    # ── Sessions ─────────────────────────────────────────────────────

    def sessions(self) -> None:
        r = self._selected("Sessions")
        if r is None:
            return
        win = make_toplevel(self._top())
        win.title(f"Sessions - #{r.intervention_id} {r.pupil_name}")
        win.geometry("720x420")
        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)
        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=(0, 6))
        info = tk.StringVar()
        tree = _tree(frm, [("id", "ID", 50), ("date", "Date", 90), ("att", "Attendance", 90),
                           ("notes", "Notes", 300), ("by", "Recorded by", 110)], height=12)

        def load() -> None:
            tree.delete(*tree.get_children())
            for s in IV.sessions(r.intervention_id):
                tree.insert("", "end", iid=str(s.session_id),
                            tags=("bad",) if s.attendance == "Absent" else (),
                            values=(s.session_id, s.session_date, s.attendance,
                                    s.notes or "", s.recorded_by or ""))
            a = IV.session_attendance(r.intervention_id)
            info.set(f"{a['ran']} run · {a['Present']} present, {a['Late']} late, "
                     f"{a['Absent']} absent, {a['Cancelled']} cancelled"
                     + (f" · {a['pct']}%" if a["pct"] is not None else ""))

        def add() -> None:
            def save(v):
                IV.record_session(r.intervention_id, v, actor=self.principal)
                load()
            _form(win, "Register session",
                  [("session_date", "Date", IV._today().isoformat(), None),
                   ("attendance", "Attendance", "Present", IV.ATTENDANCE),
                   ("notes", "Notes", "", None)], save,
                  note="A second mark on the same date replaces the first.")

        def remove() -> None:
            sel = tree.selection()
            if not sel or not messagebox.askyesno("Delete session", "Delete the selected "
                                                  "session?", parent=win):
                return
            try:
                IV.delete_session(int(sel[0]), actor=self.principal)
            except _ERRORS as e:
                messagebox.showerror("Delete session", _problems(e), parent=win)
            load()

        for text, cmd in (("Register session", add), ("Delete selected", remove),
                          ("Refresh", load)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        ttk.Label(bar, textvariable=info, foreground="#555").pack(side="left", padx=10)
        load()

    def group_register(self) -> None:
        progs = IV.programmes()
        if not progs:
            messagebox.showinfo("Group register", "No intervention has a programme / group "
                                "name yet - start one with Group….", parent=self._top())
            return
        win = make_toplevel(self._top())
        win.title("Group register")
        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)
        top = ttk.Frame(frm)
        top.pack(fill="x", pady=(0, 6))
        prog = tk.StringVar(value=self.state.get("programme", progs[0]))
        day = tk.StringVar(value=IV._today().isoformat())
        ttk.Label(top, text="Group:").pack(side="left")
        cb = ttk.Combobox(top, textvariable=prog, values=progs, state="readonly", width=28)
        cb.pack(side="left", padx=4)
        ttk.Label(top, text="Date:").pack(side="left", padx=(8, 0))
        ttk.Entry(top, textvariable=day, width=11).pack(side="left", padx=4)
        body = ttk.Frame(frm)
        body.pack(fill="both", expand=True)
        marks: dict[int, tk.StringVar] = {}

        def load(_e=None) -> None:
            for w in body.winfo_children():
                w.destroy()
            marks.clear()
            self.state["programme"] = prog.get()
            for i, iv in enumerate(IV.list_interventions(programme=prog.get(),
                                                         status="Active")):
                ttk.Label(body, text=f"{iv.admission_no} {iv.pupil_name}").grid(
                    row=i, column=0, sticky="w", padx=(0, 8), pady=1)
                v = tk.StringVar(value="Present")
                ttk.Combobox(body, textvariable=v, values=["", *IV.ATTENDANCE],
                             state="readonly", width=10).grid(row=i, column=1, sticky="w")
                marks[iv.intervention_id] = v
            if not marks:
                ttk.Label(body, text="No active interventions in this group.",
                          foreground="#777").grid(row=0, column=0)

        def save() -> None:
            try:
                n = IV.register_programme(prog.get(), day.get(),
                                          {k: v.get() for k, v in marks.items()},
                                          actor=self.principal)
            except _ERRORS as e:
                messagebox.showerror("Group register", _problems(e), parent=win)
                return
            messagebox.showinfo("Group register", f"Registered {n} pupil(s).", parent=win)
            win.destroy()

        cb.bind("<<ComboboxSelected>>", load)
        ttk.Button(frm, text="Save register", command=save).pack(anchor="e", pady=(8, 0))
        load()

    # ── Who needs one? ───────────────────────────────────────────────

    def _build_suggest(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        self.s_year = tk.StringVar(value=self.state.get("s_year", "11"))
        ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar, textvariable=self.s_year, values=["", *YEARS], state="readonly",
                     width=5).pack(side="left", padx=(0, 6))
        self.s_kinds = {k: tk.BooleanVar(value=True) for k in ("below target", "progress 8",
                                                                "attendance")}
        for k, v in self.s_kinds.items():
            ttk.Checkbutton(bar, text=k.capitalize(), variable=v).pack(side="left", padx=2)
        self._button(bar, "Apply", self.refresh_suggest)
        self._button(bar, "Start intervention…", self.start_suggested)
        if self.open_pupil:
            self._button(bar, "Open pupil", lambda: self._open_s())
        ttk.Label(tab, text="Pupils the school's data says may need support and who aren't "
                  "already in an open intervention for it. Select several to start one "
                  "group.", foreground="#555").pack(anchor="w", pady=(0, 4))
        self.s_tree = _tree(tab, [("pupil", "Pupil", 200), ("year", "Yr", 35),
                                  ("subj", "Subj", 60), ("type", "Suggested", 100),
                                  ("reason", "Why", 360)], select="extended")
        self.s_rows: dict[str, dict] = {}

    def refresh_suggest(self) -> None:
        self.state["s_year"] = self.s_year.get()
        self.s_tree.delete(*self.s_tree.get_children())
        kinds = tuple(k for k, v in self.s_kinds.items() if v.get())
        try:
            rows = IV.suggestions(year_group=int(self.s_year.get()) if self.s_year.get()
                                  else None, include=kinds)
        except _ERRORS as e:
            self._err("Suggestions", e)
            return
        self.s_rows = {}
        for i, s in enumerate(rows):
            p = s["pupil"]
            self.s_rows[str(i)] = s
            self.s_tree.insert("", "end", iid=str(i),
                               tags=("bad",) if s["severity"] > 1 else (), values=(
                                   f"{p.admission_no} {p.display_name}", p.year_group,
                                   s["subject"] or "", s["type"], s["reason"]))
        self.summary_var.set(f"{len(rows)} suggestion(s)")

    def _open_s(self) -> None:
        sel = self.s_tree.selection()
        if sel and self.open_pupil:
            self.open_pupil(self.s_rows[sel[0]]["pupil"].pupil_id)

    def start_suggested(self) -> None:
        picked = [self.s_rows[i] for i in self.s_tree.selection()]
        if not picked:
            messagebox.showinfo("Start intervention", "Select one or more pupils first.",
                                parent=self._top())
            return
        first = picked[0]
        same_subject = all(p["subject"] == first["subject"] for p in picked)

        def save(v):
            ids = [p["pupil"].pupil_id for p in picked]
            reason = v.pop("reason")
            if len(ids) == 1:
                IV.create({**v, "pupil_id": ids[0], "reason": reason}, actor=self.principal)
                msg = "Started 1 intervention."
            else:
                res = IV.create_many(ids, {**v, "reason": reason}, actor=self.principal)
                msg = f"Started {len(res['created'])} intervention(s)." + (
                    "\nSkipped: " + ", ".join(res["skipped"]) if res["skipped"] else "")
            self.refresh_suggest()
            messagebox.showinfo("Start intervention", msg, parent=self._top())
        _form(self.parent, f"Start intervention - {len(picked)} pupil(s)", [
            ("subject", "Subject", first["subject"] if same_subject else "",
             ("edit", ["", *_subjects()])),
            ("intervention_type", "Type", first["type"], IV.INTERVENTION_TYPES),
            ("programme", "Programme / group", "", ("edit", ["", *IV.programmes()])),
            ("reason", "Reason", first["reason"] if len(picked) == 1 else "", None),
            ("status", "Status", "Planned", ("Planned", "Active")),
            ("led_by", "Led by", self.principal.username, ("edit", IV.staff_names())),
            ("frequency", "Frequency", IV.DEFAULT_FREQUENCY, IV.FREQUENCIES),
            ("goal", "Goal", "", "text")], save)

    # ── Due for review ───────────────────────────────────────────────

    def _build_due(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        self.d_days = tk.StringVar(value=self.state.get("days", "28"))
        self.d_mine = tk.BooleanVar(value=self.state.get("d_mine", False))
        ttk.Label(bar, text="No review for (days):").pack(side="left", padx=(0, 4))
        ttk.Entry(bar, textvariable=self.d_days, width=5).pack(side="left", padx=(0, 6))
        ttk.Checkbutton(bar, text="Mine", variable=self.d_mine).pack(side="left", padx=(0, 6))
        self._button(bar, "Apply", self.refresh_due)
        self.d_tree = _tree(tab, [("id", "ID", 50), ("pupil", "Pupil", 200),
                                  ("subj", "Subj", 60), ("type", "Type", 100),
                                  ("led", "Led by", 130), ("start", "Start", 90),
                                  ("last", "Last review", 90)])

    def refresh_due(self) -> None:
        try:
            days = max(1, int(self.d_days.get() or 28))
        except ValueError:
            days = 28
        self.state.update(days=str(days), d_mine=self.d_mine.get())
        self.d_tree.delete(*self.d_tree.get_children())
        rows = IV.due_for_review(days=days, lead=self.principal.username
                                 if self.d_mine.get() else None)
        for d in rows:
            iv = d["intervention"]
            self.d_tree.insert("", "end", values=(
                iv.intervention_id, f"{iv.admission_no} {iv.pupil_name}",
                iv.subject_code or "", iv.intervention_type, iv.led_by or "", iv.start_date,
                d["last_review"] or "never"))
        self.summary_var.set(f"{len(rows)} active intervention(s) due a review")

    # ── Impact ───────────────────────────────────────────────────────

    def _build_impact(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        self.i_by = tk.StringVar(value=self.state.get("by", "type"))
        self.i_year = tk.StringVar(value=self.state.get("i_year", ""))
        self.i_from = tk.StringVar(value=self.state.get("i_from", ""))
        ttk.Label(bar, text="By:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar, textvariable=self.i_by, values=["type", "subject", "programme"],
                     state="readonly", width=10).pack(side="left", padx=(0, 6))
        ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar, textvariable=self.i_year, values=["", *YEARS], state="readonly",
                     width=5).pack(side="left", padx=(0, 6))
        ttk.Label(bar, text="Started from:").pack(side="left", padx=(0, 4))
        ttk.Entry(bar, textvariable=self.i_from, width=11).pack(side="left", padx=(0, 6))
        self._button(bar, "Apply", self.refresh_impact)
        self.i_tree = _tree(tab, [("group", "Group", 180), ("count", "Count", 60),
                                  ("open", "Open", 55), ("done", "Complete", 70),
                                  ("succ", "Successful", 80), ("pct", "Success %", 75),
                                  ("chg", "Avg grade change", 110), ("att", "Session att %", 95)])

    def refresh_impact(self) -> None:
        self.state.update(by=self.i_by.get(), i_year=self.i_year.get(),
                          i_from=self.i_from.get())
        self.i_tree.delete(*self.i_tree.get_children())
        rows = IV.impact(by=self.i_by.get() or "type", year_group=self.i_year.get() or None,
                         start=self.i_from.get().strip() or None)
        for r in rows:
            self.i_tree.insert("", "end", values=(
                r["group"], r["count"], r["open"], r["complete"], r["successful"],
                "-" if r["success_pct"] is None else r["success_pct"],
                "-" if r["avg_grade_change"] is None else
                f"{r['avg_grade_change']:+g} (n={r['with_grades']})",
                "-" if r["attendance_pct"] is None else r["attendance_pct"]))
        self.summary_var.set(f"{sum(r['count'] for r in rows)} intervention(s)")


def draw_interventions(parent: ttk.Frame, *, principal: Principal, state: dict,
                       open_pupil: Callable[[int], None] | None = None) -> InterventionsPage:
    return InterventionsPage(parent, principal=principal, state=state, open_pupil=open_pupil)
