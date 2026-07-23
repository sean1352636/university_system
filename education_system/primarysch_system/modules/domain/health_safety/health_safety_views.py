"""Tkinter views for Primary School Health & Safety register."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any
from education_system.shared import branding
from education_system.primarysch_system.modules.domain.health_safety import (
    health_safety as data,
)
from education_system.primarysch_system.modules.domain.health_safety.health_safety import (
    ACTION_PRIORITIES,
    ACTION_STATUSES,
    AFFECTED_PARTIES,
    CATEGORIES,
    DEFAULT_ACTION_PRIORITY,
    DEFAULT_ACTION_STATUS,
    DEFAULT_CATEGORY,
    DEFAULT_INCIDENT_TYPE,
    DEFAULT_SEVERITY,
    DEFAULT_STATUS,
    INCIDENT_TYPES,
    SEVERITIES,
    STATUSES,
    Action,
    Incident,
    ValidationError,
)
from education_system.primarysch_system.modules.domain.staff import (
    staff as staff_data,
)
from education_system.primarysch_system.modules.domain import _pupils_bridge as student_data

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STATUS_TAGS = {
    "Open":            ("#fff7e6", "#7a5800"),
    "Investigating":   ("#e6f0ff", "#1a3f8c"),
    "Actions Pending": ("#fff0d6", "#7a5800"),
    "Resolved":        ("#e6f7e6", "#0d6b2a"),
    "Closed":          ("#eeeeee", "#444444"),
    "Reopened":        ("#ffd1d1", "#8c0d0d"),
}

_SEVERITY_TAGS = {
    "Major":        ("#ffe1c4", "#7a3500"),
    "Catastrophic": ("#ffb0b0", "#6c0000"),
}


def open_health_safety_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Health & Safety — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)
    HSPanel(win)


def _staff_options() -> list[tuple[str, str]]:
    try:
        rows = sorted(staff_data.list_staff(),
                        key=lambda s: s.staff_id)
    except Exception:
        rows = []
    return [(s.staff_id,
              f"{s.staff_id} — {getattr(s, 'full_name', '')}")
            for s in rows]


def _student_options() -> list[tuple[str, str]]:
    try:
        rows = sorted(student_data.list_students(),
                        key=lambda s: s.student_id)
    except Exception:
        rows = []
    return [(s.student_id,
              f"{s.student_id} — {getattr(s, 'full_name', '')}")
            for s in rows]


# ── Main panel ─────────────────────────────────────────────────────

class HSPanel:
    def __init__(self, win: tk.Toplevel) -> None:
        self.win = win
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(
            bar, values=("",) + STATUSES,
            state="readonly", width=16)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Severity:").pack(side="left")
        self.f_severity = ttk.Combobox(
            bar, values=("",) + SEVERITIES,
            state="readonly", width=12)
        self.f_severity.current(0)
        self.f_severity.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Category:").pack(side="left")
        self.f_category = ttk.Combobox(
            bar, values=("",) + CATEGORIES,
            state="readonly", width=20)
        self.f_category.current(0)
        self.f_category.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="From:").pack(side="left")
        self.f_from = ttk.Entry(bar, width=11)
        self.f_from.pack(side="left", padx=(2, 6))
        ttk.Label(bar, text="To:").pack(side="left")
        self.f_to = ttk.Entry(bar, width=11)
        self.f_to.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Search:").pack(side="left")
        self.f_search = ttk.Entry(bar, width=18)
        self.f_search.pack(side="left", padx=(2, 8))

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")

        # Table
        table_frame = ttk.Frame(self.win)
        table_frame.pack(fill="both", expand=True, padx=10, pady=4)
        cols = ("id", "date", "location", "category", "severity",
                 "status", "affected", "actions")
        self.tree = ttk.Treeview(
            table_frame, columns=cols, show="headings",
            selectmode="browse")
        widths = {"id": 50, "date": 100, "location": 180,
                   "category": 180, "severity": 110,
                   "status": 130, "affected": 220, "actions": 80}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "actions")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _STATUS_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        for sev, (bg, fg) in _SEVERITY_TAGS.items():
            self.tree.tag_configure(f"sev:{sev}", background=bg,
                                       foreground=fg)
        self.tree.bind("<Double-Button-1>",
                          lambda _e: self._view_detail())

        # Action bar
        bbar = ttk.Frame(self.win)
        bbar.pack(fill="x", padx=10, pady=(4, 10))
        for label, cmd in (
                ("Refresh",         self.refresh),
                ("New Incident",    self._new),
                ("Edit",            self._edit),
                ("View Detail",     self._view_detail),
                ("Set Status",      self._set_status),
                ("Delete",          self._delete),
                ("Manage Actions",  self._manage_actions),
                ("Summary",         self._summary),
        ):
            ttk.Button(bbar, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(bbar, text="")
        self.count.pack(side="right")

    def _clear(self) -> None:
        for w in (self.f_status, self.f_severity, self.f_category):
            w.current(0)
        for w in (self.f_from, self.f_to, self.f_search):
            w.delete(0, "end")
        self.refresh()

    def _filters(self) -> dict[str, Any]:
        f: dict[str, Any] = {}
        if self.f_status.get():
            f["status"] = self.f_status.get()
        if self.f_severity.get():
            f["severity"] = self.f_severity.get()
        if self.f_category.get():
            f["category"] = self.f_category.get()
        if self.f_from.get().strip():
            f["date_from"] = self.f_from.get().strip()
        if self.f_to.get().strip():
            f["date_to"] = self.f_to.get().strip()
        if self.f_search.get().strip():
            f["search"] = self.f_search.get().strip()
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            views = data.list_views(**self._filters())
        except ValidationError as exc:
            messagebox.showerror("Health & Safety", str(exc),
                                    parent=self.win)
            return
        for v in views:
            i = v.incident
            tags: list[str] = [i.status]
            if i.severity in _SEVERITY_TAGS:
                tags.append(f"sev:{i.severity}")
            self.tree.insert(
                "", "end", iid=str(i.incident_id),
                values=(i.incident_id, i.incident_date,
                         i.location, i.category, i.severity,
                         i.status, v.affected_display or "—",
                         v.actions_count),
                tags=tuple(tags))
        self.count.config(text=f"{len(views)} incident(s)")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Health & Safety",
                                  "Select an incident first.",
                                  parent=self.win)
            return None
        return int(sel[0])

    def _new(self) -> None:
        if IncidentEditor(self.win).result is not None:
            self.refresh()

    def _edit(self) -> None:
        iid = self._selected_id()
        if iid is None:
            return
        inc = data.get_incident(iid)
        if inc is None:
            return
        if IncidentEditor(self.win,
                              incident=inc).result is not None:
            self.refresh()

    def _view_detail(self) -> None:
        iid = self._selected_id()
        if iid is None:
            return
        IncidentDetail(self.win, incident_id=iid,
                          on_change=self.refresh)

    def _set_status(self) -> None:
        iid = self._selected_id()
        if iid is None:
            return
        inc = data.get_incident(iid)
        if inc is None:
            return
        new = _prompt_choice(self.win, "New status",
                                list(STATUSES), default=inc.status)
        if not new:
            return
        try:
            data.set_status(iid, new)
        except ValidationError as exc:
            messagebox.showerror("Health & Safety", str(exc),
                                    parent=self.win)
            return
        self.refresh()

    def _delete(self) -> None:
        iid = self._selected_id()
        if iid is None:
            return
        if not messagebox.askyesno(
                "Health & Safety",
                f"Delete incident #{iid} and all its actions?",
                parent=self.win):
            return
        data.delete_incident(iid)
        self.refresh()

    def _manage_actions(self) -> None:
        iid = self._selected_id()
        if iid is None:
            return
        IncidentDetail(self.win, incident_id=iid,
                          on_change=self.refresh,
                          focus_actions=True)

    def _summary(self) -> None:
        SummaryDialog(self.win)


# ── Incident editor ───────────────────────────────────────────────

class IncidentEditor:
    def __init__(self, parent, *,
                 incident: Incident | None = None) -> None:
        self.incident = incident
        self.result: Incident | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Edit incident #{incident.incident_id}"
            if incident else "New H&S incident")
        self.win.geometry("880x820")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._student_opts = _student_options()
        self._staff_opts = _staff_options()
        self._build()
        if incident:
            self._load()
        else:
            self._set_defaults()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)
        self.vars: dict[str, tk.Variable] = {}
        self.bools: dict[str, tk.BooleanVar] = {}
        self.texts: dict[str, tk.Text] = {}

        def entry(row, col, label, key, width=20):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(body, textvariable=v, width=width).grid(
                row=row, column=col + 1, sticky="ew",
                padx=4, pady=2)

        def combo(row, col, label, key, values,
                    width=20, readonly=True):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            cb = ttk.Combobox(body, textvariable=v, values=values,
                                 state="readonly" if readonly else "normal",
                                 width=width)
            cb.grid(row=row, column=col + 1, sticky="ew",
                       padx=4, pady=2)
            return cb

        entry(0, 0, "Date*", "incident_date")
        entry(0, 2, "Time (HH:MM)", "incident_time")
        entry(1, 0, "Location*", "location")
        combo(1, 2, "Type*", "incident_type",
                INCIDENT_TYPES)
        combo(2, 0, "Category*", "category", CATEGORIES)
        combo(2, 2, "Severity*", "severity", SEVERITIES)

        # Affected
        af_frame = ttk.LabelFrame(body, text="Affected party")
        af_frame.grid(row=3, column=0, columnspan=4,
                          sticky="ew", padx=4, pady=(8, 4))
        af_frame.grid_columnconfigure(1, weight=1)
        af_frame.grid_columnconfigure(3, weight=1)
        ttk.Label(af_frame, text="Party:").grid(
            row=0, column=0, sticky="w", padx=4, pady=2)
        self.vars["affected_party"] = tk.StringVar()
        ttk.Combobox(af_frame,
                          textvariable=self.vars["affected_party"],
                          values=("",) + AFFECTED_PARTIES,
                          state="readonly", width=18).grid(
            row=0, column=1, sticky="w", padx=4, pady=2)
        ttk.Label(af_frame, text="Student:").grid(
            row=0, column=2, sticky="w", padx=4, pady=2)
        self.student_combo = ttk.Combobox(
            af_frame, state="readonly", width=32,
            values=[""] + [lbl for _, lbl in self._student_opts])
        self.student_combo.grid(row=0, column=3, sticky="ew",
                                    padx=4, pady=2)
        ttk.Label(af_frame, text="Staff:").grid(
            row=1, column=0, sticky="w", padx=4, pady=2)
        self.aff_staff_combo = ttk.Combobox(
            af_frame, state="readonly", width=32,
            values=[""] + [lbl for _, lbl in self._staff_opts])
        self.aff_staff_combo.grid(row=1, column=1, sticky="ew",
                                        padx=4, pady=2)
        ttk.Label(af_frame, text="Name (free text):").grid(
            row=1, column=2, sticky="w", padx=4, pady=2)
        self.vars["affected_name"] = tk.StringVar()
        ttk.Entry(af_frame,
                    textvariable=self.vars["affected_name"]).grid(
            row=1, column=3, sticky="ew", padx=4, pady=2)

        # Reporter/Assessor
        ttk.Label(body, text="Reported by:").grid(
            row=4, column=0, sticky="w", padx=4, pady=2)
        self.reporter_combo = ttk.Combobox(
            body, state="readonly", width=32,
            values=[""] + [lbl for _, lbl in self._staff_opts])
        self.reporter_combo.grid(row=4, column=1, sticky="ew",
                                       padx=4, pady=2)
        ttk.Label(body, text="Assessor:").grid(
            row=4, column=2, sticky="w", padx=4, pady=2)
        self.assessor_combo = ttk.Combobox(
            body, state="readonly", width=32,
            values=[""] + [lbl for _, lbl in self._staff_opts])
        self.assessor_combo.grid(row=4, column=3, sticky="ew",
                                       padx=4, pady=2)

        combo(5, 0, "Status*", "status", STATUSES)
        entry(5, 2, "Review due", "review_due")

        # Flags
        flags = ttk.LabelFrame(body, text="Flags")
        flags.grid(row=6, column=0, columnspan=4,
                      sticky="ew", padx=4, pady=(8, 4))
        for col, (key, label) in enumerate((
                ("riddor_reportable", "RIDDOR reportable"),
                ("parent_informed",   "Parent informed"),
                ("hse_notified",      "HSE notified"),
        )):
            v = tk.BooleanVar()
            self.bools[key] = v
            ttk.Checkbutton(flags, text=label, variable=v).grid(
                row=0, column=col, sticky="w", padx=6, pady=4)

        entry(7, 0, "RIDDOR ref", "riddor_reference")
        entry(7, 2, "RIDDOR reported on",
                 "riddor_reported_on")

        # Text fields
        row = 8
        for key, label in (
                ("description",      "Description*"),
                ("immediate_action", "Immediate action"),
                ("root_cause",       "Root cause"),
                ("lessons_learned",  "Lessons learned"),
                ("notes",            "Notes"),
        ):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="nw", padx=4, pady=(6, 2))
            t = tk.Text(body, height=2, width=80, wrap="word")
            t.grid(row=row, column=1, columnspan=3,
                     sticky="ew", padx=4, pady=(6, 2))
            self.texts[key] = t
            row += 1

        # Buttons
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")

    def _set_defaults(self) -> None:
        now = _dt.datetime.now()
        self.vars["incident_date"].set(
            _dt.date.today().isoformat())
        self.vars["incident_time"].set(now.strftime("%H:%M"))
        self.vars["category"].set(DEFAULT_CATEGORY)
        self.vars["severity"].set(DEFAULT_SEVERITY)
        self.vars["incident_type"].set(DEFAULT_INCIDENT_TYPE)
        self.vars["status"].set(DEFAULT_STATUS)

    def _load(self) -> None:
        i = self.incident
        assert i is not None
        for key in ("incident_date", "incident_time", "location",
                     "category", "severity", "incident_type",
                     "status", "review_due", "riddor_reference",
                     "riddor_reported_on", "affected_name"):
            self.vars[key].set(getattr(i, key) or "")
        self.vars["affected_party"].set(i.affected_party or "")
        for k in self.bools:
            self.bools[k].set(getattr(i, k))
        for k, t in self.texts.items():
            t.delete("1.0", "end")
            t.insert("1.0", getattr(i, k) or "")
        if i.affected_student_id:
            for idx, (sid, _) in enumerate(self._student_opts):
                if sid == i.affected_student_id:
                    self.student_combo.current(idx + 1)
                    break
        if i.affected_staff_id:
            for idx, (sid, _) in enumerate(self._staff_opts):
                if sid == i.affected_staff_id:
                    self.aff_staff_combo.current(idx + 1)
                    break
        if i.reported_by:
            for idx, (sid, _) in enumerate(self._staff_opts):
                if sid == i.reported_by:
                    self.reporter_combo.current(idx + 1)
                    break
        if i.assessor_id:
            for idx, (sid, _) in enumerate(self._staff_opts):
                if sid == i.assessor_id:
                    self.assessor_combo.current(idx + 1)
                    break

    def _combo_id(self, combo: ttk.Combobox,
                     opts: list[tuple[str, str]]) -> str | None:
        idx = combo.current()
        if idx <= 0:
            return None
        return opts[idx - 1][0]

    def _save(self) -> None:
        payload: dict[str, Any] = {}
        for k, v in self.vars.items():
            payload[k] = v.get().strip() if isinstance(
                v, tk.StringVar) else v.get()
        for k, b in self.bools.items():
            payload[k] = b.get()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        payload["affected_student_id"] = self._combo_id(
            self.student_combo, self._student_opts)
        payload["affected_staff_id"] = self._combo_id(
            self.aff_staff_combo, self._staff_opts)
        payload["reported_by"] = self._combo_id(
            self.reporter_combo, self._staff_opts)
        payload["assessor_id"] = self._combo_id(
            self.assessor_combo, self._staff_opts)
        if not payload.get("affected_party"):
            payload["affected_party"] = None
        try:
            if self.incident:
                self.result = data.update_incident(
                    self.incident.incident_id, payload)
            else:
                self.result = data.create_incident(payload)
        except ValidationError as exc:
            messagebox.showerror("Health & Safety", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


# ── Incident detail ────────────────────────────────────────────────

class IncidentDetail:
    def __init__(self, parent, *, incident_id: int,
                 on_change=None,
                 focus_actions: bool = False) -> None:
        self.incident_id = incident_id
        self.on_change = on_change
        self.win = tk.Toplevel(parent)
        self.win.title(f"Incident #{incident_id} — detail")
        self.win.geometry("960x760")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()
        self.refresh()
        if focus_actions:
            self.actions_frame.focus_set()

    def _build(self) -> None:
        # Top: incident summary text
        self.summary = tk.Text(self.win, height=18, wrap="word",
                                  font=("TkDefaultFont", 10))
        self.summary.pack(fill="x", padx=10, pady=(10, 4))
        self.summary.config(state="disabled")

        # Actions section
        self.actions_frame = ttk.LabelFrame(
            self.win, text="Corrective actions")
        self.actions_frame.pack(fill="both", expand=True,
                                       padx=10, pady=4)
        cols = ("id", "action", "owner", "due", "priority",
                 "status", "completed")
        self.tree = ttk.Treeview(
            self.actions_frame, columns=cols, show="headings",
            selectmode="browse", height=8)
        widths = {"id": 50, "action": 320, "owner": 130,
                   "due": 100, "priority": 90, "status": 110,
                   "completed": 100}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "due",
                                                  "completed",
                                                  "priority")
                                       else "w"))
        vsb = ttk.Scrollbar(self.actions_frame,
                                orient="vertical",
                                command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True,
                          padx=(4, 0), pady=4)
        vsb.pack(side="right", fill="y", pady=4)
        self.tree.tag_configure("overdue", background="#ffd1d1",
                                  foreground="#8c0d0d")
        self.tree.tag_configure("done", background="#eeeeee",
                                  foreground="#555555")
        self.tree.bind("<Double-Button-1>",
                          lambda _e: self._edit_action())

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=10, pady=(4, 10))
        ttk.Button(bar, text="Add action",
                    command=self._add_action).pack(
            side="left", padx=4)
        ttk.Button(bar, text="Edit action",
                    command=self._edit_action).pack(
            side="left", padx=4)
        ttk.Button(bar, text="Complete",
                    command=self._complete_action).pack(
            side="left", padx=4)
        ttk.Button(bar, text="Delete action",
                    command=self._delete_action).pack(
            side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="Close",
                    command=self.win.destroy).pack(side="right")

    def refresh(self) -> None:
        v = data.view_incident(self.incident_id)
        if v is None:
            self.win.destroy()
            return
        i = v.incident
        self.summary.config(state="normal")
        self.summary.delete("1.0", "end")
        lines = [
            f"#{i.incident_id}    [{i.status}]",
            f"Date / time   : {i.incident_date}  "
            f"{i.incident_time or '—'}",
            f"Location      : {i.location}",
            f"Category      : {i.category}    "
            f"Severity: {i.severity}    "
            f"Type: {i.incident_type}",
            f"Affected      : {v.affected_display or '—'}",
            f"Reported by   : {v.reporter_name or '—'}    "
            f"Assessor: {v.assessor_name or '—'}",
            "RIDDOR        : "
            + ("reportable" if i.riddor_reportable else "no")
            + (f"; ref {i.riddor_reference}"
                if i.riddor_reference else "")
            + (f"; on {i.riddor_reported_on}"
                if i.riddor_reported_on else ""),
            f"Parent informed: "
            f"{'yes' if i.parent_informed else 'no'}    "
            f"HSE notified: "
            f"{'yes' if i.hse_notified else 'no'}",
            f"Review due    : {i.review_due or '—'}",
            "",
            "Description:",
            *(f"  {ln}" for ln in (i.description or "").splitlines()),
        ]
        if i.immediate_action:
            lines.append("")
            lines.append("Immediate action:")
            for ln in i.immediate_action.splitlines():
                lines.append(f"  {ln}")
        if i.root_cause:
            lines.append("")
            lines.append(f"Root cause: {i.root_cause}")
        if i.lessons_learned:
            lines.append(f"Lessons learned: {i.lessons_learned}")
        if i.notes:
            lines.append(f"Notes: {i.notes}")
        self.summary.insert("1.0", "\n".join(lines))
        self.summary.config(state="disabled")

        for iid in self.tree.get_children():
            self.tree.delete(iid)
        for a in v.open_actions + v.completed_actions:
            tag = ("done"
                       if a.status in ("Completed", "Cancelled")
                       else ("overdue" if a.is_overdue else ""))
            owner = a.owner_id or "—"
            self.tree.insert(
                "", "end", iid=str(a.action_id),
                values=(a.action_id, a.action, owner,
                         a.due_date or "—", a.priority,
                         a.status, a.completed_on or "—"),
                tags=(tag,) if tag else ())
        if self.on_change:
            self.on_change()

    def _selected_action(self) -> Action | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Health & Safety",
                                  "Select an action first.",
                                  parent=self.win)
            return None
        return data.get_action(int(sel[0]))

    def _add_action(self) -> None:
        if ActionEditor(
                self.win,
                incident_id=self.incident_id).result is not None:
            self.refresh()

    def _edit_action(self) -> None:
        a = self._selected_action()
        if a is None:
            return
        if ActionEditor(self.win,
                            incident_id=self.incident_id,
                            action=a).result is not None:
            self.refresh()

    def _complete_action(self) -> None:
        a = self._selected_action()
        if a is None:
            return
        when = _prompt_text(
            self.win, "Completed on (YYYY-MM-DD)",
            initial=_dt.date.today().isoformat())
        if not when:
            return
        try:
            data.complete_action(a.action_id, completed_on=when)
        except ValidationError as exc:
            messagebox.showerror("Health & Safety", str(exc),
                                    parent=self.win)
            return
        self.refresh()

    def _delete_action(self) -> None:
        a = self._selected_action()
        if a is None:
            return
        if not messagebox.askyesno(
                "Health & Safety",
                f"Delete action #{a.action_id}?",
                parent=self.win):
            return
        data.delete_action(a.action_id)
        self.refresh()


# ── Action editor ──────────────────────────────────────────────────

class ActionEditor:
    def __init__(self, parent, *, incident_id: int,
                 action: Action | None = None) -> None:
        self.incident_id = incident_id
        self.action = action
        self.result: Action | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Edit action #{action.action_id}"
            if action else "New action")
        self.win.geometry("620x420")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._staff_opts = _staff_options()
        self._build()
        if action:
            self._load()
        else:
            self.vars["status"].set(DEFAULT_ACTION_STATUS)
            self.vars["priority"].set(DEFAULT_ACTION_PRIORITY)
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        self.vars: dict[str, tk.StringVar] = {}

        ttk.Label(body, text="Action*").grid(
            row=0, column=0, sticky="nw", padx=4, pady=4)
        self.action_text = tk.Text(body, height=3, width=60,
                                          wrap="word")
        self.action_text.grid(row=0, column=1, sticky="ew",
                                    padx=4, pady=4)

        ttk.Label(body, text="Owner").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.owner_combo = ttk.Combobox(
            body, state="readonly", width=40,
            values=[""] + [lbl for _, lbl in self._staff_opts])
        self.owner_combo.grid(row=1, column=1, sticky="ew",
                                    padx=4, pady=4)

        def entry(row, label, key):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="w", padx=4, pady=4)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(body, textvariable=v, width=24).grid(
                row=row, column=1, sticky="w", padx=4, pady=4)

        def combo(row, label, key, values):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="w", padx=4, pady=4)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Combobox(body, textvariable=v, values=values,
                          state="readonly", width=22).grid(
                row=row, column=1, sticky="w", padx=4, pady=4)

        entry(2, "Due date (YYYY-MM-DD)", "due_date")
        combo(3, "Priority", "priority", ACTION_PRIORITIES)
        combo(4, "Status", "status", ACTION_STATUSES)
        entry(5, "Completed on (YYYY-MM-DD)", "completed_on")

        ttk.Label(body, text="Notes").grid(
            row=6, column=0, sticky="nw", padx=4, pady=4)
        self.notes_text = tk.Text(body, height=3, width=60,
                                         wrap="word")
        self.notes_text.grid(row=6, column=1, sticky="ew",
                                   padx=4, pady=4)

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")

    def _load(self) -> None:
        a = self.action
        assert a is not None
        self.action_text.delete("1.0", "end")
        self.action_text.insert("1.0", a.action)
        self.notes_text.delete("1.0", "end")
        self.notes_text.insert("1.0", a.notes or "")
        for key in ("due_date", "completed_on",
                     "status", "priority"):
            self.vars[key].set(getattr(a, key) or "")
        if a.owner_id:
            for idx, (sid, _) in enumerate(self._staff_opts):
                if sid == a.owner_id:
                    self.owner_combo.current(idx + 1)
                    break

    def _save(self) -> None:
        owner = None
        idx = self.owner_combo.current()
        if idx > 0:
            owner = self._staff_opts[idx - 1][0]
        payload: dict[str, Any] = {
            "action": self.action_text.get("1.0", "end").rstrip(),
            "owner_id": owner,
            "due_date": self.vars["due_date"].get().strip() or None,
            "completed_on": self.vars["completed_on"].get().strip()
                or None,
            "status": self.vars["status"].get()
                or DEFAULT_ACTION_STATUS,
            "priority": self.vars["priority"].get()
                or DEFAULT_ACTION_PRIORITY,
            "notes": self.notes_text.get("1.0", "end").rstrip()
                or None,
        }
        try:
            if self.action:
                self.result = data.update_action(
                    self.action.action_id, payload)
            else:
                self.result = data.add_action(
                    self.incident_id, payload)
        except ValidationError as exc:
            messagebox.showerror("Health & Safety", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


# ── Summary dialog ─────────────────────────────────────────────────

class SummaryDialog:
    def __init__(self, parent) -> None:
        self.win = tk.Toplevel(parent)
        self.win.title("Health & Safety summary")
        self.win.geometry("520x560")
        self.win.transient(parent)
        self.text = tk.Text(self.win, wrap="word",
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=10, pady=10)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Close",
                    command=self.win.destroy).pack(side="right")
        self.refresh()

    def refresh(self) -> None:
        s = data.summary()
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", "Health & Safety Summary\n")
        self.text.insert("end", "=" * 50 + "\n\n")
        self.text.insert("end",
                            f"Total incidents      : {s.total}\n"
                            f"Open incidents       : "
                            f"{s.open_incidents}\n"
                            f"RIDDOR-reportable    : "
                            f"{s.riddor_reportable}\n"
                            f"Open actions         : "
                            f"{s.open_actions}\n"
                            f"Overdue actions      : "
                            f"{s.overdue_actions}\n\n")
        self.text.insert("end", "By status:\n")
        for k in STATUSES:
            n = s.by_status.get(k, 0)
            if n:
                self.text.insert("end",
                                    f"  {k:<18}: {n}\n")
        self.text.insert("end", "\nBy severity:\n")
        for k in SEVERITIES:
            n = s.by_severity.get(k, 0)
            if n:
                self.text.insert("end",
                                    f"  {k:<14}: {n}\n")
        self.text.insert("end", "\nBy category:\n")
        for k in CATEGORIES:
            n = s.by_category.get(k, 0)
            if n:
                self.text.insert("end",
                                    f"  {k:<22}: {n}\n")
        self.text.insert("end", "\nBy type:\n")
        for k in INCIDENT_TYPES:
            n = s.by_type.get(k, 0)
            if n:
                self.text.insert("end",
                                    f"  {k:<14}: {n}\n")
        self.text.config(state="disabled")


# ── Helpers ────────────────────────────────────────────────────────

def _prompt_text(parent, title: str, *,
                  initial: str = "") -> str | None:
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry("360x140")
    win.transient(parent)
    win.after_idle(win.grab_set)
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
    win.title(title)
    win.geometry("320x140")
    win.transient(parent)
    win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(value=default
                            or (options[0] if options else ""))
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


__all__ = ["open_health_safety_window"]
