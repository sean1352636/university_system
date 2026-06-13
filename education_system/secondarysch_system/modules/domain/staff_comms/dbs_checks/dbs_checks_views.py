"""Tkinter views for Secondary School DBS Checks."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from education_system.shared import branding
from education_system.secondarysch_system.modules.domain.staff_comms.dbs_checks import (
    dbs_checks as data,
)
from education_system.secondarysch_system.modules.domain.staff_comms.dbs_checks.dbs_checks import (
    CERTIFICATE_TYPES,
    DBSCheck,
    DEFAULT_CERTIFICATE_TYPE,
    DEFAULT_LEVEL,
    DEFAULT_STATUS,
    LEVELS,
    STATUSES,
    ValidationError,
)
from education_system.secondarysch_system.modules.domain.staff_comms.staff import (
    staff as staff_data,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STATUS_TAGS = {
    "Applied":                   ("#fff7e6", "#7a5800"),
    "Pending":                   ("#fff7e6", "#7a5800"),
    "Awaiting Certificate":      ("#fff0d6", "#7a5800"),
    "Cleared":                   ("#e6f7e6", "#0d6b2a"),
    "Cleared (with information)": ("#fff0d6", "#7a5800"),
    "Refused":                   ("#ffd1d1", "#8c0d0d"),
    "Lapsed":                    ("#ffd1d1", "#8c0d0d"),
    "Renewing":                  ("#e6e6ff", "#3a3a8c"),
    "Update Service Active":     ("#d6ffd6", "#0d6b2a"),
}


def open_dbs_checks_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"DBS Checks — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    DBSTab(nb, scope="active",          label="Active")
    DBSTab(nb, scope="expired",         label="Expired")
    DBSTab(nb, scope="expiring_soon",   label="Expiring Soon")
    DBSTab(nb, scope="update_overdue",  label="Update Overdue")
    DBSTab(nb, scope="unsigned",        label="Unsigned")
    DBSTab(nb, scope="risk_pending",    label="Risk Pending")
    DBSTab(nb, scope="all",             label="All")
    SummaryTab(nb)


def _staff_options() -> list[tuple[str, str]]:
    rows = sorted(staff_data.list_staff(),
                   key=lambda s: s.staff_id)
    return [(s.staff_id,
             f"{s.staff_id} — "
             f"{getattr(s, 'first_name', '')} "
             f"{getattr(s, 'last_name', '')}".strip())
            for s in rows]


class DBSTab:
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
        ttk.Label(bar, text="Level:").pack(side="left")
        self.f_level = ttk.Combobox(bar,
                                       values=("",) + LEVELS,
                                       state="readonly", width=26)
        self.f_level.current(0)
        self.f_level.pack(side="left", padx=(2, 8))
        if self.scope == "all":
            ttk.Label(bar, text="Status:").pack(side="left")
            self.f_status = ttk.Combobox(bar,
                                           values=("",) + STATUSES,
                                           state="readonly",
                                           width=22)
            self.f_status.current(0)
            self.f_status.pack(side="left", padx=(2, 8))
        else:
            self.f_status = None
        ttk.Label(bar, text="Cert:").pack(side="left")
        self.f_cert = ttk.Combobox(
            bar, values=("",) + CERTIFICATE_TYPES,
            state="readonly", width=18)
        self.f_cert.current(0)
        self.f_cert.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "staff", "level", "dbs_no", "issued",
                "expires", "cert_type", "update", "signed",
                "status", "flags")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "staff": 110, "level": 200,
                   "dbs_no": 120, "issued": 100,
                   "expires": 100, "cert_type": 130,
                   "update": 60, "signed": 110,
                   "status": 160, "flags": 130}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "update")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _STATUS_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.tag_configure("expired", background="#ffd1d1",
                                  foreground="#8c0d0d")
        self.tree.tag_configure("soon", background="#fff0d6",
                                  foreground="#7a5800")
        self.tree.bind("<Double-Button-1>",
                         lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("Edit",                self._edit),
                ("Issue certificate",   self._issue_cert),
                ("Mark cert seen",      self._cert_seen),
                ("Subscribe US",        self._subscribe),
                ("Record update",       self._update_check),
                ("Complete risk",       self._risk_assess),
                ("Sign off",            self._sign_off),
                ("Mark Lapsed",         self._mark_lapsed),
                ("Start renewal",       self._start_renewal),
                ("Change status",       self._set_status),
                ("Delete",              self._delete),
                ("Refresh",             self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_staff.get().strip():
            f["staff_id"] = self.f_staff.get().strip()
        if self.f_level.get():
            f["level"] = self.f_level.get()
        if self.f_cert.get():
            f["certificate_type"] = self.f_cert.get()
        if self.f_status is not None and self.f_status.get():
            f["status"] = self.f_status.get()
        if self.scope == "active":
            f["active_only"] = True
        elif self.scope == "expired":
            f["expired"] = True
        elif self.scope == "expiring_soon":
            f["expiring_soon"] = True
        elif self.scope == "update_overdue":
            f["update_check_overdue"] = True
        elif self.scope == "unsigned":
            f["unsigned"] = True
        elif self.scope == "risk_pending":
            f["risk_assessment_pending"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        rows = data.list_checks(**self._filters())
        for c in rows:
            flags = []
            if c.is_expired:
                flags.append("EXP")
            elif c.expiring_soon:
                flags.append("SOON")
            if c.update_check_overdue:
                flags.append("UC")
            if (c.risk_assessment_required
                    and not c.risk_assessment_completed_on):
                flags.append("RA")
            if not c.signed_off_by:
                flags.append("UNSGN")
            tag = ("expired" if c.is_expired
                     else "soon" if c.expiring_soon
                     else c.status)
            self.tree.insert(
                "", "end", iid=str(c.check_id),
                values=(c.check_id, c.staff_id, c.level,
                         c.dbs_number or "—",
                         c.issued_on or "—",
                         c.expires_on or "—",
                         c.certificate_type,
                         "yes" if c.update_service_subscribed
                         else "no",
                         c.signed_off_by or "—",
                         c.status, ",".join(flags)),
                tags=(tag,))
        self.count.config(text=f"{len(rows)} check(s)")

    def _selected(self) -> DBSCheck | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("DBS Checks",
                                  "Select a check first.",
                                  parent=self.frame)
            return None
        return data.get_check(int(sel[0]))

    def _new(self) -> None:
        if DBSEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        c = self._selected()
        if c and DBSEditor(self.frame,
                                check=c).result is not None:
            self.refresh()

    def _issue_cert(self) -> None:
        c = self._selected()
        if not c:
            return
        if IssueCertDialog(self.frame,
                                check=c).result is not None:
            self.refresh()

    def _cert_seen(self) -> None:
        c = self._selected()
        if not c:
            return
        when = _prompt_text(self.frame,
                              "Certificate seen on (YYYY-MM-DD)",
                              initial=_dt.date.today().isoformat())
        if not when:
            return
        try:
            data.see_certificate(c.check_id, seen_on=when)
        except ValidationError as e:
            messagebox.showerror("DBS Checks", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _subscribe(self) -> None:
        c = self._selected()
        if not c:
            return
        if SubscribeDialog(self.frame,
                                check=c).result is not None:
            self.refresh()

    def _update_check(self) -> None:
        c = self._selected()
        if not c:
            return
        if UpdateCheckDialog(self.frame,
                                  check=c).result is not None:
            self.refresh()

    def _risk_assess(self) -> None:
        c = self._selected()
        if not c:
            return
        if RiskAssessDialog(self.frame,
                                check=c).result is not None:
            self.refresh()

    def _sign_off(self) -> None:
        c = self._selected()
        if not c:
            return
        by = _prompt_text(self.frame, "Signed off by",
                            initial=c.signed_off_by or "")
        if not by:
            return
        try:
            data.sign_off(c.check_id, signed_off_by=by)
        except ValidationError as e:
            messagebox.showerror("DBS Checks", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _mark_lapsed(self) -> None:
        c = self._selected()
        if not c:
            return
        try:
            data.mark_lapsed(c.check_id)
        except ValidationError as e:
            messagebox.showerror("DBS Checks", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _start_renewal(self) -> None:
        c = self._selected()
        if not c:
            return
        try:
            data.start_renewal(c.check_id)
        except ValidationError as e:
            messagebox.showerror("DBS Checks", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _set_status(self) -> None:
        c = self._selected()
        if not c:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(STATUSES),
                                default=c.status)
        if not new:
            return
        try:
            data.set_status(c.check_id, new)
        except ValidationError as e:
            messagebox.showerror("DBS Checks", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        c = self._selected()
        if not c:
            return
        if not messagebox.askyesno(
                "DBS Checks",
                f"Delete check #{c.check_id}?",
                parent=self.frame):
            return
        data.delete_check(c.check_id)
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
        self.text.insert("end", "DBS Checks Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total                 : {s.total}\n"
                            f"Active                : {s.active}\n"
                            f"Cleared               : {s.cleared}\n"
                            f"Pending               : {s.pending}\n"
                            f"Renewing              : {s.renewing}\n"
                            f"Expired               : {s.expired}\n"
                            f"Expiring soon         : {s.expiring_soon}\n"
                            f"Update check overdue  : {s.update_check_overdue}\n"
                            f"Update service subs.  : {s.update_service_subscribed}\n"
                            f"Risk assess. pending  : {s.risk_assessment_pending}\n"
                            f"Unsigned              : {s.unsigned}\n"
                            f"Distinct staff        : {s.distinct_staff}\n\n")
        self.text.insert("end", "By level:\n")
        for k in LEVELS:
            n = s.by_level.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<32}: {n}\n")
        self.text.insert("end", "\nBy status:\n")
        for k in STATUSES:
            n = s.by_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<26}: {n}\n")
        self.text.insert("end", "\nBy certificate type:\n")
        for k in CERTIFICATE_TYPES:
            n = s.by_certificate_type.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.config(state="disabled")


# ── Editor ──────────────────────────────────────────────

class DBSEditor:
    def __init__(self, parent, *,
                 check: DBSCheck | None = None) -> None:
        self.check = check
        self.result: DBSCheck | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit DBS #{check.check_id}"
                          if check else "New DBS check")
        self.win.geometry("880x820")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if check:
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

        combo(1, 0, "Level*", "level", LEVELS, width=26)
        combo(1, 2, "Certificate type*", "certificate_type",
                 CERTIFICATE_TYPES)
        entry(2, 0, "DBS number", "dbs_number")
        combo(2, 2, "Status*", "status", STATUSES)
        entry(3, 0, "Applied on", "applied_on")
        entry(3, 2, "Issued on", "issued_on")
        entry(4, 0, "Expires on", "expires_on")
        entry(4, 2, "Certificate seen on",
                 "certificate_seen_on")
        entry(5, 0, "Update service ID", "update_service_id")
        entry(5, 2, "Last update check on",
                 "last_update_check_on")
        entry(6, 0, "Next update check due",
                 "next_update_check_due")
        entry(6, 2, "Risk assessment on",
                 "risk_assessment_completed_on")
        entry(7, 0, "Signed off by", "signed_off_by")
        entry(7, 2, "Signed off on", "signed_off_on")

        flags = ttk.LabelFrame(body, text="Flags")
        flags.grid(row=8, column=0, columnspan=4,
                     sticky="ew", padx=4, pady=(8, 4))
        for col, (key, label) in enumerate((
                ("update_service_subscribed",
                 "Update service subscribed"),
                ("portability_check", "Portability check"),
                ("risk_assessment_required",
                 "Risk assessment required"),
        )):
            v = tk.BooleanVar()
            self.bools[key] = v
            ttk.Checkbutton(flags, text=label,
                             variable=v).grid(
                row=0, column=col, sticky="w", padx=6, pady=4)

        row = 9
        for key, label in (
                ("risk_assessment_outcome",
                 "Risk assessment outcome"),
                ("notes", "Notes"),
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

        self.vars["level"].set(DEFAULT_LEVEL)
        self.vars["certificate_type"].set(
            DEFAULT_CERTIFICATE_TYPE)
        self.vars["status"].set(DEFAULT_STATUS)

    def _load(self) -> None:
        c = self.check
        assert c is not None
        for i, (sid, _) in enumerate(self._staff_opts):
            if sid == c.staff_id:
                self.staff_combo.current(i)
                break
        for key in ("level", "certificate_type", "status",
                     "dbs_number", "applied_on", "issued_on",
                     "expires_on", "certificate_seen_on",
                     "update_service_id",
                     "last_update_check_on",
                     "next_update_check_due",
                     "risk_assessment_completed_on",
                     "signed_off_by", "signed_off_on"):
            self.vars[key].set(getattr(c, key) or "")
        for k in self.bools:
            self.bools[k].set(getattr(c, k))
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(c, k) or "")

    def _save(self) -> None:
        idx = self.staff_combo.current()
        if idx < 0:
            messagebox.showerror("DBS Checks",
                                    "Pick a staff member.",
                                    parent=self.win)
            return
        payload: dict = {"staff_id": self._staff_opts[idx][0]}
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, b in self.bools.items():
            payload[k] = b.get()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        try:
            if self.check:
                self.result = data.update_check(
                    self.check.check_id, payload)
            else:
                self.result = data.create_check(payload)
        except ValidationError as exc:
            messagebox.showerror("DBS Checks", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class IssueCertDialog:
    def __init__(self, parent, *, check: DBSCheck) -> None:
        self.check = check
        self.result: DBSCheck | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Issue certificate — #{check.check_id}")
        self.win.geometry("440x240")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="DBS number*").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.num = tk.StringVar(value=check.dbs_number or "")
        ttk.Entry(body, textvariable=self.num).grid(
            row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(body, text="Issued on").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.issued = tk.StringVar(
            value=_dt.date.today().isoformat())
        ttk.Entry(body, textvariable=self.issued,
                    width=14).grid(
            row=1, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(body, text="Expires on").grid(
            row=2, column=0, sticky="w", padx=4, pady=4)
        self.expires = tk.StringVar(value=check.expires_on or "")
        ttk.Entry(body, textvariable=self.expires,
                    width=14).grid(
            row=2, column=1, sticky="w", padx=4, pady=4)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        try:
            self.result = data.issue_certificate(
                self.check.check_id,
                dbs_number=self.num.get().strip(),
                issued_on=self.issued.get().strip()
                or _dt.date.today().isoformat(),
                expires_on=self.expires.get().strip()
                or None)
        except ValidationError as exc:
            messagebox.showerror("DBS Checks", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class SubscribeDialog:
    def __init__(self, parent, *, check: DBSCheck) -> None:
        self.check = check
        self.result: DBSCheck | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Subscribe — #{check.check_id}")
        self.win.geometry("440x200")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Update service ID").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.uid = tk.StringVar(
            value=check.update_service_id or "")
        ttk.Entry(body, textvariable=self.uid).grid(
            row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(body, text="Next check due").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.next_due = tk.StringVar(
            value=check.next_update_check_due or "")
        ttk.Entry(body, textvariable=self.next_due,
                    width=14).grid(
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
            self.result = data.subscribe_update_service(
                self.check.check_id,
                update_id=self.uid.get().strip() or None,
                next_check_due=self.next_due.get().strip()
                or None)
        except ValidationError as exc:
            messagebox.showerror("DBS Checks", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class UpdateCheckDialog:
    def __init__(self, parent, *, check: DBSCheck) -> None:
        self.check = check
        self.result: DBSCheck | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Record update check — #{check.check_id}")
        self.win.geometry("440x200")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Checked on").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.when = tk.StringVar(
            value=_dt.date.today().isoformat())
        ttk.Entry(body, textvariable=self.when,
                    width=14).grid(
            row=0, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(body, text="Next check due "
                              "(blank=+12mo)").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.next_due = tk.StringVar()
        ttk.Entry(body, textvariable=self.next_due,
                    width=14).grid(
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
            self.result = data.record_update_check(
                self.check.check_id,
                checked_on=self.when.get().strip(),
                next_check_due=self.next_due.get().strip()
                or None)
        except ValidationError as exc:
            messagebox.showerror("DBS Checks", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class RiskAssessDialog:
    def __init__(self, parent, *, check: DBSCheck) -> None:
        self.check = check
        self.result: DBSCheck | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Risk assessment — #{check.check_id}")
        self.win.geometry("520x340")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Completed on").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.when = tk.StringVar(
            value=_dt.date.today().isoformat())
        ttk.Entry(body, textvariable=self.when,
                    width=14).grid(
            row=0, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(body, text="Outcome*").grid(
            row=1, column=0, sticky="nw", padx=4, pady=4)
        self.outcome = tk.Text(body, height=8, width=48,
                                  wrap="word")
        self.outcome.insert("1.0",
                                check.risk_assessment_outcome or "")
        self.outcome.grid(row=1, column=1, sticky="ew",
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
            self.result = data.complete_risk_assessment(
                self.check.check_id,
                outcome=self.outcome.get("1.0",
                                              "end").rstrip(),
                completed_on=self.when.get().strip()
                or _dt.date.today().isoformat())
        except ValidationError as exc:
            messagebox.showerror("DBS Checks", str(exc),
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


__all__ = ["open_dbs_checks_window"]
