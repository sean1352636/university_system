"""Tkinter views for Sixth Form Fees."""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, ttk
from typing import Callable
from education_system.sixthform_system.modules.domain.finance.fees import fees
from education_system.sixthform_system.modules.domain.finance.fees import fees as data
from education_system.sixthform_system.modules.domain.students.students import students as student_data
from education_system.shared import branding
from education_system.sixthform_system.modules.domain.finance.fees.fees import (
    CATEGORIES,
    CURRENCY_SYMBOL,
    DEFAULT_CATEGORY,
    DEFAULT_METHOD,
    DEFAULT_PAYMENT_STATUS,
    FeeItem,
    PAYMENT_METHODS,
    PAYMENT_STATUSES,
    Payment,
    STATUSES,
    STORED_STATUSES,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_fees_window(parent=None) -> None:
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Fees — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)
    build_fees_notebook(win)


def build_fees_notebook(parent: tk.Misc) -> ttk.Notebook:
    """Build the Fees notebook into *parent* (a Toplevel or Frame).

    Shared by the standalone window and the unified Finance hub so both
    surface the exact same tabs.
    """
    data.init_db()
    nb = ttk.Notebook(parent)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    FeesTab(nb)
    PaymentsTab(nb)
    StatementTab(nb)
    SummaryTab(nb)
    return nb


# ── Shared helpers ────────────────────────────────────────────────

def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}") for s in rows]


def _student_names() -> dict[str, str]:
    return {s.student_id: s.full_name for s in student_data.list_students()}


def _money(v: float) -> str:
    sign = "-" if v < 0 else ""
    return f"{sign}{CURRENCY_SYMBOL}{abs(v):.2f}"


# ══ Fees tab ═══════════════════════════════════════════════════════

class FeesTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Fees")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Student:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Category:").pack(side="left")
        self.f_cat = ttk.Combobox(bar, values=("",) + CATEGORIES,
                                     state="readonly", width=18)
        self.f_cat.current(0)
        self.f_cat.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + STATUSES,
                                        state="readonly", width=14)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Year:").pack(side="left")
        self.f_year = ttk.Entry(bar, width=10)
        self.f_year.pack(side="left", padx=(2, 10))
        self.f_active = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Active only",
                          variable=self.f_active,
                          command=self.refresh).pack(side="left")
        self.f_overdue = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Overdue only",
                          variable=self.f_overdue,
                          command=self.refresh).pack(side="left", padx=(8, 0))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(10, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "student", "name", "category", "issued",
                "due", "amount", "paid", "balance", "status",
                "description")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = {"id": 50, "student": 90, "name": 180, "category": 110,
                  "issued": 90, "due": 90, "amount": 80, "paid": 80,
                  "balance": 80, "status": 100, "description": 320}
        headings = {"id": "#", "student": "Student", "name": "Name",
                    "category": "Category", "issued": "Issued",
                    "due": "Due", "amount": "Amount", "paid": "Paid",
                    "balance": "Balance", "status": "Status",
                    "description": "Description"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "e" if c in ("amount", "paid", "balance") else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Overdue", background="#ffd0d0")
        self.tree.tag_configure("Paid", foreground="#888")
        self.tree.tag_configure("Waived", foreground="#888",
                                  background="#f4f4f4")
        self.tree.tag_configure("Written-Off", foreground="#888",
                                  background="#f4f4f4")
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
        ttk.Button(bar, text="Add Payment",
                    command=self._add_payment).pack(side="left", padx=4)
        ttk.Button(bar, text="Stored Status",
                    command=self._set_stored).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.f_student.delete(0, "end")
        self.f_cat.current(0)
        self.f_status.current(0)
        self.f_year.delete(0, "end")
        self.f_active.set(False)
        self.f_overdue.set(False)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_views(
                student_id=self.f_student.get().strip() or None,
                category=self.f_cat.get() or None,
                academic_year=self.f_year.get().strip() or None,
                effective_status=self.f_status.get() or None,
                active_only=self.f_active.get(),
                overdue_only=self.f_overdue.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        total_amt = total_paid = total_bal = 0.0
        for v in rows:
            it = v.item
            total_amt  += it.amount
            total_paid += v.paid
            total_bal  += v.balance if v.is_active else 0
            tags = (v.effective_status,) if v.effective_status in (
                "Overdue", "Paid", "Waived", "Written-Off") else ()
            self.tree.insert("", "end", iid=str(it.fee_id), values=(
                it.fee_id, it.student_id, v.student_name,
                it.category, it.issued_date, it.due_date or "—",
                _money(it.amount), _money(v.paid),
                _money(v.balance), v.effective_status,
                it.description,
            ), tags=tags)
        self.totals_var.set(
            f"{len(rows)} fee(s).  "
            f"Charged: {_money(round(total_amt, 2))}    "
            f"Paid: {_money(round(total_paid, 2))}    "
            f"Outstanding (active): {_money(round(total_bal, 2))}")
        self._build_actions()

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _view_selected(self) -> None:
        fid = self._selected_id()
        if fid is None:
            messagebox.showinfo("View", "Select a fee first.")
            return
        v = data.view_item(fid)
        if v is None:
            return
        it = v.item
        lines = [
            f"Fee        : #{it.fee_id}",
            f"Student    : {it.student_id} — {v.student_name}",
            f"Description: {it.description}",
            f"Category   : {it.category}",
            f"Year       : {it.academic_year or '—'}",
            f"Issued     : {it.issued_date}",
            f"Due        : {it.due_date or '—'}",
            "",
            f"Amount     : {_money(it.amount)}",
            f"Paid       : {_money(v.paid)}",
            f"Balance    : {_money(v.balance)}",
            f"Status     : {v.effective_status}",
        ]
        if it.stored_status:
            lines.append(f"Stored     : {it.stored_status}")
        if it.notes:
            lines.extend(["", "Notes:", it.notes])
        payments = data.list_payments(fee_id=fid)
        if payments:
            lines.extend(["", f"Payments ({len(payments)}):"])
            for p in payments:
                lines.append(
                    f"  #{p.payment_id}  {p.paid_on}  "
                    f"{_money(p.amount)}  {p.method:<12}  {p.status}"
                    + (f"  ref={p.reference}" if p.reference else ""))
        messagebox.showinfo(f"Fee #{it.fee_id}", "\n".join(lines))

    def _new(self) -> None:
        FeeDialog(self.frame.winfo_toplevel(), existing=None,
                   on_save=self.refresh)

    def _edit_selected(self) -> None:
        fid = self._selected_id()
        if fid is None:
            messagebox.showinfo("Edit", "Select a fee first.")
            return
        it = data.get_item(fid)
        if it is None:
            return
        FeeDialog(self.frame.winfo_toplevel(), existing=it,
                   on_save=self.refresh)

    def _add_payment(self) -> None:
        fid = self._selected_id()
        if fid is None:
            messagebox.showinfo("Payment", "Select a fee first.")
            return
        v = data.view_item(fid)
        if v is None:
            return
        PaymentDialog(self.frame.winfo_toplevel(), fee_view=v,
                        existing=None, on_save=self.refresh)

    def _set_stored(self) -> None:
        fid = self._selected_id()
        if fid is None:
            messagebox.showinfo("Stored Status",
                                  "Select a fee first.")
            return
        it = data.get_item(fid)
        if it is None:
            return
        StoredStatusDialog(self.frame.winfo_toplevel(),
                             fee=it, on_save=self.refresh)

    def _delete_selected(self) -> None:
        fid = self._selected_id()
        if fid is None:
            messagebox.showinfo("Delete", "Select a fee first.")
            return
        it = data.get_item(fid)
        if it is None:
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete fee #{fid} ({it.description!r})?\n\n"
                f"This will also delete its payments."):
            return
        try:
            data.delete_item(fid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


class FeeDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: FeeItem | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Fee" if existing else "New Fee")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        r = 0
        ttk.Label(form, text="Student:").grid(row=r, column=0,
                                                sticky="e", pady=3)
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

        ttk.Label(form, text="Description:").grid(row=r, column=0,
                                                    sticky="e", pady=3)
        self.desc_e = ttk.Entry(form, width=50)
        if self.existing:
            self.desc_e.insert(0, self.existing.description)
        self.desc_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Category:").grid(row=r, column=0,
                                                  sticky="e", pady=3)
        self.cat_cb = ttk.Combobox(form, values=CATEGORIES,
                                      state="readonly", width=22)
        self.cat_cb.set(self.existing.category if self.existing
                          else DEFAULT_CATEGORY)
        self.cat_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form,
                   text=f"Amount ({CURRENCY_SYMBOL}):").grid(
            row=r, column=0, sticky="e", pady=3)
        self.amount_e = ttk.Entry(form, width=12)
        if self.existing:
            self.amount_e.insert(0, f"{self.existing.amount:.2f}")
        self.amount_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Issued date:").grid(row=r, column=0,
                                                     sticky="e", pady=3)
        self.iss_e = ttk.Entry(form, width=14)
        self.iss_e.insert(0, self.existing.issued_date
                              if self.existing
                              else _date.today().isoformat())
        self.iss_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Due date:").grid(row=r, column=0,
                                                  sticky="e", pady=3)
        self.due_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.due_date:
            self.due_e.insert(0, self.existing.due_date)
        self.due_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Academic year:").grid(row=r, column=0,
                                                       sticky="e", pady=3)
        self.year_e = ttk.Entry(form, width=12)
        if self.existing and self.existing.academic_year:
            self.year_e.insert(0, self.existing.academic_year)
        self.year_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        if self.existing:
            ttk.Label(form, text="Stored status:").grid(row=r, column=0,
                                                         sticky="e", pady=3)
            self.stored_cb = ttk.Combobox(
                form, values=("(auto)",) + STORED_STATUSES,
                state="readonly", width=16)
            self.stored_cb.set(self.existing.stored_status
                                  if self.existing.stored_status
                                  else "(auto)")
            self.stored_cb.grid(row=r, column=1, sticky="w", padx=6)
            r += 1
        else:
            self.stored_cb = None

        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                              sticky="ne", pady=3)
        self.notes_text = tk.Text(form, width=50, height=4, wrap="word")
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
        stored_v = ""
        if self.stored_cb is not None:
            v = self.stored_cb.get()
            stored_v = "" if v == "(auto)" else v
        payload = {
            "student_id":    sid,
            "description":   self.desc_e.get().strip(),
            "category":      self.cat_cb.get(),
            "amount":        self.amount_e.get().strip(),
            "issued_date":   self.iss_e.get().strip(),
            "due_date":      self.due_e.get().strip(),
            "academic_year": self.year_e.get().strip(),
            "stored_status": stored_v,
            "notes":         self.notes_text.get("1.0", "end").strip(),
        }
        try:
            if self.existing:
                data.update_item(self.existing.fee_id, payload)
            else:
                data.create_item(payload)
        except ValidationError as e:
            messagebox.showerror("Validation", str(e))
            return
        except Exception as e:
            logger.exception("save fee failed")
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class PaymentDialog:
    def __init__(self, parent: tk.Misc, *,
                 fee_view: data.FeeView | None,
                 existing: Payment | None,
                 on_save: Callable[[], None]) -> None:
        self.fee_view = fee_view
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Payment" if existing else "Record Payment")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        r = 0
        if self.fee_view:
            it = self.fee_view.item
            ttk.Label(form,
                       text=f"Fee #{it.fee_id}  •  {it.description}\n"
                            f"Amount: {_money(it.amount)}    "
                            f"Paid: {_money(self.fee_view.paid)}    "
                            f"Balance: {_money(self.fee_view.balance)}",
                       justify="left",
                       foreground="#444").grid(
                row=r, column=0, columnspan=2, sticky="w", pady=(0, 8))
            r += 1
        elif self.existing:
            ttk.Label(form,
                       text=f"Editing payment for fee #"
                            f"{self.existing.fee_id}").grid(
                row=r, column=0, columnspan=2, sticky="w", pady=(0, 8))
            r += 1

        ttk.Label(form,
                   text=f"Amount ({CURRENCY_SYMBOL}):").grid(
            row=r, column=0, sticky="e", pady=3)
        self.amount_e = ttk.Entry(form, width=12)
        if self.existing:
            self.amount_e.insert(0, f"{self.existing.amount:.2f}")
        elif self.fee_view and self.fee_view.balance > 0:
            self.amount_e.insert(0, f"{self.fee_view.balance:.2f}")
        self.amount_e.grid(row=r, column=1, sticky="w", padx=6)
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
        self.method_cb = ttk.Combobox(form, values=PAYMENT_METHODS,
                                          state="readonly", width=18)
        self.method_cb.set(self.existing.method if self.existing
                              else DEFAULT_METHOD)
        self.method_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Status:").grid(row=r, column=0,
                                                sticky="e", pady=3)
        self.status_cb = ttk.Combobox(form, values=PAYMENT_STATUSES,
                                          state="readonly", width=14)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_PAYMENT_STATUS)
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
            "amount":      self.amount_e.get().strip(),
            "paid_on":     self.paid_e.get().strip(),
            "method":      self.method_cb.get(),
            "status":      self.status_cb.get(),
            "reference":   self.ref_e.get().strip(),
            "recorded_by": self.by_e.get().strip(),
            "notes":       self.notes_text.get("1.0", "end").strip(),
        }
        try:
            if self.existing:
                data.update_payment(self.existing.payment_id, payload)
            else:
                data.create_payment(self.fee_view.item.fee_id, payload)
        except ValidationError as e:
            messagebox.showerror("Validation", str(e))
            return
        except Exception as e:
            logger.exception("save payment failed")
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class StoredStatusDialog:
    def __init__(self, parent: tk.Misc, *,
                 fee: FeeItem,
                 on_save: Callable[[], None]) -> None:
        self.fee = fee
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Stored status — fee #{fee.fee_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        ttk.Label(form,
                   text="Use to mark this fee as waived, refunded, "
                        "written-off, or cancelled.\nLeave on '(auto)' "
                        "for normal lifecycle states."
                   ).grid(row=0, column=0, columnspan=2,
                            sticky="w", pady=(0, 8))
        ttk.Label(form, text="Stored status:").grid(row=1, column=0,
                                                       sticky="e", pady=3)
        self.cb = ttk.Combobox(form,
                                  values=("(auto)",) + STORED_STATUSES,
                                  state="readonly", width=18)
        self.cb.set(fee.stored_status if fee.stored_status else "(auto)")
        self.cb.grid(row=1, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=2, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        v = self.cb.get()
        try:
            data.set_stored_status(self.fee.fee_id,
                                     None if v == "(auto)" else v)
        except Exception as e:
            messagebox.showerror("Failed", str(e))
            return
        self.win.destroy()
        self.on_save()


# ══ Payments tab ═══════════════════════════════════════════════════

class PaymentsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Payments")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Student:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Method:").pack(side="left")
        self.f_method = ttk.Combobox(bar, values=("",) + PAYMENT_METHODS,
                                        state="readonly", width=16)
        self.f_method.current(0)
        self.f_method.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + PAYMENT_STATUSES,
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
        cols = ("id", "fee", "paid_on", "amount", "method",
                "status", "ref", "by", "notes")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = {"id": 50, "fee": 50, "paid_on": 100, "amount": 90,
                  "method": 130, "status": 90, "ref": 160, "by": 120,
                  "notes": 280}
        headings = {"id": "#", "fee": "Fee", "paid_on": "Paid on",
                    "amount": "Amount", "method": "Method",
                    "status": "Status", "ref": "Reference",
                    "by": "Recorded by", "notes": "Notes"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "e" if c == "amount" else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Failed", background="#ffe0e0")
        self.tree.tag_configure("Refunded", foreground="#888")
        self.tree.tag_configure("Pending", background="#fff7d0")
        self.tree.bind("<Double-1>", lambda _e: self._edit_selected())

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
                    command=self._edit_selected).pack(side="left")
        ttk.Button(bar, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.f_student.delete(0, "end")
        self.f_method.current(0)
        self.f_status.current(0)
        self.f_from.delete(0, "end")
        self.f_to.delete(0, "end")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_payments(
                student_id=self.f_student.get().strip() or None,
                method=self.f_method.get() or None,
                status=self.f_status.get() or None,
                date_from=self.f_from.get().strip() or None,
                date_to=self.f_to.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        cleared = 0.0
        for p in rows:
            tags = (p.status,) if p.status in (
                "Failed", "Refunded", "Pending") else ()
            if p.status == "Cleared":
                cleared += p.amount
            self.tree.insert("", "end", iid=str(p.payment_id), values=(
                p.payment_id, p.fee_id, p.paid_on,
                _money(p.amount), p.method, p.status,
                p.reference or "—", p.recorded_by or "—",
                (p.notes or "").replace("\n", " ⏎ "),
            ), tags=tags)
        self.totals_var.set(
            f"{len(rows)} payment(s).  "
            f"Cleared total: {_money(round(cleared, 2))}")
        self._build_actions()

    def _selected(self) -> Payment | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return data.get_payment(int(sel[0]))

    def _edit_selected(self) -> None:
        p = self._selected()
        if p is None:
            messagebox.showinfo("Edit", "Select a payment first.")
            return
        PaymentDialog(self.frame.winfo_toplevel(),
                        fee_view=None, existing=p,
                        on_save=self.refresh)

    def _delete_selected(self) -> None:
        p = self._selected()
        if p is None:
            messagebox.showinfo("Delete", "Select a payment first.")
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete payment #{p.payment_id} ({_money(p.amount)})?"):
            return
        try:
            data.delete_payment(p.payment_id)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


# ══ Statement tab ══════════════════════════════════════════════════

class StatementTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Statement")
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
        cols = ("id", "issued", "due", "category", "description",
                "amount", "paid", "balance", "status")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = {"id": 50, "issued": 100, "due": 100, "category": 130,
                  "description": 320, "amount": 90, "paid": 90,
                  "balance": 90, "status": 110}
        for c in cols:
            self.tree.heading(c, text=c.capitalize())
            anchor = "e" if c in ("amount", "paid", "balance") else "w"
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
        rows = data.statement(sid)
        student = student_data.get_student(sid)
        self.head_var.set(
            f"{sid} — {student.full_name if student else '?'}")
        total_amt = total_paid = 0.0
        outstanding = 0.0
        for v in rows:
            it = v.item
            total_amt += it.amount
            total_paid += v.paid
            if v.is_active:
                outstanding += v.balance
            self.tree.insert("", "end", values=(
                it.fee_id, it.issued_date, it.due_date or "—",
                it.category, it.description,
                _money(it.amount), _money(v.paid),
                _money(v.balance), v.effective_status,
            ))
        self.totals_var.set(
            f"{len(rows)} fee(s)  •  Charged "
            f"{_money(round(total_amt, 2))}  •  Paid "
            f"{_money(round(total_paid, 2))}  •  Outstanding "
            f"{_money(round(outstanding, 2))}")


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
        L.append("Totals")
        L.append("------")
        L.append(f"  Items charged     : {s.total_items}")
        L.append(f"  Total charged     : {_money(s.total_charged)}")
        L.append(f"  Total paid        : {_money(s.total_paid)}")
        L.append(f"  Outstanding       : {_money(s.total_outstanding)}")
        L.append(f"  Overdue items     : {s.overdue_count}  "
                  f"({_money(s.overdue_total)})")
        L.append(f"  Active students   : {s.active_students}")
        L.append(f"  Written off       : {_money(s.written_off)}")
        L.append(f"  Waived            : {_money(s.waived)}")
        L.append(f"  Refunded payments : {_money(s.refunded_payments)}")
        L.append("")
        L.append("By status")
        L.append("---------")
        for st in STATUSES:
            n = s.by_status.get(st, 0)
            if n:
                L.append(f"  {st:<14} : {n}")
        L.append("")
        L.append("Charges by category")
        L.append("-------------------")
        for c in CATEGORIES:
            v = s.by_category.get(c, 0.0)
            if v:
                L.append(f"  {c:<18} : {_money(v)}")
        L.append("")
        L.append("Payments by method")
        L.append("------------------")
        for m in PAYMENT_METHODS:
            v = s.by_method.get(m, 0.0)
            if v:
                L.append(f"  {m:<18} : {_money(v)}")
        if s.top_debtors:
            L.append("")
            L.append("Top debtors")
            L.append("-----------")
            for sid, name, bal in s.top_debtors:
                L.append(f"  {sid}  {name[:24]:<24}  {_money(bal)}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(L))
        self.text.configure(state="disabled")
