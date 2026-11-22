"""Lesson Plans screen.

The old screen is kept on the Plans tab: Year / Status / Teacher filters, New,
Edit, Set status, Delete and Refresh, the same columns and the "Selected plan"
panel. Added: Subject / Show / From / To / Search filters, Copy, Plan from
timetable and Export; a "My lessons" tab (timetabled lessons and their plans);
and Schemes of work (units with progress). Rules live in
:mod:`modules.curriculum.domain.lesson_plans`.
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
from education_system.systems.secondary.modules.curriculum.domain import lesson_plans as LP
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.curriculum.domain import timetable as TT
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import LESSON_PLAN_EDITORS, Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W
from education_system.systems.secondary.ui.gui.layouts.scroll import scrolled_form

logger = logging.getLogger(__name__)
ALL = "All"
SHARED = "(shared plan - no group)"
NO_UNIT = "(no unit)"
SHOW = ("All plans", "Group plans", "Shared plans")
STATUS_BG = {"Draft": "#fff6d5", "Ready": "#e6f2ff", "Delivered": "#e7f6ea",
             "Reviewed": "#eeeeee"}


_problems = W.problems


def _tree(parent, columns, height: int = 10) -> ttk.Treeview:
    return W.tree(parent, columns, height=height, stretch={"title", "unit", "lesson"},
                  tags={**STATUS_BG, "missing": "#fde2e2"})


def _subjects() -> dict[str, S.Subject]:
    return {s.label: s for s in S.list_subjects()}


class LessonPlansPage:
    TABS = ("Plans", "My lessons", "Schemes of work")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.editor = principal.role in LESSON_PLAN_EDITORS
        activity_log.record("lesson_plans.view")
        ttk.Label(parent, text="Lesson Plans", font=("", 16, "bold")).pack(anchor="w")
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(anchor="w",
                                                                                 pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._build_plans(self.tabs["Plans"])
        self.book.select(self.TABS.index(state.get("tab", "Plans")))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        if name == "Plans":
            self.refresh()
            return
        tab = self.tabs[name]
        for w in tab.winfo_children():
            w.destroy()
        try:
            (self._draw_mine if name == "My lessons" else self._draw_units)(tab)
        except Exception:
            logger.exception("Lesson plans tab %s failed", name)
            ttk.Label(tab, text="Couldn't load this tab - see the log.",
                      foreground="#a00").pack(anchor="w")

    # ── Plans tab (old layout kept) ──────────────────────────────────

    def _build_plans(self, tab: ttk.Frame) -> None:
        st = self.state
        self.subjects = _subjects()
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.year_var = tk.StringVar(value=st.get("year", ALL))
        self.status_var = tk.StringVar(value=st.get("status", ALL))
        self.teacher_var = tk.StringVar(value=st.get("teacher", ""))
        self.subject_var = tk.StringVar(value=st.get("subject", ALL))
        self.show_var = tk.StringVar(value=st.get("show", SHOW[0]))
        self.from_var = tk.StringVar(value=st.get("from", ""))
        self.to_var = tk.StringVar(value=st.get("to", ""))
        self.search_var = tk.StringVar(value=st.get("search", ""))
        ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar, textvariable=self.year_var, state="readonly", width=5,
                     values=[ALL] + [str(y) for y in P.YEAR_GROUPS]).pack(side="left")
        ttk.Label(bar, text="Status:").pack(side="left", padx=(8, 4))
        ttk.Combobox(bar, textvariable=self.status_var, state="readonly", width=10,
                     values=[ALL, *LP.STATUSES]).pack(side="left")
        ttk.Label(bar, text="Teacher:").pack(side="left", padx=(8, 4))
        ttk.Entry(bar, textvariable=self.teacher_var, width=14).pack(side="left")
        ttk.Button(bar, text="Mine", command=lambda: (
            self.teacher_var.set(self.principal.username), self.refresh())).pack(side="left",
                                                                                 padx=2)
        for text, cmd in (("New", self.new), ("Edit", self.edit),
                          ("Set status", self.set_status), ("Delete", self.delete),
                          ("Refresh", self.refresh)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(0, 4))
        ttk.Label(bar2, text="Subject:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar2, textvariable=self.subject_var, state="readonly", width=22,
                     values=[ALL, *self.subjects]).pack(side="left")
        ttk.Combobox(bar2, textvariable=self.show_var, state="readonly", width=13,
                     values=list(SHOW)).pack(side="left", padx=6)
        for text, var in (("From:", self.from_var), ("To:", self.to_var)):
            ttk.Label(bar2, text=text).pack(side="left", padx=(4, 2))
            ttk.Entry(bar2, textvariable=var, width=11).pack(side="left")
        ttk.Label(bar2, text="Search:").pack(side="left", padx=(8, 2))
        e = ttk.Entry(bar2, textvariable=self.search_var, width=16)
        e.pack(side="left")
        e.bind("<Return>", lambda _e: self.refresh())
        bar3 = ttk.Frame(tab)
        bar3.pack(fill="x", pady=(0, 4))
        for text, cmd in (("Copy…", self.copy), ("Plan from timetable…", self.from_timetable),
                          ("Export…", self.export), ("History", self.show_history)):
            ttk.Button(bar3, text=text, command=cmd).pack(side="left", padx=2)
        for var in (self.year_var, self.status_var, self.subject_var, self.show_var):
            var.trace_add("write", lambda *_: self.refresh())
        self.tree = _tree(tab, (("id", "ID", 50), ("date", "Date", 95), ("period", "P", 35),
                                ("year", "Yr", 35), ("form", "Group", 80),
                                ("subject", "Subject", 80), ("title", "Title", 240),
                                ("unit", "Unit", 140), ("teacher", "Teacher", 120),
                                ("status", "Status", 80)), height=14)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._detail())
        self.tree.bind("<Double-1>", lambda _e: self.edit())
        detail = ttk.LabelFrame(tab, text="Selected plan", padding=8)
        detail.pack(fill="x", pady=(8, 0))
        self.detail_var = tk.StringVar(value="(select a row to see details)")
        ttk.Label(detail, textvariable=self.detail_var, justify="left",
                  wraplength=1100).pack(anchor="w")
        self.plans: dict[str, LP.Plan] = {}

    def refresh(self) -> None:
        st = self.state
        st.update(year=self.year_var.get(), status=self.status_var.get(),
                  teacher=self.teacher_var.get(), subject=self.subject_var.get(),
                  show=self.show_var.get(), **{"from": self.from_var.get()},
                  to=self.to_var.get(), search=self.search_var.get())
        y, s, subj = self.year_var.get(), self.status_var.get(), self.subject_var.get()
        filters = dict(year_group=int(y) if y.isdigit() else None,
                       status=None if s == ALL else s,
                       teacher=self.teacher_var.get().strip() or None,
                       subject_id=self.subjects[subj].subject_id if subj in self.subjects
                       else None,
                       date_from=self.from_var.get().strip() or None,
                       date_to=self.to_var.get().strip() or None,
                       search=self.search_var.get().strip() or None,
                       shared={SHOW[1]: False, SHOW[2]: True}.get(self.show_var.get()))
        try:
            rows = LP.list_plans(**filters)
        except LP.ValidationError as e:
            messagebox.showerror("Lesson plans", _problems(e), parent=self.parent)
            return
        self.tree.delete(*self.tree.get_children())
        self.plans.clear()
        for p in rows:
            iid = self.tree.insert("", "end", tags=(p.status,), values=(
                p.plan_id, p.planned_date or "shared", p.period or "", p.year_group,
                p.group_code or "-", p.subject_code, p.title, p.unit_title or "",
                p.teacher_name or "", p.status))
            self.plans[iid] = p
        counts = {k: 0 for k in LP.STATUSES}
        for p in rows:
            counts[p.status] += 1
        self.summary_var.set(f"{len(rows)} plan(s) · " + " · ".join(
            f"{k} {v}" for k, v in counts.items()))
        self.detail_var.set("(select a row to see details)")

    def _selected(self) -> LP.Plan | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Lesson plans", "Select a plan first.", parent=self.parent)
            return None
        return self.plans[sel[0]]

    def _detail(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        p = self.plans[sel[0]]
        lines = [f"{p.title} · {p.subject_name} · {p.for_label} · {p.when}"
                 + (f" · {p.duration_min} min" if p.duration_min else "")
                 + f" · {p.status}"]
        for key, label in LP.TEXT_FIELDS:
            v = getattr(p, key)
            if v:
                lines.append(f"{label}: {v[:200]}{'…' if len(v) > 200 else ''}")
        self.detail_var.set("\n".join(lines))

    def new(self, **prefill) -> None:
        plan_dialog(self.parent, self.principal, None, self._after, prefill=prefill)

    def edit(self) -> None:
        p = self._selected()
        if p:
            plan_dialog(self.parent, self.principal, p, self._after)

    def _after(self) -> None:
        if self.state.get("tab") == "Plans":
            self.refresh()
        else:
            self._on_tab()

    def set_status(self) -> None:
        p = self._selected()
        if p:
            status_dialog(self.parent, self.principal, p, self.refresh)

    def delete(self) -> None:
        p = self._selected()
        if not p or not messagebox.askyesno("Delete plan", f"Delete '{p.title}' ({p.when})?",
                                            parent=self.parent):
            return
        try:
            LP.delete(p.plan_id, actor=self.principal)
        except (LP.ValidationError, LP.PermissionDenied) as e:
            messagebox.showerror("Delete plan", _problems(e), parent=self.parent)
            return
        self.refresh()

    def copy(self) -> None:
        p = self._selected()
        if p:
            copy_dialog(self.parent, self.principal, p, self.refresh)

    def from_timetable(self) -> None:
        from_timetable_dialog(self.parent, self.principal, self.refresh)

    def export(self) -> None:
        p = self._selected()
        if not p:
            return
        path = filedialog.asksaveasfilename(parent=self.parent, defaultextension=".txt",
                                            initialfile=f"lesson-plan-{p.plan_id}.txt",
                                            filetypes=[("Text", "*.txt")])
        if path:
            LP.export_text(p.plan_id, path, actor=self.principal)
            messagebox.showinfo("Export", "Saved.", parent=self.parent)

    def show_history(self) -> None:
        p = self._selected()
        if not p:
            return
        rows = LP.history(p.plan_id)
        text = "\n".join(f"{h['at']}  {h['actor']}  {h['action']}"
                         + (f"  {h['detail'].get('from', '')} → {h['detail'].get('to', '')}"
                            if h["action"] == "status" else
                            f"  {', '.join(h['detail'].get('fields', []))}"
                            if h["action"] == "update" else "")
                         for h in rows)
        messagebox.showinfo("History", text or "No changes recorded.", parent=self.parent)

    # ── My lessons ───────────────────────────────────────────────────

    def _draw_mine(self, tab: ttk.Frame) -> None:
        today = _dt.date.today()
        monday = today - _dt.timedelta(days=today.weekday())
        start = tk.StringVar(value=self.state.get("mine_from", monday.isoformat()))
        mine = tk.BooleanVar(value=self.state.get("mine_only", not self.editor))
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Week starting:").pack(side="left")
        ttk.Entry(bar, textvariable=start, width=11).pack(side="left", padx=4)
        ttk.Checkbutton(bar, text="Only my lessons", variable=mine).pack(side="left", padx=6)
        label = ttk.Label(tab, foreground="#555")
        label.pack(anchor="w")
        tree = _tree(tab, (("date", "Date", 100), ("period", "P", 35), ("lesson", "Lesson", 200),
                           ("teacher", "Teacher", 130), ("title", "Plan", 260),
                           ("status", "Status", 90)), height=16)
        rows: dict[str, tuple] = {}

        def show(*_a) -> None:
            tree.delete(*tree.get_children())
            rows.clear()
            try:
                s = _dt.date.fromisoformat(start.get().strip())
            except ValueError:
                label.configure(text="Enter the week's first day as YYYY-MM-DD.")
                return
            self.state.update(mine_from=s.isoformat(), mine_only=mine.get())
            found = LP.coverage(s, s + _dt.timedelta(days=4),
                                teacher=self.principal.username if mine.get() else None)
            missing = sum(1 for *_x, p in found if p is None)
            label.configure(text=f"{len(found)} lesson(s) · {missing} without a plan"
                                 " - double-click to write or open the plan")
            for d, x, p in found:
                iid = tree.insert("", "end", tags=(p.status,) if p else ("missing",), values=(
                    f"{d:%a %d %b}", x.period, f"{x.subject_name} {x.group_code}",
                    x.teacher or "", p.title if p else "- no plan -",
                    p.status if p else ""))
                rows[iid] = (d, x, p)

        def open_row(_e=None) -> None:
            sel = tree.selection()
            if not sel:
                return
            d, x, p = rows[sel[0]]
            if p:
                plan_dialog(tab, self.principal, p, show)
            else:
                plan_dialog(tab, self.principal, None, show, prefill={
                    "group_id": x.group_id, "planned_date": d.isoformat(), "period": x.period,
                    "title": f"{x.subject_name} - {d:%a %d %b}"})

        def step(days: int) -> None:
            try:
                s = _dt.date.fromisoformat(start.get().strip())
            except ValueError:
                s = monday
            start.set((s + _dt.timedelta(days=days)).isoformat())
            show()

        ttk.Button(bar, text="Show", command=show).pack(side="left")
        ttk.Button(bar, text="◀", width=3, command=lambda: step(-7)).pack(side="left", padx=1)
        ttk.Button(bar, text="▶", width=3, command=lambda: step(7)).pack(side="left", padx=1)
        ttk.Button(bar, text="Open / write plan", command=open_row).pack(side="left", padx=6)
        tree.bind("<Double-1>", open_row)
        mine.trace_add("write", show)
        show()

    # ── Schemes of work ──────────────────────────────────────────────

    def _draw_units(self, tab: ttk.Frame) -> None:
        subjects = _subjects()
        subj = tk.StringVar(value=self.state.get("unit_subject", ALL))
        year = tk.StringVar(value=self.state.get("unit_year", ALL))
        archived = tk.BooleanVar(value=False)
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Subject:").pack(side="left")
        ttk.Combobox(bar, textvariable=subj, state="readonly", width=22,
                     values=[ALL, *subjects]).pack(side="left", padx=4)
        ttk.Label(bar, text="Year:").pack(side="left")
        ttk.Combobox(bar, textvariable=year, state="readonly", width=5,
                     values=[ALL] + [str(y) for y in P.YEAR_GROUPS]).pack(side="left", padx=4)
        ttk.Checkbutton(bar, text="Show archived", variable=archived).pack(side="left", padx=6)
        tree = _tree(tab, (("subject", "Subject", 90), ("year", "Yr", 35), ("term", "Term", 70),
                           ("seq", "#", 35), ("title", "Unit", 240), ("lessons", "Lessons", 60),
                           ("progress", "Planned / delivered by group", 320),
                           ("status", "Status", 70)), height=14)
        units: dict[str, LP.Unit] = {}

        def show(*_a) -> None:
            tree.delete(*tree.get_children())
            units.clear()
            self.state.update(unit_subject=subj.get(), unit_year=year.get())
            s = subjects.get(subj.get())
            for u in LP.list_units(subject_id=s.subject_id if s else None,
                                   year_group=int(year.get()) if year.get().isdigit() else None,
                                   include_archived=archived.get()):
                prog = "; ".join(f"{g.group_code or 'shared'} {g.planned}/{g.delivered}"
                                 for g in LP.unit_progress(u.unit_id)) or "no plans yet"
                code = next((x.code for x in subjects.values() if x.subject_id == u.subject_id),
                            "")
                iid = tree.insert("", "end", values=(code, u.year_group, u.term, u.sequence,
                                                     u.title, u.lessons or "", prog,
                                                     "" if u.is_active else "Archived"))
                units[iid] = u

        def selected() -> LP.Unit | None:
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("Schemes of work", "Select a unit first.", parent=tab)
                return None
            return units[sel[0]]

        def plans_in() -> None:
            u = selected()
            if u:
                self.state.update(tab="Plans")
                self.search_var.set("")
                self.book.select(0)
                rows = LP.list_plans(unit_id=u.unit_id)
                self.tree.delete(*self.tree.get_children())
                self.plans.clear()
                for p in rows:
                    iid = self.tree.insert("", "end", tags=(p.status,), values=(
                        p.plan_id, p.planned_date or "shared", p.period or "", p.year_group,
                        p.group_code or "-", p.subject_code, p.title, p.unit_title or "",
                        p.teacher_name or "", p.status))
                    self.plans[iid] = p
                self.summary_var.set(f"{len(rows)} plan(s) in unit '{u.title}' "
                                     "(Refresh to see all)")

        def archive() -> None:
            u = selected()
            if not u:
                return
            try:
                (LP.archive_unit if u.is_active else LP.restore_unit)(u.unit_id,
                                                                      actor=self.principal)
            except (LP.ValidationError, LP.PermissionDenied) as e:
                messagebox.showerror("Schemes of work", _problems(e), parent=tab)
                return
            show()

        def delete() -> None:
            u = selected()
            if not u or not messagebox.askyesno("Delete unit", f"Delete '{u.title}'?",
                                                parent=tab):
                return
            try:
                LP.delete_unit(u.unit_id, actor=self.principal)
            except (LP.ValidationError, LP.PermissionDenied) as e:
                messagebox.showerror("Delete unit", _problems(e), parent=tab)
                return
            show()

        ttk.Button(bar, text="Show", command=show).pack(side="left")
        ttk.Button(bar, text="Plans in unit", command=plans_in).pack(side="left", padx=4)
        if self.editor:
            ttk.Button(bar, text="New unit", command=lambda: unit_dialog(
                tab, self.principal, None, show)).pack(side="left", padx=2)
            ttk.Button(bar, text="Edit", command=lambda: (u := selected()) and unit_dialog(
                tab, self.principal, u, show)).pack(side="left", padx=2)
            ttk.Button(bar, text="Archive / restore", command=archive).pack(side="left", padx=2)
            ttk.Button(bar, text="Delete", command=delete).pack(side="left", padx=2)
            tree.bind("<Double-1>", lambda _e: (u := selected()) and unit_dialog(
                tab, self.principal, u, show))
        for v in (subj, year, archived):
            v.trace_add("write", show)
        show()


def draw_lesson_plans(parent: ttk.Frame, *, principal: Principal,
                      state: dict | None = None) -> LessonPlansPage:
    return LessonPlansPage(parent, principal=principal,
                           state=state if state is not None else {})


# ── Dialogs ──────────────────────────────────────────────────────────

def _group_choices() -> dict[str, TG.TeachingGroup]:
    return {f"{i.group.code} - {i.subject.name} (Y{i.group.year_group})"
            + (f", {i.group.teacher_name}" if i.group.teacher_name else ""): i.group
            for i in TG.info(TG.list_groups())}


def plan_dialog(owner, principal: Principal, plan: LP.Plan | None, after: Callable[[], None],
                *, prefill: dict | None = None) -> None:
    """New or edit a plan. Read-only for people who can't change it."""
    can = plan is None or LP.can_change(principal, plan)
    if plan is None and not principal.is_staff:
        return
    win = make_toplevel(owner.winfo_toplevel())
    win.title(("Edit plan - " if can else "Plan - ") + plan.title if plan else "New lesson plan")
    win.geometry("820x700")
    body, footer = scrolled_form(win)
    body.columnconfigure(1, weight=1)
    groups = _group_choices()
    subjects = _subjects()
    pre = dict(prefill or {})
    cur = (lambda k: getattr(plan, k)) if plan else (lambda k: pre.get(k))
    r = 0

    def row(label: str, widget, hint: str = "") -> None:
        nonlocal r
        ttk.Label(body, text=label).grid(row=r, column=0, sticky="nw", pady=2, padx=(0, 8))
        widget.grid(row=r, column=1, sticky="w", pady=2)
        if hint:
            ttk.Label(body, text=hint, foreground="#888").grid(row=r, column=2, sticky="w")
        r += 1

    title = ttk.Entry(body, width=60)
    title.insert(0, cur("title") or "")
    row("Title *", title)
    group_cb = ttk.Combobox(body, values=[SHARED, *groups], state="readonly", width=58)
    gid = cur("group_id")
    group_cb.set(next((k for k, g in groups.items() if g.group_id == gid), "") if gid else
                 (SHARED if plan or pre.get("shared") else ""))
    if gid and not group_cb.get() and plan:
        group_cb.configure(values=[plan.group_code or "", *group_cb.cget("values")])
        group_cb.set(plan.group_code or "")
    row("Teaching group *", group_cb, "or a shared plan for a subject and year")
    subj_cb = ttk.Combobox(body, values=list(subjects), state="readonly", width=40)
    sid = cur("subject_id")
    subj_cb.set(next((k for k, s in subjects.items() if s.subject_id == sid), ""))
    year_cb = ttk.Combobox(body, values=[str(y) for y in P.YEAR_GROUPS], state="readonly",
                           width=5)
    year_cb.set(str(cur("year_group") or ""))
    row("Subject (shared plan)", subj_cb)
    row("Year (shared plan)", year_cb)
    unit_cb = ttk.Combobox(body, state="readonly", width=50)
    row("Unit (scheme of work)", unit_cb)
    date_e = ttk.Entry(body, width=12)
    date_e.insert(0, cur("planned_date") or "")
    row("Date", date_e, "YYYY-MM-DD - needed for a group's plan")
    plist = TT.periods()
    plabels = ["", *(f"{p.label} ({p.times})" for p in plist)]
    period_cb = ttk.Combobox(body, values=plabels, state="readonly", width=20)
    pn = cur("period")
    period_cb.set(plabels[pn] if pn and pn < len(plabels) else "")
    row("Period", period_cb)
    dur = ttk.Entry(body, width=6)
    dur.insert(0, str(cur("duration_min") or ""))
    row("Length (minutes)", dur, "blank = the period's length")
    teacher = ttk.Entry(body, width=30)
    teacher.insert(0, cur("teacher_name") or "")
    row("Teacher", teacher, "blank = the group's teacher")
    texts: dict[str, tk.Text] = {}
    for key, label in LP.TEXT_FIELDS:
        t = tk.Text(body, width=70, height=4 if key in ("objectives", "activities") else 3,
                    wrap="word")
        t.insert("1.0", cur(key) or "")
        row(label, t)
        texts[key] = t
    if plan:
        ttk.Label(body, text=f"Status: {plan.status} · written by {plan.created_by or '-'} · "
                             f"last changed {plan.updated_at} by {plan.updated_by or '-'}",
                  foreground="#666").grid(row=r, column=0, columnspan=3, sticky="w", pady=4)
    units: dict[str, LP.Unit] = {}

    def is_shared() -> bool:
        return group_cb.get() == SHARED

    def fill_units(_e=None) -> None:
        g = groups.get(group_cb.get())
        state = "readonly" if is_shared() and can else "disabled"
        subj_cb.configure(state=state)
        year_cb.configure(state=state)
        if g:
            subj_cb.set(next((k for k, s in subjects.items() if s.subject_id == g.subject_id),
                             ""))
            year_cb.set(str(g.year_group))
        s = subjects.get(subj_cb.get())
        units.clear()
        if s and year_cb.get().isdigit():
            units.update({u.label: u for u in LP.list_units(
                subject_id=s.subject_id, year_group=int(year_cb.get()))})
        unit_cb.configure(values=[NO_UNIT, *units])
        uid = (plan.unit_id if plan else pre.get("unit_id"))
        want = next((k for k, u in units.items() if u.unit_id == uid), None)
        if unit_cb.get() not in units:
            unit_cb.set(want or (plan.unit_title if plan and plan.unit_title else NO_UNIT))

    for cb in (group_cb, subj_cb, year_cb):
        cb.bind("<<ComboboxSelected>>", fill_units)
    fill_units()
    if not can:
        for w in (title, group_cb, subj_cb, year_cb, unit_cb, date_e, period_cb, dur, teacher):
            w.configure(state="disabled")
        for t in texts.values():
            t.configure(state="disabled")
    msg = ttk.Label(footer, foreground="#a00", wraplength=760, justify="left")
    msg.pack(side="left", fill="x", expand=True)

    def data() -> dict:
        g = groups.get(group_cb.get())
        s = subjects.get(subj_cb.get())
        u = units.get(unit_cb.get())
        d = {"title": title.get(), "planned_date": date_e.get().strip() or None,
             "period": period_cb.current() or None if period_cb.get() else None,
             "duration_min": dur.get().strip() or None,
             "teacher_name": teacher.get().strip() or None,
             "unit_id": u.unit_id if u else (plan.unit_id if plan and unit_cb.get() ==
                                             plan.unit_title else None)}
        if is_shared():
            d.update(group_id=None, subject_id=s.subject_id if s else None,
                     year_group=year_cb.get() or None)
        else:
            d["group_id"] = g.group_id if g else (plan.group_id if plan else None)
        if plan and plan.teacher_name == d["teacher_name"]:
            d["teacher_username"] = plan.teacher_username
        elif not d["teacher_name"]:
            d["teacher_username"] = None
        for key, t in texts.items():
            d[key] = t.get("1.0", "end").strip()
        return d

    def save() -> None:
        try:
            if plan is None:
                _p, warnings = LP.create(data(), actor=principal)
            else:
                _p, warnings = LP.update(plan.plan_id, data(), actor=principal)
        except (LP.ValidationError, LP.PermissionDenied, LP.NotFound) as e:
            msg.configure(text=_problems(e))
            return
        win.destroy()
        if warnings:
            messagebox.showwarning("Lesson plan", "\n".join(warnings), parent=owner)
        after()

    ttk.Button(footer, text="Close" if not can else "Cancel", command=win.destroy).pack(
        side="right")
    if can:
        ttk.Button(footer, text="Save", command=save).pack(side="right", padx=(0, 6))
    if plan and can:
        ttk.Button(footer, text="Set status…", command=lambda: (
            win.destroy(), status_dialog(owner, principal, plan, after))).pack(side="right",
                                                                                padx=(0, 6))


