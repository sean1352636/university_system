"""Tkinter views for the Extended Project Qualification (EPQ).

Single window with two tabs:

* **Projects** — filterable treeview, with actions to create / edit /
  delete a project, log a production-log entry, and update a
  milestone. Double-click a row to open the full detail dialog.
* **Summary** — counts by stage / artefact / final grade, plus total
  production-log hours and overdue / upcoming milestone counts.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from education_system.shared import branding
from education_system.post_16.sixthform_system.modules.domain.academics.epq import (
    epq as data,
)
from education_system.post_16.sixthform_system.modules.domain.academics.epq.epq import (
    ARTEFACT_TYPES,
    DEFAULT_ARTEFACT_TYPE,
    DEFAULT_MILESTONE_STATUS,
    DEFAULT_STAGE,
    EPQLogEntry,
    EPQMilestone,
    EPQProject,
    GRADES,
    MILESTONE_LABELS,
    MILESTONE_STATUSES,
    MILESTONE_TYPES,
    STAGES,
    ValidationError,
)
from education_system.post_16.sixthform_system.modules.domain.students.students import (
    students as student_data,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STAGE_TAGS: dict[str, tuple[str, str]] = {
    "Proposal":     ("#fff7e6", "#7a5800"),
    "Research":     ("#e6f0ff", "#1a3f8c"),
    "Drafting":     ("#e6f0ff", "#1a3f8c"),
    "Production":   ("#e6f0ff", "#1a3f8c"),
    "Review":       ("#fff0d6", "#7a5800"),
    "Presentation": ("#fff0d6", "#7a5800"),
    "Complete":     ("#e6f7e6", "#0d6b2a"),
    "Withdrawn":    ("#eeeeee", "#666666"),
}


def open_directory(parent=None) -> None:
    """Entry-point used by the sixth-form GUI main menu."""
    try:
        data.init_db()
    except Exception:
        logger.exception("EPQ init_db failed")
        messagebox.showerror(
            "EPQ",
            "Could not initialise the EPQ database. Check logs.",
        )
        return

    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"EPQ — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    projects_tab = ProjectsTab(nb, win)
    SummaryTab(nb, projects_tab)


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}")
            for s in rows]


# ─────────────────────────────────────────────────────────────────
# Projects tab
# ─────────────────────────────────────────────────────────────────

class ProjectsTab:
    def __init__(self, nb: ttk.Notebook, root: tk.Misc) -> None:
        self.root = root
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Projects")
        self._build()
        self.refresh()

    # ── build UI ─────────────────────────────────────────────────
    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Stage:").pack(side="left")
        self.f_stage = ttk.Combobox(
            bar, values=("",) + STAGES,
            state="readonly", width=14)
        self.f_stage.current(0)
        self.f_stage.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Artefact:").pack(side="left")
        self.f_artefact = ttk.Combobox(
            bar, values=("",) + ARTEFACT_TYPES,
            state="readonly", width=14)
        self.f_artefact.current(0)
        self.f_artefact.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Supervisor:").pack(side="left")
        self.f_supervisor = ttk.Entry(bar, width=18)
        self.f_supervisor.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="New project",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "student", "name", "title", "artefact",
                "stage", "hours", "milestones", "grade")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "student": 90, "name": 160,
                   "title": 280, "artefact": 110, "stage": 100,
                   "hours": 70, "milestones": 100, "grade": 70}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(
                c, width=widths[c],
                anchor=("center" if c in ("id", "hours",
                                            "milestones", "grade")
                          else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for stage, (bg, fg) in _STAGE_TAGS.items():
            self.tree.tag_configure(stage, background=bg, foreground=fg)
        self.tree.bind("<Double-Button-1>", lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("View / Edit",       self._edit),
                ("Add log entry",     self._add_log),
                ("Update milestone",  self._update_milestone),
                ("Delete",            self._delete),
                ("Refresh",           self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    # ── filter helpers ──────────────────────────────────────────
    def _clear(self) -> None:
        self.f_stage.current(0)
        self.f_artefact.current(0)
        self.f_supervisor.delete(0, "end")
        self.refresh()

    def _filters(self) -> dict[str, Any]:
        f: dict[str, Any] = {}
        if self.f_stage.get():
            f["stage"] = self.f_stage.get()
        if self.f_artefact.get():
            f["artefact_type"] = self.f_artefact.get()
        if self.f_supervisor.get().strip():
            f["supervisor_like"] = self.f_supervisor.get().strip()
        return f

    # ── refresh / actions ───────────────────────────────────────
    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.list_projects_with_detail(**self._filters())
        except ValidationError as e:
            messagebox.showwarning("EPQ", str(e))
            return
        except Exception as e:
            logger.exception("EPQ projects refresh failed")
            messagebox.showerror("EPQ", f"Could not load projects: {e}")
            return
        for r in rows:
            p = r.project
            ms = f"{r.milestones_completed}/{r.milestones_total}"
            self.tree.insert(
                "", "end", iid=str(p.project_id),
                values=(p.project_id, p.student_id, r.student_name,
                          p.working_title, p.artefact_type, p.stage,
                          f"{r.total_hours:.1f}", ms,
                          p.final_grade or "—"),
                tags=(p.stage,),
            )
        self.count.configure(text=f"{len(rows)} project(s)")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("EPQ", "Select a project first.")
            return None
        try:
            return int(sel[0])
        except (TypeError, ValueError):
            return None

    def _new(self) -> None:
        ProjectDialog(self.root, on_save=lambda _p: self.refresh())

    def _edit(self) -> None:
        pid = self._selected_id()
        if pid is None:
            return
        proj = data.get_project(pid)
        if proj is None:
            messagebox.showwarning("EPQ", "Project not found.")
            self.refresh()
            return
        ProjectDialog(self.root, project=proj,
                       on_save=lambda _p: self.refresh())

    def _delete(self) -> None:
        pid = self._selected_id()
        if pid is None:
            return
        proj = data.get_project(pid)
        if proj is None:
            self.refresh()
            return
        if not messagebox.askyesno(
                "EPQ",
                f"Delete EPQ project #{pid} for student {proj.student_id}?\n"
                "Production-log entries and milestones will also be removed."):
            return
        try:
            data.delete_project(pid)
        except Exception as e:
            logger.exception("EPQ delete_project failed")
            messagebox.showerror("EPQ", f"Delete failed: {e}")
            return
        self.refresh()

    def _add_log(self) -> None:
        pid = self._selected_id()
        if pid is None:
            return
        proj = data.get_project(pid)
        if proj is None:
            self.refresh()
            return
        LogEntryDialog(self.root, project=proj,
                        on_save=lambda _e: self.refresh())

    def _update_milestone(self) -> None:
        pid = self._selected_id()
        if pid is None:
            return
        proj = data.get_project(pid)
        if proj is None:
            self.refresh()
            return
        MilestoneDialog(self.root, project=proj,
                         on_save=lambda _m: self.refresh())


# ─────────────────────────────────────────────────────────────────
# Project add / edit dialog
# ─────────────────────────────────────────────────────────────────

class ProjectDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, *,
                 project: EPQProject | None = None,
                 on_save) -> None:
        super().__init__(master)
        self.project = project
        self.on_save = on_save
        self.title("Edit EPQ Project" if project else "New EPQ Project")
        self.geometry("700x640")
        self.transient(master)
        # Defer grab until the window is actually viewable — Tk
        # raises "grab failed: window not viewable" if grab_set runs
        # before the window mapping has been processed. after_idle
        # queues the grab for the next idle slice of the event loop.
        self.after_idle(self._safe_grab)

    def _safe_grab(self) -> None:
        try:
            self.grab_set()
        except Exception:
            pass

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        for i in range(2):
            frm.columnconfigure(i, weight=1 if i == 1 else 0)

        row = 0

        ttk.Label(frm, text="Student:").grid(
            row=row, column=0, sticky="w", pady=4)
        student_opts = _student_options()
        self.v_student = tk.StringVar(
            value=(project.student_id if project else ""))
        if project:
            ttk.Label(frm,
                       text=f"{project.student_id} — "
                            f"{(student_data.get_student(project.student_id) or '')!s}"
                       ).grid(row=row, column=1, sticky="w", pady=4)
        else:
            self.cb_student = ttk.Combobox(
                frm, values=[lbl for _sid, lbl in student_opts],
                state="readonly")
            self.cb_student.grid(row=row, column=1, sticky="ew", pady=4)
            self._student_map = {lbl: sid for sid, lbl in student_opts}
        row += 1

        ttk.Label(frm, text="Working title:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_title = ttk.Entry(frm)
        self.e_title.grid(row=row, column=1, sticky="ew", pady=4)
        if project:
            self.e_title.insert(0, project.working_title)
        row += 1

        ttk.Label(frm, text="Research question:").grid(
            row=row, column=0, sticky="nw", pady=4)
        self.t_question = tk.Text(frm, height=3, wrap="word")
        self.t_question.grid(row=row, column=1, sticky="ew", pady=4)
        if project and project.research_question:
            self.t_question.insert("1.0", project.research_question)
        row += 1

        ttk.Label(frm, text="Artefact type:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.cb_artefact = ttk.Combobox(
            frm, values=ARTEFACT_TYPES, state="readonly")
        self.cb_artefact.set(project.artefact_type if project
                              else DEFAULT_ARTEFACT_TYPE)
        self.cb_artefact.grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Label(frm, text="Supervisor:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_supervisor = ttk.Entry(frm)
        self.e_supervisor.grid(row=row, column=1, sticky="ew", pady=4)
        if project and project.supervisor:
            self.e_supervisor.insert(0, project.supervisor)
        row += 1

        ttk.Label(frm, text="Stage:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.cb_stage = ttk.Combobox(
            frm, values=STAGES, state="readonly")
        self.cb_stage.set(project.stage if project else DEFAULT_STAGE)
        self.cb_stage.grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Label(frm, text="Final mark (0-50):").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_mark = ttk.Entry(frm)
        self.e_mark.grid(row=row, column=1, sticky="ew", pady=4)
        if project and project.final_mark is not None:
            self.e_mark.insert(0, str(project.final_mark))
        row += 1

        ttk.Label(frm, text="Final grade:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.cb_grade = ttk.Combobox(
            frm, values=("",) + GRADES, state="readonly")
        self.cb_grade.set(project.final_grade if project
                            and project.final_grade else "")
        self.cb_grade.grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Label(frm, text="Notes:").grid(
            row=row, column=0, sticky="nw", pady=4)
        self.t_notes = tk.Text(frm, height=6, wrap="word")
        self.t_notes.grid(row=row, column=1, sticky="ew", pady=4)
        if project and project.notes:
            self.t_notes.insert("1.0", project.notes)
        row += 1

        btns = ttk.Frame(frm)
        btns.grid(row=row, column=0, columnspan=2,
                    sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Cancel",
                    command=self.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="Save",
                    command=self._save).pack(side="right", padx=4)

    def _payload(self) -> dict[str, Any]:
        if self.project is not None:
            sid = self.project.student_id
        else:
            picked = self.cb_student.get()
            sid = self._student_map.get(picked, "")
        return {
            "student_id":        sid,
            "working_title":     self.e_title.get(),
            "research_question": self.t_question.get("1.0", "end").strip(),
            "artefact_type":     self.cb_artefact.get(),
            "supervisor":        self.e_supervisor.get(),
            "stage":             self.cb_stage.get(),
            "final_mark":        self.e_mark.get().strip() or None,
            "final_grade":       self.cb_grade.get() or None,
            "notes":             self.t_notes.get("1.0", "end").strip(),
        }

    def _save(self) -> None:
        try:
            payload = self._payload()
            if self.project is None:
                p = data.create_project(payload)
            else:
                p = data.update_project(self.project.project_id, payload)
        except ValidationError as e:
            messagebox.showwarning("EPQ", str(e), parent=self)
            return
        except Exception as e:
            logger.exception("EPQ project save failed")
            messagebox.showerror("EPQ", f"Save failed: {e}", parent=self)
            return
        self.on_save(p)
        self.destroy()


# ─────────────────────────────────────────────────────────────────
# Log-entry dialog
# ─────────────────────────────────────────────────────────────────

class LogEntryDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, *,
                 project: EPQProject, on_save) -> None:
        super().__init__(master)
        self.project = project
        self.on_save = on_save
        self.title(f"Production-log entry — project #{project.project_id}")
        self.geometry("780x560")
        self.transient(master)
        # Defer grab until the window is actually viewable — Tk
        # raises "grab failed: window not viewable" if grab_set runs
        # before the window mapping has been processed. after_idle
        # queues the grab for the next idle slice of the event loop.
        self.after_idle(self._safe_grab)

    def _safe_grab(self) -> None:
        try:
            self.grab_set()
        except Exception:
            pass

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)

        ttk.Label(frm,
                   text=f"Project: #{project.project_id} — "
                        f"{project.working_title}").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ttk.Label(frm, text="Entry date (YYYY-MM-DD):").grid(
            row=1, column=0, sticky="w", pady=4)
        self.e_date = ttk.Entry(frm)
        self.e_date.insert(0, _dt.date.today().isoformat())
        self.e_date.grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(frm, text="Hours (e.g. 1.5):").grid(
            row=2, column=0, sticky="w", pady=4)
        self.e_hours = ttk.Entry(frm)
        self.e_hours.grid(row=2, column=1, sticky="ew", pady=4)

        ttk.Label(frm, text="Activity:").grid(
            row=3, column=0, sticky="w", pady=4)
        self.e_activity = ttk.Entry(frm)
        self.e_activity.grid(row=3, column=1, sticky="ew", pady=4)

        ttk.Label(frm, text="Reflection:").grid(
            row=4, column=0, sticky="nw", pady=4)
        self.t_refl = tk.Text(frm, height=5, wrap="word")
        self.t_refl.grid(row=4, column=1, sticky="ew", pady=4)

        # Existing entries
        ttk.Label(frm, text="Existing entries:",
                    font=("", 10, "bold")).grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(12, 4))
        list_frame = ttk.Frame(frm)
        list_frame.grid(row=6, column=0, columnspan=2, sticky="nsew")
        frm.rowconfigure(6, weight=1)
        cols = ("id", "date", "hours", "activity")
        self.tree = ttk.Treeview(list_frame, columns=cols,
                                   show="headings", selectmode="browse",
                                   height=8)
        for c, w in zip(cols, (50, 100, 70, 540)):
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=w,
                              anchor=("center"
                                       if c in ("id", "hours")
                                       else "w"))
        vsb = ttk.Scrollbar(list_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.total_lbl = ttk.Label(frm, text="")
        self.total_lbl.grid(row=7, column=0, columnspan=2,
                              sticky="w", pady=4)

        btns = ttk.Frame(frm)
        btns.grid(row=8, column=0, columnspan=2, sticky="e",
                    pady=(8, 0))
        ttk.Button(btns, text="Close",
                    command=self.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="Delete selected",
                    command=self._delete).pack(side="right", padx=4)
        ttk.Button(btns, text="Add entry",
                    command=self._add).pack(side="right", padx=4)

        self._refresh()

    def _refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        entries = data.list_log_entries(self.project.project_id)
        for e in entries:
            self.tree.insert(
                "", "end", iid=str(e.log_id),
                values=(e.log_id, e.entry_date,
                          f"{e.hours:.1f}", e.activity),
            )
        total = data.total_hours_for_project(self.project.project_id)
        self.total_lbl.configure(
            text=f"{len(entries)} entries · {total:.1f} hours total")

    def _add(self) -> None:
        try:
            data.create_log_entry({
                "project_id": self.project.project_id,
                "entry_date": self.e_date.get(),
                "hours":      self.e_hours.get(),
                "activity":   self.e_activity.get(),
                "reflection": self.t_refl.get("1.0", "end").strip(),
            })
        except ValidationError as e:
            messagebox.showwarning("EPQ", str(e), parent=self)
            return
        except Exception as e:
            logger.exception("EPQ log entry add failed")
            messagebox.showerror("EPQ", f"Add failed: {e}", parent=self)
            return
        self.e_hours.delete(0, "end")
        self.e_activity.delete(0, "end")
        self.t_refl.delete("1.0", "end")
        self._refresh()
        self.on_save(None)

    def _delete(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        try:
            log_id = int(sel[0])
        except (TypeError, ValueError):
            return
        if not messagebox.askyesno("EPQ",
                                      f"Delete log entry #{log_id}?",
                                      parent=self):
            return
        try:
            data.delete_log_entry(log_id)
        except Exception as e:
            logger.exception("EPQ log entry delete failed")
            messagebox.showerror("EPQ", f"Delete failed: {e}",
                                   parent=self)
            return
        self._refresh()
        self.on_save(None)


# ─────────────────────────────────────────────────────────────────
# Milestone dialog
# ─────────────────────────────────────────────────────────────────

class MilestoneDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, *,
                 project: EPQProject, on_save) -> None:
        super().__init__(master)
        self.project = project
        self.on_save = on_save
        self.title(f"Milestones — project #{project.project_id}")
        self.geometry("760x480")
        self.transient(master)
        # Defer grab until the window is actually viewable — Tk
        # raises "grab failed: window not viewable" if grab_set runs
        # before the window mapping has been processed. after_idle
        # queues the grab for the next idle slice of the event loop.
        self.after_idle(self._safe_grab)

    def _safe_grab(self) -> None:
        try:
            self.grab_set()
        except Exception:
            pass

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)

        ttk.Label(frm,
                   text=f"Project: #{project.project_id} — "
                        f"{project.working_title}").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ttk.Label(frm, text="Milestone:").grid(
            row=1, column=0, sticky="w", pady=4)
        self.cb_type = ttk.Combobox(
            frm,
            values=[f"{m} — {MILESTONE_LABELS[m]}"
                      for m in MILESTONE_TYPES],
            state="readonly")
        self.cb_type.current(0)
        self.cb_type.grid(row=1, column=1, sticky="ew", pady=4)
        self.cb_type.bind("<<ComboboxSelected>>",
                           lambda _e: self._load_existing())

        ttk.Label(frm, text="Due date (YYYY-MM-DD):").grid(
            row=2, column=0, sticky="w", pady=4)
        self.e_due = ttk.Entry(frm)
        self.e_due.grid(row=2, column=1, sticky="ew", pady=4)

        ttk.Label(frm, text="Status:").grid(
            row=3, column=0, sticky="w", pady=4)
        self.cb_status = ttk.Combobox(
            frm, values=MILESTONE_STATUSES, state="readonly")
        self.cb_status.set(DEFAULT_MILESTONE_STATUS)
        self.cb_status.grid(row=3, column=1, sticky="ew", pady=4)

        ttk.Label(frm,
                   text="Completed date (auto if Status = Completed):"
                   ).grid(row=4, column=0, sticky="w", pady=4)
        self.e_done = ttk.Entry(frm)
        self.e_done.grid(row=4, column=1, sticky="ew", pady=4)

        ttk.Label(frm, text="Notes:").grid(
            row=5, column=0, sticky="nw", pady=4)
        self.t_notes = tk.Text(frm, height=5, wrap="word")
        self.t_notes.grid(row=5, column=1, sticky="ew", pady=4)

        # Existing milestones snapshot
        ttk.Label(frm, text="All milestones for this project:",
                    font=("", 10, "bold")).grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(12, 4))
        self.summary_lbl = ttk.Label(frm, text="", justify="left",
                                        font=("Courier", 9))
        self.summary_lbl.grid(row=7, column=0, columnspan=2,
                                sticky="w", pady=4)

        btns = ttk.Frame(frm)
        btns.grid(row=8, column=0, columnspan=2, sticky="e",
                    pady=(12, 0))
        ttk.Button(btns, text="Close",
                    command=self.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="Save / update",
                    command=self._save).pack(side="right", padx=4)

        self._load_existing()
        self._refresh_summary()

    def _selected_type(self) -> str:
        raw = self.cb_type.get().split(" — ", 1)[0].strip()
        return raw or MILESTONE_TYPES[0]

    def _load_existing(self) -> None:
        mtype = self._selected_type()
        existing = next(
            (m for m in data.list_milestones(self.project.project_id)
             if m.milestone_type == mtype),
            None,
        )
        self.e_due.delete(0, "end")
        self.e_done.delete(0, "end")
        self.t_notes.delete("1.0", "end")
        if existing is None:
            self.cb_status.set(DEFAULT_MILESTONE_STATUS)
            return
        if existing.due_date:
            self.e_due.insert(0, existing.due_date)
        if existing.completed_date:
            self.e_done.insert(0, existing.completed_date)
        self.cb_status.set(existing.status)
        if existing.notes:
            self.t_notes.insert("1.0", existing.notes)

    def _refresh_summary(self) -> None:
        rows = data.list_milestones(self.project.project_id)
        if not rows:
            self.summary_lbl.configure(text="(no milestones yet)")
            return
        lines = [
            f"{m.milestone_type:<13} due {m.due_date or '—':<10}"
            f"  done {m.completed_date or '—':<10}  [{m.status}]"
            for m in rows
        ]
        self.summary_lbl.configure(text="\n".join(lines))

    def _save(self) -> None:
        try:
            data.save_milestone({
                "project_id":     self.project.project_id,
                "milestone_type": self._selected_type(),
                "due_date":       self.e_due.get().strip(),
                "completed_date": self.e_done.get().strip(),
                "status":         self.cb_status.get(),
                "notes":          self.t_notes.get("1.0", "end").strip(),
            })
        except ValidationError as e:
            messagebox.showwarning("EPQ", str(e), parent=self)
            return
        except Exception as e:
            logger.exception("EPQ milestone save failed")
            messagebox.showerror("EPQ", f"Save failed: {e}", parent=self)
            return
        self._refresh_summary()
        self.on_save(None)


# ─────────────────────────────────────────────────────────────────
# Summary tab
# ─────────────────────────────────────────────────────────────────

class SummaryTab:
    def __init__(self, nb: ttk.Notebook,
                  projects_tab: ProjectsTab) -> None:
        self.projects_tab = projects_tab
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._build()
        self.refresh()

    def _build(self) -> None:
        top = ttk.Frame(self.frame, padding=12)
        top.pack(fill="both", expand=True)
        ttk.Button(top, text="Refresh",
                    command=self.refresh).pack(anchor="e")
        self.body = tk.Text(top, wrap="word", font=("Courier", 10),
                             height=30, state="disabled")
        self.body.pack(fill="both", expand=True, pady=(8, 0))

    def refresh(self) -> None:
        try:
            s = data.summary()
        except Exception as e:
            logger.exception("EPQ summary failed")
            messagebox.showerror("EPQ", f"Summary failed: {e}")
            return
        lines: list[str] = []
        lines.append(f"Total projects        : {s.total_projects}")
        lines.append(
            f"Total production-log  : {s.total_log_hours:.1f} hours")
        lines.append(
            f"Overdue milestones    : {s.overdue_milestones}")
        lines.append(
            f"Upcoming milestones   : {s.upcoming_milestones}"
            "  (within 21 days)")
        lines.append("")
        lines.append("By stage:")
        for stage, n in s.by_stage.items():
            lines.append(f"  {stage:<14} {n:>4}")
        lines.append("")
        lines.append("By artefact type:")
        for art, n in s.by_artefact.items():
            lines.append(f"  {art:<14} {n:>4}")
        if any(n for n in s.by_grade.values()):
            lines.append("")
            lines.append("By final grade:")
            for g, n in s.by_grade.items():
                if n:
                    lines.append(f"  {g:<14} {n:>4}")
        self.body.configure(state="normal")
        self.body.delete("1.0", "end")
        self.body.insert("1.0", "\n".join(lines))
        self.body.configure(state="disabled")
