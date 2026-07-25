"""Tkinter views for Sixth Form Prevent Duty."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk

from education_system.platform import branding
from education_system.systems.sixth_form.domain.safeguarding.prevent_duty import (
    prevent_duty as data,
)
from education_system.systems.sixth_form.domain.safeguarding.prevent_duty.prevent_duty import (
    CONCERN_STATUSES,
    CONCERN_TYPES,
    DEFAULT_CONCERN_STATUS,
    DEFAULT_CONCERN_TYPE,
    DEFAULT_REFERRAL_AUTHORITY,
    DEFAULT_REFERRAL_STATUS,
    DEFAULT_RISK_LEVEL,
    DEFAULT_TRAINING_TYPE,
    Concern,
    REFERRAL_AUTHORITIES,
    REFERRAL_STATUSES,
    RISK_LEVELS,
    Referral,
    TRAINING_TYPES,
    Training,
    ValidationError,
)
from education_system.systems.sixth_form.domain.staff import (
    staff as staff_data,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_RISK_TAGS = {
    "Low":    ("#e6f7e6", "#0d6b2a"),
    "Medium": ("#fff7e6", "#7a5800"),
    "High":   ("#ffeaea", "#8c1a1a"),
}

_CONCERN_STATUS_TAGS = {
    "Reported":          ("#fff7e6", "#7a5800"),
    "Under Review":      ("#e6f0ff", "#1a3f8c"),
    "Channel Referred":  ("#f0e6ff", "#4a1a8c"),
    "No Further Action": ("#eeeeee", "#555555"),
    "Closed":            ("#eeeeee", "#444444"),
}

_REFERRAL_STATUS_TAGS = {
    "Submitted":     ("#fff7e6", "#7a5800"),
    "Accepted":      ("#e6f0ff", "#1a3f8c"),
    "Declined":      ("#ffeaea", "#8c1a1a"),
    "Channel Panel": ("#f0e6ff", "#4a1a8c"),
    "Supported":     ("#e6f7e6", "#0d6b2a"),
    "Closed":        ("#eeeeee", "#444444"),
}

_TRAINING_TAGS = {
    "expired":      ("#ffeaea", "#8c1a1a"),
    "expiring":     ("#fff7e6", "#7a5800"),
    "ok":           ("#e6f7e6", "#0d6b2a"),
    "no-expiry":    ("#f3f3f3", "#444444"),
}


def open_prevent_duty_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Prevent Duty — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    ConcernsTab(nb)
    ReferralsTab(nb)
    TrainingTab(nb)
    SummaryTab(nb)


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                  key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}")
            for s in rows]


def _staff_options() -> list[tuple[str, str]]:
    rows = sorted(staff_data.list_staff(), key=lambda s: s.staff_id)
    return [(s.staff_id, f"{s.staff_id} — {s.full_name}")
            for s in rows]


def _today() -> str:
    return _dt.date.today().isoformat()


def _show_error(err: Exception) -> None:
    messagebox.showerror("Validation error", str(err))


# ── Concerns tab ───────────────────────────────────────────────────

class ConcernsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Concerns")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))

        ttk.Label(bar, text="Student:").pack(side="left")
        self.f_student = ttk.Combobox(bar, state="readonly", width=30)
        self.f_student["values"] = [""] + [d for _i, d in _student_options()]
        self.f_student.current(0)
        self.f_student.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Risk:").pack(side="left")
        self.f_risk = ttk.Combobox(bar, state="readonly",
                                    values=("",) + RISK_LEVELS, width=10)
        self.f_risk.current(0)
        self.f_risk.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, state="readonly",
                                      values=("",) + CONCERN_STATUSES,
                                      width=18)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = ttk.Combobox(bar, state="readonly",
                                    values=("",) + CONCERN_TYPES,
                                    width=22)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))

        self.open_only = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Open only",
                         variable=self.open_only).pack(side="left",
                                                        padx=(6, 0))
        ttk.Button(bar, text="Apply",
                   command=self.refresh).pack(side="left", padx=(8, 0))

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Button(actions, text="Log concern",
                   command=self._add).pack(side="left")
        ttk.Button(actions, text="Edit",
                   command=self._edit).pack(side="left", padx=4)
        ttk.Button(actions, text="Add referral",
                   command=self._add_referral).pack(side="left", padx=4)
        ttk.Button(actions, text="Close",
                   command=self._close).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete",
                   command=self._delete).pack(side="left", padx=4)

        cols = ("id", "date", "student", "type", "risk", "status",
                 "refs", "summary")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                  show="headings", height=22)
        for c, w, a in [
            ("id", 50, "e"), ("date", 90, "w"),
            ("student", 200, "w"), ("type", 180, "w"),
            ("risk", 70, "center"), ("status", 130, "w"),
            ("refs", 50, "center"), ("summary", 360, "w"),
        ]:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=w, anchor=a)
        for tag, (bg, fg) in _CONCERN_STATUS_TAGS.items():
            self.tree.tag_configure(tag, background=bg, foreground=fg)
        self.tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tree.bind("<Double-1>", lambda _e: self._edit())

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(self.tree.item(sel[0], "values")[0])
        except (ValueError, IndexError):
            return None

    def _filters(self) -> dict:
        kw: dict = {}
        sl = self.f_student.get()
        if sl:
            kw["student_id"] = sl.split(" — ", 1)[0]
        if self.f_risk.get():
            kw["risk_level"] = self.f_risk.get()
        if self.f_status.get():
            kw["status"] = self.f_status.get()
        elif self.open_only.get():
            kw["open_only"] = True
        if self.f_type.get():
            kw["concern_type"] = self.f_type.get()
        return kw

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_concerns_with_detail(**self._filters())
        except ValidationError as e:
            _show_error(e)
            return
        for cr in rows:
            c = cr.concern
            self.tree.insert("", "end", values=(
                c.concern_id, c.report_date,
                f"{c.student_id} — {cr.student_name}",
                c.concern_type, c.risk_level, c.status,
                cr.referral_count, c.summary[:120],
            ), tags=(c.status,))

    def _add(self) -> None:
        _ConcernDialog(self.frame, on_save=self.refresh)

    def _edit(self) -> None:
        cid = self._selected_id()
        if cid is None:
            messagebox.showinfo("Edit", "Select a concern first.")
            return
        existing = data.get_concern(cid)
        if existing is None:
            messagebox.showerror("Edit", f"Concern #{cid} not found.")
            return
        _ConcernDialog(self.frame, existing=existing, on_save=self.refresh)

    def _close(self) -> None:
        cid = self._selected_id()
        if cid is None:
            messagebox.showinfo("Close", "Select a concern first.")
            return
        if not messagebox.askyesno("Close",
                                    f"Mark concern #{cid} as Closed?"):
            return
        try:
            data.close_concern(cid)
        except ValidationError as e:
            _show_error(e)
            return
        self.refresh()

    def _add_referral(self) -> None:
        cid = self._selected_id()
        if cid is None:
            messagebox.showinfo("Add referral",
                                "Select a concern first.")
            return
        _ReferralDialog(self.frame, concern_id=cid,
                        on_save=self.refresh)

    def _delete(self) -> None:
        cid = self._selected_id()
        if cid is None:
            messagebox.showinfo("Delete", "Select a concern first.")
            return
        refs = data.list_referrals(concern_id=cid)
        extra = (f"\nThis will also delete {len(refs)} referral(s)."
                  if refs else "")
        if not messagebox.askyesno("Delete",
                                    f"Delete concern #{cid}?{extra}"):
            return
        if data.delete_concern(cid):
            self.refresh()


class _ConcernDialog:
    def __init__(self, parent, *, existing: Concern | None = None,
                 on_save=None) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Concern"
                        + (f" #{existing.concern_id}" if existing else ""))
        self.win.transient(parent.winfo_toplevel())
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        frm = ttk.Frame(self.win, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)

        c = self.existing

        ttk.Label(frm, text="Student:").grid(row=0, column=0, sticky="w")
        self.student = ttk.Combobox(frm, state="readonly", width=44)
        self.student["values"] = [d for _i, d in _student_options()]
        if c:
            for i, (sid, _d) in enumerate(_student_options()):
                if sid == c.student_id:
                    self.student.current(i)
                    break
            self.student.config(state="disabled")
        self.student.grid(row=0, column=1, sticky="ew", pady=2)

        ttk.Label(frm, text="Report date:").grid(row=1, column=0, sticky="w")
        self.report_date = ttk.Entry(frm, width=14)
        self.report_date.insert(0,
                                 c.report_date if c else _today())
        self.report_date.grid(row=1, column=1, sticky="w", pady=2)

        ttk.Label(frm, text="Type:").grid(row=2, column=0, sticky="w")
        self.ctype = ttk.Combobox(frm, state="readonly",
                                    values=CONCERN_TYPES, width=30)
        self.ctype.set(c.concern_type if c else DEFAULT_CONCERN_TYPE)
        self.ctype.grid(row=2, column=1, sticky="w", pady=2)

        ttk.Label(frm, text="Risk level:").grid(row=3, column=0, sticky="w")
        self.risk = ttk.Combobox(frm, state="readonly",
                                  values=RISK_LEVELS, width=10)
        self.risk.set(c.risk_level if c else DEFAULT_RISK_LEVEL)
        self.risk.grid(row=3, column=1, sticky="w", pady=2)

        ttk.Label(frm, text="Summary:").grid(row=4, column=0, sticky="w")
        self.summary = ttk.Entry(frm)
        if c:
            self.summary.insert(0, c.summary)
        self.summary.grid(row=4, column=1, sticky="ew", pady=2)

        ttk.Label(frm, text="Details:").grid(row=5, column=0,
                                               sticky="nw", pady=(6, 0))
        self.details = tk.Text(frm, height=5, width=60)
        if c and c.details:
            self.details.insert("1.0", c.details)
        self.details.grid(row=5, column=1, sticky="ew", pady=(6, 0))

        ttk.Label(frm, text="Reported by:").grid(row=6, column=0, sticky="w")
        self.reporter = ttk.Entry(frm)
        if c and c.reported_by:
            self.reporter.insert(0, c.reported_by)
        self.reporter.grid(row=6, column=1, sticky="ew", pady=2)

        ttk.Label(frm, text="Status:").grid(row=7, column=0, sticky="w")
        self.status = ttk.Combobox(frm, state="readonly",
                                    values=CONCERN_STATUSES, width=20)
        self.status.set(c.status if c else DEFAULT_CONCERN_STATUS)
        self.status.grid(row=7, column=1, sticky="w", pady=2)
        self.status.bind("<<ComboboxSelected>>", lambda _e: self._on_status())

        ttk.Label(frm, text="Closed date:").grid(row=8, column=0, sticky="w")
        self.closed_date = ttk.Entry(frm, width=14)
        if c and c.closed_date:
            self.closed_date.insert(0, c.closed_date)
        self.closed_date.grid(row=8, column=1, sticky="w", pady=2)

        ttk.Label(frm, text="Outcome:").grid(row=9, column=0, sticky="w")
        self.outcome = ttk.Entry(frm)
        if c and c.outcome:
            self.outcome.insert(0, c.outcome)
        self.outcome.grid(row=9, column=1, sticky="ew", pady=2)

        btns = ttk.Frame(frm)
        btns.grid(row=10, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(btns, text="Cancel",
                    command=self.win.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="Save",
                    command=self._save).pack(side="right")
        self._on_status()

    def _on_status(self) -> None:
        if self.status.get() in ("No Further Action", "Closed"):
            self.closed_date.config(state="normal")
            self.outcome.config(state="normal")
            if not self.closed_date.get().strip():
                self.closed_date.insert(0, _today())
        else:
            self.closed_date.delete(0, tk.END)
            self.closed_date.config(state="disabled")

    def _payload(self) -> dict:
        student_label = self.student.get()
        sid = student_label.split(" — ", 1)[0] if student_label else ""
        # Re-enable disabled fields to read them
        try:
            self.closed_date.config(state="normal")
        except tk.TclError:
            pass
        return {
            "student_id":   sid,
            "report_date":  self.report_date.get().strip(),
            "concern_type": self.ctype.get(),
            "risk_level":   self.risk.get(),
            "summary":      self.summary.get().strip(),
            "details":      self.details.get("1.0", "end").strip(),
            "reported_by":  self.reporter.get().strip(),
            "status":       self.status.get(),
            "closed_date":  self.closed_date.get().strip(),
            "outcome":      self.outcome.get().strip(),
        }

    def _save(self) -> None:
        try:
            if self.existing:
                data.update_concern(self.existing.concern_id, self._payload())
            else:
                data.create_concern(self._payload())
        except ValidationError as e:
            _show_error(e)
            return
        if self.on_save:
            self.on_save()
        self.win.destroy()


# ── Referrals tab ──────────────────────────────────────────────────

class ReferralsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Channel Referrals")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, state="readonly",
                                      values=("",) + REFERRAL_STATUSES,
                                      width=16)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Authority:").pack(side="left")
        self.f_auth = ttk.Combobox(bar, state="readonly",
                                    values=("",) + REFERRAL_AUTHORITIES,
                                    width=16)
        self.f_auth.current(0)
        self.f_auth.pack(side="left", padx=(2, 8))
        self.open_only = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Open only",
                         variable=self.open_only).pack(side="left",
                                                        padx=(6, 0))
        ttk.Button(bar, text="Apply",
                   command=self.refresh).pack(side="left", padx=(8, 0))

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Button(actions, text="Add referral",
                   command=self._add).pack(side="left")
        ttk.Button(actions, text="Edit",
                   command=self._edit).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete",
                   command=self._delete).pack(side="left", padx=4)

        cols = ("id", "concern", "date", "student", "authority",
                 "status", "panel", "officer")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                  show="headings", height=22)
        for c, w, a in [
            ("id", 50, "e"), ("concern", 70, "e"),
            ("date", 100, "w"), ("student", 220, "w"),
            ("authority", 130, "w"), ("status", 130, "w"),
            ("panel", 100, "w"), ("officer", 160, "w"),
        ]:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=w, anchor=a)
        for tag, (bg, fg) in _REFERRAL_STATUS_TAGS.items():
            self.tree.tag_configure(tag, background=bg, foreground=fg)
        self.tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tree.bind("<Double-1>", lambda _e: self._edit())

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(self.tree.item(sel[0], "values")[0])
        except (ValueError, IndexError):
            return None

    def _filters(self) -> dict:
        kw: dict = {}
        if self.f_status.get():
            kw["status"] = self.f_status.get()
        elif self.open_only.get():
            kw["open_only"] = True
        if self.f_auth.get():
            kw["authority"] = self.f_auth.get()
        return kw

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_referrals_with_detail(**self._filters())
        except ValidationError as e:
            _show_error(e)
            return
        for rr in rows:
            r = rr.referral
            self.tree.insert("", "end", values=(
                r.referral_id, r.concern_id, r.referral_date,
                f"{rr.student_id} — {rr.student_name}"
                if rr.student_id else "(unknown)",
                r.authority, r.status, r.panel_date or "—",
                r.case_officer or "—",
            ), tags=(r.status,))

    def _add(self) -> None:
        # Ask for a concern id since we're not coming from a row
        cid = _ask_int(self.frame, "Concern id",
                       "Enter the concern id to link this referral to:")
        if cid is None:
            return
        if data.get_concern(cid) is None:
            messagebox.showerror("Add", f"No concern with id {cid}")
            return
        _ReferralDialog(self.frame, concern_id=cid, on_save=self.refresh)

    def _edit(self) -> None:
        rid = self._selected_id()
        if rid is None:
            messagebox.showinfo("Edit", "Select a referral first.")
            return
        existing = data.get_referral(rid)
        if existing is None:
            messagebox.showerror("Edit", f"Referral #{rid} not found.")
            return
        _ReferralDialog(self.frame, concern_id=existing.concern_id,
                         existing=existing, on_save=self.refresh)

    def _delete(self) -> None:
        rid = self._selected_id()
        if rid is None:
            messagebox.showinfo("Delete", "Select a referral first.")
            return
        if not messagebox.askyesno("Delete", f"Delete referral #{rid}?"):
            return
        if data.delete_referral(rid):
            self.refresh()


def _ask_int(parent, title: str, prompt: str) -> int | None:
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.transient(parent.winfo_toplevel())
    dlg.after_idle(dlg.grab_set)
    ttk.Label(dlg, text=prompt, padding=10).pack()
    entry = ttk.Entry(dlg, width=18)
    entry.pack(padx=10, pady=6)
    entry.focus_set()
    result: dict[str, int | None] = {"value": None}

    def _ok() -> None:
        raw = entry.get().strip()
        try:
            result["value"] = int(raw)
        except ValueError:
            messagebox.showerror(title, "Must be a number.", parent=dlg)
            return
        dlg.destroy()

    btns = ttk.Frame(dlg, padding=(0, 6, 0, 10))
    btns.pack()
    ttk.Button(btns, text="OK", command=_ok).pack(side="left", padx=4)
    ttk.Button(btns, text="Cancel",
                command=dlg.destroy).pack(side="left", padx=4)
    entry.bind("<Return>", lambda _e: _ok())
    dlg.wait_window()
    return result["value"]


class _ReferralDialog:
    def __init__(self, parent, *, concern_id: int,
                 existing: Referral | None = None,
                 on_save=None) -> None:
        self.concern_id = concern_id
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Channel referral"
                        + (f" #{existing.referral_id}" if existing
                           else f" (concern #{concern_id})"))
        self.win.transient(parent.winfo_toplevel())
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        frm = ttk.Frame(self.win, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)

        r = self.existing
        ttk.Label(frm, text=f"Concern: #{self.concern_id}").grid(
            row=0, column=0, columnspan=2, sticky="w")

        ttk.Label(frm, text="Referral date:").grid(row=1, column=0,
                                                     sticky="w")
        self.referral_date = ttk.Entry(frm, width=14)
        self.referral_date.insert(0, r.referral_date if r else _today())
        self.referral_date.grid(row=1, column=1, sticky="w", pady=2)

        ttk.Label(frm, text="Authority:").grid(row=2, column=0, sticky="w")
        self.authority = ttk.Combobox(frm, state="readonly",
                                        values=REFERRAL_AUTHORITIES,
                                        width=20)
        self.authority.set(r.authority if r else DEFAULT_REFERRAL_AUTHORITY)
        self.authority.grid(row=2, column=1, sticky="w", pady=2)

        ttk.Label(frm, text="Case officer:").grid(row=3, column=0, sticky="w")
        self.officer = ttk.Entry(frm)
        if r and r.case_officer:
            self.officer.insert(0, r.case_officer)
        self.officer.grid(row=3, column=1, sticky="ew", pady=2)

        ttk.Label(frm, text="Panel date:").grid(row=4, column=0, sticky="w")
        self.panel_date = ttk.Entry(frm, width=14)
        if r and r.panel_date:
            self.panel_date.insert(0, r.panel_date)
        self.panel_date.grid(row=4, column=1, sticky="w", pady=2)

        ttk.Label(frm, text="Status:").grid(row=5, column=0, sticky="w")
        self.status = ttk.Combobox(frm, state="readonly",
                                    values=REFERRAL_STATUSES, width=18)
        self.status.set(r.status if r else DEFAULT_REFERRAL_STATUS)
        self.status.grid(row=5, column=1, sticky="w", pady=2)

        ttk.Label(frm, text="Outcome:").grid(row=6, column=0, sticky="w")
        self.outcome = ttk.Entry(frm)
        if r and r.outcome:
            self.outcome.insert(0, r.outcome)
        self.outcome.grid(row=6, column=1, sticky="ew", pady=2)

        ttk.Label(frm, text="Notes:").grid(row=7, column=0,
                                             sticky="nw", pady=(6, 0))
        self.notes = tk.Text(frm, height=5, width=60)
        if r and r.notes:
            self.notes.insert("1.0", r.notes)
        self.notes.grid(row=7, column=1, sticky="ew", pady=(6, 0))

        btns = ttk.Frame(frm)
        btns.grid(row=8, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(btns, text="Cancel",
                    command=self.win.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="Save",
                    command=self._save).pack(side="right")

    def _payload(self) -> dict:
        return {
            "concern_id":    self.concern_id,
            "referral_date": self.referral_date.get().strip(),
            "authority":     self.authority.get(),
            "case_officer":  self.officer.get().strip(),
            "panel_date":    self.panel_date.get().strip() or None,
            "status":        self.status.get(),
            "outcome":       self.outcome.get().strip(),
            "notes":         self.notes.get("1.0", "end").strip(),
        }

    def _save(self) -> None:
        try:
            if self.existing:
                data.update_referral(self.existing.referral_id,
                                      self._payload())
            else:
                data.create_referral(self._payload())
        except ValidationError as e:
            _show_error(e)
            return
        if self.on_save:
            self.on_save()
        self.win.destroy()


# ── Training tab ───────────────────────────────────────────────────

class TrainingTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Training")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Staff:").pack(side="left")
        self.f_staff = ttk.Combobox(bar, state="readonly", width=30)
        self.f_staff["values"] = [""] + [d for _i, d in _staff_options()]
        self.f_staff.current(0)
        self.f_staff.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = ttk.Combobox(bar, state="readonly",
                                    values=("",) + TRAINING_TYPES,
                                    width=18)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))
        self.scope = tk.StringVar(value="all")
        ttk.Radiobutton(bar, text="All", value="all",
                         variable=self.scope).pack(side="left", padx=(6, 0))
        ttk.Radiobutton(bar, text="Expired", value="expired",
                         variable=self.scope).pack(side="left", padx=(6, 0))
        ttk.Radiobutton(bar, text="Expiring ≤60d", value="expiring",
                         variable=self.scope).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Apply",
                   command=self.refresh).pack(side="left", padx=(8, 0))

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Button(actions, text="Add record",
                   command=self._add).pack(side="left")
        ttk.Button(actions, text="Edit",
                   command=self._edit).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete",
                   command=self._delete).pack(side="left", padx=4)

        cols = ("id", "staff", "type", "completed", "expires",
                 "status", "provider", "cert")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                  show="headings", height=22)
        for c, w, a in [
            ("id", 50, "e"), ("staff", 220, "w"),
            ("type", 150, "w"), ("completed", 100, "w"),
            ("expires", 100, "w"), ("status", 130, "w"),
            ("provider", 160, "w"), ("cert", 120, "w"),
        ]:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=w, anchor=a)
        for tag, (bg, fg) in _TRAINING_TAGS.items():
            self.tree.tag_configure(tag, background=bg, foreground=fg)
        self.tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tree.bind("<Double-1>", lambda _e: self._edit())

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(self.tree.item(sel[0], "values")[0])
        except (ValueError, IndexError):
            return None

    def _filters(self) -> dict:
        kw: dict = {}
        sl = self.f_staff.get()
        if sl:
            kw["staff_id"] = sl.split(" — ", 1)[0]
        if self.f_type.get():
            kw["training_type"] = self.f_type.get()
        scope = self.scope.get()
        if scope == "expired":
            kw["expired_only"] = True
        elif scope == "expiring":
            kw["expiring_within_days"] = 60
        return kw

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_training_with_detail(**self._filters())
        except ValidationError as e:
            _show_error(e)
            return
        for tr in rows:
            t = tr.training
            if t.expiry_date is None:
                tag, status_text = "no-expiry", "no expiry"
            elif tr.expired:
                tag, status_text = "expired", "EXPIRED"
            elif (tr.days_to_expiry or 0) <= 60:
                tag = "expiring"
                status_text = f"expires in {tr.days_to_expiry}d"
            else:
                tag, status_text = "ok", "in date"
            self.tree.insert("", "end", values=(
                t.training_id, f"{t.staff_id} — {tr.staff_name}",
                t.training_type, t.completed_date,
                t.expiry_date or "—", status_text,
                t.provider or "", t.certificate_ref or "",
            ), tags=(tag,))

    def _add(self) -> None:
        _TrainingDialog(self.frame, on_save=self.refresh)

    def _edit(self) -> None:
        tid = self._selected_id()
        if tid is None:
            messagebox.showinfo("Edit", "Select a training record first.")
            return
        existing = data.get_training(tid)
        if existing is None:
            messagebox.showerror("Edit", f"Training #{tid} not found.")
            return
        _TrainingDialog(self.frame, existing=existing,
                         on_save=self.refresh)

    def _delete(self) -> None:
        tid = self._selected_id()
        if tid is None:
            messagebox.showinfo("Delete",
                                "Select a training record first.")
            return
        if not messagebox.askyesno("Delete",
                                    f"Delete training record #{tid}?"):
            return
        if data.delete_training(tid):
            self.refresh()


class _TrainingDialog:
    def __init__(self, parent, *, existing: Training | None = None,
                 on_save=None) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Training"
                        + (f" #{existing.training_id}" if existing else ""))
        self.win.transient(parent.winfo_toplevel())
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        frm = ttk.Frame(self.win, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)

        t = self.existing
        ttk.Label(frm, text="Staff:").grid(row=0, column=0, sticky="w")
        self.staff = ttk.Combobox(frm, state="readonly", width=44)
        self.staff["values"] = [d for _i, d in _staff_options()]
        if t:
            for i, (sid, _d) in enumerate(_staff_options()):
                if sid == t.staff_id:
                    self.staff.current(i)
                    break
            self.staff.config(state="disabled")
        self.staff.grid(row=0, column=1, sticky="ew", pady=2)

        ttk.Label(frm, text="Type:").grid(row=1, column=0, sticky="w")
        self.ttype = ttk.Combobox(frm, state="readonly",
                                    values=TRAINING_TYPES, width=22)
        self.ttype.set(t.training_type if t else DEFAULT_TRAINING_TYPE)
        self.ttype.grid(row=1, column=1, sticky="w", pady=2)

        ttk.Label(frm, text="Completed:").grid(row=2, column=0, sticky="w")
        self.completed = ttk.Entry(frm, width=14)
        self.completed.insert(0,
                               t.completed_date if t else _today())
        self.completed.grid(row=2, column=1, sticky="w", pady=2)

        ttk.Label(frm, text="Expiry:").grid(row=3, column=0, sticky="w")
        self.expiry = ttk.Entry(frm, width=14)
        if t and t.expiry_date:
            self.expiry.insert(0, t.expiry_date)
        self.expiry.grid(row=3, column=1, sticky="w", pady=2)

        ttk.Label(frm, text="Provider:").grid(row=4, column=0, sticky="w")
        self.provider = ttk.Entry(frm)
        if t and t.provider:
            self.provider.insert(0, t.provider)
        self.provider.grid(row=4, column=1, sticky="ew", pady=2)

        ttk.Label(frm, text="Cert ref:").grid(row=5, column=0, sticky="w")
        self.cert = ttk.Entry(frm)
        if t and t.certificate_ref:
            self.cert.insert(0, t.certificate_ref)
        self.cert.grid(row=5, column=1, sticky="ew", pady=2)

        ttk.Label(frm, text="Notes:").grid(row=6, column=0,
                                             sticky="nw", pady=(6, 0))
        self.notes = tk.Text(frm, height=4, width=50)
        if t and t.notes:
            self.notes.insert("1.0", t.notes)
        self.notes.grid(row=6, column=1, sticky="ew", pady=(6, 0))

        btns = ttk.Frame(frm)
        btns.grid(row=7, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(btns, text="Cancel",
                    command=self.win.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="Save",
                    command=self._save).pack(side="right")

    def _payload(self) -> dict:
        staff_label = self.staff.get()
        sid = staff_label.split(" — ", 1)[0] if staff_label else ""
        return {
            "staff_id":        sid,
            "training_type":   self.ttype.get(),
            "completed_date":  self.completed.get().strip(),
            "expiry_date":     self.expiry.get().strip() or None,
            "provider":        self.provider.get().strip(),
            "certificate_ref": self.cert.get().strip(),
            "notes":           self.notes.get("1.0", "end").strip(),
        }

    def _save(self) -> None:
        try:
            if self.existing:
                data.update_training(self.existing.training_id,
                                      self._payload())
            else:
                data.create_training(self._payload())
        except ValidationError as e:
            _show_error(e)
            return
        if self.on_save:
            self.on_save()
        self.win.destroy()


# ── Summary tab ────────────────────────────────────────────────────

class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Overview")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh",
                   command=self.refresh).pack(side="left")

        self.totals_lbl = ttk.Label(
            self.frame, text="", justify="left", padding=10,
            font=("", 10))
        self.totals_lbl.pack(fill="x", padx=8)

        cols_frame = ttk.Frame(self.frame)
        cols_frame.pack(fill="both", expand=True, padx=8, pady=8)
        for i in range(3):
            cols_frame.columnconfigure(i, weight=1)
        cols_frame.rowconfigure(1, weight=1)

        ttk.Label(cols_frame, text="Concerns by status",
                  font=("", 10, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(cols_frame, text="Concerns by risk",
                  font=("", 10, "bold")).grid(row=0, column=1,
                                                 sticky="w", padx=(8, 0))
        ttk.Label(cols_frame, text="Referrals by status",
                  font=("", 10, "bold")).grid(row=0, column=2,
                                                 sticky="w", padx=(8, 0))

        def _bytable(parent, grid_col):
            tv = ttk.Treeview(parent, columns=("k", "v"),
                               show="headings", height=14)
            tv.heading("k", text="Category")
            tv.heading("v", text="Count")
            tv.column("k", width=200, anchor="w")
            tv.column("v", width=70, anchor="e")
            tv.grid(row=1, column=grid_col, sticky="nsew",
                    pady=(4, 0),
                    padx=(0 if grid_col == 0 else 8, 0))
            return tv

        self.tv_status = _bytable(cols_frame, 0)
        self.tv_risk = _bytable(cols_frame, 1)
        self.tv_referrals = _bytable(cols_frame, 2)

    def refresh(self) -> None:
        s = data.summary()
        self.totals_lbl.config(text=(
            f"Concerns: {s.total_concerns}    "
            f"(open {s.concerns_open}, "
            f"high-risk open {s.high_risk_open})\n"
            f"Referrals: {s.total_referrals}    "
            f"(open {s.referrals_open})\n"
            f"Training: {s.total_training}    "
            f"(expired {s.training_expired}, "
            f"expiring ≤60d {s.training_expiring_soon}, "
            f"staff covered {s.staff_with_training})"
        ))
        for tv, dct in [
            (self.tv_status, s.concerns_by_status),
            (self.tv_risk, s.concerns_by_risk),
            (self.tv_referrals, s.referrals_by_status),
        ]:
            for i in tv.get_children():
                tv.delete(i)
            for k, v in dct.items():
                if v:
                    tv.insert("", "end", values=(k, v))
