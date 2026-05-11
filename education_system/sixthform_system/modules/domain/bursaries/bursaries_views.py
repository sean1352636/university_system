"""Tkinter views for Sixth Form Bursary Applications."""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, ttk
from typing import Callable
from education_system.sixthform_system.modules.domain.bursaries import bursaries
from education_system.sixthform_system.modules.domain.staff import staff
from education_system.sixthform_system.modules.domain.students import students as data
from education_system.sixthform_system.modules.domain.staff import staff as staff_data
from education_system.sixthform_system.modules.domain.students import students as student_data
from education_system.sixthform_system.modules.domain.bursaries.bursaries import (
    Application,
    BURSARY_TYPES,
    CURRENCY_SYMBOL,
    DEFAULT_DISBURSEMENT_METHOD,
    DEFAULT_DISBURSEMENT_STATUS,
    DEFAULT_STATUS,
    DEFAULT_TYPE,
    Disbursement,
    DISBURSEMENT_METHODS,
    DISBURSEMENT_STATUSES,
    ELIGIBILITY_BASES,
    STATUSES,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_bursaries_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title("Bursary Applications — Sixth Form System")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)
    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    AppsTab(nb)
    DisbsTab(nb)
    PerStudentTab(nb)
    SummaryTab(nb)


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}") for s in rows]


def _staff_options() -> list[tuple[str, str]]:
    rows = sorted(staff_data.list_staff(active_only=True),
                   key=lambda s: (s.last_name, s.first_name))
    return [(t.staff_id,
              f"{t.staff_id} — {t.full_name} ({t.role})")
            for t in rows]


def _student_names() -> dict[str, str]:
    return {s.student_id: s.full_name for s in student_data.list_students()}


