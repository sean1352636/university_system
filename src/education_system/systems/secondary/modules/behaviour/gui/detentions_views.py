"""Detentions screen.

The old "Detentions" window is the first tab, with its toolbar (Year, Pupil,
Type and Status filters; Apply, Schedule, Edit, Status, Reschedule, Pupil
summary, Delete, Refresh), its columns (ID, Date, Time, Pupil, Yr, Type,
Min, Supervisor, Status, Reason), its schedule / edit dialog (Pupil ID,
Date, Start time, Duration, Type, Location, Supervisor, Set by, Status,
Incident ID, Reason, Notes) and its total / attended / missed / minutes
line. Added to it: Schedule for several pupils, Book into a session, Notice
home, Open pupil, Daily register, Cohort summary, History and Export CSV.

New tabs: Register, Sessions, Follow-up and Reports. The rules are in
:mod:`modules.behaviour.domain.detentions`.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
from education_system.systems.secondary.modules.behaviour.domain import detentions as DT
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
YEARS = ("7", "8", "9", "10", "11")
_ERRORS = W.ERRORS
_problems = W.problems
_text_window = W.text_window
_form = W.form_dialog
_TAGS = {"Missed": "bad", "Attended": "good", "Excused": "warn", "Cancelled": "muted",
         "Rescheduled": "muted"}


def _tree(parent, columns, height: int = 16, select: str = "browse") -> ttk.Treeview:
    return W.tree(parent, columns, height=height, select=select,
                  stretch={"pupil", "reason", "group", "reasons", "session"},
                  tags=W.STANDARD_TAGS)


def _fields(d: DT.Detention | None, *, with_pupil: bool = True, pupil: str = "") -> list:
    """The old dialog's fields, in its order."""
    fields = [("pupil", "Pupil ID / admission no.", d.admission_no if d else pupil, None)] \
        if with_pupil else []
    return fields + [
        ("detention_date", "Date (YYYY-MM-DD)", d.detention_date if d else "", None),
        ("start_time", "Start time (HH:MM)", d.start_time if d else "", None),
        ("duration_min", "Duration (min)", d.duration_min if d else DT.DEFAULT_DURATION, None),
        ("detention_type", "Type", d.detention_type if d else DT.DEFAULT_TYPE,
         DT.DETENTION_TYPES),
        ("location", "Location", d.location if d else "", None),
        ("supervisor", "Supervisor", d.supervisor if d else "", ("edit", DT.staff_names())),
        ("set_by", "Set by", d.set_by if d else "", None),
        ("status", "Status", d.status if d else DT.DEFAULT_STATUS,
         DT.REGISTER_STATUSES if d else ("Scheduled",)),
        ("related_entry_id", "Incident ID (behaviour)", d.related_entry_id if d else "", None),
        ("reason", "Reason (required)", d.reason if d else "", "text"),
        ("notes", "Notes", d.notes if d else "", "text"),
    ]


def _clean(v: dict[str, Any]) -> dict[str, Any]:
    out = {k: x for k, x in v.items() if k != "status" or x != "Scheduled"}
    return out


