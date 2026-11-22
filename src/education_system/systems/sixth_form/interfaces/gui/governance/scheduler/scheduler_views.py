"""Tkinter window: Scheduled Jobs, plus the GUI's background scheduler.

* :func:`open_scheduled_jobs_window` — the admin screen: every job with
  its schedule, next due time and last result; enable / disable, change
  the schedule, run now, and the run history with full errors. A second
  tab shows the exam results inbox.
* :func:`start_background_scheduler` — call once after the main window
  is built; due jobs then run on a background thread while the app is
  open. Jobs never touch Tk; this window only reads what they record.

Open to ADMIN or GOVERNANCE.
"""

from __future__ import annotations

import logging
import queue
import tkinter as tk
from tkinter import ttk
from education_system.systems.sixth_form.interfaces.gui._sidebar import SidebarBook
from education_system.platform.delivery.gui.parented_dialogs import messagebox, simpledialog

from education_system.platform import branding
from education_system.platform.delivery.gui import window_sizing
from education_system.systems.sixth_form.infrastructure.scheduler import (
    background,
    core,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.platform.delivery.gui.parented_dialogs import make_toplevel

logger = logging.getLogger(__name__)

TITLE = "Scheduled Jobs"
WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)
AUTO_REFRESH_MS = 15000
POLL_MS = 300

_STATUS_TAGS = {
    core.SUCCESS: ("#e6f7e6", "#0d6b2a"),
    core.PARTIAL: ("#fff0d6", "#7a5800"),
    core.FAILED: ("#ffd1d1", "#8c0d0d"),
    core.ABANDONED: ("#ffd1d1", "#8c0d0d"),
    core.RUNNING: ("#e6f0ff", "#1a3f8c"),
    core.SKIPPED: ("#f0f0f0", "#555555"),
}


def can_manage(p: access.Principal | None = None) -> bool:
    p = p or access.current()
    return p.can(access.ADMIN) or p.can(access.GOVERNANCE)


# ── Background scheduler hook ───────────────────────────────────────

def start_background_scheduler(root: tk.Misc) -> background.BackgroundScheduler | None:
    """Start running due sixth form jobs in the background of the GUI.

    Safe to call more than once. The worker is a daemon thread (jobs
    never touch Tk) and is stopped when *root* is destroyed. Returns
    ``None`` when switched off with ``EDU_SIXTHFORM_SCHEDULER=off``.
    """
    sched = background.start()
    if sched is None:
        return None
    if not getattr(root, "_sf_scheduler_bound", False):
        def _on_destroy(event: tk.Event) -> None:
            if event.widget is root:
                sched.stop(timeout=1.0)
        root.bind("<Destroy>", _on_destroy, add="+")
        try:
            root._sf_scheduler_bound = True  # type: ignore[attr-defined]
        except AttributeError:
            pass
    return sched


# ── Window ──────────────────────────────────────────────────────────

def open_scheduled_jobs_window(parent=None) -> None:
    master = getattr(parent, "root", parent)
    principal = access.current()
    if not can_manage(principal):
        messagebox.showwarning(
            TITLE, "Scheduled Jobs is for administrators and governance staff.",
            parent=master)
        return
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"{TITLE} — {branding.SYSTEM_NAME}")
    window_sizing.fit(win, WIN_GEOMETRY, WIN_MINSIZE)
    try:
        core.init_db()
    except Exception as e:
        logger.exception("Scheduler tables could not be prepared")
        messagebox.showerror(TITLE, str(e), parent=win)
        win.destroy()
        return
    nb = SidebarBook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    JobsTab(nb, win, principal.username or None)
    ResultsInboxTab(nb, win)


def _tree(parent: tk.Misc, cols: tuple[str, ...], widths: dict[str, int],
          *, height: int | None = None) -> ttk.Treeview:
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True, padx=4, pady=4)
    kw = {"height": height} if height else {}
    tree = ttk.Treeview(frame, columns=cols, show="headings",
                        selectmode="browse", **kw)
    for c in cols:
        tree.heading(c, text=c.replace("_", " ").title())
        tree.column(c, width=widths.get(c, 100), anchor="w",
                    stretch=c in ("summary", "description"))
    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")
    for status, (bg, fg) in _STATUS_TAGS.items():
        tree.tag_configure(status, background=bg, foreground=fg)
    tree.tag_configure("disabled", foreground="#888888")
    return tree


def _ms(ms: int | None) -> str:
    if ms is None:
        return ""
    return f"{ms} ms" if ms < 1000 else f"{ms / 1000:.1f} s"


