"""Timetable screen. The old Year / Form / Teacher filters, Apply, New / Edit /
Delete / Refresh, the weekly grid and the lesson list are kept; Today,
Clashes, Lessons needed and Settings are added. Rules live in
:mod:`modules.curriculum.domain.timetable`."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui.parented_dialogs import make_toplevel, messagebox
from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.curriculum.domain import timetable as TT
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import TIMETABLE_EDITORS, Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
ALL = "All"
CLASH_BG, CELL_BG, EMPTY_BG = "#fde2e2", "#e6f2ff", "#ffffff"


_problems = W.problems


def _tree(parent, columns, height: int = 10, select: str = "browse") -> ttk.Treeview:
    return W.tree(parent, columns, height=height, select=select,
                  stretch={"subject", "teacher", "why", "name"})


class TimetablePage:
    TABS = ("Timetable", "Today", "Clashes", "Lessons needed", "Settings")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.editor = principal.role in TIMETABLE_EDITORS
        activity_log.record("timetable.view")
        ttk.Label(parent, text="Timetable", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(parent, text=f"{TG.current_year()} · lessons are for this year's teaching "
                               "groups", foreground="#666").pack(anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._build_main(self.tabs["Timetable"])
        self.book.select(self.TABS.index(state.get("tab", "Timetable")))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        tab = self.tabs[name]
        if name == "Timetable":
            self.apply()
            return
        for w in tab.winfo_children():
            w.destroy()
        try:
            {"Today": self._draw_today, "Clashes": self._draw_clashes,
             "Lessons needed": self._draw_needed, "Settings": self._draw_settings}[name](tab)
        except Exception:
            logger.exception("Timetable tab %s failed", name)
            ttk.Label(tab, text="Couldn't load this tab - see the log.",
                      foreground="#a00").pack(anchor="w")

    # ── Timetable tab ────────────────────────────────────────────────

    def _build_main(self, tab: ttk.Frame) -> None:
        st = self.state
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.year_var = tk.StringVar(value=st.get("year", ALL))
        self.form_var = tk.StringVar(value=st.get("form", ALL))
        self.teacher_var = tk.StringVar(value=st.get("teacher", ALL))
        self.room_var = tk.StringVar(value=st.get("room", ALL))
        self.pupil_var = tk.StringVar(value=st.get("pupil", ""))
        self.week_var = tk.StringVar(value=st.get("week", TT.WEEK_LABELS[1]))
        self.mine_var = tk.BooleanVar(value=st.get("mine", False))
        forms = sorted({f.name for f in FG.list_forms()})

        def combo(label: str, var, values, width: int) -> ttk.Combobox:
            ttk.Label(bar, text=label).pack(side="left", padx=(0, 3))
            cb = ttk.Combobox(bar, textvariable=var, values=values, state="readonly",
                              width=width)
            cb.pack(side="left", padx=(0, 8))
            return cb

        combo("Year:", self.year_var, [ALL, *map(str, P.YEAR_GROUPS)], 4)
        combo("Form:", self.form_var, [ALL, *forms], 6)
        self.teacher_cb = combo("Teacher:", self.teacher_var, [ALL, *TT.teachers()], 18)
        self.room_cb = combo("Room:", self.room_var, [ALL, *TT.rooms()], 8)
        ttk.Label(bar, text="Pupil:").pack(side="left", padx=(0, 3))
        ttk.Entry(bar, textvariable=self.pupil_var, width=10).pack(side="left", padx=(0, 8))
        self.week_cb = combo("Week:", self.week_var, [TT.WEEK_LABELS[1]], 8)
        ttk.Checkbutton(bar, text="My timetable", variable=self.mine_var).pack(side="left")
        btns = ttk.Frame(tab)
        btns.pack(fill="x", pady=(0, 4))
        ttk.Button(btns, text="Apply", command=self.apply).pack(side="left", padx=2)
        kw = {} if self.editor else {"state": "disabled"}
        ttk.Button(btns, text="New", command=lambda: self.new(), **kw).pack(side="left", padx=2)
        ttk.Button(btns, text="Edit", command=self.edit, **kw).pack(side="left", padx=2)
        ttk.Button(btns, text="Delete", command=self.delete, **kw).pack(side="left", padx=2)
        ttk.Button(btns, text="Refresh", command=self.refresh).pack(side="left", padx=2)
        self.status = ttk.Label(btns, foreground="#666")
        self.status.pack(side="left", padx=12)

        pane = ttk.PanedWindow(tab, orient="vertical")
        pane.pack(fill="both", expand=True)
        grid_box = ttk.LabelFrame(pane, text="Weekly grid", padding=6)
        list_box = ttk.LabelFrame(pane, text="Lessons", padding=6)
        pane.add(grid_box, weight=3)
        pane.add(list_box, weight=2)
        self.grid_inner = ttk.Frame(grid_box)
        self.grid_inner.pack(fill="both", expand=True)
        self.tree = _tree(list_box, (
            ("slot", "When", 150), ("subject", "Subject", 160), ("group", "Group", 100),
            ("yr", "Yr", 35), ("teacher", "Teacher", 150), ("room", "Room", 70),
            ("notes", "Notes", 150)), height=7, select="extended")
        self.tree.bind("<Double-1>", lambda _e: self.edit())

    def _filters(self) -> dict | None:
        f: dict = {}
        if self.year_var.get() != ALL:
            f["year_group"] = int(self.year_var.get())
        if self.form_var.get() != ALL:
            f["form"] = self.form_var.get()
        if self.mine_var.get():
            f["teacher"] = self.principal.username
        elif self.teacher_var.get() != ALL:
            f["teacher"] = self.teacher_var.get()
        if self.room_var.get() != ALL:
            f["room"] = self.room_var.get()
        ref = self.pupil_var.get().strip()
        if ref:
            p = P.find_by_reference(ref)
            if p is None:
                self.status.configure(text=f"No pupil with admission number or UPN {ref}")
                return None
            f["pupil_id"] = p.pupil_id
        return f

    def refresh(self) -> None:
        self.teacher_cb.configure(values=[ALL, *TT.teachers()])
        self.room_cb.configure(values=[ALL, *TT.rooms()])
        self.apply()

    def apply(self) -> None:
        st = self.state
        st.update(year=self.year_var.get(), form=self.form_var.get(),
                  teacher=self.teacher_var.get(), room=self.room_var.get(),
                  pupil=self.pupil_var.get(), week=self.week_var.get(),
                  mine=self.mine_var.get())
        weeks = TT.cycle_weeks()
        labels = [TT.WEEK_LABELS[w] for w in range(1, weeks + 1)]
        self.week_cb.configure(values=labels, state="readonly" if weeks == 2 else "disabled")
        if self.week_var.get() not in labels:
            self.week_var.set(labels[0])
        week = labels.index(self.week_var.get()) + 1
        filters = self._filters()
        if filters is None:
            return
        try:
            lessons = TT.list_lessons(**filters)
            clash_ids = {x.lesson_id for a, b, _r in TT.clashes() for x in (a, b)}
        except Exception:
            logger.exception("Timetable load failed")
            self.status.configure(text="Couldn't read the timetable - see the log.")
            return
        self.lessons = {x.lesson_id: x for x in lessons}
        self._draw_grid([x for x in lessons if x.week == week], week, clash_ids)
        self.tree.delete(*self.tree.get_children())
        for x in lessons:
            self.tree.insert("", "end", iid=str(x.lesson_id), values=(
                x.slot_label, x.subject_name, x.group_code, x.year_group, x.teacher or "",
                x.room or "", x.notes or ""))
        self.status.configure(text=f"{len(lessons)} lesson(s)"
                              + (f" · {len(clash_ids)} clashing" if clash_ids else ""))

    def _draw_grid(self, lessons: list[TT.Lesson], week: int, clash_ids: set[int]) -> None:
        g = self.grid_inner
        for w in g.winfo_children():
            w.destroy()
        cells = TT.grid(lessons)
        ttk.Label(g, text="").grid(row=0, column=0)
        for c, day in enumerate(TT.DAYS, 1):
            ttk.Label(g, text=day, anchor="center", font=("", 10, "bold")).grid(
                row=0, column=c, sticky="ew", padx=1)
            g.columnconfigure(c, weight=1, uniform="day")
        for r, p in enumerate(TT.periods(), 1):
            ttk.Label(g, text=f"{p.label}\n{p.times}", font=("", 9)).grid(
                row=r, column=0, sticky="nw", padx=(0, 6), pady=1)
            g.rowconfigure(r, weight=1)
            for c in range(1, 6):
                here = cells.get((week, c, p.period), [])
                text = "\n".join(x.cell for x in here[:3]) + (
                    f"\n+{len(here) - 3} more" if len(here) > 3 else "")
                bg = (CLASH_BG if any(x.lesson_id in clash_ids for x in here)
                      else CELL_BG if here else EMPTY_BG)
                lbl = tk.Label(g, text=text or "–", anchor="nw", justify="left", bg=bg,
                               relief="solid", bd=1, wraplength=190, font=("", 9),
                               fg="#000" if here else "#bbb")
                lbl.grid(row=r, column=c, sticky="nsew", padx=1, pady=1)
                lbl.bind("<Button-1>", lambda _e, h=here: self._select(h))
                lbl.bind("<Double-1>", lambda _e, h=here, d=c, pp=p.period:
                         self._cell_open(h, week, d, pp))

    def _select(self, here: list[TT.Lesson]) -> None:
        ids = [str(x.lesson_id) for x in here if self.tree.exists(str(x.lesson_id))]
        self.tree.selection_set(ids)
        if ids:
            self.tree.see(ids[0])

    def _cell_open(self, here, week: int, day: int, period: int) -> None:
        if not here:
            if self.editor:
                self.new(week=week, day=day, period=period)
        elif len(here) == 1:
            self.edit(here[0])
        else:
            self._select(here)

    def _selected(self) -> TT.Lesson | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Timetable", "Select a lesson first.", parent=self.parent)
            return None
        return TT.get(int(sel[0]))

    def new(self, **slot) -> None:
        year = None if self.year_var.get() == ALL else int(self.year_var.get())
        lesson_dialog(self.parent, self.principal, None, self.refresh, year=year, **slot)

    def edit(self, lesson: TT.Lesson | None = None) -> None:
        x = lesson or self._selected()
        if x:
            if self.editor:
                lesson_dialog(self.parent, self.principal, x, self.refresh)
            else:
                messagebox.showinfo(x.slot_label, f"{x.subject_name} · {x.group_code}\n"
                                    f"Teacher: {x.teacher or '—'}\nRoom: {x.room or '—'}"
                                    + (f"\n{x.notes}" if x.notes else ""), parent=self.parent)

    def delete(self) -> None:
        sel = [int(i) for i in self.tree.selection()]
        if not sel:
            messagebox.showinfo("Timetable", "Select lessons first.", parent=self.parent)
            return
        if not messagebox.askyesno("Delete", f"Delete {len(sel)} lesson(s)?",
                                   parent=self.parent):
            return
        try:
            for lid in sel:
                TT.delete_lesson(lid, actor=self.principal)
        except (TT.ValidationError, TT.PermissionDenied) as e:
            messagebox.showerror("Delete", _problems(e), parent=self.parent)
        self.refresh()

    # ── Other tabs ───────────────────────────────────────────────────

    def _draw_today(self, tab: ttk.Frame) -> None:
        day_var = tk.StringVar(value=self.state.get("day", _dt.date.today().isoformat()))
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Date (YYYY-MM-DD):").pack(side="left")
        ttk.Entry(bar, textvariable=day_var, width=12).pack(side="left", padx=4)
        mine = tk.BooleanVar(value=self.state.get("today_mine", True))
        ttk.Checkbutton(bar, text="Only my lessons", variable=mine).pack(side="left", padx=8)
        label = ttk.Label(tab, foreground="#555")
        label.pack(anchor="w")
        tree = _tree(tab, (("p", "Period", 70), ("t", "Time", 100), ("subject", "Subject", 160),
                           ("group", "Group", 100), ("teacher", "Teacher", 150),
                           ("room", "Room", 70)), height=12)

        def show(*_a) -> None:
            tree.delete(*tree.get_children())
            try:
                day = _dt.date.fromisoformat(day_var.get().strip())
            except ValueError:
                label.configure(text="Enter a date as YYYY-MM-DD.")
                return
            self.state.update(day=day.isoformat(), today_mine=mine.get())
            lessons, what = TT.lessons_on(
                day, **({"teacher": self.principal.username} if mine.get() else {}))
            label.configure(text=f"{day:%A %d %B %Y} - {what}" + ("" if lessons else
                                                                  " · no lessons"))
            times = {p.period: p for p in TT.periods()}
            for x in lessons:
                p = times.get(x.period)
                tree.insert("", "end", values=(p.label if p else x.period,
                                               p.times if p else "", x.subject_name,
                                               x.group_code, x.teacher or "", x.room or ""))

        ttk.Button(bar, text="Show", command=show).pack(side="left")
        for delta, text in ((-1, "◀"), (1, "▶")):
            def step(d=delta) -> None:
                try:
                    day = _dt.date.fromisoformat(day_var.get().strip())
                except ValueError:
                    day = _dt.date.today()
                day_var.set((day + _dt.timedelta(days=d)).isoformat())
                show()
            ttk.Button(bar, text=text, width=3, command=step).pack(side="left", padx=1)
        mine.trace_add("write", show)
        show()

    def _draw_clashes(self, tab: ttk.Frame) -> None:
        found = TT.clashes()
        ttk.Label(tab, text=(f"{len(found)} clash(es). Double-click to edit the first lesson."
                             if found else "No clashes - no teacher, room or pupil is in two "
                             "places at once."), foreground="#a00" if found else "#2a7"
                  ).pack(anchor="w", pady=(0, 6))
        tree = _tree(tab, (("slot", "When", 150), ("a", "Lesson", 160), ("b", "Clashes with", 160),
                           ("why", "Why", 420)), height=14)
        rows = {}
        for a, b, why in found:
            iid = tree.insert("", "end", values=(a.slot_label, f"{a.subject_code} {a.group_code}",
                                                 f"{b.subject_code} {b.group_code}",
                                                 "; ".join(why)))
            rows[iid] = a
        if self.editor:
            tree.bind("<Double-1>", lambda _e: tree.selection() and lesson_dialog(
                self.parent, self.principal, rows[tree.selection()[0]],
                lambda: self._on_tab()))

    def _draw_needed(self, tab: ttk.Frame) -> None:
        reqs = TT.requirements()
        per = "per fortnight" if TT.cycle_weeks() == 2 else "per week"
        short = [r for r in reqs if r.status in {"short", "over"}]
        ttk.Label(tab, text=f"Lessons {per}: needed (the group's own figure, else the "
                            f"curriculum plan) against timetabled. {len(short)} group(s) "
                            "don't match.", foreground="#555").pack(anchor="w", pady=(0, 6))
        tree = _tree(tab, (("group", "Group", 110), ("subject", "Subject", 180), ("yr", "Yr", 35),
                           ("teacher", "Teacher", 150), ("need", "Needed", 65),
                           ("have", "Timetabled", 75), ("st", "Status", 80)), height=16)
        tree.tag_configure("short", foreground="#a00")
        tree.tag_configure("over", foreground="#a60")
        tree.tag_configure("no plan", foreground="#888")
        for r in sorted(reqs, key=lambda r: (r.status == "ok", r.info.group.year_group,
                                             r.info.group.code.lower())):
            g = r.info.group
            tree.insert("", "end", tags=(r.status,), values=(
                g.code, r.info.subject.label, g.year_group, g.teacher_name or "",
                r.needed if r.needed is not None else "—", r.scheduled,
                {"ok": "✓", "short": "Short", "over": "Over", "no plan": "No plan"}[r.status]))

    def _draw_settings(self, tab: ttk.Frame) -> None:
        box = ttk.LabelFrame(tab, text="Periods of the day", padding=8)
        box.pack(fill="x")
        rows: list[tuple[ttk.Entry, ttk.Entry, ttk.Entry]] = []
        table = ttk.Frame(box)
        table.pack(anchor="w")
        for c, h in enumerate(("Period", "Label", "Start", "End")):
            ttk.Label(table, text=h, font=("", 10, "bold")).grid(row=0, column=c, padx=4)
        state = "normal" if self.editor else "readonly"

        def add_row(p: TT.Period | None = None) -> None:
            r = len(rows) + 1
            ttk.Label(table, text=str(r)).grid(row=r, column=0)
            ents = []
            for c, (v, w) in enumerate(((p.label if p else f"P{r}", 8),
                                        (p.start_time if p else "", 7),
                                        (p.end_time if p else "", 7)), 1):
                e = ttk.Entry(table, width=w)
                e.insert(0, v)
                e.configure(state=state)
                e.grid(row=r, column=c, padx=4, pady=1)
                ents.append(e)
            rows.append(tuple(ents))  # type: ignore[arg-type]

        for p in TT.periods():
            add_row(p)
        if self.editor:
            pb = ttk.Frame(box)
            pb.pack(anchor="w", pady=(6, 0))

            def remove_last() -> None:
                if len(rows) > 1:
                    for e in rows.pop():
                        e.destroy()
                    for w in table.grid_slaves(row=len(rows) + 1, column=0):
                        w.destroy()

            def save_periods() -> None:
                try:
                    TT.set_periods([{"label": a.get(), "start_time": b.get(),
                                     "end_time": c.get()} for a, b, c in rows],
                                   actor=self.principal)
                except (TT.ValidationError, TT.PermissionDenied) as e:
                    messagebox.showerror("Periods", _problems(e), parent=self.parent)
                    return
                messagebox.showinfo("Periods", "Saved.", parent=self.parent)
                self._on_tab()

            ttk.Button(pb, text="Add period", command=add_row).pack(side="left")
            ttk.Button(pb, text="Remove last", command=remove_last).pack(side="left", padx=6)
            ttk.Button(pb, text="Save periods", command=save_periods).pack(side="left")

        cyc = ttk.LabelFrame(tab, text="Week cycle", padding=8)
        cyc.pack(fill="x", pady=(10, 0))
        weeks = tk.StringVar(value=str(TT.cycle_weeks()))
        restart = tk.StringVar(value=TT.cycle_restart())
        for v, t in (("1", "One week"), ("2", "Two weeks (Week A / Week B)")):
            ttk.Radiobutton(cyc, text=t, value=v, variable=weeks,
                            state="normal" if self.editor else "disabled").pack(anchor="w")
        ttk.Label(cyc, text="Week A starts again:").pack(anchor="w", pady=(6, 0))
        for v, t in (("year", "each academic year (counting weeks from 1 September)"),
                     ("term", "each term")):
            ttk.Radiobutton(cyc, text=t, value=v, variable=restart,
                            state="normal" if self.editor else "disabled").pack(anchor="w")
        ttk.Label(cyc, text=f"Today is {TT.WEEK_LABELS[TT.week_for(_dt.date.today())]}."
                  if TT.cycle_weeks() == 2 else "", foreground="#666").pack(anchor="w")
        if self.editor:
            def save_cycle() -> None:
                try:
                    TT.set_cycle(weeks.get(), restart.get(), actor=self.principal)
                except (TT.ValidationError, TT.PermissionDenied) as e:
                    messagebox.showerror("Week cycle", _problems(e), parent=self.parent)
                    return
                self._on_tab()

            def copy() -> None:
                if not messagebox.askyesno("Copy", "Copy every Week A lesson into Week B? "
                                           "Lessons that would clash are skipped.",
                                           parent=self.parent):
                    return
                try:
                    n, notes = TT.copy_week(actor=self.principal)
                except (TT.ValidationError, TT.PermissionDenied) as e:
                    messagebox.showerror("Copy", _problems(e), parent=self.parent)
                    return
                messagebox.showinfo("Copy", f"{n} lesson(s) copied."
                                    + ("\n\nSkipped:\n" + "\n".join(notes[:15]) if notes else ""),
                                    parent=self.parent)

            cb = ttk.Frame(cyc)
            cb.pack(anchor="w", pady=(6, 0))
            ttk.Button(cb, text="Save cycle", command=save_cycle).pack(side="left")
            if TT.cycle_weeks() == 2:
                ttk.Button(cb, text="Copy Week A to Week B", command=copy).pack(side="left",
                                                                               padx=6)


def draw_timetable(parent: ttk.Frame, *, principal: Principal,
                   state: dict | None = None) -> TimetablePage:
    return TimetablePage(parent, principal=principal, state=state if state is not None else {})


# ── Lesson dialog ────────────────────────────────────────────────────

def lesson_dialog(owner, principal: Principal, x: TT.Lesson | None, after: Callable[[], None],
                  *, year: int | None = None, week: int | None = None, day: int | None = None,
                  period: int | None = None) -> None:
    if principal.role not in TIMETABLE_EDITORS:
        messagebox.showinfo("Timetable", "Your account can view the timetable but not change "
                            "it.", parent=owner)
        return
    groups = {f"{i.group.code} - {i.subject.code} Y{i.group.year_group}"
              + (f" ({i.group.teacher_name})" if i.group.teacher_name else ""): i.group
              for i in TG.info(TG.list_groups(year_group=year))}
    if not groups and x is None:
        messagebox.showinfo("Timetable", "Set up teaching groups first (Teaching Groups).",
                            parent=owner)
        return
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Edit lesson - {x.slot_label}" if x else "New lesson")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=14)
    frm.pack(fill="both", expand=True)
    r = 0

    def label(text: str, hint: str = "") -> None:
        ttk.Label(frm, text=text).grid(row=r, column=0, sticky="w", pady=2, padx=(0, 8))
        if hint:
            ttk.Label(frm, text=hint, foreground="#888").grid(row=r, column=2, sticky="w",
                                                              padx=6)

    label("Teaching group *")
    group_cb = ttk.Combobox(frm, values=list(groups), state="readonly", width=40)
    group_cb.set(next((k for k, g in groups.items() if x and g.group_id == x.group_id), ""))
    group_cb.grid(row=r, column=1, sticky="w", pady=2)
    r += 1
    weeks = TT.cycle_weeks()
    label("Week")
    week_cb = ttk.Combobox(frm, values=[TT.WEEK_LABELS[w] for w in range(1, weeks + 1)],
                           state="readonly" if weeks == 2 else "disabled", width=10)
    week_cb.set(TT.WEEK_LABELS[(x.week if x else week) or 1])
    week_cb.grid(row=r, column=1, sticky="w", pady=2)
    r += 1
    label("Day *")
    day_cb = ttk.Combobox(frm, values=list(TT.DAY_NAMES), state="readonly", width=12)
    d = (x.day if x else day)
    day_cb.set(TT.DAY_NAMES[d - 1] if d else "")
    day_cb.grid(row=r, column=1, sticky="w", pady=2)
    r += 1
    plist = TT.periods()
    plabels = [f"{p.label} ({p.times})" for p in plist]
    label("Period *")
    period_cb = ttk.Combobox(frm, values=plabels, state="readonly", width=20)
    pn = (x.period if x else period)
    period_cb.set(plabels[pn - 1] if pn and pn <= len(plabels) else "")
    period_cb.grid(row=r, column=1, sticky="w", pady=2)
    r += 1
    ents = {}
    for key, text, hint, value in (
            ("room", "Room", "blank = the group's room", x.room_override if x else None),
            ("teacher_name", "Teacher", "blank = the group's teacher",
             x.teacher_name_override if x else None),
            ("notes", "Notes", "", x.notes if x else None)):
        label(text, hint)
        e = ttk.Entry(frm, width=34 if key != "room" else 10)
        e.insert(0, value or "")
        e.grid(row=r, column=1, sticky="w", pady=2)
        ents[key] = e
        r += 1
    note = ttk.Label(frm, foreground="#a60", wraplength=460, justify="left")
    note.grid(row=r, column=0, columnspan=3, sticky="w")
    r += 1

    def data() -> dict:
        g = groups.get(group_cb.get())
        return {"group_id": g.group_id if g else (x.group_id if x else None),
                "week": week_cb.current() + 1 if weeks == 2 else 1,
                "day": day_cb.current() + 1 if day_cb.get() else "",
                "period": plist[period_cb.current()].period if period_cb.get() else "",
                "room": ents["room"].get(), "teacher_name": ents["teacher_name"].get(),
                # Keep a lesson's teacher login while its teacher name is unchanged.
                "teacher_username": (x.teacher_username_override or "") if x and
                ents["teacher_name"].get().strip() == (x.teacher_name_override or "") else "",
                "notes": ents["notes"].get()}

    def preview(_e=None) -> None:
        try:
            found = TT.check(data(), x.lesson_id if x else None)
        except TT.ValidationError:
            note.configure(text="")
            return
        note.configure(text=("⚠ " + "\n⚠ ".join(found)) if found else "No clashes.")

    for cb in (group_cb, week_cb, day_cb, period_cb):
        cb.bind("<<ComboboxSelected>>", preview)
    preview()

    def save() -> None:
        d = data()
        try:
            found = TT.check(d, x.lesson_id if x else None)
        except TT.ValidationError as e:
            messagebox.showerror("Lesson", _problems(e), parent=win)
            return
        allow = False
        if found:
            if any(f.endswith("already has a lesson then") for f in found):
                messagebox.showerror("Lesson", "\n".join(found), parent=win)
                return
            if not messagebox.askyesno("Clash", "\n".join(found) + "\n\nBook it anyway?",
                                       parent=win):
                return
            allow = True
        try:
            if x is None:
                TT.add_lesson(d, actor=principal, allow_clash=allow)
            else:
                TT.update_lesson(x.lesson_id, d, actor=principal, allow_clash=allow)
        except (TT.ValidationError, TT.PermissionDenied) as e:
            messagebox.showerror("Lesson", _problems(e), parent=win)
            return
        win.destroy()
        after()

    bar = ttk.Frame(frm)
    bar.grid(row=r, column=0, columnspan=3, sticky="e", pady=(10, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Save", command=save).pack(side="right", padx=(0, 6))
