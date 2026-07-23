"""Tkinter views for Sixth Form Census / ILR."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from education_system.shared import branding
from education_system.post_16.sixthform_system.modules.domain.finance.census_ilr import (
    census_ilr as data,
)
from education_system.post_16.sixthform_system.modules.domain.finance.census_ilr.census_ilr import (
    AIM_TYPES,
    CensusReturn,
    DEFAULT_AIM_TYPE,
    DEFAULT_FUNDING_MODEL,
    DEFAULT_LEARNER_AIM_STATUS,
    DEFAULT_RETURN_STATUS,
    DEFAULT_RETURN_TYPE,
    FUNDING_MODELS,
    LearnerAim,
    LEARNER_AIM_STATUSES,
    RETURN_STATUSES,
    RETURN_TYPES,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_RETURN_TAGS = {
    "Planned":      ("#fff7e6", "#7a5800"),
    "Draft":        ("#fff7e6", "#7a5800"),
    "Under Review": ("#e6f0ff", "#1a3f8c"),
    "Validated":    ("#d6ffd6", "#0d6b2a"),
    "Submitted":    ("#e6f7e6", "#0d6b2a"),
    "Accepted":     ("#d6ffd6", "#0d6b2a"),
    "Rejected":     ("#ffd1d1", "#8c0d0d"),
    "Resubmitted":  ("#e6f0ff", "#1a3f8c"),
    "Archived":     ("#dddddd", "#444444"),
}

_AIM_TAGS = {
    "Continuing":            ("#e6f7e6", "#0d6b2a"),
    "Completed":             ("#d6ffd6", "#0d6b2a"),
    "Achieved":              ("#d6ffd6", "#0d6b2a"),
    "Partially Achieved":    ("#fff7e6", "#7a5800"),
    "Not Achieved":          ("#ffd1d1", "#8c0d0d"),
    "Withdrawn":             ("#eeeeee", "#666666"),
    "Transferred":           ("#e6f0ff", "#1a3f8c"),
    "Temporarily Withdrawn": ("#fff7e6", "#7a5800"),
}


def open_census_ilr_window(parent=None) -> None:
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Census / ILR — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)
    build_census_ilr_notebook(win)


def build_census_ilr_notebook(parent: tk.Misc) -> ttk.Notebook:
    """Build the Census / ILR notebook into *parent* (a Toplevel or Frame)."""
    data.init_db()
    nb = ttk.Notebook(parent)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    ReturnsTab(nb, scope="all",      label="All Returns")
    ReturnsTab(nb, scope="open",     label="Open Windows")
    ReturnsTab(nb, scope="overdue",  label="Overdue")
    AimsTab(nb)
    SummaryTab(nb)
    return nb


class ReturnsTab:
    def __init__(self, nb: ttk.Notebook, *,
                 scope: str, label: str) -> None:
        self.scope = scope
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text=label)
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = ttk.Combobox(
            bar, values=("",) + RETURN_TYPES,
            state="readonly", width=24)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Year:").pack(side="left")
        self.f_year = ttk.Entry(bar, width=10)
        self.f_year.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(
            bar, values=("",) + RETURN_STATUSES,
            state="readonly", width=14)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left",
                                                 padx=4)
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left",
                                              padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True,
                            padx=8, pady=4)
        cols = ("id", "ov", "type", "year", "ref",
                "deadline", "submitted", "learners",
                "errors", "warnings", "status")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "ov": 40, "type": 220,
                   "year": 80, "ref": 100, "deadline": 100,
                   "submitted": 100, "learners": 80,
                   "errors": 60, "warnings": 70, "status": 110}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "ov",
                                                  "learners",
                                                  "errors",
                                                  "warnings")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _RETURN_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.tag_configure("overdue",
                                  background="#ffd1d1",
                                  foreground="#8c0d0d")
        self.tree.bind("<Double-Button-1>",
                         lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("Edit",      self._edit),
                ("Validate",  self._validate),
                ("Submit",    self._submit),
                ("Accept",    self._accept),
                ("Reject",    self._reject),
                ("Resubmit",  self._resubmit),
                ("Archive",   self._archive),
                ("Counts",    self._counts),
                ("Status",    self._set_status),
                ("Delete",    self._delete),
                ("Refresh",   self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_type.get():
            f["return_type"] = self.f_type.get()
        if self.f_year.get().strip():
            f["academic_year"] = self.f_year.get().strip()
        if self.f_status.get():
            f["status"] = self.f_status.get()
        if self.scope == "open":
            f["open_window_only"] = True
        elif self.scope == "overdue":
            f["overdue_only"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.list_returns(**self._filters())
        except ValidationError as e:
            messagebox.showerror("Census / ILR", str(e),
                                    parent=self.frame)
            return
        for r in rows:
            tag = "overdue" if r.is_overdue else r.status
            self.tree.insert(
                "", "end", iid=str(r.return_id),
                values=(r.return_id,
                         "!" if r.is_overdue else "",
                         r.return_type, r.academic_year,
                         r.reference_date or "—",
                         r.submission_deadline or "—",
                         r.submitted_on or "—",
                         r.learner_count, r.error_count,
                         r.warning_count, r.status),
                tags=(tag,))
        self.count.config(text=f"{len(rows)} return(s)")

    def _selected(self) -> CensusReturn | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Census / ILR",
                                  "Select a return first.",
                                  parent=self.frame)
            return None
        return data.get_return(int(sel[0]))

    def _new(self) -> None:
        if ReturnEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        r = self._selected()
        if r and ReturnEditor(
                self.frame,
                return_obj=r).result is not None:
            self.refresh()

    def _run(self, action, *args, **kwargs) -> None:
        r = self._selected()
        if not r:
            return
        try:
            action(r.return_id, *args, **kwargs)
        except ValidationError as e:
            messagebox.showerror("Census / ILR", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _validate(self) -> None:
        self._run(data.validate_return)

    def _submit(self) -> None:
        self._run(data.submit_return)

    def _accept(self) -> None:
        self._run(data.accept_return)

    def _reject(self) -> None:
        self._run(data.reject_return)

    def _resubmit(self) -> None:
        self._run(data.resubmit_return)

    def _archive(self) -> None:
        self._run(data.archive_return)

    def _counts(self) -> None:
        r = self._selected()
        if not r:
            return
        errs = _prompt_text(self.frame, "Errors",
                              initial=str(r.error_count))
        if errs is None:
            return
        wrns = _prompt_text(self.frame, "Warnings",
                              initial=str(r.warning_count))
        if wrns is None:
            return
        try:
            data.record_validation_counts(
                r.return_id,
                errors=int(errs), warnings=int(wrns))
        except (ValidationError, ValueError) as e:
            messagebox.showerror("Census / ILR", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _set_status(self) -> None:
        r = self._selected()
        if not r:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(RETURN_STATUSES),
                                default=r.status)
        if not new:
            return
        try:
            data.set_return_status(r.return_id, new)
        except ValidationError as e:
            messagebox.showerror("Census / ILR", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        r = self._selected()
        if not r:
            return
        if not messagebox.askyesno(
                "Census / ILR",
                f"Delete return #{r.return_id}?",
                parent=self.frame):
            return
        data.delete_return(r.return_id)
        self.refresh()


class AimsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Aims")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Return id:").pack(side="left")
        self.f_rid = ttk.Entry(bar, width=8)
        self.f_rid.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Learner:").pack(side="left")
        self.f_ref = ttk.Entry(bar, width=12)
        self.f_ref.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Aim type:").pack(side="left")
        self.f_at = ttk.Combobox(
            bar, values=("",) + AIM_TYPES,
            state="readonly", width=18)
        self.f_at.current(0)
        self.f_at.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Funding:").pack(side="left")
        self.f_fm = ttk.Combobox(
            bar, values=("",) + FUNDING_MODELS,
            state="readonly", width=24)
        self.f_fm.current(0)
        self.f_fm.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(
            bar, values=("",) + LEARNER_AIM_STATUSES,
            state="readonly", width=18)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left",
                                                 padx=4)
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left",
                                              padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True,
                            padx=8, pady=4)
        cols = ("id", "return", "learner", "name", "ref",
                "title", "model", "start", "planned_end",
                "status", "hours", "value")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "return": 60, "learner": 90,
                   "name": 130, "ref": 100, "title": 200,
                   "model": 200, "start": 90,
                   "planned_end": 90, "status": 130,
                   "hours": 60, "value": 80}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "return",
                                                  "hours")
                                       else "e"
                                       if c == "value"
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _AIM_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.bind("<Double-Button-1>",
                         lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("Edit",    self._edit),
                ("Delete",  self._delete),
                ("Refresh", self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_rid.get().strip().isdigit():
            f["return_id"] = int(self.f_rid.get().strip())
        if self.f_ref.get().strip():
            f["learner_ref"] = self.f_ref.get().strip()
        if self.f_at.get():
            f["aim_type"] = self.f_at.get()
        if self.f_fm.get():
            f["funding_model"] = self.f_fm.get()
        if self.f_status.get():
            f["status"] = self.f_status.get()
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        rows = data.list_aims(**self._filters())
        for a in rows:
            self.tree.insert(
                "", "end", iid=str(a.aim_id),
                values=(a.aim_id, a.return_id or "—",
                         a.learner_ref, a.learner_name or "—",
                         a.aim_reference, a.aim_title or "—",
                         a.funding_model, a.start_date,
                         a.planned_end_date or "—",
                         a.status, a.planned_hours or 0,
                         f"£{a.funding_band_value or 0:,.0f}"),
                tags=(a.status,))
        self.count.config(text=f"{len(rows)} aim(s)")

    def _selected(self) -> LearnerAim | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Census / ILR",
                                  "Select an aim first.",
                                  parent=self.frame)
            return None
        return data.get_aim(int(sel[0]))

    def _new(self) -> None:
        if AimEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        a = self._selected()
        if a and AimEditor(
                self.frame, aim=a).result is not None:
            self.refresh()

    def _delete(self) -> None:
        a = self._selected()
        if not a:
            return
        if not messagebox.askyesno(
                "Census / ILR",
                f"Delete aim #{a.aim_id}?",
                parent=self.frame):
            return
        data.delete_aim(a.aim_id)
        self.refresh()


class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8,
                          pady=(4, 8))
        self.refresh()

    def refresh(self) -> None:
        s = data.summary()
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", "Census / ILR Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total returns        : {s.total_returns}\n"
                            f"Planned              : {s.planned}\n"
                            f"In progress          : {s.in_progress}\n"
                            f"Submitted            : {s.submitted}\n"
                            f"Accepted             : {s.accepted}\n"
                            f"Rejected             : {s.rejected}\n"
                            f"Overdue              : {s.overdue}\n"
                            f"Open windows         : {s.open_windows}\n\n"
                            f"Total aims           : {s.total_aims}\n"
                            f"Distinct learners    : {s.distinct_learners}\n"
                            f"Continuing           : {s.continuing_aims}\n"
                            f"Completed            : {s.completed_aims}\n"
                            f"Achieved             : {s.achieved_aims}\n"
                            f"Withdrawn            : {s.withdrawn_aims}\n"
                            f"Total planned hours  : {s.total_planned_hours}\n"
                            f"Total funding value  : £{s.total_funding_value:,.2f}\n\n")
        self.text.insert("end", "By return type:\n")
        for k in RETURN_TYPES:
            n = s.by_return_type.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<32}: {n}\n")
        self.text.insert("end", "\nBy return status:\n")
        for k in RETURN_STATUSES:
            n = s.by_return_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.insert("end", "\nBy funding model:\n")
        for k in FUNDING_MODELS:
            n = s.by_funding_model.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<36}: {n}\n")
        self.text.insert("end", "\nBy aim status:\n")
        for k in LEARNER_AIM_STATUSES:
            n = s.by_aim_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.config(state="disabled")


# ── Editors ──────────────────────────────────────────────

class ReturnEditor:
    def __init__(self, parent, *,
                 return_obj: CensusReturn | None = None
                 ) -> None:
        self.return_obj = return_obj
        self.result: CensusReturn | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Edit return #{return_obj.return_id}"
            if return_obj else "New return")
        self.win.geometry("820x680")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if return_obj:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)
        self.vars: dict[str, tk.Variable] = {}
        self.texts: dict[str, tk.Text] = {}

        def entry(row, col, label, key, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w",
                padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(body, textvariable=v, width=width).grid(
                row=row, column=col + 1, sticky="ew",
                padx=4, pady=2)

        def combo(row, col, label, key, values, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w",
                padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Combobox(body, textvariable=v, values=values,
                          state="readonly", width=width).grid(
                row=row, column=col + 1, sticky="ew",
                padx=4, pady=2)

        combo(0, 0, "Return type*", "return_type",
                 RETURN_TYPES)
        entry(0, 2, "Academic year*", "academic_year")
        entry(1, 0, "Reference date", "reference_date")
        combo(1, 2, "Status*", "status", RETURN_STATUSES)
        entry(2, 0, "Window opens", "window_opens")
        entry(2, 2, "Window closes", "window_closes")
        entry(3, 0, "Submission deadline",
                 "submission_deadline")
        entry(3, 2, "Submitted on", "submitted_on")
        entry(4, 0, "Submitted by", "submitted_by")
        entry(4, 2, "Accepted on", "accepted_on")
        entry(5, 0, "Learner count", "learner_count")
        entry(5, 2, "Error count", "error_count")
        entry(6, 0, "Warning count", "warning_count")
        entry(6, 2, "File ref", "file_ref")

        ttk.Label(body, text="Notes").grid(
            row=7, column=0, sticky="nw",
            padx=4, pady=(6, 2))
        t = tk.Text(body, height=6, width=72, wrap="word")
        t.grid(row=7, column=1, columnspan=3, sticky="ew",
                  padx=4, pady=(6, 2))
        self.texts["notes"] = t

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right",
                                               padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")

        self.vars["return_type"].set(DEFAULT_RETURN_TYPE)
        self.vars["status"].set(DEFAULT_RETURN_STATUS)
        for k in ("learner_count", "error_count",
                   "warning_count"):
            self.vars[k].set("0")

    def _load(self) -> None:
        r = self.return_obj
        assert r is not None
        for key in ("return_type", "academic_year",
                     "reference_date", "window_opens",
                     "window_closes", "submission_deadline",
                     "status", "submitted_on",
                     "submitted_by", "accepted_on",
                     "file_ref"):
            self.vars[key].set(getattr(r, key) or "")
        self.vars["learner_count"].set(str(r.learner_count))
        self.vars["error_count"].set(str(r.error_count))
        self.vars["warning_count"].set(str(r.warning_count))
        self.texts["notes"].delete("1.0", "end")
        self.texts["notes"].insert("1.0", r.notes or "")

    def _save(self) -> None:
        payload: dict = {}
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        try:
            if self.return_obj:
                self.result = data.update_return(
                    self.return_obj.return_id, payload)
            else:
                self.result = data.create_return(payload)
        except ValidationError as exc:
            messagebox.showerror("Census / ILR", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class AimEditor:
    def __init__(self, parent, *,
                 aim: LearnerAim | None = None) -> None:
        self.aim = aim
        self.result: LearnerAim | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Edit aim #{aim.aim_id}"
            if aim else "New aim")
        self.win.geometry("880x780")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if aim:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)
        self.vars: dict[str, tk.Variable] = {}
        self.texts: dict[str, tk.Text] = {}

        def entry(row, col, label, key, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w",
                padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(body, textvariable=v, width=width).grid(
                row=row, column=col + 1, sticky="ew",
                padx=4, pady=2)

        def combo(row, col, label, key, values, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w",
                padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Combobox(body, textvariable=v, values=values,
                          state="readonly", width=width).grid(
                row=row, column=col + 1, sticky="ew",
                padx=4, pady=2)

        entry(0, 0, "Return id", "return_id")
        entry(0, 2, "Learner ref*", "learner_ref")
        entry(1, 0, "Learner name", "learner_name")
        entry(1, 2, "ULN", "uln")
        entry(2, 0, "UKPRN", "ukprn")
        entry(2, 2, "Partner UKPRN", "partner_ukprn")
        combo(3, 0, "Aim type*", "aim_type", AIM_TYPES)
        entry(3, 2, "Aim reference*", "aim_reference")
        entry(4, 0, "Aim title", "aim_title", width=48)
        combo(5, 0, "Funding model*", "funding_model",
                 FUNDING_MODELS)
        combo(5, 2, "Status*", "status",
                 LEARNER_AIM_STATUSES)
        entry(6, 0, "Start date*", "start_date")
        entry(6, 2, "Planned end date", "planned_end_date")
        entry(7, 0, "Actual end date", "actual_end_date")
        entry(7, 2, "Completion code (1/2/3/6/7/10)",
                 "completion_code")
        entry(8, 0, "Outcome code", "outcome_code")
        entry(8, 2, "Planned hours", "planned_hours")
        entry(9, 0, "Actual hours", "actual_hours")
        entry(9, 2, "Funding band value (£)",
                 "funding_band_value")
        entry(10, 0, "Delivery location",
                  "delivery_location", width=48)

        ttk.Label(body, text="Notes").grid(
            row=11, column=0, sticky="nw",
            padx=4, pady=(6, 2))
        t = tk.Text(body, height=4, width=72, wrap="word")
        t.grid(row=11, column=1, columnspan=3, sticky="ew",
                  padx=4, pady=(6, 2))
        self.texts["notes"] = t

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right",
                                               padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")

        self.vars["aim_type"].set(DEFAULT_AIM_TYPE)
        self.vars["funding_model"].set(
            DEFAULT_FUNDING_MODEL)
        self.vars["status"].set(DEFAULT_LEARNER_AIM_STATUS)

    def _load(self) -> None:
        a = self.aim
        assert a is not None
        self.vars["return_id"].set(str(a.return_id or ""))
        for key in ("learner_ref", "learner_name", "ukprn",
                     "uln", "aim_type", "aim_reference",
                     "aim_title", "funding_model",
                     "start_date", "planned_end_date",
                     "actual_end_date", "outcome_code",
                     "status", "delivery_location",
                     "partner_ukprn"):
            self.vars[key].set(getattr(a, key) or "")
        self.vars["completion_code"].set(
            str(a.completion_code or ""))
        self.vars["planned_hours"].set(
            str(a.planned_hours or ""))
        self.vars["actual_hours"].set(
            str(a.actual_hours or ""))
        self.vars["funding_band_value"].set(
            str(a.funding_band_value or ""))
        self.texts["notes"].delete("1.0", "end")
        self.texts["notes"].insert("1.0", a.notes or "")

    def _save(self) -> None:
        payload: dict = {}
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        try:
            if self.aim:
                self.result = data.update_aim(
                    self.aim.aim_id, payload)
            else:
                self.result = data.create_aim(payload)
        except ValidationError as exc:
            messagebox.showerror("Census / ILR", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


def _prompt_text(parent, title: str, *,
                  initial: str = "") -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("420x140")
    win.transient(parent); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(value=initial)
    ttk.Entry(win, textvariable=var).pack(fill="x", padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = var.get().strip()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="right",
                                                    padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


def _prompt_choice(parent, title: str, options: list[str], *,
                    default: str | None = None) -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("360x140")
    win.transient(parent); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(
        value=default or (options[0] if options else ""))
    ttk.Combobox(win, textvariable=var, values=options,
                  state="readonly").pack(fill="x", padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = var.get()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="right",
                                                    padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


__all__ = ["open_census_ilr_window"]
