"""Registers & Attendance screen.

The old register bar is kept (Date / Session / Year, Load register, Save,
Single mark, Pupil history, Daily summary) with the old columns. Added: a Form
filter, quick-mark buttons and keys, late arrivals, absence over several days,
lesson registers, register status with "missing from lessons", the first-day
calling list, attendance reports with CSV export, and session times. Rules
live in :mod:`modules.attendance.domain.attendance`.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui.parented_dialogs import (
    filedialog,
    make_toplevel,
    messagebox,
)
from education_system.systems.secondary.modules.attendance.domain import attendance as AT
from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import ATTENDANCE_EDITORS, Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
ALL = "All"
PENDING_BG, ABSENT_BG, LATE_BG = "#fff6d5", "#fde2e2", "#fff0dd"


_problems = W.problems


def _tree(parent, columns, height: int = 10, select: str = "browse") -> ttk.Treeview:
    return W.tree(parent, columns, height=height, select=select,
                  stretch={"name", "label", "notes", "contacts", "lesson"})


def _day(text: str) -> _dt.date | None:
    try:
        return _dt.date.fromisoformat(text.strip())
    except ValueError:
        return None


def _code_choices(principal: Principal, session: str) -> list[str]:
    allowed = AT.CODES if principal.role in ATTENDANCE_EDITORS else {
        c: AT.CODES[c] for c in AT.TEACHER_CODES}
    out = []
    for code, (label, _cat) in allowed.items():
        if (code == "/" and session == "PM") or (code == "\\" and session == "AM"):
            continue
        out.append(f"{code}  {label}")
    return out


def _pupil_from(owner, text: str) -> P.Pupil | None:
    p = P.find_by_reference(text.strip()) if text.strip() else None
    if p is None:
        messagebox.showinfo("Attendance", "No pupil with that admission number or UPN.",
                            parent=owner)
    return p


def _ask_pupil(owner, title: str, on_pick: Callable[[P.Pupil], None]) -> None:
    win = make_toplevel(owner.winfo_toplevel())
    win.title(title)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text="Admission number or UPN:").pack(anchor="w")
    e = ttk.Entry(frm, width=24)
    e.pack(anchor="w", pady=4)
    e.focus_set()

    def go(_e=None) -> None:
        p = _pupil_from(win, e.get())
        if p is not None:
            win.destroy()
            on_pick(p)
    e.bind("<Return>", go)
    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(6, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="OK", command=go).pack(side="right", padx=(0, 6))


class AttendancePage:
    TABS = ("Register", "Lesson registers", "Register status", "Calling list", "Reports",
            "Settings")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        self.office = principal.role in ATTENDANCE_EDITORS
        activity_log.record("attendance.view")
        ttk.Label(parent, text="Registers & Attendance", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(parent, text=("Attendance office: all codes and dates." if self.office else
                                "Take today's registers: / present, L late, N absent. "
                                "The attendance office adds reasons."),
                  foreground="#666").pack(anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._build_register(self.tabs["Register"])
        self.book.select(self.TABS.index(state.get("tab", "Register")))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        if name == "Register":
            return
        tab = self.tabs[name]
        for w in tab.winfo_children():
            w.destroy()
        try:
            {"Lesson registers": self._draw_lessons, "Register status": self._draw_status,
             "Calling list": self._draw_calling, "Reports": self._draw_reports,
             "Settings": self._draw_settings}[name](tab)
        except Exception:
            logger.exception("Attendance tab %s failed", name)
            ttk.Label(tab, text="Couldn't load this tab - see the log.",
                      foreground="#a00").pack(anchor="w")

    # ── Register tab (old bar kept) ──────────────────────────────────

    def _build_register(self, tab: ttk.Frame) -> None:
        st = self.state
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.date_var = tk.StringVar(value=st.get("date", _dt.date.today().isoformat()))
        self.session_var = tk.StringVar(value=st.get("session", "AM"
                                                     if _dt.datetime.now().hour < 12 else "PM"))
        self.year_var = tk.StringVar(value=st.get("year", ALL))
        self.form_var = tk.StringVar(value=st.get("form", ALL))
        ttk.Label(bar, text="Date:").pack(side="left", padx=(0, 4))
        ttk.Entry(bar, textvariable=self.date_var, width=11).pack(side="left")
        ttk.Label(bar, text="Session:").pack(side="left", padx=(8, 4))
        ttk.Combobox(bar, textvariable=self.session_var, values=list(AT.SESSIONS),
                     state="readonly", width=4).pack(side="left")
        ttk.Label(bar, text="Year:").pack(side="left", padx=(8, 4))
        ttk.Combobox(bar, textvariable=self.year_var, state="readonly", width=5,
                     values=[ALL] + [str(y) for y in P.YEAR_GROUPS]).pack(side="left")
        ttk.Label(bar, text="Form:").pack(side="left", padx=(8, 4))
        self.form_cb = ttk.Combobox(bar, textvariable=self.form_var, state="readonly", width=7)
        self.form_cb.pack(side="left")
        ttk.Button(bar, text="Load register", command=self.load).pack(side="left", padx=(8, 2))
        ttk.Button(bar, text="Save", command=self.save).pack(side="left", padx=2)
        ttk.Button(bar, text="Single mark", command=self.single_mark).pack(side="left", padx=2)
        ttk.Button(bar, text="Pupil history", command=self.pupil_history).pack(side="left",
                                                                                padx=2)
        ttk.Button(bar, text="Daily summary", command=self.daily_summary).pack(side="left",
                                                                                padx=2)
        quick = ttk.Frame(tab)
        quick.pack(fill="x", pady=(0, 4))
        ttk.Label(quick, text="Mark selected:").pack(side="left")
        for code, text in (("/", "Present (/)"), ("L", "Late (L)"), ("N", "Absent (N)")):
            ttk.Button(quick, text=text, command=lambda c=code: self.set_selected(c)).pack(
                side="left", padx=2)
        ttk.Button(quick, text="Other code…", command=self.other_code).pack(side="left", padx=2)
        ttk.Button(quick, text="All unmarked present", command=self.all_present).pack(
            side="left", padx=(10, 2))
        ttk.Button(quick, text="Late arrival…", command=self.late_arrival).pack(side="left",
                                                                                 padx=2)
        if self.office:
            ttk.Button(quick, text="Absence over several days…",
                       command=self.range_dialog).pack(side="left", padx=2)
        self.summary_var = tk.StringVar()
        ttk.Label(tab, textvariable=self.summary_var, foreground="#666").pack(anchor="w",
                                                                              pady=(0, 4))
        self.tree = _tree(tab, (("pupil", "Adm no", 90), ("name", "Name", 180),
                                ("year", "Year", 45), ("form", "Form", 60),
                                ("mark", "Mark", 50), ("label", "Status", 220),
                                ("late", "Mins late", 70), ("notes", "Notes", 200)),
                          height=16, select="extended")
        self.tree.tag_configure("pending", background=PENDING_BG)
        self.tree.tag_configure("absent", background=ABSENT_BG)
        self.tree.tag_configure("late", background=LATE_BG)
        self.tree.bind("<Double-1>", lambda _e: self.other_code())
        for key, code in (("/", "/"), ("l", "L"), ("L", "L"), ("n", "N"), ("N", "N"),
                          ("p", "/"), ("P", "/")):
            self.tree.bind(f"<KeyPress-{key}>" if key != "/" else "<KeyPress-slash>",
                           lambda _e, c=code: self.set_selected(c))
        self.pending: dict[int, tuple[str, str | None, int | None]] = {}
        self.rows: dict[int, AT.RegisterRow] = {}
        self.year_var.trace_add("write", lambda *_: self._forms())
        self._forms()
        self.load()

    def _forms(self) -> None:
        y = self.year_var.get()
        forms = sorted({(f.year_group, f.name) for f in FG.list_forms(
            int(y) if y.isdigit() else None)})
        self.form_cb.configure(values=[ALL] + [n for _y, n in forms])
        if self.form_var.get() not in self.form_cb.cget("values"):
            self.form_var.set(ALL)

    def _filters(self) -> tuple[_dt.date, str, int | None, str | None] | None:
        d = _day(self.date_var.get())
        if d is None:
            messagebox.showerror("Attendance", "Enter the date as YYYY-MM-DD.",
                                 parent=self.parent)
            return None
        y, f = self.year_var.get(), self.form_var.get()
        self.state.update(date=d.isoformat(), session=self.session_var.get(), year=y, form=f)
        return d, self.session_var.get(), int(y) if y.isdigit() else None, (
            None if f == ALL else f)

    def load(self) -> None:
        if self.pending and not messagebox.askyesno(
                "Attendance", f"{len(self.pending)} unsaved mark(s) will be lost. Load anyway?",
                parent=self.parent):
            return
        f = self._filters()
        if f is None:
            return
        d, s, y, form = f
        self.pending.clear()
        ok, what = AT.school_day(d)
        try:
            rows = AT.register(d, s, year_group=y, form=form)
        except (AT.ValidationError, AT.NotFound) as e:
            messagebox.showerror("Attendance", _problems(e), parent=self.parent)
            return
        self.rows = {r.pupil.pupil_id: r for r in rows}
        self._draw_rows()
        if not ok:
            self.summary_var.set(f"{d:%A %d %B %Y}: {what} - no register is taken.")

    def _draw_rows(self) -> None:
        self.tree.delete(*self.tree.get_children())
        present = unmarked = 0
        for pid, r in self.rows.items():
            code, notes, mins = self.pending.get(pid) or (
                (r.mark.code, r.mark.notes, r.mark.minutes_late) if r.mark else (None, None,
                                                                                 None))
            cat = AT.category_of(code) if code else ""
            present += cat in (AT.PRESENT, AT.AEA)
            unmarked += code is None
            tag = ("pending",) if pid in self.pending else (
                ("late",) if code in ("L", "U") else ("absent",) if cat in (
                    AT.AUTHORISED, AT.UNAUTHORISED) else ())
            self.tree.insert("", "end", iid=str(pid), tags=tag, values=(
                r.pupil.admission_no, r.pupil.display_name, r.pupil.year_group,
                r.pupil.form_group or "-", code or "-",
                AT.code_label(code) if code else "-", mins if mins is not None else "",
                notes or ""))
        self.summary_var.set(
            f"Register: {len(self.rows)} pupil(s) · present {present} · unmarked {unmarked}"
            + (f" · {len(self.pending)} unsaved (highlighted) - press Save"
               if self.pending else ""))

    def _selected_ids(self) -> list[int]:
        return [int(i) for i in self.tree.selection()]

    def set_selected(self, code: str, notes: str | None = None, mins=None) -> None:
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo("Attendance", "Select one or more pupils first.",
                                parent=self.parent)
            return
        c = AT.clean_code(code, self.session_var.get())
        for pid in ids:
            self.pending[pid] = (c, notes, mins)
        self._draw_rows()
        self.tree.selection_set([str(i) for i in ids])

    def all_present(self) -> None:
        code = AT.clean_code("/", self.session_var.get())
        for pid, r in self.rows.items():
            if r.mark is None and pid not in self.pending:
                self.pending[pid] = (code, None, None)
        self._draw_rows()

    def other_code(self) -> None:
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo("Attendance", "Select one or more pupils first.",
                                parent=self.parent)
            return
        first = self.rows[ids[0]]
        cur = self.pending.get(ids[0]) or ((first.mark.code, first.mark.notes,
                                            first.mark.minutes_late) if first.mark else None)
        mark_dialog(self.parent, self.principal, self.session_var.get(),
                    title=(first.pupil.display_name if len(ids) == 1
                           else f"{len(ids)} pupils"), current=cur,
                    on_ok=lambda c, n, m: self.set_selected(c, n, m))

    def save(self) -> None:
        f = self._filters()
        if f is None:
            return
        if not self.pending:
            messagebox.showinfo("Attendance", "No changes to save.", parent=self.parent)
            return
        d, s, y, form = f
        try:
            saved, notes = AT.save_register(d, s, dict(self.pending), actor=self.principal,
                                            year_group=y, form=form)
        except (AT.ValidationError, AT.PermissionDenied) as e:
            messagebox.showerror("Attendance", _problems(e), parent=self.parent)
            return
        self.pending.clear()
        msg = f"Saved {saved} mark(s)."
        if notes:
            msg += "\n\nNot saved:\n" + "\n".join(notes[:20])
        (messagebox.showwarning if notes else messagebox.showinfo)("Attendance", msg,
                                                                   parent=self.parent)
        self.load()

    def single_mark(self) -> None:
        ids = self._selected_ids()

        def go(p: P.Pupil) -> None:
            single_mark_dialog(self.parent, self.principal, p, self.date_var.get(),
                               self.session_var.get(), after=self.load)
        if len(ids) == 1:
            go(self.rows[ids[0]].pupil)
        else:
            _ask_pupil(self.parent, "Single mark", go)

    def pupil_history(self) -> None:
        ids = self._selected_ids()
        if len(ids) == 1:
            pupil_history_dialog(self.parent, self.principal, self.rows[ids[0]].pupil,
                                 after=self.load)
        else:
            _ask_pupil(self.parent, "Pupil history", lambda p: pupil_history_dialog(
                self.parent, self.principal, p, after=self.load))

    def daily_summary(self) -> None:
        d = _day(self.date_var.get())
        if d is None:
            messagebox.showerror("Attendance", "Enter the date as YYYY-MM-DD.",
                                 parent=self.parent)
            return
        daily_summary_dialog(self.parent, d)

    def late_arrival(self) -> None:
        ids = self._selected_ids()

        def go(p: P.Pupil) -> None:
            late_dialog(self.parent, self.principal, p, self.date_var.get(),
                        self.session_var.get(), after=self.load)
        if len(ids) == 1:
            go(self.rows[ids[0]].pupil)
        else:
            _ask_pupil(self.parent, "Late arrival", go)

    def range_dialog(self) -> None:
        ids = self._selected_ids()
        if len(ids) == 1:
            range_dialog(self.parent, self.principal, self.rows[ids[0]].pupil, after=self.load)
        else:
            _ask_pupil(self.parent, "Absence over several days", lambda p: range_dialog(
                self.parent, self.principal, p, after=self.load))

    # ── Lesson registers ─────────────────────────────────────────────

    def _draw_lessons(self, tab: ttk.Frame) -> None:
        day_var = tk.StringVar(value=self.state.get("lesson_day", _dt.date.today().isoformat()))
        mine = tk.BooleanVar(value=self.state.get("lesson_mine", not self.office))
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Date:").pack(side="left")
        ttk.Entry(bar, textvariable=day_var, width=11).pack(side="left", padx=4)
        ttk.Checkbutton(bar, text="Only my lessons", variable=mine).pack(side="left", padx=6)
        label = ttk.Label(tab, foreground="#555")
        label.pack(anchor="w")
        tree = _tree(tab, (("p", "Period", 70), ("lesson", "Lesson", 220), ("group", "Group", 100),
                           ("teacher", "Teacher", 150), ("room", "Room", 70),
                           ("taken", "Register", 90)), height=14)
        tree.tag_configure("todo", background=PENDING_BG)
        lessons: dict[str, int] = {}

        def show(*_a) -> None:
            tree.delete(*tree.get_children())
            lessons.clear()
            d = _day(day_var.get())
            if d is None:
                label.configure(text="Enter a date as YYYY-MM-DD.")
                return
            self.state.update(lesson_day=d.isoformat(), lesson_mine=mine.get())
            due, what = AT.lessons_due(d, teacher=self.principal.username if mine.get()
                                       else None)
            todo = sum(1 for _x, t in due if not t)
            label.configure(text=f"{d:%A %d %B %Y} - {what} · {len(due)} lesson(s)"
                                 + (f", {todo} register(s) to take" if todo else ""))
            for x, taken in due:
                iid = tree.insert("", "end", tags=() if taken else ("todo",), values=(
                    x.slot_label.split()[-1], f"{x.subject_name}", x.group_code,
                    x.teacher or "", x.room or "", "Taken" if taken else "Not taken"))
                lessons[iid] = x.lesson_id

        def open_reg(_e=None) -> None:
            sel = tree.selection()
            d = _day(day_var.get())
            if not sel or d is None:
                messagebox.showinfo("Lesson register", "Choose a lesson first.", parent=tab)
                return
            lesson_register_dialog(tab, self.principal, lessons[sel[0]], d, after=show)

        ttk.Button(bar, text="Show", command=show).pack(side="left")
        ttk.Button(bar, text="Take / view register", command=open_reg).pack(side="left",
                                                                            padx=6)
        tree.bind("<Double-1>", open_reg)
        mine.trace_add("write", show)
        show()

    # ── Register status ──────────────────────────────────────────────

    def _draw_status(self, tab: ttk.Frame) -> None:
        day_var = tk.StringVar(value=self.state.get("status_day", _dt.date.today().isoformat()))
        sess_var = tk.StringVar(value=self.state.get("status_session", "AM"))
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Date:").pack(side="left")
        ttk.Entry(bar, textvariable=day_var, width=11).pack(side="left", padx=4)
        ttk.Combobox(bar, textvariable=sess_var, values=list(AT.SESSIONS), state="readonly",
                     width=4).pack(side="left")
        label = ttk.Label(tab, foreground="#555")
        label.pack(anchor="w")
        tree = _tree(tab, (("year", "Year", 50), ("form", "Form", 70), ("roll", "On roll", 70),
                           ("marked", "Marked", 70), ("taken", "Taken by", 140),
                           ("at", "At", 140)), height=9)
        tree.tag_configure("todo", background=ABSENT_BG)
        ttk.Label(tab, text="Missing from lessons (present for the session, absent from a "
                            "lesson):", font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
        miss = _tree(tab, (("pupil", "Adm no", 90), ("name", "Name", 180), ("lesson", "Lesson",
                                                                             220),
                           ("code", "Session mark", 90)), height=6)
        pupils: dict[str, int] = {}

        def show(*_a) -> None:
            tree.delete(*tree.get_children())
            miss.delete(*miss.get_children())
            d = _day(day_var.get())
            if d is None:
                label.configure(text="Enter a date as YYYY-MM-DD.")
                return
            self.state.update(status_day=d.isoformat(), status_session=sess_var.get())
            ok, what = AT.school_day(d)
            rows = AT.register_status(d, sess_var.get())
            todo = [r for r in rows if r.on_roll and not r.complete]
            label.configure(text=f"{d:%A %d %B %Y} {sess_var.get()} - {what}"
                                 + (f" · {len(todo)} register(s) incomplete" if ok else ""))
            for r in rows:
                tree.insert("", "end", tags=("todo",) if r.on_roll and not r.complete else (),
                            values=(r.year_group, r.form_group or "(no form)", r.on_roll,
                                    r.marked, r.taken_by or "", r.taken_at or ""))
            for p, x, code in AT.missing_from_lessons(d):
                iid = miss.insert("", "end", values=(p.admission_no, p.display_name,
                                                     f"{x.slot_label} {x.subject_code} "
                                                     f"{x.group_code}", code))
                pupils[iid] = p.pupil_id

        ttk.Button(bar, text="Show", command=show).pack(side="left", padx=6)
        if self.open_pupil:
            miss.bind("<Double-1>", lambda _e: miss.selection() and self.open_pupil(
                pupils[miss.selection()[0]]))
        sess_var.trace_add("write", show)
        show()

    # ── Calling list ─────────────────────────────────────────────────

    def _draw_calling(self, tab: ttk.Frame) -> None:
        day_var = tk.StringVar(value=self.state.get("call_day", _dt.date.today().isoformat()))
        sess_var = tk.StringVar(value=self.state.get("call_session", "AM"))
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Date:").pack(side="left")
        ttk.Entry(bar, textvariable=day_var, width=11).pack(side="left", padx=4)
        ttk.Combobox(bar, textvariable=sess_var, values=list(AT.SESSIONS), state="readonly",
                     width=4).pack(side="left")
        label = ttk.Label(tab, text="Pupils marked N (no reason yet) - ring home, then record "
                                    "the reason.", foreground="#555")
        label.pack(anchor="w")
        tree = _tree(tab, (("pupil", "Adm no", 90), ("name", "Name", 170), ("year", "Year", 45),
                           ("form", "Form", 55), ("contacts", "Contacts (priority order)",
                                                  420)), height=14)
        found: dict[str, P.Pupil] = {}

        def show(*_a) -> None:
            tree.delete(*tree.get_children())
            found.clear()
            d = _day(day_var.get())
            if d is None:
                return
            self.state.update(call_day=d.isoformat(), call_session=sess_var.get())
            rows = AT.calling_list(d, sess_var.get())
            label.configure(text=f"{len(rows)} pupil(s) with no reason yet"
                                 + (" - double-click to record the reason" if self.office
                                    else ""))
            for p, _m, contacts in rows:
                who = "; ".join(f"{c.full_name} ({c.relationship}) {c.phone or 'no phone'}"
                                for c in contacts[:3]) or "No contacts recorded"
                iid = tree.insert("", "end", values=(p.admission_no, p.display_name,
                                                     p.year_group, p.form_group or "", who))
                found[iid] = p

        def reason(_e=None) -> None:
            sel = tree.selection()
            if sel and self.office:
                single_mark_dialog(tab, self.principal, found[sel[0]], day_var.get(),
                                   sess_var.get(), after=show)

        ttk.Button(bar, text="Show", command=show).pack(side="left", padx=6)
        if self.office:
            ttk.Button(bar, text="Record reason…", command=reason).pack(side="left")
        tree.bind("<Double-1>", reason)
        sess_var.trace_add("write", show)
        show()

    # ── Reports ──────────────────────────────────────────────────────

    def _draw_reports(self, tab: ttk.Frame) -> None:
        st = self.state
        start = tk.StringVar(value=st.get("rep_from", P.academic_year_start().isoformat()))
        end = tk.StringVar(value=st.get("rep_to", _dt.date.today().isoformat()))
        year = tk.StringVar(value=st.get("rep_year", ALL))
        only = tk.BooleanVar(value=st.get("rep_only", False))
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        for text, var, w in (("From:", start, 11), ("To:", end, 11)):
            ttk.Label(bar, text=text).pack(side="left", padx=(6, 2))
            ttk.Entry(bar, textvariable=var, width=w).pack(side="left")
        ttk.Label(bar, text="Year:").pack(side="left", padx=(8, 2))
        ttk.Combobox(bar, textvariable=year, state="readonly", width=5,
                     values=[ALL] + [str(y) for y in P.YEAR_GROUPS]).pack(side="left")
        ttk.Checkbutton(bar, text="Persistent absence only (10%+ missed)",
                        variable=only).pack(side="left", padx=8)
        label = ttk.Label(tab, foreground="#555")
        label.pack(anchor="w")
        tree = _tree(tab, (("pupil", "Adm no", 90), ("name", "Name", 170), ("year", "Yr", 35),
                           ("form", "Form", 55), ("pct", "Attendance %", 90),
                           ("poss", "Possible", 65), ("auth", "Auth abs", 65),
                           ("unauth", "Unauth abs", 75), ("late", "Late", 45),
                           ("unmarked", "Unmarked", 70), ("band", "Band", 85)), height=15)
        tree.tag_configure("severe", background=ABSENT_BG)
        tree.tag_configure("persistent", background=LATE_BG)
        rows: list[tuple[P.Pupil, AT.Summary]] = []
        ids: dict[str, P.Pupil] = {}

        def show() -> None:
            tree.delete(*tree.get_children())
            rows.clear()
            ids.clear()
            st.update(rep_from=start.get(), rep_to=end.get(), rep_year=year.get(),
                      rep_only=only.get())
            try:
                y = int(year.get()) if year.get().isdigit() else None
                rows.extend((AT.persistent_absentees if only.get() else AT.summaries)(
                    start.get(), end.get(), year_group=y))
            except AT.ValidationError as e:
                messagebox.showerror("Reports", _problems(e), parent=tab)
                return
            with_pct = [s.attendance_pct for _p, s in rows if s.attendance_pct is not None]
            overall = sum(s.attended for _p, s in rows), sum(s.possible for _p, s in rows)
            label.configure(text=f"{len(rows)} pupil(s) · overall "
                                 f"{round(100 * overall[0] / overall[1], 1) if overall[1] else '-'}%"
                                 f" · persistent {sum(1 for _p, s in rows if s.band)}"
                                 + ("" if with_pct else " · no marks in this period"))
            for p, s in rows:
                iid = tree.insert("", "end", tags=(s.band,) if s.band else (), values=(
                    p.admission_no, p.display_name, p.year_group, p.form_group or "",
                    "-" if s.attendance_pct is None else f"{s.attendance_pct:.1f}",
                    s.possible, s.authorised, s.unauthorised, s.late, s.unmarked,
                    s.band.title()))
                ids[iid] = p

        def export() -> None:
            if not rows:
                messagebox.showinfo("Reports", "Nothing to export.", parent=tab)
                return
            path = filedialog.asksaveasfilename(parent=tab, defaultextension=".csv",
                                                initialfile="attendance.csv",
                                                filetypes=[("CSV", "*.csv")])
            if path:
                n = AT.export_summaries(path, rows, actor=self.principal)
                messagebox.showinfo("Reports", f"Exported {n} pupil(s).", parent=tab)

        ttk.Button(bar, text="Show", command=show).pack(side="left", padx=4)
        ttk.Button(bar, text="Export CSV…", command=export).pack(side="left")
        tree.bind("<Double-1>", lambda _e: tree.selection() and pupil_history_dialog(
            tab, self.principal, ids[tree.selection()[0]], after=show))
        show()

    # ── Settings ─────────────────────────────────────────────────────

    def _draw_settings(self, tab: ttk.Frame) -> None:
        box = ttk.LabelFrame(tab, text="Session times", padding=8)
        box.pack(fill="x")
        times = AT.session_times()
        ents = {}
        for i, (key, text) in enumerate((("am_start", "Morning starts"),
                                         ("am_close", "Morning register closes"),
                                         ("pm_start", "Afternoon starts"),
                                         ("pm_close", "Afternoon register closes"))):
            ttk.Label(box, text=text).grid(row=i, column=0, sticky="w", pady=2)
            e = ttk.Entry(box, width=7)
            e.insert(0, times[key])
            e.grid(row=i, column=1, sticky="w", padx=6)
            if not self.office:
                e.state(["disabled"])
            ents[key] = e
        ttk.Label(box, text="Arriving after the register closes is U (unauthorised). "
                            "Lessons starting from the afternoon start time count as PM.",
                  foreground="#666").grid(row=4, column=0, columnspan=3, sticky="w", pady=(4, 0))

        def save() -> None:
            try:
                AT.set_session_times({k: e.get() for k, e in ents.items()},
                                     actor=self.principal)
            except (AT.ValidationError, AT.PermissionDenied) as e:
                messagebox.showerror("Settings", _problems(e), parent=tab)
                return
            messagebox.showinfo("Settings", "Saved.", parent=tab)

        if self.office:
            ttk.Button(box, text="Save times", command=save).grid(row=5, column=0, sticky="w",
                                                                  pady=(6, 0))
        ref = ttk.LabelFrame(tab, text="Mark codes (DfE)", padding=8)
        ref.pack(fill="both", expand=True, pady=(8, 0))
        tree = _tree(ref, (("code", "Code", 50), ("label", "Meaning", 360),
                           ("cat", "Counts as", 300)), height=12)
        for code, (lbl, cat) in AT.CODES.items():
            tree.insert("", "end", values=(code, lbl, AT.CATEGORY_LABELS[cat]))


def draw_attendance(parent: ttk.Frame, *, principal: Principal, state: dict | None = None,
                    open_pupil: Callable[[int], None] | None = None) -> AttendancePage:
    return AttendancePage(parent, principal=principal, state=state if state is not None else {},
                          open_pupil=open_pupil)


# ── Dialogs ──────────────────────────────────────────────────────────

def mark_dialog(owner, principal: Principal, session: str, *, title: str,
                current: tuple | None, on_ok: Callable[[str, str | None, int | None], None]
                ) -> None:
    """Pick a code (+ notes, minutes late) for the register; nothing is saved here."""
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Mark - {title}")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    choices = _code_choices(principal, session)
    ttk.Label(frm, text="Code").grid(row=0, column=0, sticky="w")
    cb = ttk.Combobox(frm, values=choices, state="readonly", width=52)
    cb.grid(row=0, column=1, sticky="w", pady=2)
    if current:
        cb.set(next((c for c in choices if c.split()[0] == current[0]), ""))
    ttk.Label(frm, text="Minutes late").grid(row=1, column=0, sticky="w")
    mins = ttk.Entry(frm, width=6)
    mins.grid(row=1, column=1, sticky="w", pady=2)
    ttk.Label(frm, text="Notes").grid(row=2, column=0, sticky="w")
    notes = ttk.Entry(frm, width=52)
    notes.grid(row=2, column=1, sticky="w", pady=2)
    if current:
        notes.insert(0, current[1] or "")
        mins.insert(0, "" if current[2] is None else str(current[2]))

    def ok() -> None:
        if not cb.get():
            messagebox.showerror("Mark", "Choose a code.", parent=win)
            return
        win.destroy()
        on_ok(cb.get().split()[0], notes.get().strip() or None, mins.get().strip() or None)

    bar = ttk.Frame(frm)
    bar.grid(row=3, column=0, columnspan=2, sticky="e", pady=(8, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="OK", command=ok).pack(side="right", padx=(0, 6))


def single_mark_dialog(owner, principal: Principal, pupil: P.Pupil, day: str, session: str, *,
                       after: Callable[[], None]) -> None:
    """Record one mark straight away (old 'Single mark')."""
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Single mark - {pupil.display_name}")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"Pupil: {pupil.display_name} ({pupil.admission_no})",
              font=("", 10, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
    date_e = ttk.Entry(frm, width=12)
    date_e.insert(0, day)
    sess = ttk.Combobox(frm, values=list(AT.SESSIONS), state="readonly", width=4)
    sess.set(session)
    code = ttk.Combobox(frm, state="readonly", width=52)
    mins = ttk.Entry(frm, width=6)
    notes = ttk.Entry(frm, width=52)
    for i, (text, w) in enumerate((("Date:", date_e), ("Session:", sess), ("Mark:", code),
                                   ("Minutes late:", mins), ("Notes:", notes)), start=1):
        ttk.Label(frm, text=text).grid(row=i, column=0, sticky="w", pady=2)
        w.grid(row=i, column=1, sticky="w", pady=2)

    def fill(_e=None) -> None:
        choices = _code_choices(principal, sess.get())
        code.configure(values=choices)
        d = _day(date_e.get())
        m = AT.get_for(pupil.pupil_id, d, sess.get()) if d else None
        code.set(next((c for c in choices if m and c.split()[0] == m.code), ""))
        notes.delete(0, "end")
        mins.delete(0, "end")
        if m:
            notes.insert(0, m.notes or "")
            mins.insert(0, "" if m.minutes_late is None else str(m.minutes_late))
    sess.bind("<<ComboboxSelected>>", fill)
    date_e.bind("<FocusOut>", fill)
    fill()

    def save() -> None:
        if not code.get():
            messagebox.showerror("Single mark", "Choose a mark.", parent=win)
            return
        try:
            AT.record_mark(pupil.pupil_id, date_e.get(), sess.get(), code.get().split()[0],
                           actor=principal, notes=notes.get(), minutes_late=mins.get())
        except (AT.ValidationError, AT.PermissionDenied, AT.NotFound) as e:
            messagebox.showerror("Single mark", _problems(e), parent=win)
            return
        win.destroy()
        after()

    bar = ttk.Frame(frm)
    bar.grid(row=6, column=0, columnspan=2, sticky="e", pady=(8, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Save", command=save).pack(side="right", padx=(0, 6))


def late_dialog(owner, principal: Principal, pupil: P.Pupil, day: str, session: str, *,
                after: Callable[[], None]) -> None:
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Late arrival - {pupil.display_name}")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    t = AT.session_times()
    ttk.Label(frm, text=f"{pupil.display_name} ({pupil.admission_no}) · {day} {session}\n"
                        f"Registers close {t['am_close']} (AM) / {t['pm_close']} (PM)",
              justify="left").grid(row=0, column=0, columnspan=2, sticky="w")
    arrived = ttk.Entry(frm, width=7)
    arrived.insert(0, _dt.datetime.now().strftime("%H:%M"))
    reason = ttk.Entry(frm, width=40)
    for i, (text, w) in enumerate((("Arrived (HH:MM):", arrived), ("Reason:", reason)), 1):
        ttk.Label(frm, text=text).grid(row=i, column=0, sticky="w", pady=2)
        w.grid(row=i, column=1, sticky="w", pady=2)

    def save() -> None:
        try:
            m = AT.record_late(pupil.pupil_id, day, session, arrived.get(), actor=principal,
                               notes=reason.get())
        except (AT.ValidationError, AT.PermissionDenied, AT.NotFound) as e:
            messagebox.showerror("Late arrival", _problems(e), parent=win)
            return
        win.destroy()
        messagebox.showinfo("Late arrival", f"Recorded {m.code} - {m.label}, "
                                            f"{m.minutes_late} min late.", parent=owner)
        after()

    bar = ttk.Frame(frm)
    bar.grid(row=3, column=0, columnspan=2, sticky="e", pady=(8, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Save", command=save).pack(side="right", padx=(0, 6))


def range_dialog(owner, principal: Principal, pupil: P.Pupil, *,
                 after: Callable[[], None]) -> None:
    """Office: one code over several school days."""
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Absence over several days - {pupil.display_name}")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    today = _dt.date.today().isoformat()
    start, end = ttk.Entry(frm, width=12), ttk.Entry(frm, width=12)
    start.insert(0, today)
    end.insert(0, today)
    choices = [c for c in _code_choices(principal, "AM") if not c.startswith("/")]
    code = ttk.Combobox(frm, values=choices, state="readonly", width=52)
    am, pm, over = tk.BooleanVar(value=True), tk.BooleanVar(value=True), tk.BooleanVar()
    notes = ttk.Entry(frm, width=52)
    ttk.Label(frm, text=f"{pupil.display_name} ({pupil.admission_no})",
              font=("", 10, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
    for i, (text, w) in enumerate((("From:", start), ("To:", end), ("Code:", code),
                                   ("Notes:", notes)), 1):
        ttk.Label(frm, text=text).grid(row=i, column=0, sticky="w", pady=2)
        w.grid(row=i, column=1, sticky="w", pady=2)
    opts = ttk.Frame(frm)
    opts.grid(row=5, column=1, sticky="w")
    ttk.Checkbutton(opts, text="AM", variable=am).pack(side="left")
    ttk.Checkbutton(opts, text="PM", variable=pm).pack(side="left", padx=6)
    ttk.Checkbutton(opts, text="Replace existing marks (not just N / unmarked)",
                    variable=over).pack(side="left", padx=6)

    def save() -> None:
        if not code.get():
            messagebox.showerror("Absence", "Choose a code.", parent=win)
            return
        try:
            saved, skipped = AT.record_range(
                pupil.pupil_id, start.get(), end.get(), code.get().split()[0], actor=principal,
                sessions=[s for s, v in (("AM", am), ("PM", pm)) if v.get()],
                notes=notes.get(), overwrite=over.get())
        except (AT.ValidationError, AT.PermissionDenied, AT.NotFound) as e:
            messagebox.showerror("Absence", _problems(e), parent=win)
            return
        win.destroy()
        messagebox.showinfo("Absence", f"Recorded {saved} session(s)"
                                       + (f"; {skipped} left as they were" if skipped else "")
                                       + ".", parent=owner)
        after()

    bar = ttk.Frame(frm)
    bar.grid(row=6, column=0, columnspan=2, sticky="e", pady=(8, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Save", command=save).pack(side="right", padx=(0, 6))


def pupil_history_dialog(owner, principal: Principal, pupil: P.Pupil, *,
                         after: Callable[[], None] | None = None) -> None:
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Attendance - {pupil.display_name}")
    win.geometry("860x560")
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    head = ttk.Label(frm, font=("", 11, "bold"))
    head.pack(anchor="w")
    sub = ttk.Label(frm, foreground="#555", justify="left")
    sub.pack(anchor="w", pady=(0, 6))
    tree = _tree(frm, (("date", "Date", 100), ("sess", "Session", 60), ("code", "Code", 50),
                       ("label", "Status", 260), ("late", "Mins late", 70),
                       ("notes", "Notes", 200)), height=14)
    tree.tag_configure("absent", background=ABSENT_BG)
    marks: dict[str, AT.Mark] = {}

    def show() -> None:
        tree.delete(*tree.get_children())
        marks.clear()
        s = AT.pupil_summary(pupil.pupil_id)
        lessons = AT.lesson_summary(pupil.pupil_id)
        head.configure(text=f"{pupil.display_name} ({pupil.admission_no}) · Year "
                            f"{pupil.year_group} {pupil.form_group or ''}")
        pct = "-" if s.attendance_pct is None else f"{s.attendance_pct}%"
        sub.configure(text=(
            f"This year: attendance {pct} of {s.possible} possible sessions · authorised "
            f"{s.authorised} · unauthorised {s.unauthorised} · late {s.late} · unmarked "
            f"{s.unmarked}" + (f" · {s.band.upper()} ABSENCE" if s.band else "")
            + f"\nLessons: present {lessons['P']} · late {lessons['L']} · absent "
              f"{lessons['A']} · away {lessons['X']}"))
        for m in AT.pupil_history(pupil.pupil_id):
            iid = tree.insert("", "end", tags=("absent",) if m.category in (
                AT.AUTHORISED, AT.UNAUTHORISED) else (), values=(
                m.date, m.session, m.code, m.label, m.minutes_late if m.minutes_late is not
                None else "", m.notes or ""))
            marks[iid] = m

    def selected() -> AT.Mark | None:
        sel = tree.selection()
        return marks[sel[0]] if sel else None

    def change() -> None:
        m = selected()
        if m:
            single_mark_dialog(win, principal, pupil, m.date, m.session,
                               after=lambda: (show(), after and after()))

    def remove() -> None:
        m = selected()
        if not m:
            return
        win2 = make_toplevel(win)
        win2.title("Remove mark")
        f2 = ttk.Frame(win2, padding=12)
        f2.pack()
        ttk.Label(f2, text=f"Remove {m.date} {m.session} '{m.code}'? Reason (kept in the "
                           "audit):").pack(anchor="w")
        e = ttk.Entry(f2, width=50)
        e.pack(pady=4)

        def go() -> None:
            try:
                AT.delete_mark(m.mark_id, actor=principal, reason=e.get())
            except (AT.ValidationError, AT.PermissionDenied, AT.NotFound) as err:
                messagebox.showerror("Remove mark", _problems(err), parent=win2)
                return
            win2.destroy()
            show()
            if after:
                after()
        ttk.Button(f2, text="Remove", command=go).pack(side="right")

    def changes() -> None:
        rows = AT.history(pupil.pupil_id)
        text = "\n".join(f"{h['at']}  {h['actor']}: {h['date']} {h['session']} "
                         f"{h['old'] or '-'} → {h['new'] or '(removed)'}"
                         for h in rows if h["action"] in ("mark", "change", "delete"))
        messagebox.showinfo("Changes", text or "No changes recorded.", parent=win)

    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(6, 0))
    ttk.Button(bar, text="Close", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Changes…", command=changes).pack(side="left")
    if principal.role in ATTENDANCE_EDITORS:
        ttk.Button(bar, text="Change mark…", command=change).pack(side="left", padx=4)
        ttk.Button(bar, text="Remove mark…", command=remove).pack(side="left")
        tree.bind("<Double-1>", lambda _e: change())
    show()


def daily_summary_dialog(owner, day: _dt.date) -> None:
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Daily summary - {day.isoformat()}")
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    ok, what = AT.school_day(day)
    ttk.Label(frm, text=f"Date: {day:%A %d %B %Y} - {what}",
              font=("", 11, "bold")).pack(anchor="w", pady=(0, 6))
    for sess, vals in AT.daily_summary(day).items():
        block = ttk.LabelFrame(frm, text=sess, padding=8)
        block.pack(fill="x", pady=4)
        ttk.Label(block, text=(f"On roll {vals['on_roll']} · marked {vals['marked']} · "
                               f"unmarked {vals['unmarked']} · present {vals['present']} · "
                               f"off-site education {vals['aea']} · authorised "
                               f"{vals['authorised']} · unauthorised {vals['unauthorised']}")
                  ).pack(anchor="w")
        if vals["codes"]:
            t = ttk.Treeview(block, columns=("code", "label", "count"), show="headings",
                             height=min(6, len(vals["codes"])))
            for c, text, w in (("code", "Code", 50), ("label", "Status", 300),
                               ("count", "Count", 60)):
                t.heading(c, text=text)
                t.column(c, width=w, anchor="w")
            for code, n in sorted(vals["codes"].items()):
                t.insert("", "end", values=(code, AT.code_label(code), n))
            t.pack(fill="x", pady=(4, 0))
    ttk.Button(frm, text="Close", command=win.destroy).pack(anchor="e", pady=(6, 0))


def lesson_register_dialog(owner, principal: Principal, lesson_id: int, day: _dt.date, *,
                           after: Callable[[], None]) -> None:
    try:
        reg = AT.lesson_register(lesson_id, day)
    except (AT.ValidationError, AT.NotFound) as e:
        messagebox.showerror("Lesson register", _problems(e), parent=owner)
        return
    x = reg.lesson
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Register - {x.subject_code} {x.group_code}")
    win.geometry("760x520")
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"{x.subject_name} · {x.group_code} · {day:%a %d %b} "
                        f"{x.slot_label.split()[-1]} ({reg.session})",
              font=("", 11, "bold")).pack(anchor="w")
    ttk.Label(frm, text=(f"Taken by {reg.taken_by} at {reg.taken_at}" if reg.taken_by else
                         "Not taken yet - marks below are suggestions (X = known absence "
                         "from the session register)."), foreground="#555").pack(anchor="w")
    quick = ttk.Frame(frm)
    quick.pack(fill="x", pady=4)
    tree = _tree(frm, (("pupil", "Adm no", 90), ("name", "Name", 190), ("mark", "Mark", 50),
                       ("label", "Meaning", 230), ("sess", "Session mark", 140)),
                 height=14, select="extended")
    tree.tag_configure("absent", background=ABSENT_BG)
    marks = {r.pupil.pupil_id: r.suggested for r in reg.rows}
    rows = {r.pupil.pupil_id: r for r in reg.rows}

    def draw() -> None:
        sel = tree.selection()
        tree.delete(*tree.get_children())
        for pid, r in rows.items():
            m = marks[pid]
            tree.insert("", "end", iid=str(pid), tags=("absent",) if m == "A" else (), values=(
                r.pupil.admission_no, r.pupil.display_name, m, AT.LESSON_MARKS[m],
                f"{r.session_code} {AT.code_label(r.session_code)}" if r.session_code else "-"))
        tree.selection_set([s for s in sel if tree.exists(s)])

    def set_mark(m: str) -> None:
        for iid in tree.selection():
            marks[int(iid)] = m
        draw()

    for m, text in (("P", "Present (P)"), ("L", "Late (L)"), ("A", "Absent (A)"),
                    ("X", "Away (X)")):
        ttk.Button(quick, text=text, command=lambda c=m: set_mark(c)).pack(side="left", padx=2)
        for key in (m.lower(), m):
            tree.bind(f"<KeyPress-{key}>", lambda _e, c=m: set_mark(c))
    if not rows:
        ttk.Label(frm, text="No pupils in this group.", foreground="#a60").pack(anchor="w")
    draw()

    def save() -> None:
        try:
            n = AT.save_lesson_register(lesson_id, day, dict(marks), actor=principal)
        except (AT.ValidationError, AT.PermissionDenied, AT.NotFound) as e:
            messagebox.showerror("Lesson register", _problems(e), parent=win)
            return
        win.destroy()
        messagebox.showinfo("Lesson register", f"Saved {n} mark(s).", parent=owner)
        after()

    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(6, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Save register", command=save).pack(side="right", padx=(0, 6))
