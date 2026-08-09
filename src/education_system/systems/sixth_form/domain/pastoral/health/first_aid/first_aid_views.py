"""Tkinter views for Sixth Form First Aid."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from education_system.platform import branding
from education_system.systems.sixth_form.domain.pastoral.health.first_aid import (
    first_aid as data,
)
from education_system.systems.sixth_form.domain.pastoral.health.first_aid.first_aid import (
    DEFAULT_NATURE,
    DEFAULT_STATUS,
    Incident,
    NATURES,
    SEVERITIES,
    STATUSES,
    ValidationError,
    severity_label,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STATUS_TAGS = {
    "Recorded":          ("#fff7e6", "#7a5800"),
    "Treated":           ("#e6f0ff", "#1a3f8c"),
    "Parent Informed":   ("#e6f7e6", "#0d6b2a"),
    "Follow-Up Pending": ("#fff0d6", "#7a5800"),
    "Closed":            ("#eeeeee", "#444444"),
}


def open_first_aid_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"First Aid — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    FATab(nb, scope="open",            label="Open")
    FATab(nb, scope="parent_pending",  label="Parent Pending")
    FATab(nb, scope="follow_up",       label="Follow-Up Pending")
    FATab(nb, scope="overdue",         label="Follow-Up Overdue")
    FATab(nb, scope="ambulance",       label="Ambulance")
    FATab(nb, scope="all",             label="All")
    PerStudentTab(nb)
    SummaryTab(nb)


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}")
            for s in rows]


class FATab:
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
        ttk.Label(bar, text="Student id:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Nature:").pack(side="left")
        self.f_nature = ttk.Combobox(bar, values=("",) + NATURES,
                                       state="readonly", width=22)
        self.f_nature.current(0)
        self.f_nature.pack(side="left", padx=(2, 8))
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
        ttk.Label(bar, text="First aider:").pack(side="left")
        self.f_aider = ttk.Entry(bar, width=14)
        self.f_aider.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left",
                                                  padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "date", "time", "student", "nature",
                "severity", "first_aider", "status", "flags")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "date": 90, "time": 60,
                   "student": 100, "nature": 180,
                   "severity": 90, "first_aider": 130,
                   "status": 140, "flags": 170}
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
        self.tree.tag_configure("overdue", background="#ffd1d1",
                                  foreground="#8c0d0d")
        self.tree.tag_configure("critical", background="#ffb0b0",
                                  foreground="#6c0000")
        self.tree.bind("<Double-Button-1>", lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("View / Edit",      self._edit),
                ("Inform parent",    self._inform_parent),
                ("Complete f/up",    self._complete_followup),
                ("Close",            self._close),
                ("Change status",    self._set_status),
                ("Delete",           self._delete),
                ("Refresh",          self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _clear(self) -> None:
        self.f_student.delete(0, "end")
        self.f_nature.current(0)
        self.f_sev.current(0)
        self.f_aider.delete(0, "end")
        if self.f_status is not None:
            self.f_status.current(0)
        self.refresh()

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_student.get().strip():
            f["student_id"] = self.f_student.get().strip()
        if self.f_nature.get():
            f["nature"] = self.f_nature.get()
        if self.f_sev.get():
            f["severity_min"] = int(self.f_sev.get())
        if self.f_aider.get().strip():
            f["first_aider_like"] = self.f_aider.get().strip()
        if self.f_status is not None and self.f_status.get():
            f["status"] = self.f_status.get()
        if self.scope == "open":
            f["open_only"] = True
        elif self.scope == "parent_pending":
            f["parent_pending"] = True
        elif self.scope == "follow_up":
            f["follow_up_pending"] = True
        elif self.scope == "overdue":
            f["follow_up_overdue"] = True
        elif self.scope == "ambulance":
            f["ambulance_only"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.list_incidents(**self._filters())
        except ValidationError as e:
            messagebox.showerror("First Aid", str(e),
                                    parent=self.frame)
            return
        for i in rows:
            flags = []
            if i.ambulance_called:
                flags.append("AMB")
            if i.hospital_referral:
                flags.append("HOSP")
            if i.sent_home:
                flags.append("HOME")
            if not i.parent_informed and i.is_open:
                flags.append("P-PEND")
            if i.follow_up_overdue:
                flags.append("FU-OVERDUE")
            if i.follow_up_overdue:
                tag = "overdue"
            elif i.severity >= 4:
                tag = "critical"
            else:
                tag = i.status
            self.tree.insert(
                "", "end", iid=str(i.incident_id),
                values=(i.incident_id, i.incident_date,
                         i.incident_time or "—",
                         i.student_id, i.nature,
                         f"{i.severity} {severity_label(i.severity)[:3]}",
                         i.first_aider, i.status,
                         ",".join(flags)),
                tags=(tag,))
        self.count.config(text=f"{len(rows)} incident(s)")

    def _selected(self) -> Incident | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("First Aid",
                                  "Select an incident first.",
                                  parent=self.frame)
            return None
        return data.get_incident(int(sel[0]))

    def _new(self) -> None:
        if IncidentEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        i = self._selected()
        if i and IncidentEditor(
                self.frame, incident=i).result is not None:
            self.refresh()

    def _inform_parent(self) -> None:
        i = self._selected()
        if not i:
            return
        when = _prompt_text(self.frame, "Informed on (YYYY-MM-DD)",
                              initial=_dt.date.today().isoformat())
        if not when:
            return
        try:
            data.inform_parent(i.incident_id, informed_on=when)
        except ValidationError as exc:
            messagebox.showerror("First Aid", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _complete_followup(self) -> None:
        i = self._selected()
        if not i:
            return
        notes = _prompt_multiline(self.frame,
                                       "Closing notes (optional)",
                                       initial=i.follow_up_notes
                                       or "")
        if notes is None:
            return
        try:
            data.mark_follow_up_complete(i.incident_id,
                                                notes=notes or None)
        except ValidationError as exc:
            messagebox.showerror("First Aid", str(exc),
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
            messagebox.showerror("First Aid", str(exc),
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
            messagebox.showerror("First Aid", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        i = self._selected()
        if not i:
            return
        if not messagebox.askyesno(
                "First Aid",
                f"Delete incident #{i.incident_id}?",
                parent=self.frame):
            return
        data.delete_incident(i.incident_id)
        self.refresh()


class PerStudentTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Per Student")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Student:").pack(side="left")
        self.combo = ttk.Combobox(bar, state="readonly", width=42)
        opts = _student_options()
        self._opts = opts
        self.combo["values"] = [lbl for _, lbl in opts]
        self.combo.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Show",
                    command=self._show).pack(side="left")
        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.text.config(state="disabled")

    def _show(self) -> None:
        idx = self.combo.current()
        if idx < 0:
            return
        sid = self._opts[idx][0]
        rows = data.incidents_for_student(sid)
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end",
                            f"First aid history for {sid}\n"
                            f"{'=' * 60}\n\n"
                            f"Total incidents : {len(rows)}\n\n")
        for i in rows:
            self.text.insert("end",
                                f"#{i.incident_id}  "
                                f"{i.incident_date}  "
                                f"{i.incident_time or '—'}  "
                                f"{i.nature}  sev={i.severity}  "
                                f"[{i.status}]\n")
            if i.treatment_given:
                self.text.insert("end",
                                    f"  Treatment: "
                                    f"{i.treatment_given.splitlines()[0]}\n")
            self.text.insert("end", "\n")
        self.text.config(state="disabled")


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
        self.text.insert("end", "First Aid Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total                : {s.total}\n"
                            f"Open                 : {s.open_count}\n"
                            f"Serious / Critical   : {s.serious_or_critical}\n"
                            f"Ambulance called     : {s.ambulance_called}\n"
                            f"Sent home            : {s.sent_home}\n"
                            f"Parent pending       : {s.parent_pending}\n"
                            f"Follow-up pending    : {s.follow_up_pending}\n"
                            f"Follow-up overdue    : {s.follow_up_overdue}\n"
                            f"Distinct students    : {s.distinct_students}\n"
                            f"Average severity     : "
                            f"{s.average_severity if s.average_severity is not None else '—'}\n\n")
        self.text.insert("end", "By nature:\n")
        for k in NATURES:
            n = s.by_nature.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<24}: {n}\n")
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
                self.text.insert("end", f"  {k:<18}: {n}\n")
        self.text.config(state="disabled")


# ── Editor ────────────────────────────────────────────────────────

class IncidentEditor:
    def __init__(self, parent, *,
                 incident: Incident | None = None) -> None:
        self.incident = incident
        self.result: Incident | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit incident #{incident.incident_id}"
                          if incident else "New first aid incident")
        self.win.geometry("820x780")
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

        ttk.Label(body, text="Student*").grid(
            row=0, column=0, sticky="w", padx=4, pady=2)
        self.student_combo = ttk.Combobox(body, state="readonly",
                                              width=42)
        opts = _student_options()
        self._student_opts = opts
        self.student_combo["values"] = [lbl for _, lbl in opts]
        self.student_combo.grid(row=0, column=1, columnspan=3,
                                  sticky="ew", padx=4, pady=2)

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

        entry(1, 0, "Date*", "incident_date")
        entry(1, 2, "Time (HH:MM)", "incident_time")
        entry(2, 0, "Location", "location")
        combo(2, 2, "Nature*", "nature", NATURES)
        combo(3, 0, "Severity*", "severity",
                 ("1", "2", "3", "4", "5"))
        entry(3, 2, "First aider*", "first_aider")
        entry(4, 0, "Accident book ref", "accident_book_ref")
        combo(4, 2, "Status*", "status", STATUSES)

        flags = ttk.LabelFrame(body, text="Flags")
        flags.grid(row=5, column=0, columnspan=4,
                     sticky="ew", padx=4, pady=(8, 4))
        for col, (key, label) in enumerate((
                ("ambulance_called",   "Ambulance"),
                ("hospital_referral",  "Hospital"),
                ("sent_home",          "Sent home"),
                ("parent_informed",    "Parent informed"),
                ("follow_up_required", "Follow-up required"),
        )):
            v = tk.BooleanVar()
            self.bools[key] = v
            ttk.Checkbutton(flags, text=label, variable=v).grid(
                row=0, column=col, sticky="w", padx=6, pady=4)

        entry(6, 0, "Parent informed on", "parent_informed_on")
        entry(6, 2, "Follow-up due", "follow_up_due")

        row = 7
        for key, label in (
                ("description",      "Description"),
                ("treatment_given",  "Treatment given"),
                ("follow_up_notes",  "Follow-up notes"),
                ("notes",            "Notes"),
        ):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="nw", padx=4, pady=(6, 2))
            t = tk.Text(body, height=3, width=70, wrap="word")
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
        self.vars["nature"].set(DEFAULT_NATURE)
        self.vars["severity"].set("2")
        self.vars["status"].set(DEFAULT_STATUS)

    def _load(self) -> None:
        i = self.incident
        assert i is not None
        for idx, (sid, _) in enumerate(self._student_opts):
            if sid == i.student_id:
                self.student_combo.current(idx)
                break
        for key in ("incident_date", "incident_time", "location",
                     "nature", "first_aider",
                     "accident_book_ref", "status",
                     "parent_informed_on", "follow_up_due"):
            self.vars[key].set(getattr(i, key) or "")
        self.vars["severity"].set(str(i.severity))
        for k in self.bools:
            self.bools[k].set(getattr(i, k))
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(i, k) or "")

    def _save(self) -> None:
        idx = self.student_combo.current()
        if idx < 0:
            messagebox.showerror("First Aid", "Pick a student.",
                                    parent=self.win)
            return
        payload: dict = {"student_id": self._student_opts[idx][0]}
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
            messagebox.showerror("First Aid", str(exc),
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
    win.title(title); win.geometry("500x280")
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


__all__ = ["open_first_aid_window"]
