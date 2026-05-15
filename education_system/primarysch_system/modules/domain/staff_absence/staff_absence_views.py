"""Tkinter views for Primary School Staff Absence."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from education_system.shared import branding
from education_system.primarysch_system.modules.domain.staff_absence import (
    staff_absence as data,
)
from education_system.primarysch_system.modules.domain.staff_absence.staff_absence import (
    ABSENCE_TYPES,
    Absence,
    CERTIFICATE_TYPES,
    COVER_SOURCES,
    DEFAULT_ABSENCE_TYPE,
    DEFAULT_CERTIFICATE_TYPE,
    DEFAULT_COVER_SOURCE,
    DEFAULT_NOTIFICATION_METHOD,
    DEFAULT_STATUS,
    NOTIFICATION_METHODS,
    STATUSES,
    ValidationError,
)
from education_system.primarysch_system.modules.domain.staff import (
    staff as staff_data,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STATUS_TAGS = {
    "Reported":  ("#fff7e6", "#7a5800"),
    "Confirmed": ("#e6f0ff", "#1a3f8c"),
    "Active":    ("#fff0d6", "#7a5800"),
    "Returned":  ("#e6f7e6", "#0d6b2a"),
    "Closed":    ("#eeeeee", "#444444"),
    "Cancelled": ("#dddddd", "#444444"),
}


def open_staff_absence_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Staff Absence — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    AbsenceTab(nb, scope="active_today",      label="Active Today")
    AbsenceTab(nb, scope="open",              label="Open")
    AbsenceTab(nb, scope="critical",          label="Critical")
    AbsenceTab(nb, scope="cover_outstanding", label="Cover Pending")
    AbsenceTab(nb, scope="return_overdue",    label="Return Overdue")
    AbsenceTab(nb, scope="rtw_overdue",       label="RTW Overdue")
    AbsenceTab(nb, scope="all",               label="All")
    SummaryTab(nb)


def _staff_options() -> list[tuple[str, str]]:
    rows = sorted(staff_data.list_staff(),
                   key=lambda s: s.staff_id)
    return [(s.staff_id,
             f"{s.staff_id} — "
             f"{getattr(s, 'first_name', '')} "
             f"{getattr(s, 'last_name', '')}".strip())
            for s in rows]


class AbsenceTab:
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
        ttk.Label(bar, text="Staff id:").pack(side="left")
        self.f_staff = ttk.Entry(bar, width=12)
        self.f_staff.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = ttk.Combobox(bar,
                                     values=("",) + ABSENCE_TYPES,
                                     state="readonly", width=22)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))
        if self.scope == "all":
            ttk.Label(bar, text="Status:").pack(side="left")
            self.f_status = ttk.Combobox(bar,
                                           values=("",) + STATUSES,
                                           state="readonly",
                                           width=12)
            self.f_status.current(0)
            self.f_status.pack(side="left", padx=(2, 8))
        else:
            self.f_status = None
        ttk.Label(bar, text="Cover:").pack(side="left")
        self.f_cover = ttk.Combobox(
            bar, values=("",) + COVER_SOURCES,
            state="readonly", width=14)
        self.f_cover.current(0)
        self.f_cover.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "date", "staff", "type", "exp_return",
                "act_return", "status", "cover", "days_lost",
                "flags")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "date": 90, "staff": 110,
                   "type": 170, "exp_return": 100,
                   "act_return": 100, "status": 110,
                   "cover": 130, "days_lost": 80, "flags": 150}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "days_lost")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _STATUS_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.tag_configure("critical", background="#ffd1d1",
                                  foreground="#8c0d0d")
        self.tree.tag_configure("alert", background="#ffe6cc",
                                  foreground="#a04400")
        self.tree.bind("<Double-Button-1>",
                         lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("Edit",          self._edit),
                ("Confirm",       self._confirm),
                ("Arrange cover", self._arrange_cover),
                ("Record return", self._record_return),
                ("Complete RTW",  self._complete_rtw),
                ("Close",         self._close),
                ("Cancel",        self._cancel),
                ("Change status", self._set_status),
                ("Delete",        self._delete),
                ("Refresh",       self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_staff.get().strip():
            f["staff_id"] = self.f_staff.get().strip()
        if self.f_type.get():
            f["absence_type"] = self.f_type.get()
        if self.f_cover.get():
            f["cover_source"] = self.f_cover.get()
        if self.f_status is not None and self.f_status.get():
            f["status"] = self.f_status.get()
        if self.scope == "active_today":
            f["active_today"] = True
        elif self.scope == "open":
            f["open_only"] = True
        elif self.scope == "critical":
            f["critical_only"] = True
            f["open_only"] = True
        elif self.scope == "cover_outstanding":
            f["cover_outstanding"] = True
        elif self.scope == "return_overdue":
            f["return_overdue"] = True
        elif self.scope == "rtw_overdue":
            f["rtw_overdue"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.list_absences(**self._filters())
        except ValidationError as e:
            messagebox.showerror("Staff Absence", str(e),
                                    parent=self.frame)
            return
        for a in rows:
            flags = []
            if a.critical:
                flags.append("CRIT")
            if a.cover_outstanding:
                flags.append("COVER")
            if a.return_overdue:
                flags.append("RET")
            if a.rtw_overdue:
                flags.append("RTW")
            tag = ("critical" if a.critical and a.is_open
                     else "alert" if flags
                     else a.status)
            self.tree.insert(
                "", "end", iid=str(a.absence_id),
                values=(a.absence_id, a.absence_date,
                         a.staff_id, a.absence_type,
                         a.expected_return or "—",
                         a.actual_return or "—",
                         a.status, a.cover_source,
                         (a.days_lost
                          if a.days_lost is not None
                          else "—"),
                         ",".join(flags)),
                tags=(tag,))
        self.count.config(text=f"{len(rows)} absence(s)")

    def _selected(self) -> Absence | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Staff Absence",
                                  "Select an absence first.",
                                  parent=self.frame)
            return None
        return data.get_absence(int(sel[0]))

    def _new(self) -> None:
        if AbsenceEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        a = self._selected()
        if a and AbsenceEditor(self.frame,
                                     absence=a).result is not None:
            self.refresh()

    def _confirm(self) -> None:
        a = self._selected()
        if not a:
            return
        try:
            data.confirm_absence(a.absence_id)
        except ValidationError as exc:
            messagebox.showerror("Staff Absence", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _arrange_cover(self) -> None:
        a = self._selected()
        if not a:
            return
        if CoverDialog(self.frame,
                          absence=a).result is not None:
            self.refresh()

    def _record_return(self) -> None:
        a = self._selected()
        if not a:
            return
        if ReturnDialog(self.frame,
                            absence=a).result is not None:
            self.refresh()

    def _complete_rtw(self) -> None:
        a = self._selected()
        if not a:
            return
        if RTWDialog(self.frame,
                          absence=a).result is not None:
            self.refresh()

    def _close(self) -> None:
        a = self._selected()
        if not a:
            return
        try:
            data.close_absence(a.absence_id)
        except ValidationError as exc:
            messagebox.showerror("Staff Absence", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _cancel(self) -> None:
        a = self._selected()
        if not a:
            return
        try:
            data.cancel_absence(a.absence_id)
        except ValidationError as exc:
            messagebox.showerror("Staff Absence", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _set_status(self) -> None:
        a = self._selected()
        if not a:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(STATUSES),
                                default=a.status)
        if not new:
            return
        try:
            data.set_status(a.absence_id, new)
        except ValidationError as exc:
            messagebox.showerror("Staff Absence", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        a = self._selected()
        if not a:
            return
        if not messagebox.askyesno(
                "Staff Absence",
                f"Delete absence #{a.absence_id}?",
                parent=self.frame):
            return
        data.delete_absence(a.absence_id)
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
        self.text.insert("end", "Staff Absence Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total                : {s.total}\n"
                            f"Open                 : {s.open_count}\n"
                            f"Active today         : {s.active_today}\n"
                            f"Cover outstanding    : {s.cover_outstanding}\n"
                            f"Critical open        : {s.critical_open}\n"
                            f"RTW overdue          : {s.rtw_overdue}\n"
                            f"Return overdue       : {s.return_overdue}\n"
                            f"Awaiting certificate : {s.awaiting_cert}\n"
                            f"Parents pending      : {s.parents_pending}\n"
                            f"Distinct staff       : {s.distinct_staff}\n"
                            f"Total days lost      : {s.total_days_lost}\n\n")
        self.text.insert("end", "By type:\n")
        for k in ABSENCE_TYPES:
            n = s.by_type.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.insert("end", "\nBy status:\n")
        for k in STATUSES:
            n = s.by_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.insert("end", "\nBy cover source:\n")
        for k in COVER_SOURCES:
            n = s.by_cover_source.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<18}: {n}\n")
        self.text.config(state="disabled")


# ── Editor ──────────────────────────────────────────────

class AbsenceEditor:
    def __init__(self, parent, *,
                 absence: Absence | None = None) -> None:
        self.absence = absence
        self.result: Absence | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit absence #{absence.absence_id}"
                          if absence else "New absence")
        self.win.geometry("880x820")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if absence:
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
        opts = _staff_options()
        self._staff_opts = opts
        self.staff_combo["values"] = [lbl for _, lbl in opts]
        self.staff_combo.grid(row=0, column=1, columnspan=3,
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

        entry(1, 0, "Absence date*", "absence_date")
        combo(1, 2, "Absence type*", "absence_type",
                 ABSENCE_TYPES)
        entry(2, 0, "Expected return", "expected_return")
        entry(2, 2, "Actual return", "actual_return")
        entry(3, 0, "Reason", "reason", width=48)
        entry(4, 0, "Notified on", "notified_on")
        combo(4, 2, "Notification", "notification_method",
                 NOTIFICATION_METHODS)
        entry(5, 0, "Notified by", "notified_by")
        combo(5, 2, "Certificate", "certificate_type",
                 CERTIFICATE_TYPES)
        entry(6, 0, "Cert received on", "cert_received_on")
        combo(6, 2, "Cover source*", "cover_source",
                 COVER_SOURCES)
        entry(7, 0, "Cover arranged by", "cover_arranged_by")
        combo(7, 2, "Status*", "status", STATUSES)
        entry(8, 0, "RTW meeting on", "rtw_meeting_on")
        entry(8, 2, "RTW completed by", "rtw_completed_by")
        entry(9, 0, "Days lost", "days_lost")

        flags = ttk.LabelFrame(body, text="Flags")
        flags.grid(row=10, column=0, columnspan=4,
                     sticky="ew", padx=4, pady=(8, 4))
        for col, (key, label) in enumerate((
                ("cover_required",   "Cover required"),
                ("critical",         "Critical absence"),
                ("parents_informed", "Parents informed"),
                ("slt_informed",     "SLT informed"),
                ("rtw_required",     "RTW required"),
        )):
            v = tk.BooleanVar()
            self.bools[key] = v
            ttk.Checkbutton(flags, text=label,
                             variable=v).grid(
                row=0, column=col, sticky="w", padx=6, pady=4)

        row = 11
        for key, label in (
                ("cover_notes", "Cover notes"),
                ("notes",       "Notes"),
        ):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="nw", padx=4, pady=(6, 2))
            t = tk.Text(body, height=3, width=74, wrap="word")
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

        today = _dt.date.today().isoformat()
        self.vars["absence_date"].set(today)
        self.vars["notified_on"].set(today)
        self.vars["absence_type"].set(DEFAULT_ABSENCE_TYPE)
        self.vars["notification_method"].set(
            DEFAULT_NOTIFICATION_METHOD)
        self.vars["certificate_type"].set(
            DEFAULT_CERTIFICATE_TYPE)
        self.vars["cover_source"].set(DEFAULT_COVER_SOURCE)
        self.vars["status"].set(DEFAULT_STATUS)
        self.bools["cover_required"].set(True)

    def _load(self) -> None:
        a = self.absence
        assert a is not None
        for i, (sid, _) in enumerate(self._staff_opts):
            if sid == a.staff_id:
                self.staff_combo.current(i)
                break
        for key in ("absence_date", "expected_return",
                     "actual_return", "absence_type", "reason",
                     "notified_on", "notification_method",
                     "notified_by", "certificate_type",
                     "cert_received_on", "cover_source",
                     "cover_arranged_by", "status",
                     "rtw_meeting_on", "rtw_completed_by"):
            self.vars[key].set(getattr(a, key) or "")
        self.vars["days_lost"].set(
            str(a.days_lost)
            if a.days_lost is not None else "")
        for k in self.bools:
            self.bools[k].set(getattr(a, k))
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(a, k) or "")

    def _save(self) -> None:
        idx = self.staff_combo.current()
        if idx < 0:
            messagebox.showerror("Staff Absence",
                                    "Pick a staff member.",
                                    parent=self.win)
            return
        payload: dict = {"staff_id": self._staff_opts[idx][0]}
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        for k, b in self.bools.items():
            payload[k] = b.get()
        try:
            if self.absence:
                self.result = data.update_absence(
                    self.absence.absence_id, payload)
            else:
                self.result = data.create_absence(payload)
        except ValidationError as exc:
            messagebox.showerror("Staff Absence", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class CoverDialog:
    def __init__(self, parent, *, absence: Absence) -> None:
        self.absence = absence
        self.result: Absence | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Arrange cover — #{absence.absence_id}")
        self.win.geometry("520x340")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Source*").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.source = tk.StringVar(value=absence.cover_source)
        ttk.Combobox(body, textvariable=self.source,
                      values=COVER_SOURCES,
                      state="readonly").grid(
            row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(body, text="Arranged by").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.by = tk.StringVar(value=absence.cover_arranged_by or "")
        ttk.Entry(body, textvariable=self.by).grid(
            row=1, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(body, text="Cover notes").grid(
            row=2, column=0, sticky="nw", padx=4, pady=4)
        self.notes = tk.Text(body, height=6, width=48,
                                wrap="word")
        self.notes.insert("1.0", absence.cover_notes or "")
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
            self.result = data.arrange_cover(
                self.absence.absence_id,
                source=self.source.get(),
                arranged_by=self.by.get().strip() or None,
                notes=self.notes.get("1.0", "end").rstrip()
                or None)
        except ValidationError as exc:
            messagebox.showerror("Staff Absence", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class ReturnDialog:
    def __init__(self, parent, *, absence: Absence) -> None:
        self.absence = absence
        self.result: Absence | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Record return — #{absence.absence_id}")
        self.win.geometry("420x200")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Returned on").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.when = tk.StringVar(
            value=_dt.date.today().isoformat())
        ttk.Entry(body, textvariable=self.when, width=14).grid(
            row=0, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(body, text="Days lost (blank=auto)").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.days = tk.StringVar(
            value=str(absence.days_lost)
            if absence.days_lost is not None else "")
        ttk.Entry(body, textvariable=self.days, width=8).grid(
            row=1, column=1, sticky="w", padx=4, pady=4)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Record",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        days_raw = self.days.get().strip()
        days = None
        if days_raw:
            try:
                days = float(days_raw)
            except ValueError:
                messagebox.showerror("Staff Absence",
                                        "Days must be a number.",
                                        parent=self.win)
                return
        try:
            self.result = data.record_return(
                self.absence.absence_id,
                returned_on=self.when.get().strip(),
                days_lost=days)
        except ValidationError as exc:
            messagebox.showerror("Staff Absence", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class RTWDialog:
    def __init__(self, parent, *, absence: Absence) -> None:
        self.absence = absence
        self.result: Absence | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"RTW meeting — #{absence.absence_id}")
        self.win.geometry("420x200")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Completed by*").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.by = tk.StringVar(value=absence.rtw_completed_by
                                  or "")
        ttk.Entry(body, textvariable=self.by).grid(
            row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(body, text="Meeting on").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.when = tk.StringVar(
            value=_dt.date.today().isoformat())
        ttk.Entry(body, textvariable=self.when, width=14).grid(
            row=1, column=1, sticky="w", padx=4, pady=4)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        try:
            self.result = data.complete_rtw(
                self.absence.absence_id,
                completed_by=self.by.get().strip(),
                meeting_on=self.when.get().strip())
        except ValidationError as exc:
            messagebox.showerror("Staff Absence", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


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


__all__ = ["open_staff_absence_window"]