def status_dialog(owner, principal: Principal, plan: LP.Plan,
                  after: Callable[[], None]) -> None:
    win = make_toplevel(owner.winfo_toplevel())
    win.title("Set status")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=plan.title[:60], font=("", 10, "bold")).pack(anchor="w")
    ttk.Label(frm, text=f"Current status: {plan.status}", foreground="#666").pack(anchor="w")
    var = tk.StringVar(value=plan.status)
    for s in LP.STATUSES:
        why = LP.status_problems(plan, s, evaluation="x" if s == "Reviewed" else None)
        ttk.Radiobutton(frm, text=s + (f"  - {why[0]}" if why and s != plan.status else ""),
                        variable=var, value=s).pack(anchor="w")
    ttk.Label(frm, text="Evaluation (needed for Reviewed):").pack(anchor="w", pady=(6, 0))
    ev = tk.Text(frm, width=60, height=4, wrap="word")
    ev.insert("1.0", plan.evaluation or "")
    ev.pack()

    def save() -> None:
        try:
            LP.set_status(plan.plan_id, var.get(), actor=principal,
                          evaluation=ev.get("1.0", "end").strip() or None)
        except (LP.ValidationError, LP.PermissionDenied) as e:
            messagebox.showerror("Set status", _problems(e), parent=win)
            return
        win.destroy()
        after()

    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(8, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Save", command=save).pack(side="right", padx=(0, 6))


def copy_dialog(owner, principal: Principal, plan: LP.Plan, after: Callable[[], None]) -> None:
    win = make_toplevel(owner.winfo_toplevel())
    win.title("Copy plan")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"Copy '{plan.title}' as a new Draft (the evaluation isn't copied).",
              wraplength=460).grid(row=0, column=0, columnspan=2, sticky="w")
    groups = {k: g for k, g in _group_choices().items() if g.subject_id == plan.subject_id}
    group_cb = ttk.Combobox(frm, values=[SHARED, *groups], state="readonly", width=50)
    group_cb.set(next((k for k, g in groups.items() if g.group_id == plan.group_id), SHARED))
    date_e = ttk.Entry(frm, width=12)
    plabels = ["", *(f"{p.label} ({p.times})" for p in TT.periods())]
    period_cb = ttk.Combobox(frm, values=plabels, state="readonly", width=20)
    title = ttk.Entry(frm, width=50)
    title.insert(0, plan.title)
    for i, (text, w) in enumerate((("To", group_cb), ("Date", date_e), ("Period", period_cb),
                                   ("Title", title)), 1):
        ttk.Label(frm, text=text).grid(row=i, column=0, sticky="w", pady=2, padx=(0, 8))
        w.grid(row=i, column=1, sticky="w", pady=2)

    def save() -> None:
        shared = group_cb.get() == SHARED
        g = groups.get(group_cb.get())
        try:
            new, warnings = LP.copy(plan.plan_id, actor=principal, shared=shared,
                                    group_id=g.group_id if g else None,
                                    planned_date=date_e.get().strip() or None,
                                    period=period_cb.current() or None if period_cb.get()
                                    else None, title=title.get())
        except (LP.ValidationError, LP.PermissionDenied, LP.NotFound) as e:
            messagebox.showerror("Copy plan", _problems(e), parent=win)
            return
        win.destroy()
        messagebox.showinfo("Copy plan", f"Copied as plan #{new.plan_id}."
                            + ("\n" + "\n".join(warnings) if warnings else ""), parent=owner)
        after()

    bar = ttk.Frame(frm)
    bar.grid(row=5, column=0, columnspan=2, sticky="e", pady=(8, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Copy", command=save).pack(side="right", padx=(0, 6))


def from_timetable_dialog(owner, principal: Principal, after: Callable[[], None]) -> None:
    """Draft a plan for every timetabled lesson of a group over a period."""
    groups = _group_choices()
    if principal.role not in LESSON_PLAN_EDITORS:
        groups = {k: g for k, g in groups.items()
                  if (g.teacher_username or "").lower() == principal.username.lower()}
    if not groups:
        messagebox.showinfo("Plan from timetable", "You have no teaching groups this year "
                            "(a group's teacher login must be set).", parent=owner)
        return
    win = make_toplevel(owner.winfo_toplevel())
    win.title("Plan from timetable")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text="Creates a Draft plan for each timetabled lesson (lessons that "
                        "already have a plan are skipped).", wraplength=460).grid(
        row=0, column=0, columnspan=2, sticky="w")
    group_cb = ttk.Combobox(frm, values=list(groups), state="readonly", width=50)
    today = _dt.date.today()
    start, end = ttk.Entry(frm, width=12), ttk.Entry(frm, width=12)
    start.insert(0, today.isoformat())
    end.insert(0, (today + _dt.timedelta(days=13)).isoformat())
    unit_cb = ttk.Combobox(frm, state="readonly", width=50, values=[NO_UNIT])
    unit_cb.set(NO_UNIT)
    units: dict[str, LP.Unit] = {}

    def fill(_e=None) -> None:
        g = groups.get(group_cb.get())
        units.clear()
        if g:
            units.update({u.label: u for u in LP.list_units(subject_id=g.subject_id,
                                                            year_group=g.year_group)})
        unit_cb.configure(values=[NO_UNIT, *units])
        unit_cb.set(NO_UNIT)
    group_cb.bind("<<ComboboxSelected>>", fill)
    for i, (text, w) in enumerate((("Group", group_cb), ("From", start), ("To", end),
                                   ("Unit", unit_cb)), 1):
        ttk.Label(frm, text=text).grid(row=i, column=0, sticky="w", pady=2, padx=(0, 8))
        w.grid(row=i, column=1, sticky="w", pady=2)

    def go() -> None:
        g = groups.get(group_cb.get())
        if not g:
            messagebox.showerror("Plan from timetable", "Choose a group.", parent=win)
            return
        u = units.get(unit_cb.get())
        try:
            created, skipped = LP.plan_from_timetable(
                g.group_id, start.get(), end.get(), actor=principal,
                unit_id=u.unit_id if u else None)
        except (LP.ValidationError, LP.PermissionDenied, LP.NotFound) as e:
            messagebox.showerror("Plan from timetable", _problems(e), parent=win)
            return
        win.destroy()
        messagebox.showinfo("Plan from timetable", f"Created {len(created)} draft plan(s)"
                            + (f"; {skipped} lesson(s) already had one" if skipped else "")
                            + ".", parent=owner)
        after()

    bar = ttk.Frame(frm)
    bar.grid(row=5, column=0, columnspan=2, sticky="e", pady=(8, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Create plans", command=go).pack(side="right", padx=(0, 6))


def unit_dialog(owner, principal: Principal, unit: LP.Unit | None,
                after: Callable[[], None]) -> None:
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Edit unit - {unit.title}" if unit else "New unit")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    subjects = _subjects()
    subj = ttk.Combobox(frm, values=list(subjects), state="readonly", width=40)
    subj.set(next((k for k, s in subjects.items() if unit and s.subject_id == unit.subject_id),
                  ""))
    year = ttk.Combobox(frm, values=[str(y) for y in P.YEAR_GROUPS], state="readonly", width=5)
    year.set(str(unit.year_group) if unit else "")
    title = ttk.Entry(frm, width=50)
    term = ttk.Combobox(frm, values=list(LP.TERMS), state="readonly", width=10)
    term.set(unit.term if unit else "Any")
    seq, lessons = ttk.Entry(frm, width=5), ttk.Entry(frm, width=5)
    overview = tk.Text(frm, width=50, height=5, wrap="word")
    if unit:
        title.insert(0, unit.title)
        seq.insert(0, str(unit.sequence))
        lessons.insert(0, str(unit.lessons or ""))
        overview.insert("1.0", unit.overview or "")
    for i, (text, w) in enumerate((("Subject *", subj), ("Year *", year), ("Title *", title),
                                   ("Term", term), ("Order", seq), ("Lessons", lessons),
                                   ("Overview", overview))):
        ttk.Label(frm, text=text).grid(row=i, column=0, sticky="nw", pady=2, padx=(0, 8))
        w.grid(row=i, column=1, sticky="w", pady=2)

    def save() -> None:
        s = subjects.get(subj.get())
        data = {"subject_id": s.subject_id if s else None, "year_group": year.get() or None,
                "title": title.get(), "term": term.get(), "sequence": seq.get() or None,
                "lessons": lessons.get() or None,
                "overview": overview.get("1.0", "end").strip()}
        try:
            if unit is None:
                LP.create_unit(data, actor=principal)
            else:
                LP.update_unit(unit.unit_id, data, actor=principal)
        except (LP.ValidationError, LP.PermissionDenied) as e:
            messagebox.showerror("Unit", _problems(e), parent=win)
            return
        win.destroy()
        after()

    bar = ttk.Frame(frm)
    bar.grid(row=7, column=0, columnspan=2, sticky="e", pady=(8, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Save", command=save).pack(side="right", padx=(0, 6))