class DetentionsPage:
    TABS = ("Detentions", "Register", "Sessions", "Follow-up", "Reports")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        self.editor = DT.is_editor(principal)
        activity_log.record("detentions.view")
        ttk.Label(parent, text="Detentions", font=("", 16, "bold")).pack(anchor="w")
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(
            anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._built: set[str] = set()
        start = state.get("tab") if state.get("tab") in self.TABS else "Detentions"
        self.book.select(self.TABS.index(start))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    # ── helpers ──────────────────────────────────────────────────────

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
        build = {"Detentions": (self._build_list, self.refresh),
                 "Register": (self._build_register, self.refresh_register),
                 "Sessions": (self._build_sessions, self.refresh_sessions),
                 "Follow-up": (self._build_follow_up, self.refresh_follow_up),
                 "Reports": (self._build_reports, self.refresh_reports)}[name]
        if name not in self._built:
            self._built.add(name)
            build[0](self.tabs[name])
        build[1]()

    def _confirm_warnings(self, title: str, data: dict[str, Any],
                          pupils: list[Any] | None = None) -> None:
        """Ask about DT.check's warnings; "No" keeps the form open."""
        try:
            warnings = DT.check(data, actor=self.principal, pupils=pupils)
        except _ERRORS:
            return      # the save shows the problems
        if warnings and not messagebox.askyesno(
                title, "\n\n".join(warnings) + "\n\nSet it anyway?", parent=self._top()):
            raise DT.ValidationError(["Not saved yet - change the details, or Save again "
                                      "and answer Yes"])

    def _insert(self, tree: ttk.Treeview, d: DT.Detention, rows: dict) -> None:
        rows[str(d.detention_id)] = d
        tag = _TAGS.get(d.status, "")
        tree.insert("", "end", iid=str(d.detention_id), tags=(tag,) if tag else (),
                    values=(d.detention_id, d.detention_date, d.start_time or "-",
                            f"{d.pupil_name} ({d.admission_no})", d.pupil_year,
                            d.detention_type, d.duration_min, d.supervisor or "-", d.status,
                            d.reason))

    _COLUMNS = [("id", "ID", 50), ("date", "Date", 90), ("time", "Time", 55),
                ("pupil", "Pupil", 190), ("yr", "Yr", 35), ("type", "Type", 100),
                ("dur", "Min", 45), ("sup", "Supervisor", 140), ("status", "Status", 90),
                ("reason", "Reason", 260)]

    # ── Detentions (old window) ──────────────────────────────────────

    def _build_list(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.year = tk.StringVar(value=self.state.get("year", ""))
        self.pupil = tk.StringVar(value=self.state.get("pupil", ""))
        self.dtype = tk.StringVar(value=self.state.get("type", ""))
        self.status = tk.StringVar(value=self.state.get("status", ""))
        for label, var, values, width in (
                ("Year:", self.year, ["", *YEARS], 5), ("Pupil:", self.pupil, None, 12),
                ("Type:", self.dtype, ["", *DT.DETENTION_TYPES], 13),
                ("Status:", self.status, ["", *DT.DETENTION_STATUSES], 11)):
            ttk.Label(bar, text=label).pack(side="left", padx=(0, 4))
            if values is None:
                ttk.Entry(bar, textvariable=var, width=width).pack(side="left", padx=(0, 6))
            else:
                cb = ttk.Combobox(bar, textvariable=var, values=values, state="readonly",
                                  width=width)
                cb.pack(side="left", padx=(0, 6))
                cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        for text, cmd, lead in (("Apply", self.refresh, False), ("Schedule", self.schedule, False),
                                ("Edit", self.edit, False), ("Status", self.set_status, False),
                                ("Reschedule", self.reschedule, False),
                                ("Pupil summary", self.pupil_summary, False),
                                ("Delete", self.delete, True), ("Refresh", self.refresh, False)):
            self._button(bar, text, cmd, lead)
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(0, 6))
        for text, cmd in (("Schedule for several pupils…", self.schedule_many),
                          ("Book into session…", self.book_session),
                          ("Notice home…", self.notice_home),
                          ("Open pupil", self._open_selected_pupil),
                          ("Daily register", self.daily_register),
                          ("Cohort summary", self.cohort), ("History", self.history),
                          ("Export CSV…", self.export)):
            self._button(bar2, text, cmd)
        self.tree = _tree(tab, self._COLUMNS, select="extended")
        self.tree.bind("<Double-1>", lambda _e: self.edit())
        self.rows: dict[str, DT.Detention] = {}

    def _pupil_filter(self) -> int | None:
        ref = self.pupil.get().strip()
        if not ref:
            return None
        p = DT._pupil(ref)
        if p is None:
            raise DT.ValidationError([f"No pupil {ref}"])
        return p.pupil_id

    def refresh(self) -> None:
        y, t, st = self.year.get(), self.dtype.get(), self.status.get()
        self.state.update(year=y, pupil=self.pupil.get().strip(), type=t, status=st)
        try:
            rows = DT.list_detentions(year_group=y or None, pupil_id=self._pupil_filter(),
                                      detention_type=t or None, status=st or None, limit=2000)
        except _ERRORS as e:
            self._err("Detentions", e)
            return
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        for d in rows:
            self._insert(self.tree, d, self.rows)
        s = DT.cohort_summary(year_group=y or None)
        self.summary_var.set(f"Total: {s['total']}    Attended: {s['attended']}    "
                             f"Missed: {s['missed']}    Minutes served: {s['minutes_served']}"
                             + (f"    Attendance: {s['attendance_pct']}%"
                                if s["attendance_pct"] is not None else ""))

    def _selected(self, title: str, many: bool = False):
        sel = self.tree.selection()
        if not sel:
            self._info(title, "Select a detention first.")
            return None
        return [self.rows[i] for i in sel] if many else self.rows[sel[0]]

    def schedule(self) -> None:
        def save(v):
            v = _clean(v)
            self._confirm_warnings("Schedule detention", v)
            d = DT.create(v, actor=self.principal)
            self.refresh()
            self._after_set([d])
        _form(self.parent, "Schedule detention", _fields(None, pupil=self.pupil.get().strip()),
              save, note="SLT and Saturday detentions are set by the detentions lead.")

    def _after_set(self, done: list[DT.Detention]) -> None:
        text = (f"Scheduled #{done[0].detention_id} for {done[0].pupil_name} on "
                f"{done[0].when}." if len(done) == 1 else f"Scheduled {len(done)} detentions.")
        if messagebox.askyesno("Detentions", text + "\n\nE-mail a notice to the family now?",
                               parent=self._top()):
            self._send_notice(done, "")

    def schedule_many(self) -> None:
        forms = {f.label: f.name for f in FG.list_forms()}
        if not forms:
            self._info("Schedule for several pupils", "There are no form groups yet.")
            return

        def pick(v):
            name = forms.get(v["form"])
            pupils = P.list_pupils(form_group=name) if name else []
            if not pupils:
                raise DT.ValidationError(["That form has no pupils on roll"])
            self.parent.after(10, lambda: self._schedule_form(pupils))
        _form(self.parent, "Schedule for several pupils", [("form", "Form", "", list(forms))],
              pick)

    def _schedule_form(self, pupils: list[P.Pupil]) -> None:
        def save(v):
            ids = v.pop("pupils")
            v = _clean(v)
            self._confirm_warnings("Schedule for several pupils", v, ids)
            done = DT.set_many(ids, v, actor=self.principal)
            self.refresh()
            self._after_set(done)
        _form(self.parent, "Schedule for several pupils",
              [("pupils", "Pupils", (), ("pupils", [(p.pupil_id, f"{p.display_name} "
                                                                 f"({p.admission_no})")
                                                    for p in pupils]))]
              + _fields(None, with_pupil=False), save,
              note="Click each pupil to tick them; the same detention is set for each.")

    def _session_choices(self) -> dict[str, int]:
        return {f"#{s.session_id} {s.label}"
                + (f" ({s.places_left} left)" if s.places_left is not None else ""):
                s.session_id for s in DT.list_sessions(upcoming=True)}

    def book_session(self) -> None:
        sessions = self._session_choices()
        if not sessions:
            self._info("Book into session", "There are no upcoming sessions. The detentions "
                                            "lead adds them on the Sessions tab.")
            return

        def save(v):
            data = {"session_id": sessions[v["session"]], "reason": v["reason"],
                    "related_entry_id": v["related_entry_id"], "notes": v["notes"]}
            self._confirm_warnings("Book into session", {**data, "pupil": v["pupil"]})
            d = DT.create({**data, "pupil": v["pupil"]}, actor=self.principal)
            self.refresh()
            self._after_set([d])
        _form(self.parent, "Book into session",
              [("pupil", "Pupil ID / admission no.", self.pupil.get().strip(), None),
               ("session", "Session", "", list(sessions)),
               ("related_entry_id", "Incident ID (behaviour)", "", None),
               ("reason", "Reason (required)", "", "text"), ("notes", "Notes", "", "text")],
              save)

    def edit(self) -> None:
        d = self._selected("Edit")
        if d is None:
            return
        if not DT.can_edit(self.principal, d):
            self._info("Edit", "Only the person who set it (while it's scheduled) or the "
                               "detentions lead can change it. Use Status or Reschedule.")
            return

        def save(v):
            v.pop("pupil", None)
            DT.update(d.detention_id, v, actor=self.principal)
            self.refresh()
        _form(self.parent, f"Edit detention #{d.detention_id} - {d.pupil_name}",
              _fields(d, with_pupil=False), save)

    def set_status(self) -> None:
        rows = self._selected("Status", many=True)
        if not rows:
            return

        def save(v):
            DT.mark_register({r.detention_id: v["status"] for r in rows}, actor=self.principal,
                             note=v["note"])
            self.refresh()
        _form(self.parent, f"Status - {len(rows)} detention(s)" if len(rows) > 1 else
              f"Status - #{rows[0].detention_id}",
              [("status", "Status", rows[0].status if rows[0].status != "Rescheduled"
                else "Scheduled", DT.REGISTER_STATUSES),
               ("note", "Add to notes", "", "text")], save,
              note=f"{rows[0].pupil_name} on {rows[0].when}. Current: {rows[0].status}"
              if len(rows) == 1 else None)

    def reschedule(self, d: DT.Detention | None = None) -> None:
        d = d or self._selected("Reschedule")
        if d is None:
            return
        sessions = self._session_choices()

        def save(v):
            sid = sessions.get(v["session"]) if v["session"] else None
            new = DT.reschedule(d.detention_id, actor=self.principal,
                                new_date=v["new_date"] or None,
                                new_start_time=v["start_time"] or None,
                                new_location=v["location"] or None,
                                new_supervisor=v["supervisor"] or None, session_id=sid)
            self._refresh_all()
            self._info("Detentions", f"Rescheduled #{d.detention_id} → new detention "
                                     f"#{new.detention_id} on {new.when}")
        _form(self.parent, f"Reschedule #{d.detention_id} - {d.pupil_name}",
              [("new_date", "New date (YYYY-MM-DD)", "", None),
               ("start_time", "Start time (blank = same)", "", None),
               ("location", "Location (blank = same)", "", None),
               ("supervisor", "Supervisor (blank = same)", "", ("edit", DT.staff_names())),
               ("session", "…or book into a session", "", ["", *sessions])], save,
              note=f"Currently {d.when}, {d.detention_type}. Only scheduled or missed "
                   "detentions can be rescheduled.")

    def delete(self) -> None:
        d = self._selected("Delete")
        if d is None:
            return
        if not messagebox.askyesno("Delete detention",
                                   f"Delete detention #{d.detention_id} ({d.pupil_name}, "
                                   f"{d.detention_date})?\n\nOthers can set it to Cancelled "
                                   "instead, which keeps the record.", parent=self._top()):
            return
        try:
            DT.delete(d.detention_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Delete", e)
            return
        self.refresh()

    def pupil_summary(self) -> None:
        sel = self.tree.selection()
        try:
            pid = self.rows[sel[0]].pupil_id if sel else self._pupil_filter()
        except _ERRORS as e:
            self._err("Pupil summary", e)
            return
        if pid is None:
            self._info("Pupil summary", "Select a detention or type a pupil in the Pupil box.")
            return
        s = DT.pupil_summary(pid, academic_year=DT.current_year())
        p = P.get_pupil(pid)
        lines = [f"Pupil: {p.display_name} ({p.admission_no}) - Year {p.year_group} "
                 f"{p.form_group or ''}", f"School year {DT.current_year()}", "",
                 f"Total: {s['total']}",
                 f"Attended: {s['attended']}    Missed: {s['missed']}    "
                 f"Excused: {s['excused']}    Scheduled: {s['scheduled']}",
                 f"Minutes served: {s['minutes_served']}", "", "Coming up:"] + \
            [f"  {r.when} {r.detention_type} - {r.reason[:60]}" for r in s["upcoming"]] + \
            ([] if s["upcoming"] else ["  none"]) + ["", "All:"] + \
            [f"  #{r.detention_id} {r.when:<16} {r.detention_type:<13} {r.status:<11} "
             f"{r.reason[:50]}" for r in s["detentions"]]
        _text_window(self.parent, "Detentions — pupil summary", "\n".join(lines))

    def _send_notice(self, rows: list[DT.Detention], note: str) -> None:
        res = DT.notify_parents([r.detention_id for r in rows], actor=self.principal, note=note)
        self.refresh()
        text = f"{res['emails']} e-mail(s) prepared."
        if res["no_email"]:
            text += "\n\nNo parent e-mail address for: " + ", ".join(
                p.display_name for p in res["no_email"][:20])
        if not res["message_id"]:
            self._info("Notice home", text)
            return
        from education_system.systems.secondary.modules.communication.gui import email_views

        def done(_report, error) -> None:
            try:
                self._info("Notice home", text + (f"\n\nQueued - delivery failed: {error}"
                                                  if error else "\n\nSent."))
            except tk.TclError:
                pass
        email_views.deliver_in_background(self.parent, res["message_id"], self.principal, done)

    def notice_home(self, rows: list[DT.Detention] | None = None) -> None:
        rows = rows or self._selected("Notice home", many=True)
        if not rows:
            return

        def save(v):
            self._send_notice(rows, v["note"])
        _form(self.parent, "Notice home", [("note", "Extra message (optional)", "", "text")],
              save, note=f"{len(rows)} detention(s): a notice goes to contacts with parental "
                         "responsibility (scheduled or missed ones only).")

    def _open_selected_pupil(self) -> None:
        d = self._selected("Open pupil")
        if d and self.open_pupil:
            self.open_pupil(d.pupil_id)

    def daily_register(self) -> None:
        self.state["register_date"] = DT._today().isoformat()
        self.book.select(self.TABS.index("Register"))

    def cohort(self) -> None:
        y = self.year.get() or None
        s = DT.cohort_summary(year_group=y, academic_year=DT.current_year())
        lines = [f"{'Year ' + y if y else 'Whole school'} - {DT.current_year()}", "",
                 f"Detentions: {s['total']}  ({s['pupils']} pupils)",
                 f"Attended: {s['attended']}   Missed: {s['missed']}   "
                 f"Minutes served: {s['minutes_served']}"
                 + (f"   Attendance {s['attendance_pct']}%" if s["attendance_pct"]
                    is not None else ""), "", "By type:"] + \
            [f"  {k:<16} {v}" for k, v in s["by_type"].items()] + ["", "By status:"] + \
            [f"  {k:<16} {v}" for k, v in s["by_status"].items()]
        _text_window(self.parent, "Cohort summary", "\n".join(lines))

    def history(self) -> None:
        d = self._selected("History")
        if d is None:
            return
        _text_window(self.parent, "History", "\n".join(
            f"{h['at']}  {h['actor']:<14} {h['action']:<11} "
            + ", ".join(f"{k}={v}" for k, v in h["detail"].items())
            for h in DT.history(d.detention_id)) or "No changes recorded.")

    def export(self) -> None:
        path = filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            initialfile="detentions.csv")
        if not path:
            return
        try:
            n = DT.export_csv(path, actor=self.principal, year_group=self.year.get() or None,
                              pupil_id=self._pupil_filter(),
                              detention_type=self.dtype.get() or None,
                              status=self.status.get() or None)
        except _ERRORS as e:
            self._err("Export", e)
            return
        self._info("Export", f"Exported {n} detention(s).")

    def _refresh_all(self) -> None:
        for name, fn in (("Detentions", self.refresh), ("Register", self.refresh_register),
                         ("Sessions", self.refresh_sessions),
                         ("Follow-up", self.refresh_follow_up)):
            if name in self._built:
                fn()

    # ── Register ─────────────────────────────────────────────────────

    def _build_register(self, tab) -> None:
        ttk.Label(tab, text="Take the register for a day or one session. Select pupils "
                            "(Ctrl/Shift for several) and mark them.", foreground="#555").pack(
            anchor="w", pady=(0, 6))
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        self.reg_date = tk.StringVar(value=self.state.get("register_date",
                                                          DT._today().isoformat()))
        self.reg_session = tk.StringVar(value="")
        ttk.Label(bar, text="Date:").pack(side="left")
        ttk.Entry(bar, textvariable=self.reg_date, width=11).pack(side="left", padx=(4, 8))
        ttk.Label(bar, text="or session:").pack(side="left")
        self.reg_sessions: dict[str, int] = {}
        self.reg_combo = ttk.Combobox(bar, textvariable=self.reg_session, state="readonly",
                                      width=40)
        self.reg_combo.pack(side="left", padx=(4, 8))
        self.reg_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_register())
        self._button(bar, "Show", self.refresh_register)
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(0, 6))
        for st in ("Attended", "Missed", "Excused"):
            self._button(bar2, st, lambda s=st: self._mark(s))
        self._button(bar2, "Everyone not marked: Attended", self._mark_rest)
        self._button(bar2, "Notice home (missed)…", self._notice_missed)
        self._button(bar2, "Open pupil", lambda: self._open_from(self.reg_tree, self.reg_rows))
        self.reg_tree = _tree(tab, self._COLUMNS, select="extended")
        self.reg_rows: dict[str, DT.Detention] = {}
        self.reg_count = tk.StringVar()
        ttk.Label(tab, textvariable=self.reg_count, foreground="#555").pack(anchor="w",
                                                                           pady=(4, 0))

    def refresh_register(self) -> None:
        try:
            sessions = DT.list_sessions(date_from=self.reg_date.get().strip() or None,
                                        date_to=self.reg_date.get().strip() or None) \
                if not self.reg_session.get() else None
        except _ERRORS:
            sessions = []
        if sessions is not None:
            self.reg_sessions = {f"#{s.session_id} {s.label}": s.session_id for s in sessions}
            self.reg_combo.configure(values=["", *self.reg_sessions])
        self.state["register_date"] = self.reg_date.get().strip()
        try:
            sid = self.reg_sessions.get(self.reg_session.get())
            rows = DT.session_register(sid) if sid else \
                DT.daily_register(self.reg_date.get().strip())
        except _ERRORS as e:
            self._err("Register", e)
            return
        self.reg_tree.delete(*self.reg_tree.get_children())
        self.reg_rows = {}
        for d in rows:
            self._insert(self.reg_tree, d, self.reg_rows)
        by = {s: sum(1 for d in rows if d.status == s) for s in DT.REGISTER_STATUSES}
        self.reg_count.set(f"{len(rows)} due · " + " · ".join(f"{k} {v}" for k, v in by.items()
                                                              if v))

    def _mark(self, status: str) -> None:
        sel = self.reg_tree.selection()
        if not sel:
            self._info("Register", "Select pupils first.")
            return
        try:
            DT.mark_register({int(i): status for i in sel}, actor=self.principal)
        except _ERRORS as e:
            self._err("Register", e)
            return
        self._refresh_all()

    def _mark_rest(self) -> None:
        todo = {int(i): "Attended" for i, d in self.reg_rows.items() if d.status == "Scheduled"}
        if not todo:
            self._info("Register", "Everyone has been marked.")
            return
        if not messagebox.askyesno("Register", f"Mark {len(todo)} pupil(s) as attended?",
                                   parent=self._top()):
            return
        try:
            DT.mark_register(todo, actor=self.principal)
        except _ERRORS as e:
            self._err("Register", e)
            return
        self._refresh_all()

    def _notice_missed(self) -> None:
        rows = [d for d in self.reg_rows.values() if d.status == "Missed"]
        if not rows:
            self._info("Notice home", "Nobody has been marked as missed.")
            return
        self.notice_home(rows)

    def _open_from(self, tree, rows) -> None:
        sel = tree.selection()
        if sel and self.open_pupil:
            self.open_pupil(rows[sel[0]].pupil_id)

    # ── Sessions ─────────────────────────────────────────────────────

    def _build_sessions(self, tab) -> None:
        ttk.Label(tab, text="Detention sessions the school runs (e.g. Tuesday after-school "
                            "detention). Staff book pupils into them; the detentions lead "
                            "adds and changes them.", foreground="#555").pack(anchor="w",
                                                                            pady=(0, 6))
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        self.show_past = tk.BooleanVar(value=self.state.get("show_past", False))
        ttk.Checkbutton(bar, text="Include past and cancelled", variable=self.show_past,
                        command=self.refresh_sessions).pack(side="left", padx=(0, 8))
        self._button(bar, "Add session…", lambda: self._session_form(None), True)
        self._button(bar, "Edit…", self._edit_session, True)
        self._button(bar, "Cancel session", self._cancel_session, True)
        self._button(bar, "Move pupils…", self._move_session, True)
        self._button(bar, "Open register", self._open_session_register)
        self.ses_tree = _tree(tab, [("id", "ID", 45), ("date", "Date", 90), ("time", "Time", 55),
                                    ("type", "Type", 100), ("dur", "Min", 45),
                                    ("room", "Location", 90), ("sup", "Supervisor", 140),
                                    ("booked", "Booked", 70), ("status", "Status", 80),
                                    ("session", "Notes", 200)])
        self.ses_tree.bind("<Double-1>", lambda _e: self._open_session_register())
        self.ses_rows: dict[str, DT.Session] = {}

    def refresh_sessions(self) -> None:
        past = self.show_past.get()
        self.state["show_past"] = past
        rows = DT.list_sessions(include_cancelled=past, upcoming=not past)
        self.ses_tree.delete(*self.ses_tree.get_children())
        self.ses_rows = {}
        for s in rows:
            self.ses_rows[str(s.session_id)] = s
            full = s.places_left == 0
            self.ses_tree.insert("", "end", iid=str(s.session_id),
                                 tags=("muted",) if s.status == "Cancelled" else
                                 ("warn",) if full else (),
                                 values=(s.session_id, s.session_date, s.start_time or "-",
                                         s.detention_type, s.duration_min, s.location or "-",
                                         s.supervisor or "-",
                                         f"{s.booked}/{s.capacity}" if s.capacity else s.booked,
                                         s.status, s.notes or ""))

    def _session_selected(self) -> DT.Session | None:
        sel = self.ses_tree.selection()
        if not sel:
            self._info("Sessions", "Select a session first.")
            return None
        return self.ses_rows[sel[0]]

    def _session_form(self, s: DT.Session | None) -> None:
        def save(v):
            DT.save_session(v, actor=self.principal, session_id=s.session_id if s else None)
            self._refresh_all()
        _form(self.parent, f"Edit session #{s.session_id}" if s else "Add session", [
            ("session_date", "Date (YYYY-MM-DD)", s.session_date if s else "", None),
            ("detention_type", "Type", s.detention_type if s else DT.DEFAULT_TYPE,
             DT.DETENTION_TYPES),
            ("start_time", "Start time (HH:MM)", s.start_time if s else "", None),
            ("duration_min", "Duration (min)", s.duration_min if s else 60, None),
            ("location", "Location", s.location if s else "", None),
            ("supervisor", "Supervisor", s.supervisor if s else "", ("edit", DT.staff_names())),
            ("capacity", "Capacity (blank = no limit)", s.capacity if s and s.capacity else "",
             None),
            ("notes", "Notes", s.notes if s else "", "text")], save,
            note="Changing a session moves every pupil still booked into it." if s else None)

    def _edit_session(self) -> None:
        s = self._session_selected()
        if s:
            self._session_form(s)

    def _cancel_session(self) -> None:
        s = self._session_selected()
        if s is None or not messagebox.askyesno("Cancel session", f"Cancel {s.label}?",
                                                parent=self._top()):
            return
        try:
            DT.cancel_session(s.session_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Cancel session", e)
            return
        self._refresh_all()

    def _move_session(self) -> None:
        s = self._session_selected()
        if s is None:
            return
        others = {k: v for k, v in self._session_choices().items() if v != s.session_id}
        if not others:
            self._info("Move pupils", "Add another session to move them to first.")
            return

        def save(v):
            n = DT.move_session(s.session_id, others[v["to"]], actor=self.principal)
            self._refresh_all()
            self._info("Move pupils", f"Moved {n} pupil(s).")
        _form(self.parent, f"Move pupils from {s.label}", [("to", "To session", "",
                                                           list(others))], save)

    def _open_session_register(self) -> None:
        s = self._session_selected()
        if s is None:
            return
        self.state["register_date"] = s.session_date
        self.book.select(self.TABS.index("Register"))
        label = next((k for k, v in self.reg_sessions.items() if v == s.session_id), None)
        if label is None:
            self.reg_sessions[f"#{s.session_id} {s.label}"] = s.session_id
            label = f"#{s.session_id} {s.label}"
            self.reg_combo.configure(values=["", *self.reg_sessions])
        self.reg_date.set(s.session_date)
        self.reg_session.set(label)
        self.refresh_register()

    # ── Follow-up ────────────────────────────────────────────────────

    def _build_follow_up(self, tab) -> None:
        ttk.Label(tab, text="Missed detentions not yet rescheduled or excused.",
                  font=("", 11, "bold")).pack(anchor="w")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(4, 4))
        self._button(bar, "Reschedule…", lambda: self._follow(self.reschedule))
        self._button(bar, "Excuse", lambda: self._follow(lambda d: self._excuse(d)))
        self._button(bar, "Notice home…",
                     lambda: self.fu_tree.selection() and self.notice_home(
                         [self.fu_rows[i] for i in self.fu_tree.selection()]))
        self._button(bar, "Open pupil", lambda: self._open_from(self.fu_tree, self.fu_rows))
        self.fu_tree = _tree(tab, self._COLUMNS, height=9, select="extended")
        self.fu_rows: dict[str, DT.Detention] = {}
        ttk.Label(tab, text=f"Pupils who missed {DT.MISSED_CONCERN} or more detentions this "
                            "term (also shown in Behaviour concerns and intervention "
                            "suggestions).", font=("", 11, "bold")).pack(anchor="w",
                                                                         pady=(10, 4))
        self.cn_tree = _tree(tab, [("pupil", "Pupil", 260), ("yr", "Yr", 40),
                                   ("missed", "Missed", 70)], height=6)
        if self.open_pupil:
            self.cn_tree.bind("<Double-1>", lambda _e: self.cn_tree.selection() and
                              self.open_pupil(int(self.cn_tree.selection()[0])))

    def refresh_follow_up(self) -> None:
        self.fu_tree.delete(*self.fu_tree.get_children())
        self.fu_rows = {}
        for d in DT.missed_to_follow_up():
            self._insert(self.fu_tree, d, self.fu_rows)
        self.cn_tree.delete(*self.cn_tree.get_children())
        for c in DT.concerns():
            self.cn_tree.insert("", "end", iid=str(c["pupil_id"]), values=(
                f"{c['pupil_name']} ({c['admission_no']})", c["year_group"], c["missed"]))

    def _follow(self, fn) -> None:
        sel = self.fu_tree.selection()
        if not sel:
            self._info("Follow-up", "Select a missed detention first.")
            return
        fn(self.fu_rows[sel[0]])

    def _excuse(self, d: DT.Detention) -> None:
        def save(v):
            DT.set_status(d.detention_id, "Excused", actor=self.principal, note=v["note"])
            self._refresh_all()
        _form(self.parent, f"Excuse #{d.detention_id} - {d.pupil_name}",
              [("note", "Why (added to notes)", "", "text")], save)

    # ── Reports ──────────────────────────────────────────────────────

    def _build_reports(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        self.rep_by = tk.StringVar(value=self.state.get("report_by", "type"))
        self.rep_year = tk.StringVar(value="")
        ttk.Label(bar, text="Group by:").pack(side="left")
        cb = ttk.Combobox(bar, textvariable=self.rep_by, state="readonly", width=10,
                          values=["type", "reason", "staff", "weekday", "year"])
        cb.pack(side="left", padx=(4, 8))
        ttk.Label(bar, text="Year:").pack(side="left")
        yb = ttk.Combobox(bar, textvariable=self.rep_year, state="readonly", width=5,
                          values=["", *YEARS])
        yb.pack(side="left", padx=(4, 8))
        for w in (cb, yb):
            w.bind("<<ComboboxSelected>>", lambda _e: self.refresh_reports())
        ttk.Label(bar, text=f"School year {DT.current_year()}", foreground="#777").pack(
            side="left")
        self.rep_tree = _tree(tab, [("group", "Group", 220), ("total", "Detentions", 90),
                                    ("att", "Attended", 80), ("miss", "Missed", 70),
                                    ("min", "Minutes served", 110), ("pupils", "Pupils", 70)])

    def refresh_reports(self) -> None:
        self.state["report_by"] = self.rep_by.get()
        try:
            rows = DT.analysis(by=self.rep_by.get(), year_group=self.rep_year.get() or None,
                               academic_year=DT.current_year())
        except _ERRORS as e:
            self._err("Reports", e)
            return
        self.rep_tree.delete(*self.rep_tree.get_children())
        for g in rows:
            self.rep_tree.insert("", "end", values=(g["group"], g["total"], g["attended"],
                                                    g["missed"], g["minutes"], g["pupils"]))


def draw_detentions(parent: ttk.Frame, *, principal: Principal, state: dict,
                    open_pupil: Callable[[int], None] | None = None) -> DetentionsPage:
    return DetentionsPage(parent, principal=principal, state=state, open_pupil=open_pupil)
