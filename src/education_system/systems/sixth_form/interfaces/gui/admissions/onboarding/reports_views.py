"""Onboarding reports: the progress dashboard, the outstanding-tasks list
and the chase log.

* **Reports** — :func:`onboarding_reports.dashboard` grouped by tutor
  group, course or year group, drawn as stat tiles and labelled bars in
  the style of the destinations summary; CSV / PDF export.
* **Outstanding** — :func:`onboarding_reports.outstanding_tasks` with its
  filters; CSV / PDF export.
* **Chase log** — :func:`onboarding_jobs.chase_log`, read-only.

All three read only; each has the "Open in new window" button.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any

from education_system.platform.delivery.gui.parented_dialogs import (
    filedialog,
    messagebox,
)
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding as data,
)
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding_jobs as jobs,
)
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding_reports as reports,
)
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    templates as tpl,
)
from education_system.systems.sixth_form.interfaces.gui import popout
from education_system.systems.sixth_form.interfaces.gui.admissions import (
    _admissions_ui as ui,
)

logger = logging.getLogger(__name__)

GROUP_LABELS = {"Tutor group": "tutor_group", "Course": "course",
                "Year group": "year_group"}


def export(parent: tk.Misc, kind: str, fmt: str, **kw: Any) -> None:
    """Ask for a file name and write the report as CSV or PDF."""
    path = filedialog.asksaveasfilename(
        parent=parent, title=f"Export onboarding report ({fmt.upper()})",
        defaultextension=f".{fmt}",
        initialfile=f"onboarding_{kind}.{fmt}",
        filetypes=[(fmt.upper(), f"*.{fmt}"), ("All files", "*.*")])
    if not path:
        return
    try:
        if fmt == "csv":
            reports.export_csv(kind, path, **kw)
        else:
            reports.export_pdf(kind, path, **kw)
    except Exception as e:  # noqa: BLE001 — ValidationError / reportlab missing
        messagebox.showerror("Export", str(e), parent=parent)
        return
    messagebox.showinfo("Export", f"Saved to {path}", parent=parent)


# ══ Dashboard ═════════════════════════════════════════════════════

class ReportsTab:
    """Progress per group as stat tiles and labelled bars (one neutral
    accent for % complete; overdue counts in the warning colour)."""

    BAR = "#1a3f8c"
    WARN = "#b3261e"
    TRACK = "#e3e6ea"
    INK = "#1c2430"
    MUTED = "#5b6672"

    def __init__(self, nb: ttk.Notebook, *, group: str = "Tutor group",
                 year: str = "", open_only: bool = False) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Reports")
        self._build(group, year, open_only)
        self.refresh()

    def _build(self, group: str, year: str, open_only: bool) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=12, pady=(12, 0))
        ttk.Label(bar, text="Onboarding progress",
                  font=("", 15, "bold")).pack(side="left")
        ttk.Label(bar, text="Group by:").pack(side="left", padx=(16, 2))
        self.group_cb = ttk.Combobox(bar, values=list(GROUP_LABELS),
                                     state="readonly", width=12)
        self.group_cb.set(group)
        self.group_cb.pack(side="left")
        self.group_cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        ttk.Label(bar, text="Academic year:").pack(side="left", padx=(10, 2))
        self.year_e = ttk.Entry(bar, width=10)
        self.year_e.insert(0, year)
        self.year_e.pack(side="left")
        self.year_e.bind("<Return>", lambda _e: self.refresh())
        self.open_var = tk.BooleanVar(value=open_only)
        ttk.Checkbutton(bar, text="Open checklists only",
                        variable=self.open_var,
                        command=self.refresh).pack(side="left", padx=8)
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side="right")
        ttk.Button(bar, text="Export PDF…",
                   command=lambda: self._export("pdf")).pack(side="right",
                                                             padx=4)
        ttk.Button(bar, text="Export CSV…",
                   command=lambda: self._export("csv")).pack(side="right")
        if not isinstance(self.frame.master, popout.FrameBook):
            popout.add_page_button(
                bar, "Onboarding progress",
                lambda book: ReportsTab(
                    book, group=self.group_cb.get(),
                    year=self.year_e.get().strip(),
                    open_only=self.open_var.get()), padx=(0, 6))

        outer = ttk.Frame(self.frame)
        outer.pack(fill="both", expand=True, padx=12, pady=12)
        self.canvas = tk.Canvas(outer, highlightthickness=0, bg="#ffffff")
        vsb = ttk.Scrollbar(outer, orient="vertical",
                            command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.body = tk.Frame(self.canvas, bg="#ffffff")
        self._body_id = self.canvas.create_window((0, 0), window=self.body,
                                                  anchor="nw")
        self.body.bind("<Configure>", lambda _e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(
            self._body_id, width=e.width))

    def _kw(self) -> dict[str, Any]:
        return {"academic_year": self.year_e.get().strip() or None,
                "open_only": self.open_var.get()}

    def _group(self) -> str:
        return GROUP_LABELS.get(self.group_cb.get(), "tutor_group")

    def _export(self, fmt: str) -> None:
        export(self.frame.winfo_toplevel(), self._group(), fmt, **self._kw())

    # ── pieces ───────────────────────────────────────────────────
    def _tile(self, parent: tk.Misc, value: Any, label: str,
              note: str = "") -> None:
        card = tk.Frame(parent, bg="#f6f8fa", highlightthickness=1,
                        highlightbackground="#dde2e8")
        card.pack(side="left", expand=True, fill="both", padx=4)
        tk.Label(card, text=str(value), font=("", 26, "bold"),
                 bg="#f6f8fa", fg=self.INK).pack(anchor="w", padx=14,
                                                  pady=(12, 0))
        tk.Label(card, text=label, font=("", 9), bg="#f6f8fa",
                 fg=self.MUTED).pack(anchor="w", padx=14, pady=(0, 2))
        tk.Label(card, text=note, font=("", 9), bg="#f6f8fa",
                 fg=self.MUTED).pack(anchor="w", padx=14, pady=(0, 12))

    def _heading(self, text: str) -> None:
        tk.Label(self.body, text=text, font=("", 11, "bold"), fg=self.INK,
                 bg="#ffffff").pack(anchor="w", pady=(18, 6))

    def _bar_row(self, label: str, value: float, total: float, shown: str,
                 note: str = "", colour: str | None = None) -> None:
        row = tk.Frame(self.body, bg="#ffffff")
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, width=24, anchor="w", font=("", 10),
                 fg=self.INK, bg="#ffffff").pack(side="left")
        tk.Label(row, text=shown, width=7, anchor="e",
                 font=("", 10, "bold"), fg=self.INK,
                 bg="#ffffff").pack(side="right")
        if note:
            tk.Label(row, text=note, width=34, anchor="e", font=("", 9),
                     fg=self.MUTED, bg="#ffffff").pack(side="right")
        track = tk.Canvas(row, height=12, bg="#ffffff", highlightthickness=0)
        track.pack(side="left", fill="x", expand=True, padx=8)

        def draw(_event=None, c=track, n=value, t=total,
                 col=colour or self.BAR) -> None:
            c.delete("all")
            width = max(c.winfo_width(), 1)
            c.create_rectangle(0, 3, width, 11, fill=self.TRACK, outline="")
            if t > 0 and n > 0:
                c.create_rectangle(0, 3, max(int(width * n / t), 3), 11,
                                   fill=col, outline="")

        track.bind("<Configure>", draw)
        draw()

    # ── data ─────────────────────────────────────────────────────
    def refresh(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()
        try:
            rows = reports.dashboard(self._group(), **self._kw())
        except Exception as e:  # noqa: BLE001
            logger.exception("Onboarding dashboard failed")
            tk.Label(self.body, text=f"Could not load the report: {e}",
                     fg=self.WARN, bg="#ffffff").pack(anchor="w")
            return
        group = self.group_cb.get()
        learners = len({s for r in rows for s in r._students})
        checklists = sum(r.checklists for r in rows) if \
            self._group() != "course" else None
        tasks = sum(r.tasks for r in rows)
        done = sum(r.tasks_done for r in rows)
        overdue = sum(r.overdue for r in rows)
        blocked = sum(r.blocked for r in rows)
        tiles = tk.Frame(self.body, bg="#ffffff")
        tiles.pack(fill="x", pady=(4, 0))
        self._tile(tiles, learners, "Learners", f"in {len(rows)} group(s)")
        self._tile(tiles, f"{round(100 * done / tasks) if tasks else 0}%",
                   "Tasks done", f"{done} of {tasks}"
                   + (" (a learner counts once per course)"
                      if checklists is None else ""))
        self._tile(tiles, overdue, "Overdue tasks", "not done, past due")
        self._tile(tiles, blocked, "Blocked tasks", "waiting on something")
        if not rows:
            self._heading("No checklists for this year yet.")
            return
        self._heading(f"% of tasks done, by {group.lower()}")
        for r in rows:
            self._bar_row(r.group, r.percent_complete, 100,
                          f"{r.percent_complete:.0f}%",
                          note=f"{r.learners} learner(s) · {r.completed}/"
                               f"{r.checklists} complete")
        if overdue:
            self._heading(f"Overdue tasks, by {group.lower()}")
            top = max(r.overdue for r in rows) or 1
            for r in rows:
                if r.overdue:
                    self._bar_row(r.group, r.overdue, top, str(r.overdue),
                                  colour=self.WARN)
        if blocked:
            self._heading(f"Blocked tasks, by {group.lower()}")
            top = max(r.blocked for r in rows) or 1
            for r in rows:
                if r.blocked:
                    self._bar_row(r.group, r.blocked, top, str(r.blocked))


# ══ Outstanding tasks ═════════════════════════════════════════════

class OutstandingTab:
    COLS = [("due", "Due", 90), ("student", "Student", 80),
            ("name", "Name", 150), ("tg", "Tutor group", 85),
            ("yg", "Year", 45), ("chk", "Checklist", 70),
            ("task", "Task", 280), ("status", "Status", 80),
            ("req", "Req.", 40), ("owner", "Owner", 90),
            ("assigned", "Assigned", 100), ("blocked", "Blocked by", 200)]

    def __init__(self, nb: ttk.Notebook, *, initial: dict | None = None
                 ) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Outstanding")
        self._build(initial or {})
        self.refresh()

    def _build(self, init: dict) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Year:").pack(side="left")
        self.year_e = ttk.Entry(bar, width=9)
        self.year_e.insert(0, init.get("academic_year") or "")
        self.year_e.pack(side="left", padx=(2, 6))
        ttk.Label(bar, text="Tutor group:").pack(side="left")
        self.tg_e = ttk.Entry(bar, width=8)
        self.tg_e.insert(0, init.get("tutor_group") or "")
        self.tg_e.pack(side="left", padx=(2, 6))
        ttk.Label(bar, text="Owner:").pack(side="left")
        self.owner_cb = ttk.Combobox(bar, values=("",) + tpl.OWNER_ROLES,
                                     state="readonly", width=12)
        self.owner_cb.set(init.get("owner_role") or "")
        self.owner_cb.pack(side="left", padx=(2, 6))
        ttk.Label(bar, text="Category:").pack(side="left")
        self.cat_cb = ttk.Combobox(bar, values=("",) + data.CATEGORIES,
                                   state="readonly", width=18)
        self.cat_cb.set(init.get("category") or "")
        self.cat_cb.pack(side="left", padx=(2, 6))
        self.vars = {}
        for key, text in (("overdue_only", "Overdue"),
                          ("blocked_only", "Blocked"),
                          ("required_only", "Required")):
            var = tk.BooleanVar(value=bool(init.get(key)))
            self.vars[key] = var
            ttk.Checkbutton(bar, text=text, variable=var,
                            command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Show", command=self.refresh).pack(side="left",
                                                                 padx=6)
        bar2 = ttk.Frame(self.frame)
        bar2.pack(fill="x", padx=8, pady=(0, 4))
        self.count_var = tk.StringVar()
        ttk.Label(bar2, textvariable=self.count_var,
                  foreground="#555").pack(side="left")
        ttk.Button(bar2, text="Export PDF…",
                   command=lambda: self._export("pdf")).pack(side="right",
                                                             padx=4)
        ttk.Button(bar2, text="Export CSV…",
                   command=lambda: self._export("csv")).pack(side="right")
        if not isinstance(self.frame.master, popout.FrameBook):
            popout.add_page_button(
                bar2, "Outstanding onboarding tasks",
                lambda book: OutstandingTab(book, initial=self._kw()),
                padx=(0, 6))
        holder = ttk.Frame(self.frame)
        holder.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tree = ui.make_tree(holder, self.COLS, height=24)
        self.tree.tag_configure("overdue", background="#ffd0d0")
        self.tree.tag_configure("Blocked", foreground="#a33")

    def _kw(self) -> dict[str, Any]:
        kw: dict[str, Any] = {k: v.get() for k, v in self.vars.items()}
        kw.update(academic_year=self.year_e.get().strip() or None,
                  tutor_group=self.tg_e.get().strip() or None,
                  owner_role=self.owner_cb.get() or None,
                  category=self.cat_cb.get() or None)
        return kw

    def _export(self, fmt: str) -> None:
        export(self.frame.winfo_toplevel(), "outstanding", fmt, **self._kw())

    def refresh(self) -> None:
        ui.clear(self.tree)
        try:
            rows = reports.outstanding_tasks(**self._kw())
        except Exception as e:  # noqa: BLE001
            logger.exception("Outstanding onboarding tasks failed")
            self.count_var.set(f"Could not load: {e}")
            return
        for n, t in enumerate(rows):
            tags = (["overdue"] if t.overdue else []) + (
                ["Blocked"] if t.status == "Blocked" else [])
            self.tree.insert("", "end", iid=str(n), tags=tuple(tags), values=(
                t.due_date or "—", t.student_id, t.student_name,
                t.tutor_group or "", t.year_group or "", f"#{t.checklist_id}",
                t.task, t.status, "*" if t.required else "",
                t.owner_role or "", t.assigned_to or "",
                t.blocked_reason or ""))
        late = sum(1 for t in rows if t.overdue)
        self.count_var.set(f"{len(rows)} outstanding task(s), {late} overdue "
                           "(overdue first)")


# ══ Chase log ═════════════════════════════════════════════════════

class ChaseLogTab:
    """Who was chased about overdue tasks, and when (read-only)."""

    def __init__(self, nb: ttk.Notebook, *, checklist_id: int | None = None
                 ) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Chase log")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Checklist #:").pack(side="left")
        self.chk_e = ttk.Entry(bar, width=8)
        if checklist_id is not None:
            self.chk_e.insert(0, str(checklist_id))
        self.chk_e.pack(side="left", padx=(2, 6))
        self.chk_e.bind("<Return>", lambda _e: self.refresh())
        ttk.Button(bar, text="Show", command=self.refresh).pack(side="left")
        ttk.Label(bar, foreground="#777", text=(
            f"Owners of overdue tasks get one in-app reminder per checklist "
            f"at most every {jobs.CHASE_EVERY_DAYS} days (the nightly job)."
        )).pack(side="left", padx=12)
        self.count_var = tk.StringVar()
        ttk.Label(bar, textvariable=self.count_var,
                  foreground="#555").pack(side="right")
        holder = ttk.Frame(self.frame)
        holder.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tree = ui.make_tree(holder, [
            ("id", "#", 50), ("on", "Chased on", 100),
            ("chk", "Checklist", 80), ("who", "Sent to", 160),
            ("tasks", "Overdue tasks", 100)], height=24)
        self.refresh()

    def refresh(self) -> None:
        ui.clear(self.tree)
        raw = self.chk_e.get().strip().lstrip("#")
        if raw and not raw.isdigit():
            self.count_var.set("Checklist # must be a number")
            return
        try:
            rows = jobs.chase_log(int(raw) if raw else None)
        except Exception as e:  # noqa: BLE001
            logger.exception("Onboarding chase log failed")
            self.count_var.set(f"Could not load: {e}")
            return
        for r in rows:
            self.tree.insert("", "end", iid=str(r["chase_id"]), values=(
                r["chase_id"], r["chased_on"], f"#{r['checklist_id']}",
                r["recipient"], r["tasks"]))
        self.count_var.set(f"{len(rows)} reminder(s), newest first")
