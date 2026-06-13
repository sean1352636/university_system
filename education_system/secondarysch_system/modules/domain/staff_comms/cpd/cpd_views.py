"""Tkinter views for Secondary School CPD."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from education_system.shared import branding
from education_system.secondarysch_system.modules.domain.staff_comms.cpd import (
    cpd as data,
)
from education_system.secondarysch_system.modules.domain.staff_comms.cpd.cpd import (
    ACTIVITY_STATUSES,
    ACTIVITY_TYPES,
    Activity,
    DEFAULT_ACTIVITY_STATUS,
    DEFAULT_ACTIVITY_TYPE,
    DEFAULT_RECORD_STATUS,
    RATINGS,
    RECORD_STATUSES,
    Record,
    ValidationError,
    rating_label,
)
from education_system.secondarysch_system.modules.domain.staff_comms.staff import (
    staff as staff_data,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_ACT_TAGS = {
    "Planned":          ("#fff7e6", "#7a5800"),
    "Confirmed":        ("#e6f0ff", "#1a3f8c"),
    "Open for Booking": ("#e6f0ff", "#1a3f8c"),
    "Cancelled":        ("#ffd1d1", "#8c0d0d"),
    "Completed":        ("#e6f7e6", "#0d6b2a"),
    "Archived":         ("#eeeeee", "#444444"),
}
_REC_TAGS = {
    "Booked":    ("#fff7e6", "#7a5800"),
    "Confirmed": ("#e6f0ff", "#1a3f8c"),
    "Attended":  ("#fff0d6", "#7a5800"),
    "Completed": ("#e6f7e6", "#0d6b2a"),
    "Cancelled": ("#eeeeee", "#444444"),
    "No-Show":   ("#ffd1d1", "#8c0d0d"),
    "Declined":  ("#eeeeee", "#444444"),
}


def open_cpd_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"CPD — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    ActivitiesTab(nb)
    RecordsTab(nb)
    SummaryTab(nb)


def _staff_options() -> list[tuple[str, str]]:
    rows = sorted(staff_data.list_staff(),
                   key=lambda s: s.staff_id)
    return [(s.staff_id,
             f"{s.staff_id} — "
             f"{getattr(s, 'first_name', '')} "
             f"{getattr(s, 'last_name', '')}".strip())
            for s in rows]


def _activity_options() -> list[tuple[int | None, str]]:
    rows = data.list_activities()
    opts: list[tuple[int | None, str]] = [(None, "(none)")]
    for a in rows:
        opts.append((a.activity_id,
                       f"#{a.activity_id} — {a.title[:40]} "
                       f"({a.activity_date})"))
    return opts


# ── Activities tab ──────────────────────────────────────

class ActivitiesTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Activities")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = ttk.Combobox(
            bar, values=("",) + ACTIVITY_TYPES,
            state="readonly", width=18)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(
            bar, values=("",) + ACTIVITY_STATUSES,
            state="readonly", width=14)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Title:").pack(side="left")
        self.f_title = ttk.Entry(bar, width=20)
        self.f_title.pack(side="left", padx=(2, 8))
        self.upcoming = tk.BooleanVar()
        ttk.Checkbutton(bar, text="Upcoming only",
                         variable=self.upcoming,
                         command=self.refresh).pack(side="left",
                                                        padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "date", "type", "title", "provider",
                "hours", "cost", "cert", "records", "status")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "date": 90, "type": 140,
                   "title": 260, "provider": 140, "hours": 60,
                   "cost": 70, "cert": 50, "records": 70,
                   "status": 130}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "hours",
                                                  "cert",
                                                  "records")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _ACT_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.bind("<Double-Button-1>",
                         lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("Edit",           self._edit),
                ("Mark Completed", self._mark_completed),
                ("Change status",  self._set_status),
                ("Delete",         self._delete),
                ("Refresh",        self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_type.get():
            f["activity_type"] = self.f_type.get()
        if self.f_status.get():
            f["status"] = self.f_status.get()
        if self.f_title.get().strip():
            f["title_like"] = self.f_title.get().strip()
        if self.upcoming.get():
            f["upcoming_only"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        rows = data.list_activities(**self._filters())
        for a in rows:
            nrec = data.record_count(a.activity_id)
            self.tree.insert(
                "", "end", iid=str(a.activity_id),
                values=(a.activity_id, a.activity_date,
                         a.activity_type, a.title,
                         a.provider or "—",
                         (a.hours if a.hours is not None else "—"),
                         (f"£{a.cost:.0f}"
                          if a.cost is not None else "—"),
                         "yes" if a.certificated else "no",
                         nrec, a.status),
                tags=(a.status,))
        self.count.config(text=f"{len(rows)} activity(ies)")

    def _selected(self) -> Activity | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("CPD",
                                  "Select an activity first.",
                                  parent=self.frame)
            return None
        return data.get_activity(int(sel[0]))

    def _new(self) -> None:
        if ActivityEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        a = self._selected()
        if a and ActivityEditor(self.frame,
                                      activity=a).result is not None:
            self.refresh()

    def _mark_completed(self) -> None:
        a = self._selected()
        if not a:
            return
        try:
            data.mark_activity_completed(a.activity_id)
        except ValidationError as e:
            messagebox.showerror("CPD", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _set_status(self) -> None:
        a = self._selected()
        if not a:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(ACTIVITY_STATUSES),
                                default=a.status)
        if not new:
            return
        try:
            data.set_activity_status(a.activity_id, new)
        except ValidationError as e:
            messagebox.showerror("CPD", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        a = self._selected()
        if not a:
            return
        if not messagebox.askyesno(
                "CPD",
                f"Delete activity #{a.activity_id}?",
                parent=self.frame):
            return
        data.delete_activity(a.activity_id)
        self.refresh()


# ── Records tab ─────────────────────────────────────────

class RecordsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Records")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Staff id:").pack(side="left")
        self.f_staff = ttk.Entry(bar, width=12)
        self.f_staff.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(
            bar, values=("",) + RECORD_STATUSES,
            state="readonly", width=14)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 8))
        self.awaiting_cert = tk.BooleanVar()
        ttk.Checkbutton(bar, text="Awaiting cert",
                         variable=self.awaiting_cert,
                         command=self.refresh).pack(side="left",
                                                        padx=(2, 8))
        self.completed = tk.BooleanVar()
        ttk.Checkbutton(bar, text="Completed only",
                         variable=self.completed,
                         command=self.refresh).pack(side="left",
                                                        padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "staff", "activity", "booked",
                "attended", "hours", "rating", "cert",
                "status")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "staff": 110, "activity": 280,
                   "booked": 100, "attended": 100,
                   "hours": 60, "rating": 90, "cert": 70,
                   "status": 130}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "hours",
                                                  "rating", "cert")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _REC_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.bind("<Double-Button-1>",
                         lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("Edit",              self._edit),
                ("Mark attended",     self._mark_attended),
                ("Record evaluation", self._evaluate),
                ("File certificate",  self._file_cert),
                ("Change status",     self._set_status),
                ("Delete",            self._delete),
                ("Refresh",           self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_staff.get().strip():
            f["staff_id"] = self.f_staff.get().strip()
        if self.f_status.get():
            f["status"] = self.f_status.get()
        if self.awaiting_cert.get():
            f["awaiting_certificate"] = True
        if self.completed.get():
            f["completed_only"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        rows = data.list_records(**self._filters())
        for r in rows:
            rating = (rating_label(r.evaluation_rating)[:8]
                        if r.evaluation_rating else "—")
            cert = ("filed" if r.certificate_filed
                     else "rcvd" if r.certificate_received
                     else "—")
            self.tree.insert(
                "", "end", iid=str(r.record_id),
                values=(r.record_id, r.staff_id,
                         r.activity_title_cache or "—",
                         r.booked_on,
                         r.attended_on or "—",
                         (r.hours_completed
                          if r.hours_completed is not None
                          else "—"),
                         rating, cert, r.status),
                tags=(r.status,))
        self.count.config(text=f"{len(rows)} record(s)")

    def _selected(self) -> Record | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("CPD",
                                  "Select a record first.",
                                  parent=self.frame)
            return None
        return data.get_record(int(sel[0]))

    def _new(self) -> None:
        if RecordEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        r = self._selected()
        if r and RecordEditor(self.frame,
                                    record=r).result is not None:
            self.refresh()

    def _mark_attended(self) -> None:
        r = self._selected()
        if not r:
            return
        if AttendDialog(self.frame,
                            record=r).result is not None:
            self.refresh()

    def _evaluate(self) -> None:
        r = self._selected()
        if not r:
            return
        if EvaluateDialog(self.frame,
                              record=r).result is not None:
            self.refresh()

    def _file_cert(self) -> None:
        r = self._selected()
        if not r:
            return
        ref = _prompt_text(self.frame, "Certificate ref",
                              initial=r.certificate_ref or "")
        if ref is None:
            return
        try:
            data.file_certificate(r.record_id,
                                        ref=ref or None)
        except ValidationError as e:
            messagebox.showerror("CPD", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _set_status(self) -> None:
        r = self._selected()
        if not r:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(RECORD_STATUSES),
                                default=r.status)
        if not new:
            return
        try:
            data.set_record_status(r.record_id, new)
        except ValidationError as e:
            messagebox.showerror("CPD", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        r = self._selected()
        if not r:
            return
        if not messagebox.askyesno(
                "CPD", f"Delete record #{r.record_id}?",
                parent=self.frame):
            return
        data.delete_record(r.record_id)
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
        self.text.insert("end", "CPD Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total activities       : {s.total_activities}\n"
                            f"Upcoming               : {s.upcoming_activities}\n"
                            f"Completed activities   : {s.completed_activities}\n"
                            f"Total records          : {s.total_records}\n"
                            f"Completed records      : {s.completed_records}\n"
                            f"Total hours logged     : {s.total_hours_logged}\n"
                            f"Awaiting certificate   : {s.awaiting_certificate}\n"
                            f"Distinct staff         : {s.distinct_staff}\n"
                            f"Average rating         : "
                            f"{s.average_rating if s.average_rating is not None else '—'}\n\n")
        self.text.insert("end", "By activity type:\n")
        for k in ACTIVITY_TYPES:
            n = s.by_activity_type.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<24}: {n}\n")
        self.text.insert("end", "\nBy activity status:\n")
        for k in ACTIVITY_STATUSES:
            n = s.by_activity_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<18}: {n}\n")
        self.text.insert("end", "\nBy record status:\n")
        for k in RECORD_STATUSES:
            n = s.by_record_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.config(state="disabled")


# ── Editors ─────────────────────────────────────────────

class ActivityEditor:
    def __init__(self, parent, *,
                 activity: Activity | None = None) -> None:
        self.activity = activity
        self.result: Activity | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit activity #{activity.activity_id}"
                          if activity else "New activity")
        self.win.geometry("820x780")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if activity:
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
        entry(1, 0, "Provider", "provider")
        combo(1, 2, "Type*", "activity_type", ACTIVITY_TYPES)
        entry(2, 0, "Date*", "activity_date")
        entry(2, 2, "End date", "end_date")
        entry(3, 0, "Hours", "hours")
        entry(3, 2, "Cost (£)", "cost")
        entry(4, 0, "Accreditor", "accreditor")
        entry(4, 2, "Location", "location")
        entry(5, 0, "Capacity", "capacity")
        entry(5, 2, "Organiser", "organiser")
        combo(6, 0, "Status*", "status", ACTIVITY_STATUSES)
        self.bools["certificated"] = tk.BooleanVar()
        ttk.Checkbutton(body, text="Certificated",
                         variable=self.bools["certificated"]).grid(
            row=6, column=2, sticky="w", padx=4, pady=2)

        row = 7
        for key, label in (
                ("description", "Description"),
                ("outcomes",    "Outcomes"),
                ("notes",       "Notes"),
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

        self.vars["activity_date"].set(
            _dt.date.today().isoformat())
        self.vars["activity_type"].set(DEFAULT_ACTIVITY_TYPE)
        self.vars["status"].set(DEFAULT_ACTIVITY_STATUS)

    def _load(self) -> None:
        a = self.activity
        assert a is not None
        for key in ("title", "provider", "activity_type",
                     "activity_date", "end_date", "accreditor",
                     "location", "organiser", "status"):
            self.vars[key].set(getattr(a, key) or "")
        self.vars["hours"].set(
            str(a.hours) if a.hours is not None else "")
        self.vars["cost"].set(
            str(a.cost) if a.cost is not None else "")
        self.vars["capacity"].set(
            str(a.capacity)
            if a.capacity is not None else "")
        self.bools["certificated"].set(a.certificated)
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(a, k) or "")

    def _save(self) -> None:
        payload: dict = {}
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        for k, b in self.bools.items():
            payload[k] = b.get()
        try:
            if self.activity:
                self.result = data.update_activity(
                    self.activity.activity_id, payload)
            else:
                self.result = data.create_activity(payload)
        except ValidationError as exc:
            messagebox.showerror("CPD", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class RecordEditor:
    def __init__(self, parent, *,
                 record: Record | None = None) -> None:
        self.record = record
        self.result: Record | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit record #{record.record_id}"
                          if record else "New record")
        self.win.geometry("820x720")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if record:
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

        ttk.Label(body, text="Staff*").grid(
            row=0, column=0, sticky="w", padx=4, pady=2)
        self.staff_combo = ttk.Combobox(body, state="readonly",
                                            width=42)
        sopts = _staff_options()
        self._staff_opts = sopts
        self.staff_combo["values"] = [lbl for _, lbl in sopts]
        self.staff_combo.grid(row=0, column=1, sticky="ew",
                                  padx=4, pady=2)

        ttk.Label(body, text="Activity").grid(
            row=0, column=2, sticky="w", padx=4, pady=2)
        self.act_combo = ttk.Combobox(body, state="readonly",
                                          width=42)
        aopts = _activity_options()
        self._act_opts = aopts
        self.act_combo["values"] = [lbl for _, lbl in aopts]
        self.act_combo.current(0)
        self.act_combo.grid(row=0, column=3, sticky="ew",
                                padx=4, pady=2)

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

        entry(1, 0, "Booked on*", "booked_on")
        entry(1, 2, "Attended on", "attended_on")
        entry(2, 0, "Hours completed", "hours_completed")
        combo(2, 2, "Evaluation rating", "evaluation_rating",
                 ("", "1", "2", "3", "4", "5"))
        entry(3, 0, "Cost to staff (£)", "cost_to_staff")
        combo(3, 2, "Status*", "status", RECORD_STATUSES)
        entry(4, 0, "Certificate reference", "certificate_ref")
        flags = ttk.LabelFrame(body, text="Certificate")
        flags.grid(row=4, column=2, columnspan=2, sticky="ew",
                     padx=4, pady=2)
        for col, (key, label) in enumerate((
                ("certificate_received", "Received"),
                ("certificate_filed",    "Filed"),
        )):
            v = tk.BooleanVar()
            self.bools[key] = v
            ttk.Checkbutton(flags, text=label,
                             variable=v).grid(
                row=0, column=col, sticky="w", padx=6, pady=4)

        row = 5
        for key, label in (
                ("evaluation_notes",    "Evaluation notes"),
                ("impact_on_practice",  "Impact on practice"),
                ("notes",               "Notes"),
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

        self.vars["booked_on"].set(_dt.date.today().isoformat())
        self.vars["status"].set(DEFAULT_RECORD_STATUS)

    def _load(self) -> None:
        r = self.record
        assert r is not None
        for i, (sid, _) in enumerate(self._staff_opts):
            if sid == r.staff_id:
                self.staff_combo.current(i)
                break
        for i, (aid, _) in enumerate(self._act_opts):
            if aid == r.activity_id:
                self.act_combo.current(i)
                break
        for key in ("booked_on", "attended_on",
                     "certificate_ref", "status"):
            self.vars[key].set(getattr(r, key) or "")
        self.vars["hours_completed"].set(
            str(r.hours_completed)
            if r.hours_completed is not None else "")
        self.vars["evaluation_rating"].set(
            str(r.evaluation_rating)
            if r.evaluation_rating is not None else "")
        self.vars["cost_to_staff"].set(
            str(r.cost_to_staff)
            if r.cost_to_staff is not None else "")
        for k in self.bools:
            self.bools[k].set(getattr(r, k))
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(r, k) or "")

    def _save(self) -> None:
        sidx = self.staff_combo.current()
        if sidx < 0:
            messagebox.showerror("CPD", "Pick a staff member.",
                                    parent=self.win)
            return
        aidx = self.act_combo.current()
        payload: dict = {
            "staff_id": self._staff_opts[sidx][0],
            "activity_id": (self._act_opts[aidx][0]
                                if aidx >= 0 else None),
        }
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        for k, b in self.bools.items():
            payload[k] = b.get()
        try:
            if self.record:
                self.result = data.update_record(
                    self.record.record_id, payload)
            else:
                self.result = data.create_record(payload)
        except ValidationError as exc:
            messagebox.showerror("CPD", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class AttendDialog:
    def __init__(self, parent, *, record: Record) -> None:
        self.record = record
        self.result: Record | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Mark attended — #{record.record_id}")
        self.win.geometry("420x200")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Attended on").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.when = tk.StringVar(
            value=_dt.date.today().isoformat())
        ttk.Entry(body, textvariable=self.when,
                    width=14).grid(
            row=0, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(body, text="Hours completed").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.hours = tk.StringVar(
            value=str(record.hours_completed)
            if record.hours_completed is not None else "")
        ttk.Entry(body, textvariable=self.hours,
                    width=8).grid(
            row=1, column=1, sticky="w", padx=4, pady=4)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        hours_raw = self.hours.get().strip()
        hours = None
        if hours_raw:
            try:
                hours = float(hours_raw)
            except ValueError:
                messagebox.showerror("CPD",
                                        "Hours must be a number.",
                                        parent=self.win)
                return
        try:
            self.result = data.mark_attended(
                self.record.record_id,
                attended_on=self.when.get().strip(),
                hours=hours)
        except ValidationError as exc:
            messagebox.showerror("CPD", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class EvaluateDialog:
    def __init__(self, parent, *, record: Record) -> None:
        self.record = record
        self.result: Record | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Evaluation — #{record.record_id}")
        self.win.geometry("520x440")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Rating (1-5)").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.rating = tk.StringVar(
            value=str(record.evaluation_rating)
            if record.evaluation_rating is not None else "")
        ttk.Combobox(body, textvariable=self.rating,
                      values=("", "1", "2", "3", "4", "5"),
                      state="readonly", width=6).grid(
            row=0, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(body, text="Notes").grid(
            row=1, column=0, sticky="nw", padx=4, pady=4)
        self.notes = tk.Text(body, height=5, wrap="word")
        self.notes.insert("1.0", record.evaluation_notes or "")
        self.notes.grid(row=1, column=1, sticky="ew",
                          padx=4, pady=4)
        ttk.Label(body, text="Impact on practice").grid(
            row=2, column=0, sticky="nw", padx=4, pady=4)
        self.impact = tk.Text(body, height=5, wrap="word")
        self.impact.insert("1.0", record.impact_on_practice or "")
        self.impact.grid(row=2, column=1, sticky="ew",
                            padx=4, pady=4)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        rating_raw = self.rating.get().strip()
        rating = (int(rating_raw)
                    if rating_raw.isdigit() else None)
        try:
            self.result = data.record_evaluation(
                self.record.record_id,
                rating=rating,
                notes=self.notes.get("1.0", "end").rstrip()
                or None,
                impact=self.impact.get("1.0", "end").rstrip()
                or None)
        except ValidationError as exc:
            messagebox.showerror("CPD", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


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


__all__ = ["open_cpd_window"]
