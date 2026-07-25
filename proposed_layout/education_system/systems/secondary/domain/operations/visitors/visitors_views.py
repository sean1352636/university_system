"""Tkinter views for Secondary School Visitors."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from education_system.platform import branding
from education_system.systems.secondary.domain.operations.visitors import (
    visitors as data,
)
from education_system.systems.secondary.domain.operations.visitors.visitors import (
    DEFAULT_ID_TYPE,
    DEFAULT_STATUS,
    DEFAULT_VISITOR_TYPE,
    ID_TYPES,
    STATUSES,
    VISITOR_TYPES,
    ValidationError,
    Visitor,
)
from education_system.systems.secondary.domain.staff import (
    staff as staff_data,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STATUS_TAGS = {
    "Expected":      ("#fff7e6", "#7a5800"),
    "Signed In":     ("#fff0d6", "#7a5800"),
    "On Site":       ("#e6f0ff", "#1a3f8c"),
    "Signed Out":    ("#e6f7e6", "#0d6b2a"),
    "No-Show":       ("#eeeeee", "#444444"),
    "Refused Entry": ("#ffd1d1", "#8c0d0d"),
    "Overstay":     ("#ffd1d1", "#8c0d0d"),
}


def open_visitors_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Visitors — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    VisitorsTab(nb, scope="on_site",       label="On Site Now")
    VisitorsTab(nb, scope="overdue",       label="Overdue")
    VisitorsTab(nb, scope="today",         label="Today")
    VisitorsTab(nb, scope="no_show",       label="No-Shows")
    VisitorsTab(nb, scope="safeguarding",  label="Safeguarding")
    VisitorsTab(nb, scope="all",           label="All")
    SummaryTab(nb)


def _staff_options() -> list[tuple[str | None, str]]:
    rows = sorted(staff_data.list_staff(),
                   key=lambda s: s.staff_id)
    opts: list[tuple[str | None, str]] = [(None, "(none)")]
    for s in rows:
        full = f"{getattr(s, 'first_name', '')} " \
               f"{getattr(s, 'last_name', '')}".strip()
        opts.append((s.staff_id,
                       f"{s.staff_id} — {full}"))
    return opts


class VisitorsTab:
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
                                     values=("",) + VISITOR_TYPES,
                                     state="readonly", width=22)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))
        if self.scope == "all":
            ttk.Label(bar, text="Status:").pack(side="left")
            self.f_status = ttk.Combobox(bar,
                                           values=("",) + STATUSES,
                                           state="readonly",
                                           width=14)
            self.f_status.current(0)
            self.f_status.pack(side="left", padx=(2, 8))
        else:
            self.f_status = None
        ttk.Label(bar, text="Name:").pack(side="left")
        self.f_name = ttk.Entry(bar, width=18)
        self.f_name.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Org:").pack(side="left")
        self.f_org = ttk.Entry(bar, width=14)
        self.f_org.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "date", "name", "org", "type", "host",
                "badge", "arrived", "expected", "status",
                "flags")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "date": 90, "name": 160,
                   "org": 130, "type": 130, "host": 100,
                   "badge": 80, "arrived": 110,
                   "expected": 110, "status": 100,
                   "flags": 120}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c == "id" else "w"))
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
        self.tree.tag_configure("safeguarding",
                                   background="#ffb0b0",
                                   foreground="#6c0000")
        self.tree.bind("<Double-Button-1>",
                         lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("Edit",          self._edit),
                ("Sign in",       self._sign_in),
                ("Sign out",      self._sign_out),
                ("Overstay",      self._overstay),
                ("No-Show",       self._no_show),
                ("Refuse",        self._refuse),
                ("Safeguarding",  self._safeguarding),
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
        if self.f_type.get():
            f["visitor_type"] = self.f_type.get()
        if self.f_status is not None and self.f_status.get():
            f["status"] = self.f_status.get()
        if self.f_name.get().strip():
            f["name_like"] = self.f_name.get().strip()
        if self.f_org.get().strip():
            f["org_like"] = self.f_org.get().strip()
        if self.scope == "on_site":
            f["on_site_only"] = True
        elif self.scope == "overdue":
            f["overdue_only"] = True
        elif self.scope == "today":
            f["today_only"] = True
        elif self.scope == "no_show":
            f["no_show_only"] = True
        elif self.scope == "safeguarding":
            f["safeguarding_only"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        rows = data.list_visitors(**self._filters())
        for v in rows:
            flags = []
            if v.is_overdue:
                flags.append("OVERDUE")
            if v.safeguarding_concern:
                flags.append("SG")
            if v.escort_required and not v.escorted_by:
                flags.append("ESC-PEND")
            tag = ("safeguarding" if v.safeguarding_concern
                     else "overdue" if v.is_overdue
                     else v.status)
            self.tree.insert(
                "", "end", iid=str(v.visitor_id),
                values=(v.visitor_id, v.visit_date,
                         v.visitor_name,
                         v.organisation or "—",
                         v.visitor_type,
                         v.host_staff_id or v.host_name or "—",
                         v.badge_number or "—",
                         v.arrived_at or "—",
                         v.expected_departure or "—",
                         v.status, ",".join(flags)),
                tags=(tag,))
        self.count.config(text=f"{len(rows)} visitor(s)")

    def _selected(self) -> Visitor | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Visitors",
                                  "Select a visitor first.",
                                  parent=self.frame)
            return None
        return data.get_visitor(int(sel[0]))

    def _new(self) -> None:
        if VisitorEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        v = self._selected()
        if v and VisitorEditor(self.frame,
                                     visitor=v).result is not None:
            self.refresh()

    def _sign_in(self) -> None:
        v = self._selected()
        if not v:
            return
        badge = _prompt_text(self.frame, "Badge number",
                                initial=v.badge_number or "")
        if badge is None:
            return
        try:
            data.sign_in(v.visitor_id,
                            badge_number=badge or None)
        except ValidationError as e:
            messagebox.showerror("Visitors", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _sign_out(self) -> None:
        v = self._selected()
        if not v:
            return
        try:
            data.sign_out(v.visitor_id)
        except ValidationError as e:
            messagebox.showerror("Visitors", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _overstay(self) -> None:
        v = self._selected()
        if not v:
            return
        try:
            data.mark_overstay(v.visitor_id)
        except ValidationError as e:
            messagebox.showerror("Visitors", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _no_show(self) -> None:
        v = self._selected()
        if not v:
            return
        try:
            data.mark_no_show(v.visitor_id)
        except ValidationError as e:
            messagebox.showerror("Visitors", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _refuse(self) -> None:
        v = self._selected()
        if not v:
            return
        reason = _prompt_multiline(self.frame,
                                       "Reason for refusal")
        if reason is None:
            return
        try:
            data.refuse_entry(v.visitor_id,
                                  reason=reason or None)
        except ValidationError as e:
            messagebox.showerror("Visitors", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _safeguarding(self) -> None:
        v = self._selected()
        if not v:
            return
        detail = _prompt_multiline(self.frame,
                                        "Concern detail")
        if detail is None:
            return
        try:
            data.raise_safeguarding(v.visitor_id,
                                          detail=detail or None)
        except ValidationError as e:
            messagebox.showerror("Visitors", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _set_status(self) -> None:
        v = self._selected()
        if not v:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(STATUSES),
                                default=v.status)
        if not new:
            return
        try:
            data.set_status(v.visitor_id, new)
        except ValidationError as e:
            messagebox.showerror("Visitors", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        v = self._selected()
        if not v:
            return
        if not messagebox.askyesno(
                "Visitors",
                f"Delete visitor #{v.visitor_id}?",
                parent=self.frame):
            return
        data.delete_visitor(v.visitor_id)
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
        self.text.insert("end", "Visitors Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total                 : {s.total}\n"
                            f"On site now           : {s.on_site_now}\n"
                            f"Overdue               : {s.overdue}\n"
                            f"Expected today        : {s.expected_today}\n"
                            f"No-shows              : {s.no_shows}\n"
                            f"Safeguarding concerns : {s.safeguarding_concerns}\n"
                            f"Contractors on site   : {s.contractors_on_site}\n"
                            f"DBS seen count        : {s.dbs_seen_count}\n\n")
        self.text.insert("end", "By type:\n")
        for k in VISITOR_TYPES:
            n = s.by_type.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.insert("end", "\nBy status:\n")
        for k in STATUSES:
            n = s.by_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.insert("end", "\nBy ID check:\n")
        for k in ID_TYPES:
            n = s.by_id_check.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.config(state="disabled")


# ── Editor ──────────────────────────────────────────────

class VisitorEditor:
    def __init__(self, parent, *,
                 visitor: Visitor | None = None) -> None:
        self.visitor = visitor
        self.result: Visitor | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit visitor #{visitor.visitor_id}"
                          if visitor else "New visitor")
        self.win.geometry("880x820")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if visitor:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)
        self.vars: dict[str, tk.Variable] = {}
        self.bools: dict[str, tk.BooleanVar] = {}
        self.texts: dict[str, tk.Text] = {}

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

        entry(0, 0, "Visitor name*", "visitor_name", width=48)
        entry(1, 0, "Organisation", "organisation")
        combo(1, 2, "Visitor type*", "visitor_type",
                 VISITOR_TYPES)
        entry(2, 0, "Purpose", "purpose", width=48)

        ttk.Label(body, text="Host (staff)").grid(
            row=3, column=0, sticky="w", padx=4, pady=2)
        self.host_combo = ttk.Combobox(body, state="readonly",
                                            width=42)
        opts = _staff_options()
        self._host_opts = opts
        self.host_combo["values"] = [lbl for _, lbl in opts]
        self.host_combo.current(0)
        self.host_combo.grid(row=3, column=1, sticky="ew",
                                  padx=4, pady=2)
        entry(3, 2, "Host name", "host_name")
        entry(4, 0, "Badge number", "badge_number")
        combo(4, 2, "Status*", "status", STATUSES)
        entry(5, 0, "Visit date*", "visit_date")
        combo(5, 2, "ID check*", "id_check", ID_TYPES)
        entry(6, 0, "Arrived at (YYYY-MM-DDTHH:MM)",
                 "arrived_at")
        entry(6, 2, "Expected departure", "expected_departure")
        entry(7, 0, "Signed out at", "signed_out_at")

        flags = ttk.LabelFrame(body, text="Checks & flags")
        flags.grid(row=8, column=0, columnspan=4,
                     sticky="ew", padx=4, pady=(8, 4))
        for col, (key, label) in enumerate((
                ("dbs_seen",              "DBS seen"),
                ("photo_id_seen",         "Photo ID seen"),
                ("induction_given",       "Induction given"),
                ("safeguarding_briefing", "Sg briefing"),
        )):
            v = tk.BooleanVar()
            self.bools[key] = v
            ttk.Checkbutton(flags, text=label,
                             variable=v).grid(
                row=0, column=col, sticky="w", padx=6, pady=4)
        for col, (key, label) in enumerate((
                ("escort_required",      "Escort required"),
                ("safeguarding_concern", "Safeguarding concern"),
        )):
            v = tk.BooleanVar()
            self.bools[key] = v
            ttk.Checkbutton(flags, text=label,
                             variable=v).grid(
                row=1, column=col, sticky="w", padx=6, pady=4)

        entry(9, 0, "Escorted by", "escorted_by")
        entry(9, 2, "Car registration", "car_registration")
        entry(10, 0, "Car park used", "car_park_used")
        entry(10, 2, "Contact phone", "contact_phone")
        entry(11, 0, "Contact email", "contact_email")

        ttk.Label(body, text="Notes").grid(
            row=12, column=0, sticky="nw", padx=4, pady=(6, 2))
        self.notes = tk.Text(body, height=4, width=74,
                                wrap="word")
        self.notes.grid(row=12, column=1, columnspan=3,
                          sticky="ew", padx=4, pady=(6, 2))

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")

        self.vars["visit_date"].set(_dt.date.today().isoformat())
        self.vars["visitor_type"].set(DEFAULT_VISITOR_TYPE)
        self.vars["id_check"].set(DEFAULT_ID_TYPE)
        self.vars["status"].set(DEFAULT_STATUS)

    def _load(self) -> None:
        v = self.visitor
        assert v is not None
        for i, (sid, _) in enumerate(self._host_opts):
            if sid == v.host_staff_id:
                self.host_combo.current(i)
                break
        for key in ("visitor_name", "organisation",
                     "visitor_type", "purpose", "host_name",
                     "badge_number", "visit_date",
                     "arrived_at", "expected_departure",
                     "signed_out_at", "id_check",
                     "escorted_by", "car_registration",
                     "car_park_used", "contact_phone",
                     "contact_email", "status"):
            self.vars[key].set(getattr(v, key) or "")
        for k in self.bools:
            self.bools[k].set(getattr(v, k))
        self.notes.delete("1.0", "end")
        self.notes.insert("1.0", v.notes or "")

    def _save(self) -> None:
        idx = self.host_combo.current()
        payload: dict = {
            "host_staff_id": (self._host_opts[idx][0]
                                  if idx >= 0 else None),
            "notes": self.notes.get("1.0", "end").rstrip()
            or None,
        }
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, b in self.bools.items():
            payload[k] = b.get()
        try:
            if self.visitor:
                self.result = data.update_visitor(
                    self.visitor.visitor_id, payload)
            else:
                self.result = data.create_visitor(payload)
        except ValidationError as exc:
            messagebox.showerror("Visitors", str(exc),
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


__all__ = ["open_visitors_window"]