class JobsTab:
    JOB_COLS = ("job", "category", "schedule", "enabled", "next_due",
                "last_run", "last_status", "duration")
    RUN_COLS = ("run", "job", "trigger", "by", "status", "started",
                "duration", "summary")

    def __init__(self, nb: ttk.Notebook, win: tk.Misc, username: str | None) -> None:
        self.win = win
        self.username = username
        self.done: queue.Queue = queue.Queue()
        self.jobs: dict[str, core.JobState] = {}
        self._after_ids: list[str] = []
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Jobs")

        self.status_var = tk.StringVar()
        ttk.Label(self.frame, textvariable=self.status_var,
                  foreground="#444").pack(fill="x", padx=6, pady=(6, 2))

        # Action bars are packed before the expanding tables.
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=4, pady=4)
        ttk.Button(bar, text="Run now", command=self._run_now).pack(side="left")
        ttk.Button(bar, text="Enable", command=lambda: self._set_enabled(True)
                   ).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Disable", command=lambda: self._set_enabled(False)
                   ).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Change schedule…", command=self._change_schedule
                   ).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Reset schedule", command=self._reset_schedule
                   ).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side="right")

        panes = ttk.PanedWindow(self.frame, orient="vertical")
        panes.pack(fill="both", expand=True)
        top = ttk.Frame(panes)
        bottom = ttk.Frame(panes)
        panes.add(top, weight=3)
        panes.add(bottom, weight=2)

        self.jobs_tree = _tree(top, self.JOB_COLS, {
            "job": 260, "category": 150, "schedule": 130, "enabled": 70,
            "next_due": 150, "last_run": 150, "last_status": 100,
            "duration": 80}, height=14)
        self.jobs_tree.bind("<<TreeviewSelect>>", lambda _e: self._on_select())
        self.desc_var = tk.StringVar()
        ttk.Label(top, textvariable=self.desc_var, wraplength=1250,
                  justify="left").pack(fill="x", padx=6, pady=(0, 4))

        hbar = ttk.Frame(bottom)
        hbar.pack(fill="x", padx=4, pady=(4, 0))
        ttk.Label(hbar, text="History:").pack(side="left")
        self.scope = tk.StringVar(value="selected")
        for value, text in (("selected", "Selected job"), ("all", "All jobs"),
                            ("problems", "Problems only")):
            ttk.Radiobutton(hbar, text=text, value=value, variable=self.scope,
                            command=self._load_history).pack(side="left", padx=4)
        ttk.Button(hbar, text="Show details", command=self._show_run
                   ).pack(side="right")
        self.runs_tree = _tree(bottom, self.RUN_COLS, {
            "run": 60, "job": 200, "trigger": 80, "by": 120, "status": 90,
            "started": 150, "duration": 80, "summary": 520})
        self.runs_tree.bind("<Double-1>", lambda _e: self._show_run())

        self.refresh()
        self._schedule_auto()
        self.frame.bind("<Destroy>", self._on_destroy, add="+")

    # ── helpers ────────────────────────────────────────────────────
    def _after(self, ms: int, fn) -> None:
        try:
            self._after_ids.append(self.win.after(ms, fn))
        except tk.TclError:
            pass

    def _on_destroy(self, event: tk.Event) -> None:
        if event.widget is not self.frame:
            return
        for aid in self._after_ids:
            try:
                self.win.after_cancel(aid)
            except tk.TclError:
                pass

    def _schedule_auto(self) -> None:
        def tick() -> None:
            if not self.frame.winfo_exists():
                return
            self.refresh(keep_selection=True)
            self._schedule_auto()
        self._after(AUTO_REFRESH_MS, tick)

    def _selected(self) -> str | None:
        sel = self.jobs_tree.selection()
        return sel[0] if sel else None

    def _need_selection(self) -> str | None:
        name = self._selected()
        if name is None:
            messagebox.showwarning(TITLE, "Select a job first.", parent=self.win)
        return name

    # ── data ───────────────────────────────────────────────────────
    def _status_line(self) -> str:
        bg = background.instance()
        if background.disabled_by_env():
            run = f"Background runner: OFF ({background.ENV_SWITCH}=off — use cron)"
        elif bg is not None and bg.running:
            run = f"Background runner: on (checks every {bg.tick_seconds}s)"
            if bg.last_error:
                run += f" — last tick failed: {bg.last_error}"
        else:
            run = ("Background runner: not running in this window — jobs run when "
                   "the main app has started it, or from cron (run_due_jobs)")
        try:
            from education_system.systems.sixth_form.domains.communications.domain.messages import (
                delivery,
            )
            mail = " · ".join(delivery.channel_status().lines())
        except Exception:  # noqa: BLE001 - status line only
            logger.debug("channel status unavailable", exc_info=True)
            mail = ""
        return run + ("   |   " + mail if mail else "")

    def refresh(self, *, keep_selection: bool = True) -> None:
        current = self._selected() if keep_selection else None
        try:
            jobs = core.list_jobs()
        except Exception as e:
            logger.exception("Could not list scheduled jobs")
            self.status_var.set(f"Could not read the job list: {e}")
            return
        self.jobs = {j.name: j for j in jobs}
        self.jobs_tree.delete(*self.jobs_tree.get_children())
        for j in jobs:
            status = core.RUNNING if j.running else (j.last_status or "")
            tags = [status] if status in _STATUS_TAGS else []
            if not j.enabled:
                tags.append("disabled")
            self.jobs_tree.insert("", "end", iid=j.name, tags=tuple(tags), values=(
                j.title, j.category, j.schedule_label, "Yes" if j.enabled else "No",
                (j.next_due_at or "") if j.enabled else "—",
                j.last_started_at or "never", status or "—",
                _ms(j.last_duration_ms)))
        if current and current in self.jobs:
            self.jobs_tree.selection_set(current)
            self.jobs_tree.see(current)
        self.status_var.set(self._status_line())
        self._on_select(load=False)
        self._load_history()

    def _on_select(self, *, load: bool = True) -> None:
        name = self._selected()
        j = self.jobs.get(name) if name else None
        if j is None:
            self.desc_var.set("")
        else:
            default = (f"Daily at {j.default_daily_at}" if j.default_daily_at
                       else f"Every {j.default_interval} min")
            self.desc_var.set(
                f"{j.title} ({j.name}) — {j.description}  Default: {default}, "
                f"{'on' if j.default_enabled else 'off'}.")
        if load:
            self._load_history()

    def _load_history(self) -> None:
        scope = self.scope.get()
        name = self._selected()
        try:
            if scope == "problems":
                runs = core.list_runs(problems_only=True)
            elif scope == "selected" and name:
                runs = core.list_runs(job_name=name)
            else:
                runs = core.list_runs()
        except Exception as e:
            logger.exception("Could not read job history")
            self.status_var.set(f"Could not read the job history: {e}")
            return
        self.runs_tree.delete(*self.runs_tree.get_children())
        for r in runs:
            title = self.jobs[r.job_name].title if r.job_name in self.jobs else r.job_name
            summary = (r.summary or "").replace("\n", " ")
            if r.error and r.status != core.FAILED:
                summary += f"  [{r.error.count(chr(10)) + 1} problem(s)]"
            self.runs_tree.insert("", "end", iid=str(r.run_id),
                                  tags=(r.status,) if r.status in _STATUS_TAGS else (),
                                  values=(r.run_id, title, r.trigger,
                                          r.triggered_by or "", r.status,
                                          r.started_at, _ms(r.duration_ms),
                                          summary[:400]))

    # ── actions ────────────────────────────────────────────────────
    def _run_now(self) -> None:
        name = self._need_selection()
        if name is None:
            return
        j = self.jobs.get(name)
        if j is not None and j.running:
            messagebox.showwarning(TITLE, f"{j.title} is already running.",
                                   parent=self.win)
            return
        background.run_in_background(
            name, triggered_by=self.username,
            on_done=lambda run, err: self.done.put((name, run, err)))
        self.status_var.set(f"Running {self.jobs[name].title}… (the window stays "
                            "usable; the result appears in the history)")
        self._after(POLL_MS, self._poll_done)

    def _poll_done(self) -> None:
        try:
            name, run, err = self.done.get_nowait()
        except queue.Empty:
            self._after(POLL_MS, self._poll_done)
            return
        if not self.frame.winfo_exists():
            return
        self.refresh()
        title = self.jobs[name].title if name in self.jobs else name
        if err is not None:
            messagebox.showerror(TITLE, f"{title} could not be run:\n{err}",
                                 parent=self.win)
        elif run is None:
            messagebox.showwarning(
                TITLE, f"{title} is already running elsewhere (another window, "
                "app instance or cron run) — not run again.", parent=self.win)
        elif run.status == core.SUCCESS:
            messagebox.showinfo(TITLE, f"{title}: {run.summary}", parent=self.win)
        else:
            messagebox.showwarning(
                TITLE, f"{title}: {run.status}\n\n{run.summary}\n\n"
                f"{(run.error or '')[:1500]}", parent=self.win)

    def _set_enabled(self, enabled: bool) -> None:
        name = self._need_selection()
        if name is None:
            return
        try:
            core.set_enabled(name, enabled, by=self.username)
        except core.ValidationError as e:
            messagebox.showwarning(TITLE, str(e), parent=self.win)
            return
        self.refresh()

    def _change_schedule(self) -> None:
        name = self._need_selection()
        if name is None:
            return
        j = self.jobs[name]
        current = j.daily_at or str(j.interval_minutes or "")
        raw = simpledialog.askstring(
            TITLE, f"New schedule for {j.title}:\n\n"
            "• a time of day as HH:MM (runs daily), or\n"
            "• a number of minutes (runs every N minutes).",
            initialvalue=current, parent=self.win)
        if raw is None:
            return
        raw = raw.strip()
        if not raw:
            messagebox.showwarning(TITLE, "Enter HH:MM or a number of minutes.",
                                   parent=self.win)
            return
        try:
            if ":" in raw:
                core.set_schedule(name, daily_at=raw, by=self.username)
            else:
                core.set_schedule(name, interval_minutes=raw, by=self.username)
        except core.ValidationError as e:
            messagebox.showwarning(TITLE, str(e), parent=self.win)
            return
        self.refresh()

    def _reset_schedule(self) -> None:
        name = self._need_selection()
        if name is None:
            return
        core.set_schedule(name, by=self.username)
        self.refresh()

    def _show_run(self) -> None:
        sel = self.runs_tree.selection()
        if not sel:
            messagebox.showwarning(TITLE, "Select a run in the history first.",
                                   parent=self.win)
            return
        run = core.get_run(int(sel[0]))
        if run is None:
            return
        top = make_toplevel(self.win)
        top.title(f"Run #{run.run_id} — {run.job_name}")
        window_sizing.fit(top, "900x600", (600, 400))
        text = tk.Text(top, wrap="word")
        vsb = ttk.Scrollbar(top, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=vsb.set)
        ttk.Button(top, text="Close", command=top.destroy).pack(side="bottom", pady=6)
        vsb.pack(side="right", fill="y")
        text.pack(fill="both", expand=True, padx=6, pady=6)
        text.insert("end", "\n".join([
            f"Job:        {run.job_name}",
            f"Status:     {run.status}",
            f"Trigger:    {run.trigger}" + (f" by {run.triggered_by}" if run.triggered_by else ""),
            f"Started:    {run.started_at}",
            f"Finished:   {run.finished_at or '—'}",
            f"Duration:   {_ms(run.duration_ms) or '—'}",
            f"Instance:   {run.owner or '—'}",
            "", "Summary:", run.summary or "—",
            "", "Errors:" if run.error else "No errors.", run.error or "",
        ]))
        text.configure(state="disabled")


