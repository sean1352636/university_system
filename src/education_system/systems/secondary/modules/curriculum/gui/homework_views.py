"""Homework screen.

The old Homework window is the Homework tab: Year / Status filters and New,
Edit, Set status, Seed, Submissions, Summary, Delete and Refresh, with the old
columns. The old Submissions window keeps Seed pupils, Add / edit submission,
Edit selected, Delete selected and Refresh. Added: homework set to a teaching
group, my homework, copy to another group, e-mailing parents about missing
homework, exporting marks, ticking off several pupils at once, To mark, the
missing-homework report, the homework timetable and the daily limit.
Rules live in :mod:`modules.curriculum.domain.homework`.
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
    simpledialog,
)
from education_system.systems.secondary.modules.curriculum.domain import homework as HW
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.core.permissions.access import HOMEWORK_EDITORS, Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
ALL = "All"
YEARS = ("7", "8", "9", "10", "11")
STATUS_BG = {"Draft": "#eeeeee", "Set": "#e6f2ff", "Closed": "#e7f6ea",
             "Pending": "#ffffff", "Submitted": "#e6f2ff", "Late": "#fff6d5",
             "Missing": "#fde2e2", "Graded": "#e7f6ea", "Excused": "#eeeeee",
             "overdue": "#fde2e2"}
_ERRORS = (HW.ValidationError, HW.PermissionDenied, HW.NotFound)


_problems = W.problems


def _tree(parent, columns, height: int = 10, *, multi: bool = False) -> ttk.Treeview:
    return W.tree(parent, columns, height=height, select="extended" if multi else "browse",
                  stretch={"title", "feedback", "titles", "name", "pupil"}, tags=STATUS_BG)


_text_window = W.text_window


_TASK_COLS = (("id", "ID", 45), ("due", "Due", 90), ("year", "Yr", 35), ("form", "Form", 80),
              ("subj", "Subject", 70), ("title", "Title", 240), ("by", "Set by", 120),
              ("pts", "Pts", 40), ("status", "Status", 70))


def _task_row(t: HW.Task) -> tuple:
    return (t.task_id, t.due_date, t.year_group, t.group_code or t.form_group or "",
            t.subject_code, t.title, t.set_by_name or "", t.points or "", t.status)


class HomeworkPage:
    TABS = ("Homework", "To mark", "Missing homework", "Homework timetable", "Settings")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        self.editor = principal.role in HOMEWORK_EDITORS
        activity_log.record("homework.view")
        ttk.Label(parent, text="Homework", font=("", 16, "bold")).pack(anchor="w")
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(anchor="w",
                                                                                 pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._build_homework(self.tabs["Homework"])
        self.book.select(self.TABS.index(state.get("tab", "Homework")))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        if name == "Homework":
            self.refresh()
            return
        tab = self.tabs[name]
        for w in tab.winfo_children():
            w.destroy()
        try:
            {"To mark": self._draw_to_mark, "Missing homework": self._draw_missing,
             "Homework timetable": self._draw_timetable,
             "Settings": self._draw_settings}[name](tab)
        except Exception:
            logger.exception("Homework tab %s failed", name)
            ttk.Label(tab, text="Couldn't load this tab - see the log.",
                      foreground="#a00").pack(anchor="w")

    # ── Homework tab (old window) ────────────────────────────────────

    def _build_homework(self, tab: ttk.Frame) -> None:
        st = self.state
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.year_var = tk.StringVar(value=st.get("year", ALL))
        self.status_var = tk.StringVar(value=st.get("status", ALL))
        ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar, textvariable=self.year_var, values=[ALL, *YEARS], state="readonly",
                     width=5).pack(side="left")
        ttk.Label(bar, text="Status:").pack(side="left", padx=(8, 4))
        ttk.Combobox(bar, textvariable=self.status_var, values=[ALL, *HW.STATUSES],
                     state="readonly", width=8).pack(side="left")
        for text, cmd in (("New", self.new), ("Edit", self.edit),
                          ("Set status", self.set_status), ("Seed", self.seed),
                          ("Submissions", self.submissions), ("Summary", self.show_summary),
                          ("Delete", self.delete), ("Refresh", self.refresh)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(0, 4))
        self.mine_var = tk.BooleanVar(value=st.get("mine", not self.editor))
        ttk.Checkbutton(bar2, text="Only mine", variable=self.mine_var,
                        command=self.refresh).pack(side="left")
        ttk.Label(bar2, text="Search:").pack(side="left", padx=(8, 4))
        self.search_var = tk.StringVar(value=st.get("search", ""))
        search = ttk.Entry(bar2, textvariable=self.search_var, width=18)
        search.pack(side="left")
        search.bind("<Return>", lambda _e: self.refresh())
        for text, cmd in (("Copy…", self.copy), ("View / print", self.view_text),
                          ("E-mail parents…", self.email_parents),
                          ("Export marks…", self.export), ("History", self.history)):
            ttk.Button(bar2, text=text, command=cmd).pack(side="left", padx=(8, 2))
        for var in (self.year_var, self.status_var):
            var.trace_add("write", lambda *_: self.refresh())
        self.tree = _tree(tab, _TASK_COLS, height=14)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._detail())
        self.tree.bind("<Double-1>", lambda _e: self.submissions())
        box = ttk.LabelFrame(tab, text="Selected homework", padding=8)
        box.pack(fill="x", pady=(8, 0))
        self.detail_var = tk.StringVar(value="(select a row to see the details)")
        ttk.Label(box, textvariable=self.detail_var, justify="left",
                  wraplength=1100).pack(anchor="w")
        self.rows: dict[str, HW.Task] = {}

    def refresh(self) -> None:
        st = self.state
        st.update(year=self.year_var.get(), status=self.status_var.get(),
                  mine=self.mine_var.get(), search=self.search_var.get())
        year, status = self.year_var.get(), self.status_var.get()
        try:
            rows = HW.list_tasks(year_group=None if year == ALL else int(year),
                                 status=None if status == ALL else status,
                                 teacher=self.principal.username if self.mine_var.get()
                                 else None, search=self.search_var.get().strip() or None)
        except HW.ValidationError as e:
            messagebox.showerror("Homework", _problems(e), parent=self.parent)
            return
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        for t in rows:
            iid = str(t.task_id)
            self.rows[iid] = t
            self.tree.insert("", "end", iid=iid, values=_task_row(t),
                             tags=("overdue" if t.overdue else t.status,))
        c = HW.status_counts()
        self.summary_var.set(f"{len(rows)} shown · Draft {c['Draft']} · Set {c['Set']} · "
                             f"Closed {c['Closed']} · daily limit {HW.daily_limit()} per pupil")
        self._detail()

    def _selected(self, quiet: bool = False) -> HW.Task | None:
        sel = self.tree.selection()
        if not sel:
            if not quiet:
                messagebox.showinfo("Homework", "Select a homework first.", parent=self.parent)
            return None
        return self.rows.get(sel[0])

    def _detail(self) -> None:
        t = self._selected(quiet=True)
        if t is None:
            self.detail_var.set("(select a row to see the details)")
            return
        try:
            s = HW.summary(t.task_id)
        except Exception:  # noqa: BLE001
            logger.exception("Homework summary failed")
            s = None
        lines = [f"{t.title} · {t.subject_name} · {t.for_label} · set {t.set_date} · due "
                 f"{t.due_date}" + (" (OVERDUE - close it)" if t.overdue else "")
                 + (f" · about {t.est_minutes} min" if t.est_minutes else ""),
                 f"Instructions: {(t.instructions or '-')[:300]}"]
        if t.resources:
            lines.append(f"Resources: {t.resources[:200]}")
        if s and s["total"]:
            b = s["by_status"]
            lines.append(f"{s['total']} pupils · handed in {s['handed_in']} (late "
                         f"{s['late']}) · to mark {s['to_mark']} · missing {b['Missing']} · "
                         f"excused {b['Excused']} · pending {b['Pending']}"
                         + (f" · average {s['average_pct']}%" if s["average_pct"] is not None
                            else ""))
        self.detail_var.set("\n".join(lines))

    def _report(self, title: str, warnings: list[str]) -> None:
        if warnings:
            messagebox.showwarning(title, "Saved. Note:\n" + "\n".join(f"• {w}" for w in
                                                                       warnings),
                                   parent=self.parent)

    def new(self) -> None:
        task_dialog(self.parent, self.principal, None, self._after_save)

    def edit(self) -> None:
        t = self._selected()
        if t:
            task_dialog(self.parent, self.principal, t, self._after_save)

    def _after_save(self, warnings: list[str]) -> None:
        self.refresh()
        self._report("Homework", warnings)

    def set_status(self) -> None:
        t = self._selected()
        if t:
            status_dialog(self.parent, self.principal, t, self._after_save)

    def seed(self) -> None:
        t = self._selected()
        if not t:
            return
        try:
            n = HW.seed(t.task_id, actor=self.principal)
        except _ERRORS as e:
            messagebox.showerror("Seed", _problems(e), parent=self.parent)
            return
        messagebox.showinfo("Seed", f"Added {n} pupil(s) to {t.for_label}'s list."
                            if n else "Everyone in the class is already on the list.",
                            parent=self.parent)
        self.refresh()

    def submissions(self) -> None:
        t = self._selected()
        if t:
            SubmissionsWindow(self.parent, self.principal, t, on_close=self.refresh)

    def show_summary(self) -> None:
        t = self._selected()
        if not t:
            return
        s = HW.summary(t.task_id)
        lines = [f"{t.title} ({t.for_label}, due {t.due_date})", "",
                 f"Pupils:        {s['total']}"]
        lines += [f"  {k:<12} {v}" for k, v in s["by_status"].items()]
        lines += ["", f"Handed in:     {s['handed_in']} (late {s['late']})",
                  f"Completion:    {s['completion_pct'] if s['completion_pct'] is not None else '-'}%",
                  f"Marked:        {s['marked']}",
                  f"Average mark:  {s['average_pct'] if s['average_pct'] is not None else '-'}%"]
        messagebox.showinfo("Summary", "\n".join(lines), parent=self.parent)

    def delete(self) -> None:
        t = self._selected()
        if not t or not messagebox.askyesno(
                "Delete homework", f"Delete '{t.title}' for {t.for_label} and every pupil's "
                "record of it?", parent=self.parent):
            return
        try:
            HW.delete(t.task_id, actor=self.principal)
        except _ERRORS as e:
            messagebox.showerror("Delete homework", _problems(e), parent=self.parent)
            return
        self.refresh()

    def copy(self) -> None:
        t = self._selected()
        if t:
            copy_dialog(self.parent, self.principal, t, self._after_save)

    def view_text(self) -> None:
        t = self._selected()
        if t:
            _text_window(self.parent, t.title, HW.as_text(t.task_id),
                         save_name=f"homework-{t.task_id}.txt")

    def email_parents(self) -> None:
        t = self._selected()
        if not t:
            return
        missing = [w for w in HW.list_work(t.task_id) if w.status == "Missing"]
        if not missing:
            messagebox.showinfo("E-mail parents", "Nobody's homework is marked Missing.",
                                parent=self.parent)
            return
        email_parents_dialog(self.parent, self.principal, t, missing)

    def export(self) -> None:
        t = self._selected()
        if t:
            _export_marks(self.parent, self.principal, t)

    def history(self) -> None:
        t = self._selected()
        if not t:
            return
        rows = HW.history(task_id=t.task_id)
        text = "\n".join(f"{h['at']}  {h['actor']:<12} {h['action']:<12} "
                         f"{', '.join(f'{k}={v}' for k, v in h['detail'].items())}"
                         for h in rows) or "No changes recorded."
        _text_window(self.parent, f"History - {t.title}", text)

    # ── Other tabs ───────────────────────────────────────────────────

    def _draw_to_mark(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        everyone = tk.BooleanVar(value=self.state.get("to_mark_all", False))
        tree = _tree(tab, (("id", "ID", 45), ("due", "Due", 90), ("for", "For", 90),
                           ("subj", "Subject", 70), ("title", "Title", 260),
                           ("by", "Set by", 120), ("n", "To mark", 70)), height=16)
        rows: dict[str, HW.Task] = {}

        def fill() -> None:
            self.state["to_mark_all"] = everyone.get()
            tree.delete(*tree.get_children())
            rows.clear()
            for t, n in HW.to_mark(self.principal, everyone=everyone.get()):
                rows[str(t.task_id)] = t
                tree.insert("", "end", iid=str(t.task_id), values=(
                    t.task_id, t.due_date, t.for_label, t.subject_code, t.title,
                    t.set_by_name or "", n))
            if not rows:
                tree.insert("", "end", values=("", "", "", "", "Nothing waiting to be marked.",
                                               "", ""))

        def open_selected() -> None:
            sel = tree.selection()
            if sel and sel[0] in rows:
                SubmissionsWindow(self.parent, self.principal, rows[sel[0]], on_close=fill)
        if self.editor:
            ttk.Checkbutton(bar, text="Everyone's homework", variable=everyone,
                            command=fill).pack(side="left")
        ttk.Button(bar, text="Open submissions", command=open_selected).pack(side="left",
                                                                            padx=8)
        ttk.Button(bar, text="Refresh", command=fill).pack(side="left")
        tree.bind("<Double-1>", lambda _e: open_selected())
        fill()

    def _draw_missing(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        start = tk.StringVar(value=self.state.get("miss_from", ""))
        end = tk.StringVar(value=self.state.get("miss_to", ""))
        year = tk.StringVar(value=self.state.get("miss_year", ALL))
        for label, var, w in (("From:", start, 11), ("To:", end, 11)):
            ttk.Label(bar, text=label).pack(side="left", padx=(8, 4))
            ttk.Entry(bar, textvariable=var, width=w).pack(side="left")
        ttk.Label(bar, text="Year:").pack(side="left", padx=(8, 4))
        ttk.Combobox(bar, textvariable=year, values=[ALL, *YEARS], state="readonly",
                     width=5).pack(side="left")
        tree = _tree(tab, (("name", "Pupil", 170), ("adm", "Adm no", 90), ("form", "Form", 60),
                           ("set", "Due", 45), ("missing", "Missing", 60),
                           ("late", "Late", 45), ("titles", "Missing homework", 420)),
                     height=16)
        note = tk.StringVar()
        ttk.Label(tab, textvariable=note, foreground="#666").pack(anchor="w", pady=(4, 0))

        def fill() -> None:
            self.state.update(miss_from=start.get(), miss_to=end.get(), miss_year=year.get())
            try:
                rows = HW.missing_report(start=start.get().strip() or None,
                                         end=end.get().strip() or None,
                                         year_group=None if year.get() == ALL
                                         else int(year.get()))
            except HW.ValidationError as e:
                messagebox.showerror("Missing homework", _problems(e), parent=self.parent)
                return
            tree.delete(*tree.get_children())
            for r in rows:
                tree.insert("", "end", iid=str(r["pupil_id"]), values=(
                    r["name"], r["admission_no"], r["form_group"] or "", r["set"],
                    r["missing"], r["late"], "; ".join(r["titles"])),
                    tags=("Missing" if r["missing"] else "Late",))
            note.set(f"{len(rows)} pupil(s) with missing or late homework (blank dates = "
                     "this academic year to today)."
                     + (" Double-click a pupil to open their record." if self.open_pupil
                        else ""))
        ttk.Button(bar, text="Show", command=fill).pack(side="left", padx=8)
        if self.open_pupil:
            tree.bind("<Double-1>", lambda _e: tree.selection() and self.open_pupil(
                int(tree.selection()[0])))
        fill()

    def _draw_timetable(self, tab: ttk.Frame) -> None:
        today = _dt.date.today()
        monday = self.state.get("tt_monday") or (today - _dt.timedelta(days=today.weekday())
                                                 ).isoformat()
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        year = tk.StringVar(value=self.state.get("tt_year", ALL))
        label = tk.StringVar()

        def move(days: int) -> None:
            d = _dt.date.fromisoformat(self.state.get("tt_monday", monday))
            self.state["tt_monday"] = (d + _dt.timedelta(days=days)).isoformat()
            fill()
        ttk.Button(bar, text="◀ Week", command=lambda: move(-7)).pack(side="left")
        ttk.Button(bar, text="Week ▶", command=lambda: move(7)).pack(side="left", padx=4)
        ttk.Label(bar, textvariable=label, font=("", 10, "bold")).pack(side="left", padx=8)
        ttk.Label(bar, text="Year:").pack(side="left", padx=(8, 4))
        cb = ttk.Combobox(bar, textvariable=year, values=[ALL, *YEARS], state="readonly",
                          width=5)
        cb.pack(side="left")
        tree = _tree(tab, (("day", "Due", 110), ("yr", "Yr", 35), ("for", "For", 90),
                           ("subj", "Subject", 70), ("title", "Title", 280),
                           ("mins", "Minutes", 60), ("status", "Status", 70)), height=16)
        tree.tag_configure("day", font=("", 9, "bold"))

        def fill() -> None:
            self.state["tt_monday"] = self.state.get("tt_monday", monday)
            self.state["tt_year"] = year.get()
            start = _dt.date.fromisoformat(self.state["tt_monday"])
            end = start + _dt.timedelta(days=6)
            label.set(f"Week of {start:%d %b %Y}")
            cal = HW.due_calendar(start, end, year_group=None if year.get() == ALL
                                  else int(year.get()))
            tree.delete(*tree.get_children())
            for day, tasks in cal.items():
                d = _dt.date.fromisoformat(day)
                mins = sum(t.est_minutes or 0 for t in tasks)
                tree.insert("", "end", values=(f"{d:%a %d %b}", "", f"{len(tasks)} due", "",
                                               "", mins or "", ""), tags=("day",))
                for t in tasks:
                    tree.insert("", "end", values=("", t.year_group, t.for_label,
                                                   t.subject_code, t.title,
                                                   t.est_minutes or "", t.status),
                                tags=(t.status,))
            if not cal:
                tree.insert("", "end", values=("", "", "", "", "No homework due this week.",
                                               "", ""))
        cb.bind("<<ComboboxSelected>>", lambda _e: fill())
        fill()

    def _draw_settings(self, tab: ttk.Frame) -> None:
        box = ttk.LabelFrame(tab, text="Daily homework limit", padding=8)
        box.pack(fill="x")
        ttk.Label(box, text="A warning is given when homework would make a pupil have more "
                            "than this many pieces due on one day.").pack(anchor="w")
        row = ttk.Frame(box)
        row.pack(anchor="w", pady=(4, 0))
        var = tk.StringVar(value=str(HW.daily_limit()))
        spin = ttk.Spinbox(row, from_=1, to=10, textvariable=var, width=5)
        spin.pack(side="left")

        def save() -> None:
            try:
                n = HW.set_daily_limit(var.get(), actor=self.principal)
            except _ERRORS as e:
                messagebox.showerror("Daily limit", _problems(e), parent=self.parent)
                return
            messagebox.showinfo("Daily limit", f"Daily limit is now {n}.", parent=self.parent)
            self.refresh()
        b = ttk.Button(row, text="Save", command=save)
        b.pack(side="left", padx=6)
        if not self.editor:
            spin.state(["disabled"])
            b.state(["disabled"])
            ttk.Label(row, text="(administrators change this)", foreground="#888").pack(
                side="left")
        rep = ttk.LabelFrame(tab, text="Completion this year by class", padding=8)
        rep.pack(fill="both", expand=True, pady=(8, 0))
        tree = _tree(rep, (("for", "Class", 100), ("subj", "Subject", 70),
                           ("tasks", "Homeworks", 80), ("n", "Pupil pieces", 90),
                           ("done", "Handed in", 80), ("pct", "Completion %", 90),
                           ("avg", "Average mark %", 100)), height=12)
        for r in HW.completion_by_group():
            tree.insert("", "end", values=(r["for"], r["subject"], r["tasks"],
                                           r["pupil_tasks"], r["handed_in"],
                                           r["completion_pct"] if r["completion_pct"]
                                           is not None else "-",
                                           r["average_pct"] if r["average_pct"] is not None
                                           else "-"))


def draw_homework(parent: ttk.Frame, *, principal: Principal, state: dict | None = None,
                  open_pupil: Callable[[int], None] | None = None) -> HomeworkPage:
    return HomeworkPage(parent, principal=principal, state=state if state is not None else {},
                        open_pupil=open_pupil)


# ── Submissions window (old) ─────────────────────────────────────────

_WORK_COLS = (("id", "ID", 45), ("pupil", "Pupil", 170), ("submitted", "Submitted", 90),
              ("status", "Status", 80), ("grade", "Grade", 60), ("pct", "%", 50),
              ("mark", "Mark", 70), ("feedback", "Feedback", 260))


class SubmissionsWindow:
    def __init__(self, owner, principal: Principal, task: HW.Task, *,
                 on_close: Callable[[], None]) -> None:
        self.principal, self.task, self.on_close = principal, task, on_close
        self.win = win = make_toplevel(owner.winfo_toplevel())
        win.title(f"Submissions - {task.title}")
        win.geometry("1000x600")
        win.protocol("WM_DELETE_WINDOW", self.close)
        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=f"{task.title}    Yr {task.year_group}    {task.for_label}    "
                            f"due {task.due_date}    {task.status}",
                  font=("", 11, "bold")).pack(anchor="w")
        self.info = tk.StringVar()
        ttk.Label(frm, textvariable=self.info, foreground="#666").pack(anchor="w", pady=(0, 4))
        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=(0, 4))
        for text, cmd in (("Seed pupils", self.seed), ("Add / edit submission", self.add),
                          ("Edit selected", self.edit), ("Delete selected", self.delete),
                          ("Refresh", self.refresh)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        bar2 = ttk.Frame(frm)
        bar2.pack(fill="x", pady=(0, 4))
        ttk.Label(bar2, text="Selected pupils:").pack(side="left")
        for text, status in (("Handed in", "Submitted"), ("Missing", "Missing"),
                             ("Pending", "Pending")):
            ttk.Button(bar2, text=text, command=lambda s=status: self.bulk(s)).pack(
                side="left", padx=2)
        ttk.Button(bar2, text="Excused…", command=self.excuse).pack(side="left", padx=2)
        ttk.Button(bar2, text="Export marks…", command=lambda: _export_marks(
            self.win, self.principal, self.task)).pack(side="right")
        self.tree = _tree(frm, _WORK_COLS, height=18, multi=True)
        self.tree.bind("<Double-1>", lambda _e: self.edit())
        self.rows: dict[str, HW.Work] = {}
        self.refresh()

    def close(self) -> None:
        self.win.destroy()
        self.on_close()

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        for w in HW.list_work(self.task.task_id):
            iid = str(w.pupil_id)
            self.rows[iid] = w
            pct = w.mark_pct
            self.tree.insert("", "end", iid=iid, values=(
                w.work_id, w.pupil_name, w.handed_in or "", w.status, w.grade or "",
                "" if pct is None else f"{pct:g}", w.mark_label if w.mark is not None else "",
                (w.feedback or w.excuse_reason or "")[:120]), tags=(w.status,))
        s = HW.summary(self.task.task_id)
        self.info.set(f"{s['total']} pupils · handed in {s['handed_in']} (late {s['late']}) · "
                      f"to mark {s['to_mark']} · missing {s['by_status']['Missing']}"
                      + (f" · average {s['average_pct']}%" if s["average_pct"] is not None
                         else "")
                      + ("" if self.task.points is None else
                         f" · marked out of {self.task.points}"))

    def _chosen(self) -> list[int]:
        return [int(i) for i in self.tree.selection()]

    def seed(self) -> None:
        try:
            n = HW.seed(self.task.task_id, actor=self.principal)
        except _ERRORS as e:
            messagebox.showerror("Seed pupils", _problems(e), parent=self.win)
            return
        messagebox.showinfo("Seed pupils", f"Added {n} pupil(s).", parent=self.win)
        self.refresh()

    def add(self) -> None:
        work_dialog(self.win, self.principal, self.task, None, self.refresh)

    def edit(self) -> None:
        chosen = self._chosen()
        if not chosen:
            messagebox.showinfo("Edit", "Select a pupil first.", parent=self.win)
            return
        work_dialog(self.win, self.principal, self.task, self.rows[str(chosen[0])],
                    self.refresh)

    def delete(self) -> None:
        chosen = self._chosen()
        if not chosen or not messagebox.askyesno(
                "Delete", f"Remove {len(chosen)} pupil(s) from this homework's list?",
                parent=self.win):
            return
        problems = []
        for pid in chosen:
            try:
                HW.delete_work(self.task.task_id, pid, actor=self.principal)
            except _ERRORS as e:
                problems.append(f"{self.rows[str(pid)].pupil_name}: {_problems(e)}")
        if problems:
            messagebox.showerror("Delete", "\n".join(problems), parent=self.win)
        self.refresh()

    def bulk(self, status: str, reason: str | None = None) -> None:
        chosen = self._chosen()
        if not chosen:
            messagebox.showinfo("Homework", "Select one or more pupils first (Ctrl/Shift-click "
                                "for several).", parent=self.win)
            return
        try:
            n, problems = HW.record_many(self.task.task_id, chosen, status,
                                         actor=self.principal, excuse_reason=reason)
        except _ERRORS as e:
            messagebox.showerror("Homework", _problems(e), parent=self.win)
            return
        if problems:
            messagebox.showwarning("Homework", f"{n} updated. Not changed:\n"
                                   + "\n".join(problems), parent=self.win)
        self.refresh()

    def excuse(self) -> None:
        if not self._chosen():
            self.bulk("Excused")
            return
        reason = simpledialog.askstring("Excused", "Why are they excused?", parent=self.win)
        if reason:
            self.bulk("Excused", reason)


# ── Dialogs ──────────────────────────────────────────────────────────

def _grid_rows(frm, rows, start: int = 0) -> None:
    for i, (text, w) in enumerate(rows, start):
        ttk.Label(frm, text=text).grid(row=i, column=0, sticky="nw", pady=2, padx=(0, 8))
        w.grid(row=i, column=1, sticky="w", pady=2)


def _buttons(frm, row: int, win, save, label: str = "Save") -> None:
    bar = ttk.Frame(frm)
    bar.grid(row=row, column=0, columnspan=2, sticky="e", pady=(8, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text=label, command=save).pack(side="right", padx=(0, 6))


def _group_choices() -> dict[str, TG.TeachingGroup]:
    return {f"{i.group.code} - {i.subject.code} Y{i.group.year_group}"
            + (f" ({i.group.teacher_name})" if i.group.teacher_name else ""): i.group
            for i in TG.info(TG.list_groups()) if i.group.is_active}


def _text(frm, value: str | None, height: int = 4) -> tk.Text:
    t = tk.Text(frm, width=60, height=height, wrap="word")
    t.insert("1.0", value or "")
    return t


def task_dialog(owner, principal: Principal, task: HW.Task | None,
                after: Callable[[list[str]], None]) -> None:
    """New / Edit homework: for a teaching group, or a whole year (and form)."""
    win = make_toplevel(owner.winfo_toplevel())
    win.title("Edit homework" if task else "New homework")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    groups = _group_choices()
    subjects = {f"{s.code} - {s.name}": s for s in S.list_subjects()}
    teachers = {f"{t['display_name']} ({t['username']})": t for t in TG.teacher_choices()}
    locked = task is not None and task.status != "Draft"
    mode = tk.StringVar(value="year" if task and task.group_id is None and not task.group_code
                        else "group")
    title = ttk.Entry(frm, width=50)
    kind = ttk.Frame(frm)
    ttk.Radiobutton(kind, text="Teaching group", variable=mode, value="group").pack(side="left")
    ttk.Radiobutton(kind, text="Whole year (old style)", variable=mode,
                    value="year").pack(side="left", padx=8)
    group_cb = ttk.Combobox(frm, values=list(groups), state="readonly", width=48)
    year_row = ttk.Frame(frm)
    subj_cb = ttk.Combobox(year_row, values=list(subjects), state="readonly", width=22)
    year_cb = ttk.Combobox(year_row, values=YEARS, state="readonly", width=4)
    form_e = ttk.Entry(year_row, width=8)
    for lbl, w in (("Subject", subj_cb), ("Year", year_cb), ("Form (optional)", form_e)):
        ttk.Label(year_row, text=lbl).pack(side="left", padx=(0, 4))
        w.pack(side="left", padx=(0, 8))
    dates = ttk.Frame(frm)
    set_e = ttk.Entry(dates, width=11)
    due_e = ttk.Entry(dates, width=11)
    pts_e = ttk.Entry(dates, width=6)
    min_e = ttk.Entry(dates, width=6)
    for lbl, w in (("Set", set_e), ("Due *", due_e), ("Points", pts_e), ("Minutes", min_e)):
        ttk.Label(dates, text=lbl).pack(side="left", padx=(0, 4))
        w.pack(side="left", padx=(0, 8))
    by_cb = ttk.Combobox(frm, values=list(teachers), width=40)
    instr, res, notes = _text(frm, None, 5), _text(frm, None, 2), _text(frm, None, 2)
    set_now = tk.BooleanVar(value=False)
    if task:
        title.insert(0, task.title)
        label = next((k for k, g in groups.items() if g.group_id == task.group_id), "")
        group_cb.set(label or (task.group_code or ""))
        subj_cb.set(next((k for k, s in subjects.items() if s.subject_id == task.subject_id),
                         ""))
        year_cb.set(str(task.year_group))
        form_e.insert(0, task.form_group or "")
        set_e.insert(0, task.set_date)
        due_e.insert(0, task.due_date)
        pts_e.insert(0, str(task.points or ""))
        min_e.insert(0, str(task.est_minutes or ""))
        by_cb.set(next((k for k, t in teachers.items()
                        if t["username"] == task.set_by_username), task.set_by_name or ""))
        for widget, value in ((instr, task.instructions), (res, task.resources),
                              (notes, task.notes)):
            widget.insert("1.0", value or "")
    else:
        set_e.insert(0, _dt.date.today().isoformat())
    rows = [("Title *", title), ("Set to", kind), ("Group", group_cb), ("Year", year_row),
            ("Dates", dates), ("Set by", by_cb), ("Instructions", instr),
            ("Resources / links", res), ("Notes", notes)]
    _grid_rows(frm, rows)
    if locked:
        for w in (group_cb, subj_cb, year_cb, form_e):
            w.state(["disabled"])
        ttk.Label(frm, text="Already set - copy it to set it to another class.",
                  foreground="#888").grid(row=len(rows), column=1, sticky="w")
    elif task is None:
        ttk.Checkbutton(frm, text="Set it now (adds the class to the list)",
                        variable=set_now).grid(row=len(rows), column=1, sticky="w")

    def toggle(*_a) -> None:
        if locked:
            return
        g = mode.get() == "group"
        group_cb.state(["!disabled", "readonly"] if g else ["disabled"])
        for w in (subj_cb, year_cb):
            w.state(["disabled"] if g else ["!disabled", "readonly"])
        form_e.state(["disabled"] if g else ["!disabled"])
    mode.trace_add("write", toggle)
    toggle()

    def save() -> None:
        data = {"title": title.get(), "set_date": set_e.get(), "due_date": due_e.get(),
                "points": pts_e.get(), "est_minutes": min_e.get(),
                "instructions": instr.get("1.0", "end"), "resources": res.get("1.0", "end"),
                "notes": notes.get("1.0", "end")}
        who = teachers.get(by_cb.get())
        if who:
            data.update(set_by_username=who["username"], set_by_name=who["display_name"])
        elif by_cb.get().strip():
            data.update(set_by_username=None, set_by_name=by_cb.get())
        if not locked:
            if mode.get() == "group":
                g = groups.get(group_cb.get())
                data.update(group_id=g.group_id if g else None)
                if g is None and task is None:
                    data["group_id"] = ""
            else:
                s = subjects.get(subj_cb.get())
                data.update(group_id=None, subject_id=s.subject_id if s else None,
                            year_group=year_cb.get(), form_group=form_e.get())
        try:
            if task is None:
                if set_now.get():
                    data["status"] = "Set"
                _t, warnings = HW.create(data, actor=principal)
            else:
                _t, warnings = HW.update(task.task_id, data, actor=principal)
        except _ERRORS as e:
            messagebox.showerror("Homework", _problems(e), parent=win)
            return
        win.destroy()
        after(warnings)
    _buttons(frm, len(rows) + 1, win, save)


def status_dialog(owner, principal: Principal, task: HW.Task,
                  after: Callable[[list[str]], None]) -> None:
    win = make_toplevel(owner.winfo_toplevel())
    win.title("Set status")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=task.title[:60]).grid(row=0, column=0, columnspan=2, sticky="w")
    ttk.Label(frm, text=f"Current status: {task.status}", foreground="#555").grid(
        row=1, column=0, columnspan=2, sticky="w")
    var = tk.StringVar(value=task.status)
    help_text = {"Draft": "not visible to the class yet (only while nobody has handed in)",
                 "Set": "adds the class to the list as Pending",
                 "Closed": "from the due date: anyone still Pending becomes Missing"}
    for i, s in enumerate(HW.STATUSES, 2):
        ttk.Radiobutton(frm, text=f"{s} - {help_text[s]}", variable=var, value=s).grid(
            row=i, column=0, columnspan=2, sticky="w")

    def save() -> None:
        if var.get() == task.status:
            win.destroy()
            return
        try:
            _t, warnings = HW.set_status(task.task_id, var.get(), actor=principal)
        except _ERRORS as e:
            messagebox.showerror("Set status", _problems(e), parent=win)
            return
        win.destroy()
        after(warnings)
    _buttons(frm, 6, win, save)


def copy_dialog(owner, principal: Principal, task: HW.Task,
                after: Callable[[list[str]], None]) -> None:
    win = make_toplevel(owner.winfo_toplevel())
    win.title("Copy homework")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    groups = {k: g for k, g in _group_choices().items() if g.subject_id == task.subject_id}
    group_cb = ttk.Combobox(frm, values=list(groups), state="readonly", width=46)
    group_cb.set(next((k for k, g in groups.items() if g.group_id == task.group_id), ""))
    title = ttk.Entry(frm, width=46)
    title.insert(0, task.title)
    set_e, due_e = ttk.Entry(frm, width=12), ttk.Entry(frm, width=12)
    set_e.insert(0, _dt.date.today().isoformat())
    _grid_rows(frm, (("Title", title), ("Group", group_cb), ("Set date", set_e),
                     ("Due date *", due_e)))
    ttk.Label(frm, text="The copy is a Draft - set it when it's ready.",
              foreground="#888").grid(row=4, column=1, sticky="w")

    def save() -> None:
        g = groups.get(group_cb.get())
        try:
            _t, warnings = HW.copy(task.task_id, actor=principal,
                                   group_id=g.group_id if g else None, set_date=set_e.get(),
                                   due_date=due_e.get(), title=title.get())
        except _ERRORS as e:
            messagebox.showerror("Copy homework", _problems(e), parent=win)
            return
        win.destroy()
        after(warnings)
    _buttons(frm, 5, win, save, "Copy")


def work_dialog(owner, principal: Principal, task: HW.Task, work: HW.Work | None,
                after: Callable[[], None]) -> None:
    """The old 'Add / edit submission' for one pupil."""
    win = make_toplevel(owner.winfo_toplevel())
    win.title("Submission")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"Assignment: {task.title}", font=("", 10, "bold")).grid(
        row=0, column=0, columnspan=2, sticky="w")
    pupils = {f"{p.legal_last_name}, {p.preferred_name or p.legal_first_name} "
              f"({p.admission_no})": p for p in HW.pupils_for(task)}
    pupil_cb = ttk.Combobox(frm, values=list(pupils), state="readonly", width=40)
    status_cb = ttk.Combobox(frm, values=list(HW.WORK_STATUSES), state="readonly", width=12)
    handed = ttk.Entry(frm, width=12)
    mark = ttk.Entry(frm, width=8)
    grade = ttk.Entry(frm, width=8)
    reason = ttk.Entry(frm, width=40)
    feedback = _text(frm, None, 5)
    if work:
        pupil_cb.set(next((k for k, p in pupils.items() if p.pupil_id == work.pupil_id),
                          work.pupil_name))
        pupil_cb.state(["disabled"])
        status_cb.set(work.status)
        handed.insert(0, work.handed_in or "")
        mark.insert(0, "" if work.mark is None else f"{work.mark:g}")
        grade.insert(0, work.grade or "")
        reason.insert(0, work.excuse_reason or "")
        feedback.insert("1.0", work.feedback or "")
    else:
        status_cb.set("Submitted")
    out_of = f"Mark (out of {task.points})" if task.points else "Mark (%)"
    _grid_rows(frm, (("Pupil", pupil_cb), ("Status", status_cb), ("Handed in", handed),
                     (out_of, mark), ("Grade", grade), ("Excused because", reason),
                     ("Feedback", feedback)), start=1)
    ttk.Label(frm, text="Handed in after the due date is recorded as Late; blank = today.",
              foreground="#888").grid(row=8, column=1, sticky="w")

    def save() -> None:
        p = pupils.get(pupil_cb.get())
        pid = work.pupil_id if work else (p.pupil_id if p else None)
        if pid is None:
            messagebox.showerror("Submission", "Choose the pupil.", parent=win)
            return
        status = status_cb.get()
        data = {"status": status, "feedback": feedback.get("1.0", "end"),
                "excuse_reason": reason.get()}
        if status in HW.HANDED_IN:
            data.update(handed_in=handed.get(), mark=mark.get(), grade=grade.get())
        try:
            HW.record(task.task_id, pid, data, actor=principal)
        except _ERRORS as e:
            messagebox.showerror("Submission", _problems(e), parent=win)
            return
        win.destroy()
        after()
    _buttons(frm, 9, win, save)


def email_parents_dialog(owner, principal: Principal, task: HW.Task,
                         missing: list[HW.Work]) -> None:
    win = make_toplevel(owner.winfo_toplevel())
    win.title("E-mail parents - missing homework")
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"{len(missing)} pupil(s) haven't handed in '{task.title}': "
                        + ", ".join(w.pupil_name for w in missing[:8])
                        + (" …" if len(missing) > 8 else ""),
              wraplength=600, justify="left").pack(anchor="w")
    ttk.Label(frm, text="Each family gets their own copy; {contact_name} and "
                        "{pupil_first_name} are filled in.", foreground="#888").pack(
        anchor="w", pady=(4, 4))
    body = tk.Text(frm, width=80, height=12, wrap="word")
    body.insert("1.0", HW.email_body(task))
    body.pack(fill="both", expand=True)
    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(8, 0))

    def send() -> None:
        try:
            result = HW.notify_parents(task.task_id, actor=principal,
                                       pupil_ids=[w.pupil_id for w in missing],
                                       body=body.get("1.0", "end"))
        except _ERRORS as e:
            messagebox.showerror("E-mail parents", _problems(e), parent=win)
            return
        from education_system.systems.secondary.modules.communication.gui import email_views

        def done(_report, error) -> None:
            if error:
                messagebox.showwarning("E-mail parents", f"Saved in the outbox but not sent "
                                       f"yet: {error}", parent=owner)
        email_views.deliver_in_background(owner, result.message_id, principal, done)
        no_email = result.pupils_without_email
        messagebox.showinfo("E-mail parents", f"E-mail to {result.recipients} contact(s) is on "
                            "its way (see Email for delivery)."
                            + (f"\n\nNo e-mail address for: "
                               + ", ".join(p.display_name for p in no_email) if no_email
                               else ""), parent=win)
        win.destroy()
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Send", command=send).pack(side="right", padx=6)


def _export_marks(owner, principal: Principal, task: HW.Task) -> None:
    path = filedialog.asksaveasfilename(parent=owner, defaultextension=".csv",
                                        initialfile=f"homework-{task.task_id}-marks.csv",
                                        filetypes=[("CSV", "*.csv")])
    if not path:
        return
    try:
        n = HW.export_marks(task.task_id, path, actor=principal)
    except (*_ERRORS, OSError) as e:
        messagebox.showerror("Export marks", _problems(e), parent=owner)
        return
    messagebox.showinfo("Export marks", f"Saved {n} pupil(s) to {path}.", parent=owner)
