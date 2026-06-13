"""Tkinter views for Sixth Form Emergency Incidents."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from education_system.shared import branding
from education_system.sixthform_system.modules.domain.pastoral.emergency import (
    emergency as data,
)
from education_system.sixthform_system.modules.domain.pastoral.emergency.emergency import (
    DEFAULT_EMERGENCY_TYPE,
    DEFAULT_STATUS,
    EMERGENCY_TYPES,
    Emergency,
    SEVERITIES,
    STATUSES,
    ValidationError,
    severity_label,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STATUS_TAGS = {
    "Reported":   ("#ffd1d1", "#8c0d0d"),
    "Responding": ("#fff0d6", "#7a5800"),
    "Resolved":   ("#e6f0ff", "#1a3f8c"),
    "Debriefed":  ("#e6f7e6", "#0d6b2a"),
    "Closed":     ("#eeeeee", "#444444"),
}


def open_emergency_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Emergency — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    EmergencyTab(nb, scope="open",      label="Open")
    EmergencyTab(nb, scope="debrief",   label="Awaiting Debrief")
    EmergencyTab(nb, scope="services",  label="Services Called")
    EmergencyTab(nb, scope="evacuation", label="Evacuations")
    EmergencyTab(nb, scope="lockdown",  label="Lockdowns")
    EmergencyTab(nb, scope="all",       label="All")
    SummaryTab(nb)


class EmergencyTab:
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
                                     values=("",) + EMERGENCY_TYPES,
                                     state="readonly", width=22)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))
        if self.scope == "all":
            ttk.Label(bar, text="Status:").pack(side="left")
            self.f_status = ttk.Combobox(bar,
                                           values=("",) + STATUSES,
                                           state="readonly", width=14)
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
        ttk.Label(bar, text="Reported by:").pack(side="left")
        self.f_rep = ttk.Entry(bar, width=14)
        self.f_rep.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Location:").pack(side="left")
        self.f_loc = ttk.Entry(bar, width=14)
        self.f_loc.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left",
                                                  padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "date", "time", "type", "severity",
                "title", "reported_by", "status", "flags")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "date": 90, "time": 60,
                   "type": 180, "severity": 100,
                   "title": 240, "reported_by": 130,
                   "status": 120, "flags": 140}
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
                ("Append log",      self._append_log),
                ("Start response",  self._start),
                ("Resolve",         self._resolve),
                ("Record debrief",  self._debrief),
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
        self.f_sev.current(0)
        self.f_rep.delete(0, "end")
        self.f_loc.delete(0, "end")
        if self.f_status is not None:
            self.f_status.current(0)
        self.refresh()

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_type.get():
            f["incident_type"] = self.f_type.get()
        if self.f_sev.get():
            f["severity_min"] = int(self.f_sev.get())
        if self.f_rep.get().strip():
            f["reported_by_like"] = self.f_rep.get().strip()
        if self.f_loc.get().strip():
            f["location_like"] = self.f_loc.get().strip()
        if self.f_status is not None and self.f_status.get():
            f["status"] = self.f_status.get()
        if self.scope == "open":
            f["open_only"] = True
        elif self.scope == "debrief":
            f["awaiting_debrief"] = True
        elif self.scope == "services":
            f["services_only"] = True
        elif self.scope == "evacuation":
            f["evacuation_only"] = True
        elif self.scope == "lockdown":
            f["lockdown_only"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.list_incidents(**self._filters())
        except ValidationError as e:
            messagebox.showerror("Emergency", str(e),
                                    parent=self.frame)
            return
        for e in rows:
            flags = []
            if e.evacuation:
                flags.append("EVAC")
            if e.lockdown:
                flags.append("LOCK")
            if e.police_called:
                flags.append("POL")
            if e.fire_called:
                flags.append("FIRE")
            if e.ambulance_called:
                flags.append("AMB")
            tag = ("critical" if e.severity >= 4
                     else e.status)
            self.tree.insert(
                "", "end", iid=str(e.incident_id),
                values=(e.incident_id, e.incident_date,
                         e.incident_time or "—",
                         e.incident_type,
                         f"{e.severity} {severity_label(e.severity)[:3]}",
                         e.title, e.reported_by,
                         e.status, ",".join(flags)),
                tags=(tag,))
        self.count.config(text=f"{len(rows)} incident(s)")

    def _selected(self) -> Emergency | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Emergency",
                                  "Select an incident first.",
                                  parent=self.frame)
            return None
        return data.get_incident(int(sel[0]))

    def _new(self) -> None:
        if EmergencyEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        e = self._selected()
        if e and EmergencyEditor(self.frame,
                                       incident=e).result is not None:
            self.refresh()

    def _append_log(self) -> None:
        e = self._selected()
        if not e:
            return
        entry = _prompt_multiline(self.frame, "Log entry")
        if not entry:
            return
        try:
            data.append_log(e.incident_id, entry=entry)
        except ValidationError as exc:
            messagebox.showerror("Emergency", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _start(self) -> None:
        e = self._selected()
        if not e:
            return
        lead = _prompt_text(self.frame,
                              "Lead responder (optional)",
                              initial=e.lead_responder or "")
        if lead is None:
            return
        try:
            data.start_response(e.incident_id,
                                      lead_responder=lead or None)
        except ValidationError as exc:
            messagebox.showerror("Emergency", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _resolve(self) -> None:
        e = self._selected()
        if not e:
            return
        if ResolveDialog(self.frame,
                            incident=e).result is not None:
            self.refresh()

    def _debrief(self) -> None:
        e = self._selected()
        if not e:
            return
        if DebriefDialog(self.frame,
                              incident=e).result is not None:
            self.refresh()

    def _close(self) -> None:
        e = self._selected()
        if not e:
            return
        try:
            data.close_incident(e.incident_id)
        except ValidationError as exc:
            messagebox.showerror("Emergency", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _set_status(self) -> None:
        e = self._selected()
        if not e:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(STATUSES), default=e.status)
        if not new:
            return
        try:
            data.set_status(e.incident_id, new)
        except ValidationError as exc:
            messagebox.showerror("Emergency", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        e = self._selected()
        if not e:
            return
        if not messagebox.askyesno(
                "Emergency", f"Delete incident #{e.incident_id}?",
                parent=self.frame):
            return
        data.delete_incident(e.incident_id)
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
        self.text.insert("end", "Emergency Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total                : {s.total}\n"
                            f"Open                 : {s.open_count}\n"
                            f"Major / Critical     : {s.major_or_critical}\n"
                            f"Services called      : {s.services_called}\n"
                            f"Evacuations          : {s.evacuations}\n"
                            f"Lockdowns            : {s.lockdowns}\n"
                            f"Drills               : {s.drills}\n"
                            f"Awaiting debrief     : {s.awaiting_debrief}\n"
                            f"Average severity     : "
                            f"{s.average_severity if s.average_severity is not None else '—'}\n\n")
        self.text.insert("end", "By type:\n")
        for k in EMERGENCY_TYPES:
            n = s.by_type.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.insert("end", "\nBy severity:\n")
        for sev in SEVERITIES:
            n = s.by_severity.get(sev, 0)
            if n:
                self.text.insert("end",
                                    f"  {sev}  {severity_label(sev):<14}: {n}\n")
        self.text.insert("end", "\nBy status:\n")
        for k in STATUSES:
            n = s.by_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.config(state="disabled")


# ── Editor ────────────────────────────────────────────────────────

class EmergencyEditor:
    def __init__(self, parent, *,
                 incident: Emergency | None = None) -> None:
        self.incident = incident
        self.result: Emergency | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit incident #{incident.incident_id}"
                          if incident else "New emergency incident")
        self.win.geometry("880x880")
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

        entry(0, 0, "Title*", "title", width=48)
        entry(1, 0, "Date*", "incident_date")
        entry(1, 2, "Time (HH:MM)", "incident_time")
        combo(2, 0, "Type*", "incident_type", EMERGENCY_TYPES)
        combo(2, 2, "Severity*", "severity",
                 ("1", "2", "3", "4", "5"))
        entry(3, 0, "Location", "location")
        combo(3, 2, "Status*", "status", STATUSES)
        entry(4, 0, "Reported by*", "reported_by")
        entry(4, 2, "Lead responder", "lead_responder")
        entry(5, 0, "Students affected", "students_affected")
        entry(5, 2, "Staff affected", "staff_affected")
        entry(6, 0, "Resolved on", "resolved_on")
        entry(6, 2, "Resolved time", "resolved_time")
        entry(7, 0, "Debriefed on", "debriefed_on")

        flags = ttk.LabelFrame(body, text="Response flags")
        flags.grid(row=8, column=0, columnspan=4,
                     sticky="ew", padx=4, pady=(8, 4))
        for col, (key, label) in enumerate((
                ("evacuation",         "Evacuation"),
                ("lockdown",           "Lockdown"),
                ("police_called",      "Police"),
                ("fire_called",        "Fire"),
                ("ambulance_called",   "Ambulance"),
        )):
            v = tk.BooleanVar()
            self.bools[key] = v
            ttk.Checkbutton(flags, text=label,
                             variable=v).grid(
                row=0, column=col, sticky="w", padx=6, pady=4)
        for col, (key, label) in enumerate((
                ("parents_informed",   "Parents informed"),
                ("governors_informed", "Governors informed"),
                ("follow_up_required", "Follow-up required"),
        )):
            v = tk.BooleanVar()
            self.bools[key] = v
            ttk.Checkbutton(flags, text=label,
                             variable=v).grid(
                row=1, column=col, sticky="w", padx=6, pady=4)

        row = 9
        for key, label in (
                ("description",     "Description"),
                ("incident_log",    "Incident log"),
                ("actions_taken",   "Actions taken"),
                ("follow_up_notes", "Follow-up notes"),
                ("debrief_notes",   "Debrief notes"),
                ("lessons_learned", "Lessons learned"),
                ("notes",           "Notes"),
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
        self.vars["incident_type"].set(DEFAULT_EMERGENCY_TYPE)
        self.vars["severity"].set("2")
        self.vars["status"].set(DEFAULT_STATUS)

    def _load(self) -> None:
        e = self.incident
        assert e is not None
        for key in ("title", "incident_date", "incident_time",
                     "incident_type", "location", "status",
                     "reported_by", "lead_responder",
                     "students_affected", "staff_affected",
                     "resolved_on", "resolved_time",
                     "debriefed_on"):
            self.vars[key].set(getattr(e, key) or "")
        self.vars["severity"].set(str(e.severity))
        for k in self.bools:
            self.bools[k].set(getattr(e, k))
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(e, k) or "")

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
            messagebox.showerror("Emergency", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class ResolveDialog:
    def __init__(self, parent, *, incident: Emergency) -> None:
        self.incident = incident
        self.result: Emergency | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Resolve — #{incident.incident_id}")
        self.win.geometry("520x380")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Resolved on").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.when = tk.StringVar(
            value=incident.resolved_on
            or _dt.date.today().isoformat())
        ttk.Entry(body, textvariable=self.when, width=14).grid(
            row=0, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(body, text="Resolved time").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.time_ = tk.StringVar(
            value=incident.resolved_time
            or _dt.datetime.now().strftime("%H:%M"))
        ttk.Entry(body, textvariable=self.time_, width=8).grid(
            row=1, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(body, text="Actions taken").grid(
            row=2, column=0, sticky="nw", padx=4, pady=4)
        self.actions = tk.Text(body, height=8, width=48,
                                  wrap="word")
        self.actions.insert("1.0", incident.actions_taken or "")
        self.actions.grid(row=2, column=1, sticky="ew",
                            padx=4, pady=4)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Resolve",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        try:
            self.result = data.resolve(
                self.incident.incident_id,
                actions_taken=self.actions.get("1.0", "end").rstrip()
                or None,
                resolved_on=self.when.get().strip(),
                resolved_time=self.time_.get().strip() or None)
        except ValidationError as exc:
            messagebox.showerror("Emergency", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class DebriefDialog:
    def __init__(self, parent, *, incident: Emergency) -> None:
        self.incident = incident
        self.result: Emergency | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Debrief — #{incident.incident_id}")
        self.win.geometry("560x520")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Debriefed on").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.when = tk.StringVar(
            value=incident.debriefed_on
            or _dt.date.today().isoformat())
        ttk.Entry(body, textvariable=self.when, width=14).grid(
            row=0, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(body, text="Debrief notes*").grid(
            row=1, column=0, sticky="nw", padx=4, pady=4)
        self.notes = tk.Text(body, height=6, width=52, wrap="word")
        self.notes.insert("1.0", incident.debrief_notes or "")
        self.notes.grid(row=1, column=1, sticky="ew",
                          padx=4, pady=4)
        ttk.Label(body, text="Lessons learned").grid(
            row=2, column=0, sticky="nw", padx=4, pady=4)
        self.lessons = tk.Text(body, height=6, width=52,
                                  wrap="word")
        self.lessons.insert("1.0", incident.lessons_learned or "")
        self.lessons.grid(row=2, column=1, sticky="ew",
                              padx=4, pady=4)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save debrief",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        try:
            self.result = data.record_debrief(
                self.incident.incident_id,
                debrief_notes=self.notes.get("1.0", "end").rstrip(),
                lessons_learned=self.lessons.get("1.0", "end").rstrip()
                or None,
                debriefed_on=self.when.get().strip()
                or _dt.date.today().isoformat())
        except ValidationError as exc:
            messagebox.showerror("Emergency", str(exc),
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


def _prompt_multiline(parent, title: str, *,
                       initial: str = "") -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("520x300")
    win.transient(parent); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    txt = tk.Text(win, wrap="word", height=8)
    txt.pack(fill="both", expand=True, padx=8)
    txt.insert("1.0", initial)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = txt.get("1.0", "end").rstrip()
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


__all__ = ["open_emergency_window"]