def _money(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{CURRENCY_SYMBOL}{v:.2f}"


# ══ Applications tab ═══════════════════════════════════════════════

class AppsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Applications")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Student:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = ttk.Combobox(bar, values=("",) + BURSARY_TYPES,
                                      state="readonly", width=24)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + STATUSES,
                                        state="readonly", width=18)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Year:").pack(side="left")
        self.f_year = ttk.Entry(bar, width=10)
        self.f_year.pack(side="left", padx=(2, 10))
        self.f_active = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Active only",
                          variable=self.f_active,
                          command=self.refresh).pack(side="left")
        self.f_approved = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Approved only",
                          variable=self.f_approved,
                          command=self.refresh).pack(side="left", padx=(8, 0))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(10, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "student", "name", "type", "applied", "year",
                "req", "awd", "paid", "rem", "status")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = {"id": 50, "student": 90, "name": 180, "type": 180,
                  "applied": 90, "year": 80, "req": 80, "awd": 80,
                  "paid": 80, "rem": 80, "status": 130}
        headings = {"id": "#", "student": "Student", "name": "Name",
                    "type": "Type", "applied": "Applied", "year": "Year",
                    "req": "Requested", "awd": "Awarded", "paid": "Paid",
                    "rem": "Remaining", "status": "Status"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "e" if c in ("req", "awd", "paid", "rem") else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Approved", background="#e6f7e0")
        self.tree.tag_configure("Partially Paid", background="#e6f7e0")
        self.tree.tag_configure("Paid in Full", foreground="#666",
                                  background="#f0f6ee")
        self.tree.tag_configure("Rejected", foreground="#888",
                                  background="#f5f5f5")
        self.tree.tag_configure("Cancelled", foreground="#888")
        self.tree.tag_configure("Withdrawn", foreground="#888")
        self.tree.bind("<Double-1>", lambda _e: self._view_selected())

        self.totals_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.totals_var,
                   anchor="w").pack(fill="x", padx=8)

        self.actions_holder = ttk.Frame(self.frame)
        self.actions_holder.pack(fill="x", padx=8, pady=(4, 8))
        self._build_actions()

    def _build_actions(self) -> None:
        for w in self.actions_holder.winfo_children():
            w.destroy()
        bar = ttk.Frame(self.actions_holder)
        bar.pack(fill="x")
        ttk.Button(bar, text="View",
                    command=self._view_selected).pack(side="left")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=4)
        ttk.Button(bar, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Approve",
                    command=self._approve).pack(side="left", padx=4)
        ttk.Button(bar, text="Reject",
                    command=self._reject).pack(side="left", padx=4)
        ttk.Button(bar, text="Add Disbursement",
                    command=self._add_disb).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.f_student.delete(0, "end")
        self.f_type.current(0)
        self.f_status.current(0)
        self.f_year.delete(0, "end")
        self.f_active.set(False)
        self.f_approved.set(False)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_views(
                student_id=self.f_student.get().strip() or None,
                bursary_type=self.f_type.get() or None,
                status=self.f_status.get() or None,
                academic_year=self.f_year.get().strip() or None,
                active_only=self.f_active.get(),
                approved_only=self.f_approved.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        req = awd = paid = rem = 0.0
        for v in rows:
            a = v.app
            if a.amount_requested: req += a.amount_requested
            if a.amount_awarded:   awd += a.amount_awarded
            paid += v.paid
            rem  += v.remaining if a.is_approved else 0
            tags = (a.status,) if a.status in (
                "Approved", "Partially Paid", "Paid in Full",
                "Rejected", "Cancelled", "Withdrawn") else ()
            self.tree.insert("", "end", iid=str(a.application_id), values=(
                a.application_id, a.student_id, v.student_name,
                a.bursary_type, a.application_date,
                a.academic_year or "—",
                _money(a.amount_requested), _money(a.amount_awarded),
                _money(v.paid), _money(v.remaining), a.status,
            ), tags=tags)
        self.totals_var.set(
            f"{len(rows)} application(s).  "
            f"Requested: {_money(round(req, 2))}    "
            f"Awarded: {_money(round(awd, 2))}    "
            f"Paid: {_money(round(paid, 2))}    "
            f"Remaining: {_money(round(rem, 2))}")
        self._build_actions()

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _view_selected(self) -> None:
        aid = self._selected_id()
        if aid is None:
            messagebox.showinfo("View", "Select an application first.")
            return
        v = data.view_application(aid)
        if v is None:
            return
        a = v.app
        lines = [
            f"Application : #{a.application_id}",
            f"Student     : {a.student_id} — {v.student_name}",
            f"Type        : {a.bursary_type}",
            f"Year        : {a.academic_year or '—'}",
            f"Applied     : {a.application_date}",
            f"Status      : {a.status}",
            f"Basis       : {a.eligibility_basis or '—'}",
            f"Household   : "
            f"income {_money(a.household_income)}, "
            f"size {a.household_size or '—'}",
            f"Evidence    : "
            f"{'Yes' if a.evidence_received else 'No'}"
            + (f"  ({a.evidence_note})" if a.evidence_note else ""),
            "",
            f"Requested   : {_money(a.amount_requested)}",
            f"Awarded     : {_money(a.amount_awarded)}",
            f"Paid        : {_money(v.paid)}",
            f"Remaining   : {_money(v.remaining)}",
        ]
        if a.assessed_by:
            lines.append(f"Assessed by : {a.assessed_by}  "
                          f"on {a.assessed_on or '—'}")
        if a.reason:
            lines.extend(["", "Reason:", a.reason])
        if a.decision_note:
            lines.extend(["", "Decision note:", a.decision_note])
        if a.notes:
            lines.extend(["", "Notes:", a.notes])
        disbs = data.list_disbursements(application_id=aid)
        if disbs:
            lines.extend(["", f"Disbursements ({len(disbs)}):"])
            for d in disbs:
                lines.append(
                    f"  #{d.disbursement_id}  {d.paid_on}  "
                    f"{_money(d.amount)}  {d.method:<16}  {d.status}"
                    + (f"  ref={d.reference}" if d.reference else ""))
        messagebox.showinfo(
            f"Application #{a.application_id}", "\n".join(lines))

    def _new(self) -> None:
        ApplicationDialog(self.frame.winfo_toplevel(),
                            existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        aid = self._selected_id()
        if aid is None:
            messagebox.showinfo("Edit", "Select an application first.")
            return
        a = data.get_application(aid)
        if a is None:
            return
        ApplicationDialog(self.frame.winfo_toplevel(),
                            existing=a, on_save=self.refresh)

    def _approve(self) -> None:
        aid = self._selected_id()
        if aid is None:
            messagebox.showinfo("Approve",
                                  "Select an application first.")
            return
        a = data.get_application(aid)
        if a is None:
            return
        ApproveDialog(self.frame.winfo_toplevel(), app=a,
                        on_save=self.refresh)

    def _reject(self) -> None:
        aid = self._selected_id()
        if aid is None:
            messagebox.showinfo("Reject",
                                  "Select an application first.")
            return
        a = data.get_application(aid)
        if a is None:
            return
        RejectDialog(self.frame.winfo_toplevel(), app=a,
                       on_save=self.refresh)

    def _add_disb(self) -> None:
        aid = self._selected_id()
        if aid is None:
            messagebox.showinfo("Disbursement",
                                  "Select an application first.")
            return
        v = data.view_application(aid)
        if v is None:
            return
        if not v.app.is_approved:
            messagebox.showerror(
                "Disbursement",
                "Disbursements can only be added to approved "
                "applications.")
            return
        DisbursementDialog(self.frame.winfo_toplevel(),
                              app_view=v, existing=None,
                              on_save=self.refresh)

    def _delete(self) -> None:
        aid = self._selected_id()
        if aid is None:
            messagebox.showinfo("Delete",
                                  "Select an application first.")
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete application #{aid}?\n\n"
                f"This also deletes all its disbursements."):
            return
        try:
            data.delete_application(aid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


class ApplicationDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: Application | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Application" if existing
                          else "New Application")
        self.win.transient(parent)
        self.win.grab_set()
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        r = 0

        def label(t: str):
            nonlocal r
            ttk.Label(form, text=t).grid(row=r, column=0,
                                           sticky="e", pady=3)

        label("Student:")
        if self.existing:
            self.student_cb = None
            self._student_id = self.existing.student_id
            names = _student_names()
            ttk.Label(form,
                       text=f"{self._student_id} — "
                            f"{names.get(self._student_id, '?')}"
                       ).grid(row=r, column=1, sticky="w", padx=6)
        else:
            opts = _student_options()
            self._student_ids = [s for s, _ in opts]
            self.student_cb = ttk.Combobox(
                form, values=[l for _, l in opts],
                state="readonly", width=40)
            if opts:
                self.student_cb.current(0)
            self.student_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Bursary type:")
        self.type_cb = ttk.Combobox(form, values=BURSARY_TYPES,
                                       state="readonly", width=26)
        self.type_cb.set(self.existing.bursary_type if self.existing
                            else DEFAULT_TYPE)
        self.type_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Academic year:")
        self.year_e = ttk.Entry(form, width=12)
        if self.existing and self.existing.academic_year:
            self.year_e.insert(0, self.existing.academic_year)
        self.year_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Applied:")
        self.applied_e = ttk.Entry(form, width=14)
        self.applied_e.insert(0, self.existing.application_date
                                   if self.existing
                                   else _date.today().isoformat())
        self.applied_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label(f"Requested ({CURRENCY_SYMBOL}):")
        self.req_e = ttk.Entry(form, width=12)
        if (self.existing and
                self.existing.amount_requested is not None):
            self.req_e.insert(0,
                                f"{self.existing.amount_requested:.2f}")
        self.req_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label(f"Awarded ({CURRENCY_SYMBOL}):")
        self.awd_e = ttk.Entry(form, width=12)
        if (self.existing and
                self.existing.amount_awarded is not None):
            self.awd_e.insert(0, f"{self.existing.amount_awarded:.2f}")
        self.awd_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Status:")
        self.status_cb = ttk.Combobox(form, values=STATUSES,
                                          state="readonly", width=18)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_STATUS)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Eligibility basis:")
        self.basis_cb = ttk.Combobox(
            form, values=("(none)",) + ELIGIBILITY_BASES,
            state="readonly", width=32)
        seed = (self.existing.eligibility_basis
                 if self.existing and self.existing.eligibility_basis
                 else "(none)")
        self.basis_cb.set(seed)
        self.basis_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label(f"Household income ({CURRENCY_SYMBOL}):")
        self.hi_e = ttk.Entry(form, width=12)
        if (self.existing and
                self.existing.household_income is not None):
            self.hi_e.insert(0,
                                f"{self.existing.household_income:.2f}")
        self.hi_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Household size:")
        self.hs_e = ttk.Entry(form, width=8)
        if (self.existing and
                self.existing.household_size is not None):
            self.hs_e.insert(0, str(self.existing.household_size))
        self.hs_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Evidence:")
        self.ev_var = tk.BooleanVar(
            value=self.existing.evidence_received
                  if self.existing else False)
        ttk.Checkbutton(form, text="Received",
                          variable=self.ev_var).grid(
            row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Evidence note:")
        self.ev_e = ttk.Entry(form, width=50)
        if self.existing and self.existing.evidence_note:
            self.ev_e.insert(0, self.existing.evidence_note)
        self.ev_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Reason:")
        self.reason_text = tk.Text(form, width=50, height=3,
                                       wrap="word")
        if self.existing and self.existing.reason:
            self.reason_text.insert("1.0", self.existing.reason)
        self.reason_text.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Assessed by (staff ID):")
        self.by_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.assessed_by:
            self.by_e.insert(0, self.existing.assessed_by)
        self.by_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Assessed on:")
        self.on_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.assessed_on:
            self.on_e.insert(0, self.existing.assessed_on)
        self.on_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Decision note:")
        self.dec_text = tk.Text(form, width=50, height=3, wrap="word")
        if self.existing and self.existing.decision_note:
            self.dec_text.insert("1.0", self.existing.decision_note)
        self.dec_text.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Notes:")
        self.notes_text = tk.Text(form, width=50, height=3, wrap="word")
        if self.existing and self.existing.notes:
            self.notes_text.insert("1.0", self.existing.notes)
        self.notes_text.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        if self.student_cb is not None:
            idx = self.student_cb.current()
            if idx < 0:
                messagebox.showerror("Validation", "Pick a student.")
                return
            sid = self._student_ids[idx]
        else:
            sid = self._student_id
        basis = self.basis_cb.get()
        payload = {
            "student_id":       sid,
            "bursary_type":     self.type_cb.get(),
            "academic_year":    self.year_e.get().strip(),
            "application_date": self.applied_e.get().strip(),
            "amount_requested": self.req_e.get().strip(),
            "amount_awarded":   self.awd_e.get().strip(),
            "status":           self.status_cb.get(),
            "eligibility_basis": "" if basis == "(none)" else basis,
            "household_income": self.hi_e.get().strip(),
            "household_size":   self.hs_e.get().strip(),
            "evidence_received": self.ev_var.get(),
            "evidence_note":    self.ev_e.get().strip(),
            "reason":           self.reason_text.get("1.0",
                                                        "end").strip(),
            "assessed_by":      self.by_e.get().strip(),
            "assessed_on":      self.on_e.get().strip(),
            "decision_note":    self.dec_text.get("1.0",
                                                     "end").strip(),
            "notes":            self.notes_text.get("1.0",
                                                       "end").strip(),
        }
        try:
            if self.existing:
                data.update_application(
                    self.existing.application_id, payload)
            else:
                data.create_application(payload)
        except ValidationError as e:
            messagebox.showerror("Validation", str(e))
            return
        except Exception as e:
            logger.exception("save application failed")
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class ApproveDialog:
    def __init__(self, parent: tk.Misc, *,
                 app: Application,
                 on_save: Callable[[], None]) -> None:
        self.app = app
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Approve #{app.application_id}")
        self.win.transient(parent)
        self.win.grab_set()
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        ttk.Label(form,
                   text=f"Approving #{app.application_id} for "
                        f"{app.student_id} — {app.bursary_type}"
                   ).grid(row=0, column=0, columnspan=2,
                            sticky="w", pady=(0, 8))
        ttk.Label(form,
                   text=f"Amount awarded ({CURRENCY_SYMBOL}):").grid(
            row=1, column=0, sticky="e", pady=3)
        self.amt_e = ttk.Entry(form, width=14)
        if app.amount_requested:
            self.amt_e.insert(0, f"{app.amount_requested:.2f}")
        self.amt_e.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Assessed by:").grid(row=2, column=0,
                                                     sticky="e", pady=3)
        opts = _staff_options()
        labels = ["(none)"] + [l for _, l in opts]
        ids = [None] + [s for s, _ in opts]
        self._ids = ids
        self.by_cb = ttk.Combobox(form, values=labels,
                                      state="readonly", width=40)
        self.by_cb.current(0)
        self.by_cb.grid(row=2, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Decision note:").grid(row=3, column=0,
                                                       sticky="ne", pady=3)
        self.note_text = tk.Text(form, width=50, height=4, wrap="word")
        self.note_text.grid(row=3, column=1, sticky="w", padx=6)

        bar = ttk.Frame(form)
        bar.grid(row=4, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Approve",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        amt = self.amt_e.get().strip()
        if not amt:
            messagebox.showerror("Validation",
                                  "Awarded amount is required.")
            return
        idx = self.by_cb.current()
        by = self._ids[idx] if idx > 0 else None
        note = self.note_text.get("1.0", "end").strip() or None
        try:
            data.approve(self.app.application_id, float(amt),
                          by, note)
        except (ValidationError, ValueError) as e:
            messagebox.showerror("Approve failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class RejectDialog:
    def __init__(self, parent: tk.Misc, *,
                 app: Application,
                 on_save: Callable[[], None]) -> None:
        self.app = app
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Reject #{app.application_id}")
        self.win.transient(parent)
        self.win.grab_set()
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        ttk.Label(form,
                   text=f"Rejecting #{app.application_id} — "
                        f"please record a reason.").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(form, text="Assessed by:").grid(row=1, column=0,
                                                     sticky="e", pady=3)
        opts = _staff_options()
        labels = ["(none)"] + [l for _, l in opts]
        ids = [None] + [s for s, _ in opts]
        self._ids = ids
        self.by_cb = ttk.Combobox(form, values=labels,
                                      state="readonly", width=40)
        self.by_cb.current(0)
        self.by_cb.grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Decision note (required):").grid(
            row=2, column=0, sticky="ne", pady=3)
        self.note_text = tk.Text(form, width=50, height=5, wrap="word")
        self.note_text.grid(row=2, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=3, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Reject",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        note = self.note_text.get("1.0", "end").strip()
        if not note:
            messagebox.showerror("Validation",
                                  "Decision note is required.")
            return
        idx = self.by_cb.current()
        by = self._ids[idx] if idx > 0 else None
        try:
            data.reject(self.app.application_id, note, by)
        except ValidationError as e:
            messagebox.showerror("Reject failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class DisbursementDialog:
    def __init__(self, parent: tk.Misc, *,
                 app_view: data.ApplicationView | None,
                 existing: Disbursement | None,
                 on_save: Callable[[], None]) -> None:
        self.app_view = app_view
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Disbursement" if existing
                          else "Add Disbursement")
        self.win.transient(parent)
        self.win.grab_set()
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        r = 0
        if self.app_view:
            v = self.app_view
            ttk.Label(form,
                       text=f"Application #{v.app.application_id}  "
                            f"({v.app.bursary_type})\n"
                            f"Awarded: {_money(v.app.amount_awarded)}    "
                            f"Paid: {_money(v.paid)}    "
                            f"Remaining: {_money(v.remaining)}",
                       justify="left", foreground="#444").grid(
                row=r, column=0, columnspan=2, sticky="w", pady=(0, 8))
            r += 1
        elif self.existing:
            ttk.Label(form,
                       text=f"Editing disbursement for "
                            f"app #{self.existing.application_id}").grid(
                row=r, column=0, columnspan=2, sticky="w", pady=(0, 8))
            r += 1

        ttk.Label(form,
                   text=f"Amount ({CURRENCY_SYMBOL}):").grid(
            row=r, column=0, sticky="e", pady=3)
        self.amt_e = ttk.Entry(form, width=12)
        if self.existing:
            self.amt_e.insert(0, f"{self.existing.amount:.2f}")
        elif self.app_view and self.app_view.remaining > 0:
            self.amt_e.insert(0, f"{self.app_view.remaining:.2f}")
        self.amt_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Paid on:").grid(row=r, column=0,
                                                sticky="e", pady=3)
        self.paid_e = ttk.Entry(form, width=14)
        self.paid_e.insert(0, self.existing.paid_on if self.existing
                                else _date.today().isoformat())
        self.paid_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Method:").grid(row=r, column=0,
                                                sticky="e", pady=3)
        self.method_cb = ttk.Combobox(form, values=DISBURSEMENT_METHODS,
                                          state="readonly", width=20)
        self.method_cb.set(self.existing.method if self.existing
                              else DEFAULT_DISBURSEMENT_METHOD)
        self.method_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Status:").grid(row=r, column=0,
                                                sticky="e", pady=3)
        self.status_cb = ttk.Combobox(form, values=DISBURSEMENT_STATUSES,
                                          state="readonly", width=14)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_DISBURSEMENT_STATUS)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Reference:").grid(row=r, column=0,
                                                  sticky="e", pady=3)
        self.ref_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.reference:
            self.ref_e.insert(0, self.existing.reference)
        self.ref_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Recorded by:").grid(row=r, column=0,
                                                    sticky="e", pady=3)
        self.by_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.recorded_by:
            self.by_e.insert(0, self.existing.recorded_by)
        self.by_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                              sticky="ne", pady=3)
        self.notes_text = tk.Text(form, width=40, height=3, wrap="word")
        if self.existing and self.existing.notes:
            self.notes_text.insert("1.0", self.existing.notes)
        self.notes_text.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        payload = {
            "amount":      self.amt_e.get().strip(),
            "paid_on":     self.paid_e.get().strip(),
            "method":      self.method_cb.get(),
            "status":      self.status_cb.get(),
            "reference":   self.ref_e.get().strip(),
            "recorded_by": self.by_e.get().strip(),
            "notes":       self.notes_text.get("1.0", "end").strip(),
        }
        try:
            if self.existing:
                data.update_disbursement(
                    self.existing.disbursement_id, payload)
            else:
                data.add_disbursement(
                    self.app_view.app.application_id, payload)
        except ValidationError as e:
            messagebox.showerror("Validation", str(e))
            return
        except Exception as e:
            logger.exception("save disbursement failed")
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


