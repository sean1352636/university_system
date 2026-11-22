"""Form Tutors screen.

The old window is the first tab with its toolbar (Year / Academic year /
Status / Role with Apply, New, Edit, End, Meetings, Delete, Refresh) and
columns (ID, Academic yr, Yr, Form, Tutor, Role, Status, Start, End); its
Meetings window keeps Log meeting / Edit / Delete / Refresh and the columns
ID, Date, Type, Agenda, Follow-up; the assignment dialog keeps Year, Form,
Academic year, Tutor, Role, Email, Start / End date, Status and Notes, and
the meeting dialog Date, Type, Pupils present, Agenda, Decisions, Follow-up
actions and Notes. Added: Summary, Take from form groups, Carry forward,
Export CSV, the pupils a meeting was about and a follow-up due date.

New tabs: My form, Meetings, Follow-ups and Coverage. The rules are in
:mod:`modules.curriculum.domain.form_tutors`.
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
from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
from education_system.systems.secondary.modules.curriculum.domain import form_tutors as FT
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
YEARS = ("7", "8", "9", "10", "11")
_ERRORS = (FT.ValidationError, FT.PermissionDenied, FT.NotFound)


_problems = W.problems


def _tree(parent, columns, height: int = 16, select: str = "browse") -> ttk.Treeview:
    return W.tree(parent, columns, height=height, select=select,
                  stretch={"tutor", "pupil", "agenda", "follow_up", "detail"}, tags=W.STANDARD_TAGS)


_text_window = W.text_window
_form = W.form_dialog


def _forms() -> dict[str, int]:
    return {f.label: f.form_id for f in FG.list_forms()}


def _meeting_fields(m: FT.TutorMeeting | None, a: FT.TutorAssignment) -> list:
    g = (lambda k, d=None: getattr(m, k) if m else d)
    pupils = [(p.pupil_id, f"{p.admission_no} {p.display_name}") for p in FG.members(a.form_id)]
    return [("meeting_date", "Date", g("meeting_date", FT._today().isoformat()), None),
            ("meeting_type", "Type", g("meeting_type", FT.DEFAULT_MEETING_TYPE),
             FT.MEETING_TYPES),
            ("pupils", "About pupils", g("pupil_ids", ()), ("pupils", pupils)),
            ("pupils_present", "Pupils present", g("pupils_present", ""), None),
            ("agenda", "Agenda", g("agenda", ""), "text"),
            ("decisions", "Decisions", g("decisions", ""), "text"),
            ("follow_up_actions", "Follow-up actions", g("follow_up_actions", ""), "text"),
            ("follow_up_due", "Follow-up due (YYYY-MM-DD)", g("follow_up_due", ""), None),
            ("notes", "Notes", g("notes", ""), "text")]


class FormTutorsPage:
    TABS = ("Assignments", "My form", "Meetings", "Follow-ups", "Coverage")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        self.editor = FT.is_editor(principal)
        activity_log.record("form_tutors.view")
        ttk.Label(parent, text="Form Tutors", font=("", 16, "bold")).pack(anchor="w")
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(
            anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._built: set[str] = set()
        start = state.get("tab") or ("Assignments" if self.editor else "My form")
        self.book.select(self.TABS.index(start))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    def _top(self):
        return self.parent.winfo_toplevel()

    def _err(self, title: str, e: Exception) -> None:
        messagebox.showerror(title, _problems(e), parent=self._top())

    def _info(self, title: str, text: str) -> None:
        messagebox.showinfo(title, text, parent=self._top())

    def _button(self, bar, text: str, command, editor_only: bool = False) -> None:
        b = ttk.Button(bar, text=text, command=command)
        if editor_only and not self.editor:
            b.state(["disabled"])
        b.pack(side="left", padx=2)

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        build = {"Assignments": (self._build_assign, self.refresh),
                 "My form": (self._build_form, self.refresh_form),
                 "Meetings": (self._build_meetings, self.refresh_meetings),
                 "Follow-ups": (self._build_follow, self.refresh_follow),
                 "Coverage": (self._build_cover, self.refresh_cover)}[name]
        if name not in self._built:
            self._built.add(name)
            build[0](self.tabs[name])
        build[1]()

    # ── Assignments (old window) ─────────────────────────────────────

    def _build_assign(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.year = tk.StringVar(value=self.state.get("year", ""))
        self.ay = tk.StringVar(value=self.state.get("ay", FT.current_year()))
        self.status = tk.StringVar(value=self.state.get("status", ""))
        self.role = tk.StringVar(value=self.state.get("role", ""))
        ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar, textvariable=self.year, values=["", *YEARS], state="readonly",
                     width=5).pack(side="left", padx=(0, 6))
        ttk.Label(bar, text="Academic year:").pack(side="left", padx=(0, 4))
        ttk.Entry(bar, textvariable=self.ay, width=9).pack(side="left", padx=(0, 6))
        ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar, textvariable=self.status, values=["", *FT.ASSIGNMENT_STATUSES],
                     state="readonly", width=11).pack(side="left", padx=(0, 6))
        ttk.Label(bar, text="Role:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar, textvariable=self.role, values=["", *FT.ROLES], state="readonly",
                     width=9).pack(side="left", padx=(0, 8))
        self._button(bar, "Apply", self.refresh)
        self._button(bar, "New", self.new, True)
        self._button(bar, "Edit", self.edit, True)
        self._button(bar, "End", self.end, True)
        self._button(bar, "Meetings", self.meetings)
        self._button(bar, "Delete", self.delete, True)
        self._button(bar, "Refresh", self.refresh)
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(0, 6))
        self._button(bar2, "Summary", self.summary)
        self._button(bar2, "Take from form groups", self.import_forms, True)
        self._button(bar2, "Carry forward to next year…", self.carry_forward, True)
        self._button(bar2, "History", self.history)
        self._button(bar2, "Export CSV…", self.export)
        self.tree = _tree(tab, [
            ("id", "ID", 50), ("ay", "Academic yr", 90), ("year", "Yr", 40),
            ("form", "Form", 70), ("tutor", "Tutor", 200), ("role", "Role", 85),
            ("status", "Status", 90), ("start", "Start", 95), ("end", "End", 95),
            ("email", "Email", 180), ("n", "Meetings", 70)])
        self.tree.bind("<Double-1>", lambda _e: self.meetings())
        self.rows: dict[str, FT.TutorAssignment] = {}

    def refresh(self) -> None:
        y, ay, st, ro = self.year.get(), self.ay.get().strip(), self.status.get(), \
            self.role.get()
        self.state.update(year=y, ay=ay, status=st, role=ro)
        self.tree.delete(*self.tree.get_children())
        rows = FT.list_assignments(year_group=y or None, academic_year=ay or None,
                                   status=st or None, role=ro or None)
        self.rows = {}
        for a in rows:
            self.rows[str(a.assignment_id)] = a
            tag = {"Ended": "muted", "Provisional": "warn", "Suspended": "warn"}.get(a.status)
            self.tree.insert("", "end", iid=str(a.assignment_id), tags=(tag,) if tag else (),
                             values=(a.assignment_id, a.academic_year, a.year_group,
                                     a.form_group, a.tutor_name, a.role, a.status,
                                     a.start_date, a.end_date or "", a.contact_email or "",
                                     FT.meeting_count(a.assignment_id)))
        s = FT.cohort_summary(academic_year=ay or None)
        self.summary_var.set(f"{len(rows)} assignment(s) · {s['tutors']} tutor(s) across "
                             f"{s['forms']} form(s)")

    def _selected(self, title: str) -> FT.TutorAssignment | None:
        sel = self.tree.selection()
        if not sel:
            self._info(title, "Select an assignment first.")
            return None
        return self.rows.get(sel[0])

    def _fields(self, a: FT.TutorAssignment | None) -> tuple[list, dict[str, int]]:
        forms = _forms()
        g = (lambda k, d=None: getattr(a, k) if a else d)
        return [("form", "Form", a.form_label if a else next(iter(forms), ""), list(forms)),
                ("academic_year", "Academic year", g("academic_year", FT.current_year()),
                 None),
                ("tutor", "Tutor", g("tutor_name", ""), ("edit", FT.staff_names())),
                ("role", "Role", g("role", FT.DEFAULT_ROLE), FT.ROLES),
                ("contact_email", "Email (blank = their login's)", g("contact_email", ""),
                 None),
                ("start_date", "Start date", g("start_date", FT._today().isoformat()), None),
                ("end_date", "End date", g("end_date", ""), None),
                ("status", "Status", g("status", FT.DEFAULT_ASSIGNMENT_STATUS),
                 FT.ASSIGNMENT_STATUSES),
                ("notes", "Notes", g("notes", ""), "text")], forms

    _NOTE = ("The active Tutor (or Cover while the tutor is suspended) and Co-tutor are "
             "written to the form group record, which reports and e-mails use.")

    def new(self) -> None:
        fields, forms = self._fields(None)
        if not forms:
            self._info("New assignment", "Set up the form groups first.")
            return

        def save(v):
            v["form_id"] = forms.get(v.pop("form"))
            FT.create_assignment(v, actor=self.principal)
            self.refresh()
        _form(self.parent, "New tutor assignment", fields, save, note=self._NOTE)

    def edit(self) -> None:
        a = self._selected("Edit assignment")
        if a is None:
            return
        fields, forms = self._fields(a)
        if a.form_label not in forms:
            forms[a.form_label] = a.form_id

        def save(v):
            v["form_id"] = forms.get(v.pop("form"))
            if v["tutor"].strip() == a.tutor_name:
                v.pop("tutor")
            FT.update_assignment(a.assignment_id, v, actor=self.principal)
            self.refresh()
        _form(self.parent, f"Edit assignment #{a.assignment_id}", fields, save,
              note=self._NOTE)

    def end(self) -> None:
        a = self._selected("End assignment")
        if a is None or not messagebox.askyesno(
                "End assignment", f"End {a.tutor_name}'s {a.role.lower()} assignment for "
                                  f"{a.form_label} today?", parent=self._top()):
            return
        try:
            FT.end_assignment(a.assignment_id, actor=self.principal)
        except _ERRORS as e:
            self._err("End", e)
        self.refresh()

    def delete(self) -> None:
        a = self._selected("Delete")
        if a is None:
            return
        n = FT.meeting_count(a.assignment_id)
        if not messagebox.askyesno(
                "Delete", f"Delete assignment #{a.assignment_id}"
                + (f" and its {n} meeting record(s)? Ending it keeps them." if n else "?"),
                parent=self._top()):
            return
        try:
            FT.delete_assignment(a.assignment_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Delete", e)
        self.refresh()

    def summary(self) -> None:
        sel = self.tree.selection()
        if sel and sel[0] in self.rows:
            try:
                s = FT.assignment_summary(int(sel[0]), actor=self.principal)
            except _ERRORS as e:
                self._err("Summary", e)
                return
            a = s["assignment"]
            lines = [f"#{a.assignment_id}  {a.tutor_name} - {a.role}, {a.form_label}, "
                     f"{a.academic_year}", f"{a.status}, {a.start_date} → {a.end_date or 'now'}",
                     "", f"{s['meeting_count']} meeting(s), {s['open_follow_ups']} open "
                         f"follow-up(s), {s['pupils_seen']} pupil(s) seen individually", ""]
            lines += [f"  {k:<16} {v}" for k, v in sorted(s["by_type"].items())]
            _text_window(self.parent, "Assignment summary", "\n".join(lines))
            return
        ay = self.ay.get().strip() or None
        s = FT.cohort_summary(academic_year=ay)
        lines = [f"Cohort summary{' - ' + ay if ay else ''}",
                 f"{s['total']} assignment(s), {s['tutors']} tutor(s), {s['forms']} form(s)", ""]
        for title, key in (("By status", "by_status"), ("By role", "by_role"),
                           ("By year", "by_year")):
            lines.append(title + ":")
            lines += [f"  {k!s:<14} {v}" for k, v in sorted(s[key].items())] or ["  -"]
        _text_window(self.parent, "Cohort summary", "\n".join(lines))

    def import_forms(self) -> None:
        try:
            r = FT.import_from_forms(actor=self.principal)
        except _ERRORS as e:
            self._err("Take from form groups", e)
            return
        self.refresh()
        self._info("Take from form groups", f"Created {r['created']} assignment(s) from the "
                   f"tutors named on form groups" + (f"; {r['skipped']} skipped" if r["skipped"]
                                                     else "") + ".")

    def carry_forward(self) -> None:
        frm = self.ay.get().strip() or FT.current_year()
        to = FT.next_year(frm)
        if not messagebox.askyesno(
                "Carry forward", f"Copy {frm}'s active assignments to {to} (each form keeps "
                f"its tutor as it moves up) and end the {frm} ones on 31 August?",
                parent=self._top()):
            return
        try:
            r = FT.carry_forward(actor=self.principal, from_year=frm)
        except _ERRORS as e:
            self._err("Carry forward", e)
            return
        self.refresh()
        self._info("Carry forward", f"Copied {r['copied']} assignment(s) to {r['to_year']}."
                   + ("\n\nSkipped:\n" + "\n".join(r["skipped"][:20]) if r["skipped"] else ""))

    def history(self) -> None:
        a = self._selected("History")
        if a is None:
            return
        _text_window(self.parent, "History", "\n".join(
            f"{h['at']}  {h['actor']:<14} {h['action']:<18} "
            + ", ".join(f"{k}={v}" for k, v in h["detail"].items())
            for h in FT.history(a.assignment_id)) or "No changes recorded.")

    def export(self) -> None:
        path = filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            initialfile="form_tutors.csv")
        if path:
            n = FT.export_csv(path, actor=self.principal,
                              academic_year=self.ay.get().strip() or None,
                              year_group=self.year.get() or None)
            self._info("Export", f"Exported {n} assignment(s).")

    # ── Meetings window (old) ────────────────────────────────────────

    def meetings(self, a: FT.TutorAssignment | None = None) -> None:
        a = a or self._selected("Meetings")
        if a is None:
            return
        if not FT.can_see(self.principal, a):
            self._info("Meetings", "You can see the meetings for your own form(s) only.")
            return
        win = make_toplevel(self._top())
        win.title(f"Meetings - Yr{a.year_group}/{a.form_group} {a.tutor_name} ({a.role})")
        win.geometry("900x440")
        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)
        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=(0, 6))
        tree = _tree(frm, [("id", "ID", 50), ("date", "Date", 95), ("type", "Type", 120),
                           ("agenda", "Agenda", 260), ("follow_up", "Follow-up", 220),
                           ("pupils", "Pupils", 70), ("due", "Due", 90)], height=12)
        rows: dict[str, FT.TutorMeeting] = {}

        def load() -> None:
            tree.delete(*tree.get_children())
            rows.clear()
            for m in FT.list_meetings(assignment_id=a.assignment_id):
                rows[str(m.meeting_id)] = m
                tag = "bad" if FT.overdue(m) else ("muted" if m.follow_up_done_at else "")
                tree.insert("", "end", iid=str(m.meeting_id), tags=(tag,) if tag else (),
                            values=(m.meeting_id, m.meeting_date, m.meeting_type,
                                    (m.agenda or "").replace("\n", " "),
                                    (m.follow_up_actions or "").replace("\n", " ")
                                    + (" ✓" if m.follow_up_done_at else ""),
                                    len(m.pupil_ids) or "", m.follow_up_due or ""))

        def save_new(v):
            FT.add_meeting(a.assignment_id, v, actor=self.principal)
            load()

        def edit() -> None:
            sel = tree.selection()
            if not sel:
                return
            m = rows[sel[0]]

            def save(v):
                FT.update_meeting(m.meeting_id, v, actor=self.principal)
                load()
            _form(win, f"Meeting #{m.meeting_id}", _meeting_fields(m, a), save)

        def remove() -> None:
            sel = tree.selection()
            if not sel or not messagebox.askyesno("Delete", "Delete the selected meeting?",
                                                  parent=win):
                return
            try:
                FT.delete_meeting(int(sel[0]), actor=self.principal)
            except _ERRORS as e:
                messagebox.showerror("Delete", _problems(e), parent=win)
            load()

        def done() -> None:
            sel = tree.selection()
            if sel:
                try:
                    m = rows[sel[0]]
                    FT.complete_follow_up(m.meeting_id, actor=self.principal,
                                          undo=bool(m.follow_up_done_at))
                except _ERRORS as e:
                    messagebox.showerror("Follow-up", _problems(e), parent=win)
                load()

        for text, cmd in (("Log meeting", lambda: _form(
                win, f"Meeting - assignment #{a.assignment_id}", _meeting_fields(None, a),
                save_new)), ("Edit", edit), ("Delete", remove), ("Refresh", load),
                ("Follow-up done / reopen", done)):
            b = ttk.Button(bar, text=text, command=cmd)
            if text != "Refresh" and not FT.can_log(self.principal, a):
                b.state(["disabled"])
            b.pack(side="left", padx=2)
        tree.bind("<Double-1>", lambda _e: edit())
        load()

    # ── My form ──────────────────────────────────────────────────────

    def _build_form(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        self.f_var = tk.StringVar()
        ttk.Label(bar, text="Form:").pack(side="left", padx=(0, 4))
        self.f_cb = ttk.Combobox(bar, textvariable=self.f_var, state="readonly", width=20)
        self.f_cb.pack(side="left", padx=(0, 6))
        self.f_cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_form())
        self._button(bar, "Refresh", self.refresh_form)
        self._button(bar, "Log meeting about selected…", self.form_meeting)
        self._button(bar, "Meetings", self.form_meetings)
        if self.open_pupil:
            self._button(bar, "Open pupil", self._open_form_pupil)
        self.f_tutors = tk.StringVar()
        ttk.Label(tab, textvariable=self.f_tutors, foreground="#555").pack(anchor="w")
        self.f_tree = _tree(tab, [("pupil", "Pupil", 220), ("att", "Attendance %", 95),
                                  ("band", "Absence", 90), ("late", "Lates", 55),
                                  ("iv", "Interventions", 90), ("last", "Last 1-to-1", 95),
                                  ("mail", "Parent e-mail", 95)], select="extended")
        self.f_tree.bind("<Double-1>", lambda _e: self._open_form_pupil())
        self.f_forms: dict[str, FG.FormGroup] = {}

    def refresh_form(self) -> None:
        forms = FT.my_forms(self.principal)
        self.f_forms = {f.label: f for f in forms}
        self.f_cb.configure(values=list(self.f_forms))
        if self.f_var.get() not in self.f_forms:
            keep = self.state.get("form_id")
            self.f_var.set(next((k for k, f in self.f_forms.items() if f.form_id == keep),
                                next(iter(self.f_forms), "")))
        self.f_tree.delete(*self.f_tree.get_children())
        f = self.f_forms.get(self.f_var.get())
        if f is None:
            self.summary_var.set("You aren't the tutor of a form this year.")
            self.f_tutors.set("")
            return
        self.state["form_id"] = f.form_id
        try:
            ov = FT.form_overview(f.form_id, actor=self.principal)
        except _ERRORS as e:
            self._err("My form", e)
            return
        self.f_tutors.set(" · ".join(f"{a.role}: {a.tutor_name}" for a in ov["tutors"])
                          or "No active tutor assignment this year")
        for r in ov["pupils"]:
            p = r["pupil"]
            tag = "bad" if r["band"] else ("warn" if not r["email_contact"] else "")
            self.f_tree.insert("", "end", iid=str(p.pupil_id), tags=(tag,) if tag else (),
                               values=(f"{p.admission_no} {p.display_name}",
                                       "-" if r["attendance_pct"] is None
                                       else r["attendance_pct"], r["band"], r["late"],
                                       r["interventions"] or "", r["last_contact"] or "never",
                                       "yes" if r["email_contact"] else "none"))
        self.summary_var.set(f"{f.label} · {len(ov['pupils'])} pupil(s) · "
                             f"{len(ov['no_contact_this_term'])} not seen 1-to-1 this term")

    def _form_assignment(self) -> FT.TutorAssignment | None:
        f = self.f_forms.get(self.f_var.get())
        if f is None:
            return None
        rows = [a for a in FT.list_assignments(form_id=f.form_id,
                                               academic_year=FT.current_year())
                if a.status == "Active"]
        mine = [a for a in rows if FT.can_log(self.principal, a)
                and FT._is_mine(a, FT._me(self.principal))]
        pick = (mine or [a for a in rows if a.role == "Tutor"] or rows or [None])[0]
        if pick is None:
            self._info("Meetings", f"{f.label} has no active tutor assignment this year.")
        return pick

    def form_meeting(self) -> None:
        a = self._form_assignment()
        if a is None:
            return
        chosen = tuple(int(i) for i in self.f_tree.selection())
        fields = _meeting_fields(None, a)
        fields = [(k, lab, chosen if k == "pupils" else init,
                   ch) if k != "meeting_type" else (k, lab, "1-to-1" if len(chosen) == 1
                                                    else init, ch)
                  for k, lab, init, ch in fields]

        def save(v):
            FT.add_meeting(a.assignment_id, v, actor=self.principal)
            self.refresh_form()
        _form(self.parent, f"Log meeting - {a.form_label}", fields, save)

    def form_meetings(self) -> None:
        a = self._form_assignment()
        if a is not None:
            self.meetings(a)

    def _open_form_pupil(self) -> None:
        sel = self.f_tree.selection()
        if sel and self.open_pupil:
            self.open_pupil(int(sel[0]))

    # ── Meetings (all I can see) ─────────────────────────────────────

    def _build_meetings(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        self.m_type = tk.StringVar(value=self.state.get("m_type", ""))
        self.m_from = tk.StringVar(value=self.state.get("m_from", ""))
        self.m_to = tk.StringVar(value=self.state.get("m_to", ""))
        ttk.Label(bar, text="Type:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar, textvariable=self.m_type, values=["", *FT.MEETING_TYPES],
                     state="readonly", width=14).pack(side="left", padx=(0, 6))
        ttk.Label(bar, text="From:").pack(side="left", padx=(0, 4))
        ttk.Entry(bar, textvariable=self.m_from, width=11).pack(side="left", padx=(0, 6))
        ttk.Label(bar, text="To:").pack(side="left", padx=(0, 4))
        ttk.Entry(bar, textvariable=self.m_to, width=11).pack(side="left", padx=(0, 6))
        self._button(bar, "Apply", self.refresh_meetings)
        self._button(bar, "View", self.view_meeting)
        self.m_tree = _tree(tab, [("id", "ID", 50), ("date", "Date", 95),
                                  ("form", "Form", 60), ("tutor", "Tutor", 150),
                                  ("type", "Type", 110), ("agenda", "Agenda", 260),
                                  ("follow_up", "Follow-up", 200)])
        self.m_tree.bind("<Double-1>", lambda _e: self.view_meeting())
        self.m_rows: dict[str, FT.TutorMeeting] = {}

    def refresh_meetings(self) -> None:
        self.state.update(m_type=self.m_type.get(), m_from=self.m_from.get(),
                          m_to=self.m_to.get())
        self.m_tree.delete(*self.m_tree.get_children())
        try:
            rows = FT.list_meetings(actor=self.principal, meeting_type=self.m_type.get()
                                    or None, date_from=self.m_from.get() or None,
                                    date_to=self.m_to.get() or None)
        except _ERRORS as e:
            self._err("Meetings", e)
            return
        self.m_rows = {}
        for m in rows:
            self.m_rows[str(m.meeting_id)] = m
            self.m_tree.insert("", "end", iid=str(m.meeting_id),
                               tags=("bad",) if FT.overdue(m) else (), values=(
                                   m.meeting_id, m.meeting_date, m.form_group,
                                   m.tutor_name, m.meeting_type,
                                   (m.agenda or "").replace("\n", " "),
                                   (m.follow_up_actions or "").replace("\n", " ")))
        self.summary_var.set(f"{len(rows)} meeting(s)")

    def view_meeting(self) -> None:
        sel = self.m_tree.selection()
        if not sel:
            return
        m = self.m_rows[sel[0]]
        from education_system.systems.secondary.modules.pupils.domain import pupils as P
        names = [P.get_pupil(i) for i in m.pupil_ids]
        lines = [f"#{m.meeting_id}  {m.meeting_date}  {m.meeting_type}  {m.form_group} - "
                 f"{m.tutor_name}"]
        if names:
            lines.append("About: " + ", ".join(p.display_name for p in names if p))
        for label, v in (("Pupils present", m.pupils_present), ("Agenda", m.agenda),
                         ("Decisions", m.decisions), ("Follow-up", m.follow_up_actions),
                         ("Notes", m.notes)):
            if v:
                lines += ["", f"{label}:", v]
        if m.follow_up_due:
            lines.append(f"Due {m.follow_up_due}" + (f" - done {m.follow_up_done_at[:10]}"
                                                     if m.follow_up_done_at else ""))
        _text_window(self.parent, "Meeting", "\n".join(lines))

    # ── Follow-ups ───────────────────────────────────────────────────

    def _build_follow(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        self.fu_all = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Include done", variable=self.fu_all,
                        command=self.refresh_follow).pack(side="left", padx=(0, 6))
        self._button(bar, "Mark done / reopen", self.toggle_follow)
        self._button(bar, "Refresh", self.refresh_follow)
        self.fu_tree = _tree(tab, [("due", "Due", 90), ("form", "Form", 60),
                                   ("tutor", "Tutor", 150), ("date", "Meeting", 90),
                                   ("type", "Type", 110), ("follow_up", "Follow-up", 360)])
        self.fu_rows: dict[str, FT.TutorMeeting] = {}

    def refresh_follow(self) -> None:
        self.fu_tree.delete(*self.fu_tree.get_children())
        rows = FT.follow_ups(actor=self.principal, include_done=self.fu_all.get())
        self.fu_rows = {str(m.meeting_id): m for m in rows}
        for m in rows:
            tag = "bad" if FT.overdue(m) else ("muted" if m.follow_up_done_at else "")
            self.fu_tree.insert("", "end", iid=str(m.meeting_id), tags=(tag,) if tag else (),
                                values=(m.follow_up_due or "", m.form_group, m.tutor_name,
                                        m.meeting_date, m.meeting_type,
                                        (m.follow_up_actions or "").replace("\n", " ")))
        self.summary_var.set(f"{sum(1 for m in rows if m.follow_up_open)} open follow-up(s), "
                             f"{sum(1 for m in rows if FT.overdue(m))} overdue")

    def toggle_follow(self) -> None:
        sel = self.fu_tree.selection()
        if not sel:
            return
        m = self.fu_rows[sel[0]]
        try:
            FT.complete_follow_up(m.meeting_id, actor=self.principal,
                                  undo=bool(m.follow_up_done_at))
        except _ERRORS as e:
            self._err("Follow-up", e)
        self.refresh_follow()

    # ── Coverage ─────────────────────────────────────────────────────

    def _build_cover(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        self._button(bar, "Refresh", self.refresh_cover)
        self.cv_tree = _tree(tab, [("what", "Check", 200), ("form", "Form", 120),
                                   ("detail", "Detail", 460)])

    def refresh_cover(self) -> None:
        self.cv_tree.delete(*self.cv_tree.get_children())
        cv = FT.coverage()
        n = 0
        for f in cv["no_tutor"]:
            self.cv_tree.insert("", "end", tags=("bad",), values=(
                "No active tutor", f.label, f"form record says: {f.tutor_name or '-'}"))
            n += 1
        for name, forms in cv["several_forms"].items():
            self.cv_tree.insert("", "end", tags=("warn",), values=(
                "Tutor for several forms", "", f"{name}: {', '.join(forms)}"))
            n += 1
        for a in cv["archived_forms"]:
            self.cv_tree.insert("", "end", tags=("warn",), values=(
                "Form archived", a.form_label, f"{a.tutor_name} still active - end it"))
            n += 1
        for a in cv["provisional"]:
            self.cv_tree.insert("", "end", values=(
                "Provisional", a.form_label, f"{a.tutor_name} ({a.role})"))
            n += 1
        for x in FT.mismatches():
            self.cv_tree.insert("", "end", tags=("warn",), values=(
                "Form record differs", x["form"].label,
                f"{x['role']}: form says {x['on_form'] or '-'}, assignment says "
                f"{x['assigned'] or '-'}"))
            n += 1
        self.summary_var.set(f"{cv['academic_year']}: {n} thing(s) to look at" if n
                             else f"{cv['academic_year']}: every form has a tutor")


def draw_form_tutors(parent: ttk.Frame, *, principal: Principal, state: dict,
                     open_pupil: Callable[[int], None] | None = None) -> FormTutorsPage:
    return FormTutorsPage(parent, principal=principal, state=state, open_pupil=open_pupil)
