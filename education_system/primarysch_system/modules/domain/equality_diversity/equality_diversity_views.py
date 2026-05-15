"""Tkinter views for Sixth Form Equality & Diversity."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from education_system.shared import branding
from education_system.primarysch_system.modules.domain.equality_diversity import (
    equality_diversity as data,
)
from education_system.primarysch_system.modules.domain.equality_diversity.equality_diversity import (
    DEFAULT_CHARACTERISTIC,
    DEFAULT_INCIDENT_TYPE,
    DEFAULT_STATUS,
    DEFAULT_SUBJECT_ROLE,
    EDIncident,
    INCIDENT_TYPES,
    PROTECTED_CHARACTERISTICS,
    SEVERITIES,
    STATUSES,
    SUBJECT_ROLES,
    ValidationError,
    severity_label,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STATUS_TAGS = {
    "Reported":            ("#fff7e6", "#7a5800"),
    "Under Investigation": ("#fff0d6", "#7a5800"),
    "Substantiated":       ("#ffd1d1", "#8c0d0d"),
    "Unsubstantiated":     ("#e6e6ff", "#3a3a8c"),
    "Actions Set":         ("#e6f0ff", "#1a3f8c"),
    "Resolved":            ("#e6f7e6", "#0d6b2a"),
    "Closed":              ("#eeeeee", "#444444"),
}


def open_equality_diversity_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Equality & Diversity — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    EDTab(nb, scope="open",          label="Open")
    EDTab(nb, scope="substantiated", label="Substantiated")
    EDTab(nb, scope="escalated",     label="Escalated")
    EDTab(nb, scope="all",           label="All")
    SummaryTab(nb)


class EDTab:
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
        self.f_type = ttk.Combobox(bar,
                                     values=("",) + INCIDENT_TYPES,
                                     state="readonly", width=22)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Characteristic:").pack(side="left")
        self.f_char = ttk.Combobox(bar,
                                     values=("",) + PROTECTED_CHARACTERISTICS,
                                     state="readonly", width=24)
        self.f_char.current(0)
        self.f_char.pack(side="left", padx=(2, 8))
        if self.scope == "all":
            ttk.Label(bar, text="Status:").pack(side="left")
            self.f_status = ttk.Combobox(bar,
                                           values=("",) + STATUSES,
                                           state="readonly", width=18)
            self.f_status.current(0)
            self.f_status.pack(side="left", padx=(2, 8))
        else:
            self.f_status = None
        ttk.Label(bar, text="Min sev:").pack(side="left")
        self.f_sev = ttk.Combobox(bar,
                                     values=("",) + tuple(str(s)
                                                            for s in SEVERITIES),
                                     state="readonly", width=4)
        self.f_sev.current(0)
        self.f_sev.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Reporter:").pack(side="left")
        self.f_rep = ttk.Entry(bar, width=12)
        self.f_rep.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left",
                                                  padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "date", "type", "characteristic",
                "severity", "reporter", "subject",
                "status", "flags")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "date": 90, "type": 170,
                   "characteristic": 200, "severity": 100,
                   "reporter": 130, "subject": 130,
                   "status": 150, "flags": 140}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "severity")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _STATUS_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.tag_configure("critical", background="#ffb0b0",
                                  foreground="#6c0000")
        self.tree.bind("<Double-Button-1>", lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("View / Edit",     self._edit),
                ("Investigate",     self._investigate),
                ("Record outcome",  self._outcome),
                ("Set actions",     self._actions),
                ("Resolve",         self._resolve),
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
        self.f_type.current(0)
        self.f_char.current(0)
        self.f_sev.current(0)
        self.f_rep.delete(0, "end")
        if self.f_status is not None:
            self.f_status.current(0)
        self.refresh()

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_type.get():
            f["incident_type"] = self.f_type.get()
        if self.f_char.get():
            f["characteristic"] = self.f_char.get()
        if self.f_sev.get():
            f["severity_min"] = int(self.f_sev.get())
        if self.f_rep.get().strip():
            f["reporter_like"] = self.f_rep.get().strip()
        if self.f_status is not None and self.f_status.get():
            f["status"] = self.f_status.get()
        if self.scope == "open":
            f["open_only"] = True
        elif self.scope == "substantiated":
            f["substantiated_only"] = True
        elif self.scope == "escalated":
            f["escalated_only"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.list_incidents(**self._filters())
        except ValidationError as e:
            messagebox.showerror("E&D", str(e),
                                    parent=self.frame)
            return
        for i in rows:
            flags = []
            if i.anonymous:
                flags.append("ANON")
            if i.escalated_to_head:
                flags.append("HEAD")
            if i.escalated_to_dsl:
                flags.append("DSL")
            if i.governors_informed:
                flags.append("GOV")
            tag = ("critical" if i.severity >= 4
                     else i.status)
            self.tree.insert(
                "", "end", iid=str(i.incident_id),
                values=(i.incident_id, i.incident_date,
                         i.incident_type,
                         i.protected_characteristic,
                         f"{i.severity} {severity_label(i.severity)[:3]}",
                         i.reporter,
                         i.subject_name or "—",
                         i.status, ",".join(flags)),
                tags=(tag,))
        self.count.config(text=f"{len(rows)} incident(s)")

    def _selected(self) -> EDIncident | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("E&D",
                                  "Select an incident first.",
                                  parent=self.frame)
            return None
        return data.get_incident(int(sel[0]))

    def _new(self) -> None:
        if EDEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        i = self._selected()
        if i and EDEditor(self.frame,
                              incident=i).result is not None:
            self.refresh()

    def _investigate(self) -> None:
        i = self._selected()
        if not i:
            return
        by = _prompt_text(self.frame, "Investigator",
                            initial=i.investigated_by or "")
        if not by:
            return
        try:
            data.start_investigation(i.incident_id,
                                           investigated_by=by)
        except ValidationError as exc:
            messagebox.showerror("E&D", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _outcome(self) -> None:
        i = self._selected()
        if not i:
            return
        if OutcomeDialog(self.frame,
                              incident=i).result is not None:
            self.refresh()

    def _actions(self) -> None:
        i = self._selected()
        if not i:
            return
        if ActionsDialog(self.frame,
                              incident=i).result is not None:
            self.refresh()

    def _resolve(self) -> None:
        i = self._selected()
        if not i:
            return
        try:
            data.resolve(i.incident_id)
        except ValidationError as exc:
            messagebox.showerror("E&D", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _close(self) -> None:
        i = self._selected()
        if not i:
            return
        try:
            data.close_incident(i.incident_id)
        except ValidationError as exc:
            messagebox.showerror("E&D", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _set_status(self) -> None:
        i = self._selected()
        if not i:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(STATUSES), default=i.status)
        if not new:
            return
        try:
            data.set_status(i.incident_id, new)
        except ValidationError as exc:
            messagebox.showerror("E&D", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        i = self._selected()
        if not i:
            return
        if not messagebox.askyesno(
                "E&D", f"Delete incident #{i.incident_id}?",
                parent=self.frame):
            return
        data.delete_incident(i.incident_id)
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
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.refresh()

    def refresh(self) -> None:
        s = data.summary()
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end",
                            "Equality & Diversity Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total                : {s.total}\n"
                            f"Open                 : {s.open_count}\n"
                            f"Serious / Critical   : {s.serious_or_critical}\n"
                            f"Substantiated        : {s.substantiated}\n"
                            f"Awaiting action      : {s.awaiting_action}\n"
                            f"Governors informed   : {s.governors_informed}\n\n")
        self.text.insert("end", "By type:\n")
        for k in INCIDENT_TYPES:
            n = s.by_type.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<24}: {n}\n")
        self.text.insert("end", "\nBy protected characteristic:\n")
        for k in PROTECTED_CHARACTERISTICS:
            n = s.by_characteristic.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<30}: {n}\n")
        self.text.insert("end", "\nBy severity:\n")
        for sev in SEVERITIES:
            n = s.by_severity.get(sev, 0)
            if n:
                self.text.insert("end",
                                    f"  {sev}  {severity_label(sev):<12}: {n}\n")
        self.text.insert("end", "\nBy status:\n")
        for k in STATUSES:
            n = s.by_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.config(state="disabled")


# ── Editor ────────────────────────────────────────────────────────

class EDEditor:
    def __init__(self, parent, *,
                 incident: EDIncident | None = None) -> None:
        self.incident = incident
        self.result: EDIncident | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit incident #{incident.incident_id}"
                          if incident else "New E&D incident")
        self.win.geometry("860x880")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if incident:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)
        self.vars: dict[str, tk.Variable] = {}
        self.texts: dict[str, tk.Text] = {}
        self.bools: dict[str, tk.BooleanVar] = {}

        def entry(row, col, label, key, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(body, textvariable=v, width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        def combo(row, col, label, key, values, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Combobox(body, textvariable=v, values=values,
                          state="readonly", width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        entry(0, 0, "Date*", "incident_date")
        entry(0, 2, "Time (HH:MM)", "incident_time")
        entry(1, 0, "Reported on", "reported_on")
        entry(1, 2, "Reporter*", "reporter")
        combo(2, 0, "Reporter role*", "reporter_role",
                 SUBJECT_ROLES)
        combo(2, 2, "Subject role*", "subject_role", SUBJECT_ROLES)
        entry(3, 0, "Subject name", "subject_name")
        entry(3, 2, "Alleged perpetrator", "alleged_perpetrator")
        combo(4, 0, "Perpetrator role*", "perpetrator_role",
                 SUBJECT_ROLES)
        combo(4, 2, "Incident type*", "incident_type",
                 INCIDENT_TYPES)
        combo(5, 0, "Characteristic*", "protected_characteristic",
                 PROTECTED_CHARACTERISTICS)
        combo(5, 2, "Severity*", "severity",
                 ("1", "2", "3", "4", "5"))
        entry(6, 0, "Location", "location")
        combo(6, 2, "Status*", "status", STATUSES)
        entry(7, 0, "Investigated by", "investigated_by")
        entry(7, 2, "Closed on", "closed_on")

        flags = ttk.LabelFrame(body, text="Flags")
        flags.grid(row=8, column=0, columnspan=4,
                     sticky="ew", padx=4, pady=(8, 4))
        for col, (key, label) in enumerate((
                ("anonymous",            "Anonymous"),
                ("training_required",    "Training required"),
                ("complainant_informed", "Complainant informed"),
                ("perpetrator_informed", "Perpetrator informed"),
        )):
            v = tk.BooleanVar()
            self.bools[key] = v
            ttk.Checkbutton(flags, text=label,
                             variable=v).grid(
                row=0, column=col, sticky="w", padx=6, pady=4)
        for col, (key, label) in enumerate((
                ("escalated_to_head",  "Escalated to Head"),
                ("escalated_to_dsl",   "Escalated to DSL"),
                ("governors_informed", "Governors informed"),
        )):
            v = tk.BooleanVar()
            self.bools[key] = v
            ttk.Checkbutton(flags, text=label,
                             variable=v).grid(
                row=1, column=col, sticky="w", padx=6, pady=4)

        row = 9
        for key, label in (
                ("description",         "Description"),
                ("witnesses",           "Witnesses"),
                ("investigation_notes", "Investigation notes"),
                ("outcome",             "Outcome"),
                ("actions_taken",       "Actions taken"),
                ("notes",               "Notes"),
        ):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="nw", padx=4, pady=(6, 2))
            t = tk.Text(body, height=2, width=74, wrap="word")
            t.grid(row=row, column=1, columnspan=3,
                     sticky="ew", padx=4, pady=(6, 2))
            self.texts[key] = t
            row += 1

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")

        now = _dt.datetime.now()
        self.vars["incident_date"].set(
            _dt.date.today().isoformat())
        self.vars["incident_time"].set(now.strftime("%H:%M"))
        self.vars["reported_on"].set(
            _dt.date.today().isoformat())
        self.vars["reporter_role"].set("Staff")
        self.vars["subject_role"].set(DEFAULT_SUBJECT_ROLE)
        self.vars["perpetrator_role"].set(DEFAULT_SUBJECT_ROLE)
        self.vars["incident_type"].set(DEFAULT_INCIDENT_TYPE)
        self.vars["protected_characteristic"].set(
            DEFAULT_CHARACTERISTIC)
        self.vars["severity"].set("2")
        self.vars["status"].set(DEFAULT_STATUS)

    def _load(self) -> None:
        i = self.incident
        assert i is not None
        for key in ("incident_date", "incident_time",
                     "reported_on", "reporter", "reporter_role",
                     "subject_name", "subject_role",
                     "alleged_perpetrator", "perpetrator_role",
                     "incident_type",
                     "protected_characteristic",
                     "location", "investigated_by",
                     "status", "closed_on"):
            self.vars[key].set(getattr(i, key) or "")
        self.vars["severity"].set(str(i.severity))
        for k in self.bools:
            self.bools[k].set(getattr(i, k))
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(i, k) or "")

    def _save(self) -> None:
        payload: dict = {}
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        for k, b in self.bools.items():
            payload[k] = b.get()
        try:
            if self.incident:
                self.result = data.update_incident(
                    self.incident.incident_id, payload)
            else:
                self.result = data.create_incident(payload)
        except ValidationError as exc:
            messagebox.showerror("E&D", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class OutcomeDialog:
    def __init__(self, parent, *, incident: EDIncident) -> None:
        self.incident = incident
        self.result: EDIncident | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Record outcome — #{incident.incident_id}")
        self.win.geometry("540x420")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        self.substantiated = tk.BooleanVar(value=True)
        ttk.Checkbutton(body, text="Substantiated",
                         variable=self.substantiated).grid(
            row=0, column=0, columnspan=2, sticky="w",
            padx=4, pady=4)
        ttk.Label(body, text="Outcome*").grid(
            row=1, column=0, sticky="nw", padx=4, pady=4)
        self.outcome = tk.Text(body, height=4, width=50,
                                  wrap="word")
        self.outcome.insert("1.0", incident.outcome or "")
        self.outcome.grid(row=1, column=1, sticky="ew",
                            padx=4, pady=4)
        ttk.Label(body, text="Investigation notes").grid(
            row=2, column=0, sticky="nw", padx=4, pady=4)
        self.notes = tk.Text(body, height=6, width=50,
                                wrap="word")
        self.notes.insert("1.0", incident.investigation_notes or "")
        self.notes.grid(row=2, column=1, sticky="ew",
                          padx=4, pady=4)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        try:
            self.result = data.record_outcome(
                self.incident.incident_id,
                substantiated=self.substantiated.get(),
                outcome=self.outcome.get("1.0", "end").rstrip(),
                investigation_notes=self.notes.get(
                    "1.0", "end").rstrip() or None)
        except ValidationError as exc:
            messagebox.showerror("E&D", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class ActionsDialog:
    def __init__(self, parent, *, incident: EDIncident) -> None:
        self.incident = incident
        self.result: EDIncident | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Set actions — #{incident.incident_id}")
        self.win.geometry("520x360")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Actions taken*").grid(
            row=0, column=0, sticky="nw", padx=4, pady=4)
        self.actions = tk.Text(body, height=8, width=48,
                                  wrap="word")
        self.actions.insert("1.0", incident.actions_taken or "")
        self.actions.grid(row=0, column=1, sticky="ew",
                            padx=4, pady=4)
        self.training = tk.BooleanVar(
            value=incident.training_required)
        ttk.Checkbutton(body, text="Training required",
                         variable=self.training).grid(
            row=1, column=0, columnspan=2, sticky="w",
            padx=4, pady=4)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        try:
            self.result = data.set_actions(
                self.incident.incident_id,
                actions_taken=self.actions.get(
                    "1.0", "end").rstrip(),
                training_required=self.training.get())
        except ValidationError as exc:
            messagebox.showerror("E&D", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


# ── Helpers ────────────────────────────────────────────────────────

def _prompt_text(parent, title: str, *,
                  initial: str = "") -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("360x140")
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
    ttk.Button(bar, text="OK", command=ok).pack(side="right", padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


def _prompt_choice(parent, title: str, options: list[str], *,
                    default: str | None = None) -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("320x140")
    win.transient(parent); win.after_idle(win.grab_set)
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


__all__ = ["open_equality_diversity_window"]