# ══ Disbursements tab ══════════════════════════════════════════════

class DisbsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Disbursements")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Application ID:").pack(side="left")
        self.f_app = ttk.Entry(bar, width=8)
        self.f_app.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Student:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar,
                                        values=("",) + DISBURSEMENT_STATUSES,
                                        state="readonly", width=12)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="From:").pack(side="left")
        self.f_from = ttk.Entry(bar, width=12)
        self.f_from.pack(side="left", padx=(2, 6))
        ttk.Label(bar, text="To:").pack(side="left")
        self.f_to = ttk.Entry(bar, width=12)
        self.f_to.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "app", "paid_on", "amount", "method",
                "status", "ref", "by", "notes")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = {"id": 50, "app": 50, "paid_on": 100, "amount": 90,
                  "method": 150, "status": 90, "ref": 160, "by": 120,
                  "notes": 280}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").capitalize())
            anchor = "e" if c == "amount" else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Pending", background="#fff7d0")
        self.tree.tag_configure("Failed", background="#ffe0e0")
        self.tree.tag_configure("Reversed", foreground="#888")
        self.tree.bind("<Double-1>", lambda _e: self._edit())

        self.totals_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.totals_var,
                   anchor="w").pack(fill="x", padx=8)

        self.actions_holder = ttk.Frame(self.frame)
        self.actions_holder.pack(fill="x", padx=8, pady=(4, 8))
        self._build_actions()

    def _build_actions(self) -> None:
        for w in self.actions_holder.winfo_children():
            w.destroy()
        bar = ttk.Frame(self.actions_holder)
        bar.pack(fill="x")
        ttk.Button(bar, text="Edit",
                    command=self._edit).pack(side="left")
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.f_app.delete(0, "end")
        self.f_student.delete(0, "end")
        self.f_status.current(0)
        self.f_from.delete(0, "end")
        self.f_to.delete(0, "end")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            aid = self.f_app.get().strip()
            rows = data.list_disbursements(
                application_id=int(aid) if aid else None,
                student_id=self.f_student.get().strip() or None,
                status=self.f_status.get() or None,
                date_from=self.f_from.get().strip() or None,
                date_to=self.f_to.get().strip() or None,
            )
        except (ValidationError, ValueError) as e:
            messagebox.showerror("Filter error", str(e))
            return
        paid_total = 0.0
        for d in rows:
            tags = (d.status,) if d.status in (
                "Pending", "Failed", "Reversed") else ()
            if d.status == "Paid":
                paid_total += d.amount
            self.tree.insert("", "end", iid=str(d.disbursement_id),
                                values=(
                d.disbursement_id, d.application_id, d.paid_on,
                _money(d.amount), d.method, d.status,
                d.reference or "—", d.recorded_by or "—",
                (d.notes or "").replace("\n", " ⏎ "),
            ), tags=tags)
        self.totals_var.set(
            f"{len(rows)} disbursement(s).  "
            f"Paid total: {_money(round(paid_total, 2))}")
        self._build_actions()

    def _selected(self) -> Disbursement | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return data.get_disbursement(int(sel[0]))

    def _edit(self) -> None:
        d = self._selected()
        if d is None:
            messagebox.showinfo("Edit", "Select a disbursement first.")
            return
        v = data.view_application(d.application_id)
        DisbursementDialog(self.frame.winfo_toplevel(),
                              app_view=v, existing=d,
                              on_save=self.refresh)

    def _delete(self) -> None:
        d = self._selected()
        if d is None:
            messagebox.showinfo("Delete", "Select a disbursement first.")
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete disbursement #{d.disbursement_id} "
                f"({_money(d.amount)})?"):
            return
        try:
            data.delete_disbursement(d.disbursement_id)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


