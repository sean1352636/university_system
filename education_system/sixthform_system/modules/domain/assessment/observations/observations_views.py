"""Tkinter views for Sixth Form Observations."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable
from education_system.shared import branding
from education_system.sixthform_system.modules.domain.assessment.observations import (
    observations as data,
)
from education_system.sixthform_system.modules.domain.assessment.observations.observations import (
    DEFAULT_FOCUS_AREA,
    DEFAULT_OBSERVATION_TYPE,
    DEFAULT_STATUS,
    FOCUS_AREAS,
    JUDGEMENTS,
    OBSERVATION_TYPES,
    Observation,
    STATUSES,
    ValidationError,
    YEAR_GROUPS,
    judgement_label,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STATUS_TAGS = {
    "Draft":           ("#fff7e6", "#7a5800"),
    "Submitted":       ("#e6f0ff", "#1a3f8c"),
    "Discussed":       ("#e6f7e6", "#0d6b2a"),
    "Acknowledged":    ("#e6f7e6", "#0d6b2a"),
    "Action Required": ("#ffe6e6", "#8c0d0d"),
    "Closed":          ("#eeeeee", "#444444"),
}


def open_observations_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Observations — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    ObservationsTab(nb, scope="open",     label="Open")
    ObservationsTab(nb, scope="overdue",  label="Overdue Follow-Up")
    ObservationsTab(nb, scope="all",      label="All Observations")
    PerTeacherTab(nb)
    SummaryTab(nb)


# ══ Observations table tab ════════════════════════════════════════

class ObservationsTab:
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
        ttk.Label(bar, text="Observer:").pack(side="left")
        self.f_observer = ttk.Entry(bar, width=14)
        self.f_observer.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Teacher:").pack(side="left")
        self.f_teacher = ttk.Entry(bar, width=14)
        self.f_teacher.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = ttk.Combobox(bar,
                                     values=("",) + OBSERVATION_TYPES,
                                     state="readonly", width=14)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Focus:").pack(side="left")
        self.f_focus = ttk.Combobox(bar, values=("",) + FOCUS_AREAS,
                                      state="readonly", width=20)
        self.f_focus.current(0)
        self.f_focus.pack(side="left", padx=(2, 8))

        if self.scope == "all":
            ttk.Label(bar, text="Status:").pack(side="left")
            self.f_status = ttk.Combobox(bar,
                                           values=("",) + STATUSES,
                                           state="readonly", width=14)
            self.f_status.current(0)
            self.f_status.pack(side="left", padx=(2, 8))
        else:
            self.f_status = None

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left",
                                                  padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "date", "observer", "teacher", "type",
                "focus", "judgement", "status", "follow_up")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings", selectmode="browse")
        widths = {"id": 60, "date": 90, "observer": 130,
                   "teacher": 130, "type": 110, "focus": 170,
                   "judgement": 90, "status": 110, "follow_up": 140}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor="w" if c not in ("id",
                                                       "judgement")
                              else "center")
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _STATUS_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.tag_configure("overdue", background="#ffd1d1",
                                  foreground="#8c0d0d")
        self.tree.bind("<Double-Button-1>", lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("View / Edit",     self._edit),
                ("Share",           self._share),
                ("Record response", self._response),
                ("Close",           self._close),
                ("Change status",   self._set_status),
                ("Delete",          self._delete),
                ("Refresh",         self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _clear(self) -> None:
        for entry in (self.f_observer, self.f_teacher):
            entry.delete(0, "end")
        self.f_type.current(0)
        self.f_focus.current(0)
        if self.f_status is not None:
            self.f_status.current(0)
        self.refresh()

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_observer.get().strip():
            f["observer_like"] = self.f_observer.get().strip()
        if self.f_teacher.get().strip():
            f["teacher_like"] = self.f_teacher.get().strip()
        if self.f_type.get():
            f["observation_type"] = self.f_type.get()
        if self.f_focus.get():
            f["focus_area"] = self.f_focus.get()
        if self.f_status is not None and self.f_status.get():
            f["status"] = self.f_status.get()
        if self.scope == "open":
            f["open_only"] = True
        elif self.scope == "overdue":
            f["follow_up_overdue"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.list_observations(**self._filters())
        except ValidationError as e:
            messagebox.showerror("Observations", str(e),
                                    parent=self.frame)
            return
        for o in rows:
            fu = ("—")
            if o.follow_up_required:
                fu = (f"due {o.follow_up_due or '—'}"
                       if o.follow_up_due else "yes")
                if o.follow_up_overdue:
                    fu = f"OVERDUE ({o.follow_up_due})"
            jval = (f"{o.judgement} {judgement_label(o.judgement)[:3]}"
                     if o.judgement else "—")
            tag = "overdue" if o.follow_up_overdue else o.status
            self.tree.insert("", "end",
                              iid=str(o.observation_id),
                              values=(o.observation_id,
                                       o.observation_date,
                                       o.observer,
                                       o.observed_teacher,
                                       o.observation_type,
                                       o.focus_area or "—",
                                       jval, o.status, fu),
                              tags=(tag,))
        self.count.config(text=f"{len(rows)} observation(s)")

    def _selected(self) -> Observation | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Observations",
                                  "Select an observation first.",
                                  parent=self.frame)
            return None
        return data.get_observation(int(sel[0]))

    def _new(self) -> None:
        if ObservationEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        o = self._selected()
        if not o:
            return
        if ObservationEditor(self.frame, observation=o).result is not None:
            self.refresh()

    def _share(self) -> None:
        o = self._selected()
        if not o:
            return
        try:
            data.share(o.observation_id)
        except ValidationError as e:
            messagebox.showerror("Observations", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _response(self) -> None:
        o = self._selected()
        if not o:
            return
        resp = _prompt_multiline(self.frame, "Teacher response",
                                    initial=o.teacher_response or "")
        if resp is None:
            return
        try:
            data.record_teacher_response(o.observation_id,
                                              response=resp)
        except ValidationError as e:
            messagebox.showerror("Observations", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _close(self) -> None:
        o = self._selected()
        if not o:
            return
        try:
            data.close_observation(o.observation_id)
        except ValidationError as e:
            messagebox.showerror("Observations", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _set_status(self) -> None:
        o = self._selected()
        if not o:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(STATUSES), default=o.status)
        if not new:
            return
        try:
            data.set_status(o.observation_id, new)
        except ValidationError as e:
            messagebox.showerror("Observations", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        o = self._selected()
        if not o:
            return
        if not messagebox.askyesno("Observations",
                                       f"Delete observation #{o.observation_id}?",
                                       parent=self.frame):
            return
        data.delete_observation(o.observation_id)
        self.refresh()


# ══ Per-teacher tab ═══════════════════════════════════════════════

class PerTeacherTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Per Teacher")
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Teacher:").pack(side="left")
        self.entry = ttk.Entry(bar, width=24)
        self.entry.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Show",
                    command=self._show).pack(side="left")

        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.text.config(state="disabled")

    def _show(self) -> None:
        teacher = self.entry.get().strip()
        if not teacher:
            return
        rows = data.observations_for_teacher(teacher)
        summ = data.teacher_summary(teacher)
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end",
                            f"Observations for {teacher}\n"
                            f"{'=' * 60}\n\n"
                            f"Total            : {summ.total}\n"
                            f"Average judgement: "
                            f"{summ.average_judgement if summ.average_judgement is not None else '—'}\n"
                            f"Most recent      : {summ.most_recent or '—'}\n\n"
                            f"By judgement:\n")
        for j in JUDGEMENTS:
            n = summ.by_judgement.get(j, 0)
            if n:
                self.text.insert("end",
                                    f"  {j}  {judgement_label(j):<24}: {n}\n")
        self.text.insert("end", f"\n{'-' * 60}\nObservations:\n\n")
        for o in rows:
            self.text.insert("end",
                                f"#{o.observation_id}  "
                                f"{o.observation_date}  "
                                f"{o.observation_type}  "
                                f"J={o.judgement or '—'}  "
                                f"[{o.status}]\n")
            if o.focus_area:
                self.text.insert("end",
                                    f"   Focus: {o.focus_area}\n")
            if o.strengths:
                self.text.insert("end",
                                    f"   + {o.strengths.splitlines()[0]}\n")
            if o.areas_to_develop:
                self.text.insert("end",
                                    f"   - {o.areas_to_develop.splitlines()[0]}\n")
            self.text.insert("end", "\n")
        self.text.config(state="disabled")


# ══ Summary tab ═══════════════════════════════════════════════════

class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.text.config(state="disabled")

    def refresh(self) -> None:
        s = data.summary()
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", "Observations Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total                 : {s.total}\n"
                            f"Open                  : {s.open_count}\n"
                            f"Follow-ups open       : {s.follow_up_open}\n"
                            f"Follow-ups overdue    : {s.follow_up_overdue}\n"
                            f"Average judgement     : "
                            f"{s.average_judgement if s.average_judgement is not None else '—'}\n"
                            f"Distinct observers    : {s.distinct_observers}\n"
                            f"Distinct teachers     : {s.distinct_teachers}\n\n")
        self.text.insert("end", "By status:\n")
        for k in STATUSES:
            n = s.by_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.insert("end", "\nBy type:\n")
        for k in OBSERVATION_TYPES:
            n = s.by_type.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<18}: {n}\n")
        self.text.insert("end", "\nBy judgement:\n")
        for j in JUDGEMENTS:
            n = s.by_judgement.get(j, 0)
            if n:
                self.text.insert("end",
                                    f"  {j}  {judgement_label(j):<24}: {n}\n")
        if s.by_focus:
            self.text.insert("end", "\nBy focus area:\n")
            for f, n in s.by_focus.items():
                self.text.insert("end", f"  {f:<24}: {n}\n")
        self.text.config(state="disabled")


# ══ Editor dialog ═════════════════════════════════════════════════

class ObservationEditor:
    def __init__(self, parent, *,
                 observation: Observation | None = None) -> None:
        self.observation = observation
        self.result: Observation | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Edit observation #{observation.observation_id}"
            if observation else "New observation")
        self.win.geometry("760x720")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()
        if observation:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)

        self.vars: dict[str, tk.Variable] = {}
        self.texts: dict[str, tk.Text] = {}

        def label_entry(row, col, label, key, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(body, textvariable=v, width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        def label_combo(row, col, label, key, values, width=20):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Combobox(body, textvariable=v,
                          values=values, state="readonly",
                          width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        label_entry(0, 0, "Observer*", "observer")
        label_entry(0, 2, "Observed teacher*", "observed_teacher")
        label_entry(1, 0, "Date* (YYYY-MM-DD)", "observation_date")
        label_entry(1, 2, "Time (HH:MM)", "observation_time")
        label_entry(2, 0, "Duration (mins)", "duration_minutes")
        label_combo(2, 2, "Type*", "observation_type",
                       OBSERVATION_TYPES)
        label_combo(3, 0, "Focus area", "focus_area",
                       ("",) + FOCUS_AREAS)
        label_entry(3, 2, "Subject", "subject_name")
        label_entry(4, 0, "Class group id", "class_group_id")
        label_entry(4, 2, "Class group label", "class_group_label")
        label_combo(5, 0, "Year group", "year_group",
                       ("",) + YEAR_GROUPS)
        label_entry(5, 2, "Room", "room")
        label_combo(6, 0, "Judgement (1-4)", "judgement",
                       ("",) + tuple(str(j) for j in JUDGEMENTS))
        label_combo(6, 2, "Status*", "status", STATUSES)

        # Follow-up panel
        fu = ttk.LabelFrame(body, text="Follow-up")
        fu.grid(row=7, column=0, columnspan=4, sticky="ew",
                 padx=4, pady=(8, 4))
        fu.grid_columnconfigure(1, weight=1)
        fu.grid_columnconfigure(3, weight=1)
        self.fu_required = tk.BooleanVar()
        ttk.Checkbutton(fu, text="Required",
                         variable=self.fu_required).grid(
            row=0, column=0, sticky="w", padx=4)
        self.vars["follow_up_due"] = tk.StringVar()
        ttk.Label(fu, text="Due (YYYY-MM-DD)").grid(
            row=0, column=1, sticky="e", padx=4)
        ttk.Entry(fu, textvariable=self.vars["follow_up_due"],
                    width=14).grid(row=0, column=2, sticky="w",
                                      padx=4)
        self.vars["follow_up_by"] = tk.StringVar()
        ttk.Label(fu, text="By").grid(row=0, column=3,
                                          sticky="e", padx=4)
        ttk.Entry(fu, textvariable=self.vars["follow_up_by"],
                    width=20).grid(row=0, column=4, sticky="w",
                                      padx=4)
        self.shared = tk.BooleanVar()
        ttk.Checkbutton(fu, text="Shared with teacher",
                         variable=self.shared).grid(
            row=0, column=5, sticky="w", padx=4)

        # Text areas
        row = 8
        for key, label in (
                ("strengths",          "Strengths"),
                ("areas_to_develop",   "Areas to develop"),
                ("student_engagement", "Student engagement"),
                ("student_progress",   "Student progress"),
                ("teacher_response",   "Teacher response"),
                ("notes",              "Notes"),
        ):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="nw", padx=4, pady=(8, 2))
            t = tk.Text(body, height=3, width=60, wrap="word")
            t.grid(row=row, column=1, columnspan=3,
                     sticky="ew", padx=4, pady=(8, 2))
            self.texts[key] = t
            row += 1

        actions = ttk.Frame(self.win)
        actions.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(actions, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(actions, text="Cancel",
                    command=self.win.destroy).pack(side="right")

        # Defaults
        self.vars["observation_date"].set(_dt.date.today().isoformat())
        self.vars["observation_type"].set(DEFAULT_OBSERVATION_TYPE)
        self.vars["focus_area"].set(DEFAULT_FOCUS_AREA)
        self.vars["status"].set(DEFAULT_STATUS)
        self.vars["duration_minutes"].set("30")

    def _load(self) -> None:
        o = self.observation
        assert o is not None
        for key in ("observer", "observed_teacher", "observation_date",
                     "observation_time", "subject_name",
                     "class_group_label", "year_group", "room",
                     "observation_type", "focus_area", "status",
                     "follow_up_due", "follow_up_by"):
            val = getattr(o, key) or ""
            self.vars[key].set(str(val))
        self.vars["duration_minutes"].set(
            str(o.duration_minutes) if o.duration_minutes is not None
            else "")
        self.vars["class_group_id"].set(
            str(o.class_group_id) if o.class_group_id else "")
        self.vars["judgement"].set(
            str(o.judgement) if o.judgement is not None else "")
        self.fu_required.set(o.follow_up_required)
        self.shared.set(o.shared_with_teacher)
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(o, k) or "")

    def _save(self) -> None:
        payload: dict = {}
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        payload["follow_up_required"] = self.fu_required.get()
        payload["shared_with_teacher"] = self.shared.get()
        try:
            if self.observation:
                self.result = data.update_observation(
                    self.observation.observation_id, payload)
            else:
                self.result = data.create_observation(payload)
        except ValidationError as e:
            messagebox.showerror("Observations", str(e),
                                    parent=self.win)
            return
        self.win.destroy()


# ── Small helpers ─────────────────────────────────────────────────

def _prompt_multiline(parent, title: str, *,
                       initial: str = "") -> str | None:
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry("520x300")
    win.transient(parent)
    win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=6)
    txt = tk.Text(win, wrap="word", height=10)
    txt.pack(fill="both", expand=True, padx=8, pady=4)
    txt.insert("1.0", initial)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = txt.get("1.0", "end").rstrip()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=6)
    ttk.Button(bar, text="OK", command=ok).pack(side="right",
                                                     padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


def _prompt_choice(parent, title: str, options: list[str], *,
                    default: str | None = None) -> str | None:
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry("320x140")
    win.transient(parent)
    win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(value=default or (options[0] if options else ""))
    ttk.Combobox(win, textvariable=var, values=options,
                  state="readonly").pack(fill="x", padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = var.get()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="right", padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


__all__ = ["open_observations_window"]