class ResultsInboxTab:
    COLS = ("file", "status", "series", "board", "rows", "results", "embargo",
            "problem", "processed")

    def __init__(self, nb: ttk.Notebook, win: tk.Misc) -> None:
        from education_system.systems.sixth_form.domain.assessment.exams_office import (
            results_inbox,
        )
        self.inbox = results_inbox
        self.win = win
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Results Inbox")
        ttk.Label(
            self.frame, wraplength=1250, justify="left",
            text=("Drop exam board results files (A2C / EDI fixed-width or CSV) into "
                  f"{results_inbox.inbox_dir()} — name the file or its folder with the "
                  "season, year and (for EDI) board, e.g. AQA_Summer_2026_results.txt. "
                  "The 'Import exam board results' job imports them under the "
                  "results-day embargo, moves each to processed/ or failed/, and never "
                  "imports the same file twice.")).pack(fill="x", padx=6, pady=6)
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=4, pady=4)
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side="right")
        self.tree = _tree(self.frame, self.COLS, {
            "file": 260, "status": 90, "series": 110, "board": 110, "rows": 60,
            "results": 90, "embargo": 330, "problem": 300, "processed": 140})
        self.refresh()

    def refresh(self) -> None:
        try:
            rows = self.inbox.list_files()
        except Exception as e:
            logger.exception("Could not read the results inbox log")
            messagebox.showerror(TITLE, str(e), parent=self.win)
            return
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            tag = core.SUCCESS if r.status == self.inbox.STATUS_IMPORTED else core.PARTIAL
            series = f"{r.season or '?'} {r.year or '?'}" if (r.season or r.year) else ""
            self.tree.insert("", "end", iid=str(r.file_id), tags=(tag,), values=(
                r.file_name, r.status, series, r.exam_board or "", r.rows,
                f"{r.components}+{r.qualifications}", r.embargo_note or "",
                (r.error or r.problems or "").replace("\n", " ")[:200],
                r.processed_at))