# ══ Per-Student tab ════════════════════════════════════════════════

class PerStudentTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Per-Student")
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Student:").pack(side="left")
        opts = _student_options()
        self._ids = [s for s, _ in opts]
        self.cb = ttk.Combobox(bar, values=[l for _, l in opts],
                                  state="readonly", width=40)
        if opts:
            self.cb.current(0)
        self.cb.pack(side="left", padx=6)
        ttk.Button(bar, text="Load",
                    command=self._load).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh roster",
                    command=self._refresh_roster).pack(side="left", padx=4)

        self.head_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.head_var,
                   anchor="w", font=("", 10, "bold")).pack(
            fill="x", padx=12)

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "type", "applied", "year", "req",
                "awd", "paid", "rem", "status")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = {"id": 50, "type": 180, "applied": 100, "year": 80,
                  "req": 90, "awd": 90, "paid": 90, "rem": 90,
                  "status": 130}
        for c in cols:
            self.tree.heading(c, text=c.capitalize())
            anchor = "e" if c in ("req", "awd", "paid", "rem") else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        self.totals_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.totals_var,
                   anchor="w").pack(fill="x", padx=12, pady=(0, 8))

    def _refresh_roster(self) -> None:
        opts = _student_options()
        self._ids = [s for s, _ in opts]
        self.cb["values"] = [l for _, l in opts]
        if opts:
            self.cb.current(0)

    def _load(self) -> None:
        idx = self.cb.current()
        if idx < 0:
            return
        sid = self._ids[idx]
        for i in self.tree.get_children():
            self.tree.delete(i)
        rows = data.list_views(student_id=sid)
        student = student_data.get_student(sid)
        self.head_var.set(
            f"{sid} — {student.full_name if student else '?'}")
        for v in rows:
            a = v.app
            self.tree.insert("", "end", values=(
                a.application_id, a.bursary_type, a.application_date,
                a.academic_year or "—",
                _money(a.amount_requested), _money(a.amount_awarded),
                _money(v.paid), _money(v.remaining), a.status,
            ))
        aw, pd, rm = data.student_summary(sid)
        self.totals_var.set(
            f"{len(rows)} application(s).  Awarded {_money(aw)}  "
            f"Paid {_money(pd)}  Remaining {_money(rm)}")


# ══ Summary tab ════════════════════════════════════════════════════

class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10), state="disabled")
        self.text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def refresh(self) -> None:
        s = data.summary()
        L: list[str] = []
        L.append("Pipeline")
        L.append("--------")
        L.append(f"  Total applications  : {s.total_applications}")
        L.append(f"  Submitted / Awaiting: {s.submitted}")
        L.append(f"  Under review        : {s.under_review}")
        L.append(f"  Approved (active)   : {s.approved_active}")
        L.append(f"  Paid in full        : {s.paid_in_full}")
        L.append(f"  Rejected            : {s.rejected}")
        L.append(f"  Cancelled / Withdrawn: {s.cancelled_withdrawn}")
        L.append("")
        L.append("Money")
        L.append("-----")
        L.append(f"  Total requested     : {_money(s.total_requested)}")
        L.append(f"  Total awarded       : {_money(s.total_awarded)}")
        L.append(f"  Total paid out      : {_money(s.total_paid)}")
        L.append(f"  Remaining commitment: {_money(s.total_remaining)}")
        if s.avg_award is not None:
            L.append(f"  Average award       : {_money(s.avg_award)}")
        L.append("")
        L.append("By type")
        L.append("-------")
        for t in BURSARY_TYPES:
            n = s.by_type.get(t, 0)
            if n:
                L.append(f"  {t:<28} : {n}")
        L.append("")
        L.append("By status")
        L.append("---------")
        for st in STATUSES:
            n = s.by_status.get(st, 0)
            if n:
                L.append(f"  {st:<18} : {n}")
        if any(s.by_basis.values()):
            L.append("")
            L.append("By eligibility basis")
            L.append("--------------------")
            for b in ELIGIBILITY_BASES:
                n = s.by_basis.get(b, 0)
                if n:
                    L.append(f"  {b:<32} : {n}")
        if s.top_recipients:
            L.append("")
            L.append("Top recipients")
            L.append("--------------")
            for sid, name, paid in s.top_recipients:
                L.append(f"  {sid}  {name[:24]:<24}  {_money(paid)}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(L))
        self.text.configure(state="disabled")
