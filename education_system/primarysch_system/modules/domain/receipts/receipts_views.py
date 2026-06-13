"""Tkinter views for Primary School Receipts."""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, ttk
from typing import Callable
from education_system.primarysch_system.modules.domain.receipts import receipts
from education_system.primarysch_system.modules.domain.receipts import receipts as data
from education_system.primarysch_system.modules.domain import _pupils_bridge as student_data
from education_system.shared import branding
from education_system.primarysch_system.modules.domain.receipts.receipts import (
    CURRENCY_SYMBOL,
    DEFAULT_LINE_KIND,
    DEFAULT_METHOD,
    DEFAULT_STATUS,
    LINE_KINDS,
    PAYMENT_METHODS,
    Receipt,
    ReceiptLine,
    STATUSES,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_receipts_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Receipts — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)
    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    ReceiptsTab(nb)
    ImportTab(nb)
    SummaryTab(nb)


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}") for s in rows]


def _money(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{CURRENCY_SYMBOL}{v:.2f}"


# ══ Receipts tab ═══════════════════════════════════════════════════

class ReceiptsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Receipts")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Search:").pack(side="left")
        self.q_e = ttk.Entry(bar, width=22)
        self.q_e.pack(side="left", padx=(2, 10))
        self.q_e.bind("<Return>", lambda _e: self.refresh())
        ttk.Label(bar, text="Student:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + STATUSES,
                                        state="readonly", width=10)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Method:").pack(side="left")
        self.f_method = ttk.Combobox(bar, values=("",) + PAYMENT_METHODS,
                                        state="readonly", width=16)
        self.f_method.current(0)
        self.f_method.pack(side="left", padx=(2, 10))
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
        cols = ("id", "number", "date", "student", "payer",
                "method", "total", "status", "ref")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = {"id": 50, "number": 130, "date": 100, "student": 90,
                  "payer": 220, "method": 130, "total": 100,
                  "status": 80, "ref": 200}
        headings = {"id": "#", "number": "Number", "date": "Issued",
                    "student": "Student", "payer": "Payer",
                    "method": "Method", "total": "Total",
                    "status": "Status", "ref": "Reference"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "e" if c == "total" else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Draft", foreground="#666",
                                  background="#f0f0f0")
        self.tree.tag_configure("Voided", foreground="#999",
                                  background="#fbeaea")
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
        ttk.Button(bar, text="Issue",
                    command=self._issue_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Void",
                    command=self._void_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete (Draft)",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.q_e.delete(0, "end")
        self.f_student.delete(0, "end")
        self.f_status.current(0)
        self.f_method.current(0)
        self.f_from.delete(0, "end")
        self.f_to.delete(0, "end")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        q = self.q_e.get().strip()
        try:
            if q:
                rows = data.search_receipts(q)
            else:
                rows = data.list_receipts(
                    student_id=self.f_student.get().strip() or None,
                    status=self.f_status.get() or None,
                    method=self.f_method.get() or None,
                    date_from=self.f_from.get().strip() or None,
                    date_to=self.f_to.get().strip() or None,
                )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        issued_t = voided_t = 0.0
        for r in rows:
            if r.status == "Issued":
                issued_t += r.total_amount
            elif r.status == "Voided":
                voided_t += r.total_amount
            tags = (r.status,) if r.status in ("Draft", "Voided") else ()
            self.tree.insert("", "end", iid=str(r.receipt_id), values=(
                r.receipt_id, r.receipt_number, r.issued_date,
                r.student_id or "—", r.payer_name,
                r.method, _money(r.total_amount), r.status,
                r.reference or "—",
            ), tags=tags)
        self.totals_var.set(
            f"{len(rows)} receipt(s).  "
            f"Issued: {_money(round(issued_t, 2))}    "
            f"Voided: {_money(round(voided_t, 2))}")
        self._build_actions()

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _view_selected(self) -> None:
        rid = self._selected_id()
        if rid is None:
            messagebox.showinfo("View", "Select a receipt first.")
            return
        ViewDialog(self.frame.winfo_toplevel(), rid)

    def _new(self) -> None:
        ReceiptDialog(self.frame.winfo_toplevel(),
                        existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        rid = self._selected_id()
        if rid is None:
            messagebox.showinfo("Edit", "Select a receipt first.")
            return
        r = data.get_receipt(rid)
        if r is None:
            return
        if r.is_voided:
            messagebox.showerror(
                "Edit", "Voided receipts cannot be edited.")
            return
        ReceiptDialog(self.frame.winfo_toplevel(),
                        existing=r, on_save=self.refresh)

    def _issue_selected(self) -> None:
        rid = self._selected_id()
        if rid is None:
            messagebox.showinfo("Issue", "Select a receipt first.")
            return
        r = data.get_receipt(rid)
        if r is None:
            return
        if r.is_issued:
            messagebox.showinfo("Issue",
                                  f"{r.receipt_number} is already Issued.")
            return
        if not messagebox.askyesno(
                "Issue",
                f"Issue {r.receipt_number} for "
                f"{_money(r.total_amount)}?\n\n"
                f"Once issued, only notes/reference/received-by "
                f"can be edited."):
            return
        try:
            data.issue(rid)
        except ValidationError as e:
            messagebox.showerror("Issue failed", str(e))
            return
        self.refresh()

    def _void_selected(self) -> None:
        rid = self._selected_id()
        if rid is None:
            messagebox.showinfo("Void", "Select a receipt first.")
            return
        r = data.get_receipt(rid)
        if r is None:
            return
        VoidDialog(self.frame.winfo_toplevel(), receipt=r,
                     on_save=self.refresh)

    def _delete_selected(self) -> None:
        rid = self._selected_id()
        if rid is None:
            messagebox.showinfo("Delete", "Select a receipt first.")
            return
        r = data.get_receipt(rid)
        if r is None:
            return
        if r.status != "Draft":
            messagebox.showerror(
                "Delete",
                f"Only Draft receipts can be deleted. "
                f"{r.receipt_number} is {r.status} — void it instead.")
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete draft {r.receipt_number}?"):
            return
        try:
            data.delete_receipt(rid)
        except ValidationError as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


class ViewDialog:
    def __init__(self, parent: tk.Misc, receipt_id: int) -> None:
        self.win = tk.Toplevel(parent)
        rv = data.view_receipt(receipt_id)
        if rv is None:
            self.win.destroy()
            return
        r = rv.receipt
        self.win.title(f"Receipt {r.receipt_number}")
        self.win.transient(parent)
        self.win.geometry("700x600")

        head = ttk.Frame(self.win)
        head.pack(fill="x", padx=12, pady=(12, 4))
        ttk.Label(head, text=r.receipt_number,
                   font=("", 14, "bold")).pack(side="left")
        ttk.Label(head, text=f"[{r.status}]",
                   foreground="#888").pack(side="right")

        info = ttk.Frame(self.win)
        info.pack(fill="x", padx=12)
        rows = [
            ("Issued",     r.issued_date),
            ("Payer",      r.payer_name),
            ("Student",    (f"{r.student_id} — {rv.student_name}"
                              if r.student_id and rv.student_name
                              else r.student_id or "—")),
            ("Method",     r.method),
            ("Received by", r.received_by or "—"),
            ("Reference",  r.reference or "—"),
        ]
        if r.is_voided:
            rows.append(("Voided at",   r.voided_at or "—"))
            rows.append(("Reason",      r.void_reason or "—"))
        for i, (k, v) in enumerate(rows):
            ttk.Label(info, text=f"{k}:",
                       foreground="#555").grid(row=i, column=0,
                                                 sticky="e", padx=(0, 6),
                                                 pady=1)
            ttk.Label(info, text=v).grid(row=i, column=1, sticky="w")

        ttk.Separator(self.win, orient="horizontal").pack(
            fill="x", padx=12, pady=8)

        table_frame = ttk.Frame(self.win)
        table_frame.pack(fill="both", expand=True, padx=12)
        cols = ("desc", "kind", "amount")
        tree = ttk.Treeview(table_frame, columns=cols, show="headings",
                              height=10)
        tree.heading("desc", text="Description")
        tree.heading("kind", text="Kind")
        tree.heading("amount", text="Amount")
        tree.column("desc", width=400, anchor="w")
        tree.column("kind", width=100, anchor="w")
        tree.column("amount", width=120, anchor="e")
        tree.pack(side="left", fill="both", expand=True)
        for l in rv.lines:
            tree.insert("", "end", values=(
                l.description, l.kind, _money(l.amount),
            ))

        total = ttk.Frame(self.win)
        total.pack(fill="x", padx=12, pady=8)
        ttk.Label(total, text="TOTAL",
                   font=("", 12, "bold")).pack(side="left")
        ttk.Label(total, text=_money(r.total_amount),
                   font=("", 12, "bold")).pack(side="right")

        if r.notes:
            sep = ttk.Separator(self.win, orient="horizontal")
            sep.pack(fill="x", padx=12, pady=4)
            ttk.Label(self.win, text="Notes:",
                       foreground="#555").pack(anchor="w", padx=12)
            ttk.Label(self.win, text=r.notes, justify="left",
                       wraplength=650).pack(anchor="w", padx=12)

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(bar, text="Close",
                    command=self.win.destroy).pack(side="right")


class VoidDialog:
    def __init__(self, parent: tk.Misc, *,
                 receipt: Receipt,
                 on_save: Callable[[], None]) -> None:
        self.receipt = receipt
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Void {receipt.receipt_number}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        ttk.Label(form,
                   text=f"Voiding receipt {receipt.receipt_number}\n"
                        f"Total: {_money(receipt.total_amount)}",
                   justify="left").grid(row=0, column=0,
                                          columnspan=2, sticky="w",
                                          pady=(0, 8))
        ttk.Label(form, text="Reason (required):").grid(
            row=1, column=0, sticky="ne", pady=3)
        self.reason_text = tk.Text(form, width=50, height=4, wrap="word")
        self.reason_text.grid(row=1, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=2, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Void",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        reason = self.reason_text.get("1.0", "end").strip()
        if not reason:
            messagebox.showerror("Validation", "Reason is required.")
            return
        try:
            data.void_receipt(self.receipt.receipt_id, reason)
        except ValidationError as e:
            messagebox.showerror("Failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class ReceiptDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: Receipt | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.lines: list[dict] = []
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Receipt" if existing else "New Receipt")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        self.is_issued = bool(self.existing and self.existing.is_issued)
        outer = ttk.Frame(self.win)
        outer.pack(fill="both", expand=True, padx=12, pady=12)

        form = ttk.Frame(outer)
        form.pack(fill="x")
        r = 0

        def label(t: str):
            nonlocal r
            ttk.Label(form, text=t).grid(row=r, column=0,
                                           sticky="e", pady=3)

        if self.existing:
            label("Number:")
            ttk.Label(form, text=self.existing.receipt_number,
                       font=("", 10, "bold")).grid(row=r, column=1,
                                                       sticky="w", padx=6)
            r += 1

        label("Issued date:")
        self.date_e = ttk.Entry(form, width=14)
        self.date_e.insert(0, self.existing.issued_date
                                if self.existing
                                else _date.today().isoformat())
        if self.is_issued:
            self.date_e.configure(state="disabled")
        self.date_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Payer name:")
        self.payer_e = ttk.Entry(form, width=40)
        if self.existing:
            self.payer_e.insert(0, self.existing.payer_name)
        if self.is_issued:
            self.payer_e.configure(state="disabled")
        self.payer_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Student:")
        opts = _student_options()
        labels = ["(none)"] + [l for _, l in opts]
        ids = [None] + [s for s, _ in opts]
        self._student_ids = ids
        self.student_cb = ttk.Combobox(form, values=labels,
                                          state="readonly", width=40)
        seed = (self.existing.student_id
                 if self.existing and self.existing.student_id else None)
        if seed in ids:
            self.student_cb.current(ids.index(seed))
        else:
            self.student_cb.current(0)
        if self.is_issued:
            self.student_cb.configure(state="disabled")
        self.student_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Method:")
        self.method_cb = ttk.Combobox(form, values=PAYMENT_METHODS,
                                          state="readonly", width=18)
        self.method_cb.set(self.existing.method if self.existing
                              else DEFAULT_METHOD)
        if self.is_issued:
            self.method_cb.configure(state="disabled")
        self.method_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Status:")
        self.status_cb = ttk.Combobox(
            form, values=["Draft", "Issued"],
            state="readonly", width=10)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_STATUS)
        if self.is_issued:
            self.status_cb.configure(state="disabled")
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Received by:")
        self.by_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.received_by:
            self.by_e.insert(0, self.existing.received_by)
        self.by_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Reference:")
        self.ref_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.reference:
            self.ref_e.insert(0, self.existing.reference)
        self.ref_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Notes:")
        self.notes_text = tk.Text(form, width=50, height=3, wrap="word")
        if self.existing and self.existing.notes:
            self.notes_text.insert("1.0", self.existing.notes)
        self.notes_text.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        # Lines section (disabled for Issued)
        ttk.Separator(outer, orient="horizontal").pack(
            fill="x", pady=8)
        if self.is_issued:
            ttk.Label(outer,
                       text="Lines (frozen — receipt is Issued)",
                       foreground="#888").pack(anchor="w")
        else:
            ttk.Label(outer, text="Lines:").pack(anchor="w")

        lines_frame = ttk.Frame(outer)
        lines_frame.pack(fill="both", expand=True, pady=4)
        cols = ("desc", "kind", "amount")
        self.lines_tree = ttk.Treeview(lines_frame, columns=cols,
                                          show="headings", height=6)
        self.lines_tree.heading("desc", text="Description")
        self.lines_tree.heading("kind", text="Kind")
        self.lines_tree.heading("amount", text="Amount")
        self.lines_tree.column("desc", width=400, anchor="w")
        self.lines_tree.column("kind", width=100, anchor="w")
        self.lines_tree.column("amount", width=120, anchor="e")
        vs = ttk.Scrollbar(lines_frame, orient="vertical",
                            command=self.lines_tree.yview)
        self.lines_tree.configure(yscrollcommand=vs.set)
        self.lines_tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        if self.existing:
            for el in data.list_lines(self.existing.receipt_id):
                self.lines.append({
                    "description": el.description,
                    "amount":      el.amount,
                    "kind":        el.kind,
                    "source_id":   el.source_id,
                    "notes":       el.notes,
                })
        self._refresh_lines()

        if not self.is_issued:
            lbar = ttk.Frame(outer)
            lbar.pack(fill="x", pady=4)
            ttk.Button(lbar, text="Add line",
                        command=self._add_line).pack(side="left")
            ttk.Button(lbar, text="Edit line",
                        command=self._edit_line).pack(side="left", padx=4)
            ttk.Button(lbar, text="Remove line",
                        command=self._remove_line).pack(side="left", padx=4)

        self.total_var = tk.StringVar(value="")
        ttk.Label(outer, textvariable=self.total_var,
                   font=("", 11, "bold"),
                   anchor="e").pack(fill="x", pady=(4, 8))
        self._refresh_total()

        bar = ttk.Frame(outer)
        bar.pack(fill="x")
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _refresh_lines(self) -> None:
        for i in self.lines_tree.get_children():
            self.lines_tree.delete(i)
        for idx, l in enumerate(self.lines):
            try:
                amt = float(l["amount"])
            except (TypeError, ValueError):
                amt = 0.0
            self.lines_tree.insert(
                "", "end", iid=str(idx),
                values=(l["description"], l.get("kind", "general"),
                          _money(amt)))
        self._refresh_total()

    def _refresh_total(self) -> None:
        total = 0.0
        for l in self.lines:
            try:
                total += float(l["amount"])
            except (TypeError, ValueError):
                pass
        self.total_var.set(f"TOTAL: {_money(round(total, 2))}")

    def _add_line(self) -> None:
        LineDialog(self.win, line=None,
                     on_save=self._handle_line_save)

    def _edit_line(self) -> None:
        sel = self.lines_tree.selection()
        if not sel:
            messagebox.showinfo("Edit", "Select a line first.")
            return
        idx = int(sel[0])
        LineDialog(self.win, line=self.lines[idx],
                     on_save=lambda l: self._handle_line_save(l, idx))

    def _handle_line_save(self, line: dict, idx: int | None = None) -> None:
        if idx is None:
            self.lines.append(line)
        else:
            self.lines[idx] = line
        self._refresh_lines()

    def _remove_line(self) -> None:
        sel = self.lines_tree.selection()
        if not sel:
            messagebox.showinfo("Remove", "Select a line first.")
            return
        idx = int(sel[0])
        del self.lines[idx]
        self._refresh_lines()

    def _save(self) -> None:
        if self.is_issued:
            # Only notes / reference / received_by go through.
            try:
                data.update_receipt(self.existing.receipt_id, {
                    "received_by": self.by_e.get().strip(),
                    "reference":   self.ref_e.get().strip(),
                    "notes":       self.notes_text.get("1.0",
                                                          "end").strip(),
                })
            except ValidationError as e:
                messagebox.showerror("Validation", str(e))
                return
            self.win.destroy()
            self.on_save()
            return

        if not self.lines:
            messagebox.showerror("Validation",
                                  "Add at least one line.")
            return
        idx = self.student_cb.current()
        sid = self._student_ids[idx] if idx > 0 else ""
        header = {
            "issued_date": self.date_e.get().strip(),
            "payer_name":  self.payer_e.get().strip(),
            "student_id":  sid or "",
            "method":      self.method_cb.get(),
            "status":      self.status_cb.get(),
            "received_by": self.by_e.get().strip(),
            "reference":   self.ref_e.get().strip(),
            "notes":       self.notes_text.get("1.0", "end").strip(),
        }
        try:
            if self.existing:
                data.update_receipt(self.existing.receipt_id,
                                      header, self.lines)
            else:
                data.create_receipt(header, self.lines)
        except ValidationError as e:
            messagebox.showerror("Validation", str(e))
            return
        except Exception as e:
            logger.exception("save receipt failed")
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class LineDialog:
    def __init__(self, parent: tk.Misc, *,
                 line: dict | None,
                 on_save: Callable[[dict], None]) -> None:
        self.line = line
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Line" if line else "Add Line")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        r = 0

        ttk.Label(form, text="Description:").grid(row=r, column=0,
                                                     sticky="e", pady=3)
        self.desc_e = ttk.Entry(form, width=50)
        if line:
            self.desc_e.insert(0, line.get("description", ""))
        self.desc_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form,
                   text=f"Amount ({CURRENCY_SYMBOL}):").grid(
            row=r, column=0, sticky="e", pady=3)
        self.amt_e = ttk.Entry(form, width=12)
        if line:
            try:
                self.amt_e.insert(0, f"{float(line.get('amount', 0)):.2f}")
            except (TypeError, ValueError):
                self.amt_e.insert(0, str(line.get("amount", "")))
        self.amt_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Kind:").grid(row=r, column=0,
                                              sticky="e", pady=3)
        self.kind_cb = ttk.Combobox(form, values=LINE_KINDS,
                                       state="readonly", width=14)
        self.kind_cb.set(line.get("kind", DEFAULT_LINE_KIND)
                            if line else DEFAULT_LINE_KIND)
        self.kind_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Source ID:").grid(row=r, column=0,
                                                   sticky="e", pady=3)
        self.src_e = ttk.Entry(form, width=10)
        if line and line.get("source_id"):
            self.src_e.insert(0, str(line["source_id"]))
        self.src_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                              sticky="e", pady=3)
        self.notes_e = ttk.Entry(form, width=40)
        if line and line.get("notes"):
            self.notes_e.insert(0, line["notes"])
        self.notes_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        desc = self.desc_e.get().strip()
        amt = self.amt_e.get().strip()
        if not desc or not amt:
            messagebox.showerror("Validation",
                                  "Description and amount are required.")
            return
        try:
            float(amt)
        except ValueError:
            messagebox.showerror("Validation",
                                  "Amount must be a number.")
            return
        payload = {
            "description": desc,
            "amount":      amt,
            "kind":        self.kind_cb.get(),
            "source_id":   self.src_e.get().strip() or None,
            "notes":       self.notes_e.get().strip() or None,
        }
        self.win.destroy()
        self.on_save(payload)


# ══ Import tab ═════════════════════════════════════════════════════

class ImportTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Import")
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self.frame)
        outer.pack(fill="x", padx=20, pady=20)
        ttk.Label(outer,
                   text="Generate a receipt from an existing payment "
                        "recorded in another module.\n"
                        "Only cleared payments can be receipted; the "
                        "receipt number is allocated automatically.",
                   foreground="#444", justify="left").pack(anchor="w",
                                                              pady=(0, 12))

        # Fee payment import.
        fee = ttk.LabelFrame(outer, text="From a fee payment")
        fee.pack(fill="x", pady=6)
        ttk.Label(fee, text="Fee payment ID:").grid(
            row=0, column=0, sticky="e", padx=6, pady=4)
        self.fee_e = ttk.Entry(fee, width=10)
        self.fee_e.grid(row=0, column=1, sticky="w", padx=6, pady=4)
        ttk.Label(fee, text="Received by:").grid(
            row=0, column=2, sticky="e", padx=6, pady=4)
        self.fee_by_e = ttk.Entry(fee, width=20)
        self.fee_by_e.grid(row=0, column=3, sticky="w", padx=6, pady=4)
        self.fee_issued = tk.BooleanVar(value=True)
        ttk.Checkbutton(fee, text="Issue immediately",
                          variable=self.fee_issued).grid(
            row=0, column=4, sticky="w", padx=6, pady=4)
        ttk.Button(fee, text="Create receipt",
                    command=self._import_fee).grid(
            row=0, column=5, padx=6, pady=4)

        # Trip payment import.
        trip = ttk.LabelFrame(outer, text="From a trip payment")
        trip.pack(fill="x", pady=6)
        ttk.Label(trip, text="Trip payment ID:").grid(
            row=0, column=0, sticky="e", padx=6, pady=4)
        self.trip_e = ttk.Entry(trip, width=10)
        self.trip_e.grid(row=0, column=1, sticky="w", padx=6, pady=4)
        ttk.Label(trip, text="Received by:").grid(
            row=0, column=2, sticky="e", padx=6, pady=4)
        self.trip_by_e = ttk.Entry(trip, width=20)
        self.trip_by_e.grid(row=0, column=3, sticky="w", padx=6, pady=4)
        self.trip_issued = tk.BooleanVar(value=True)
        ttk.Checkbutton(trip, text="Issue immediately",
                          variable=self.trip_issued).grid(
            row=0, column=4, sticky="w", padx=6, pady=4)
        ttk.Button(trip, text="Create receipt",
                    command=self._import_trip).grid(
            row=0, column=5, padx=6, pady=4)

    def _import_fee(self) -> None:
        pid = self.fee_e.get().strip()
        if not pid.isdigit():
            messagebox.showerror("Import",
                                  "Fee payment ID must be a number.")
            return
        try:
            r = data.receipt_from_fee_payment(
                int(pid),
                received_by=self.fee_by_e.get().strip() or None,
                issued=self.fee_issued.get())
        except ValidationError as e:
            messagebox.showerror("Import failed", str(e))
            return
        except Exception as e:
            messagebox.showerror("Import failed", str(e))
            return
        messagebox.showinfo(
            "Done",
            f"Created receipt {r.receipt_number} for "
            f"{_money(r.total_amount)} ({r.status})")
        self.fee_e.delete(0, "end")
        self.fee_by_e.delete(0, "end")

    def _import_trip(self) -> None:
        pid = self.trip_e.get().strip()
        if not pid.isdigit():
            messagebox.showerror("Import",
                                  "Trip payment ID must be a number.")
            return
        try:
            r = data.receipt_from_trip_payment(
                int(pid),
                received_by=self.trip_by_e.get().strip() or None,
                issued=self.trip_issued.get())
        except ValidationError as e:
            messagebox.showerror("Import failed", str(e))
            return
        except Exception as e:
            messagebox.showerror("Import failed", str(e))
            return
        messagebox.showinfo(
            "Done",
            f"Created receipt {r.receipt_number} for "
            f"{_money(r.total_amount)} ({r.status})")
        self.trip_e.delete(0, "end")
        self.trip_by_e.delete(0, "end")


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
        L.append("Counts")
        L.append("------")
        L.append(f"  Total receipts        : {s.total_receipts}")
        L.append(f"  Drafts                : {s.drafts}")
        L.append(f"  Issued                : {s.issued}")
        L.append(f"  Voided                : {s.voided}")
        L.append("")
        L.append("Money")
        L.append("-----")
        L.append(f"  Issued total          : "
                  f"{_money(s.total_issued_amount)}")
        L.append(f"  Voided total          : "
                  f"{_money(s.total_voided_amount)}")
        L.append("")
        L.append(f"  Today (issued)        : {_money(s.daily_today)}")
        L.append(f"  This week (issued)    : "
                  f"{_money(s.daily_this_week)}")
        L.append(f"  This month (issued)   : "
                  f"{_money(s.daily_this_month)}")
        L.append("")
        L.append("By payment method (issued)")
        L.append("--------------------------")
        for m in PAYMENT_METHODS:
            v = s.by_method.get(m, 0.0)
            if v:
                L.append(f"  {m:<18} : {_money(v)}")
        L.append("")
        L.append("By line kind (issued)")
        L.append("---------------------")
        for k in LINE_KINDS:
            v = s.by_kind.get(k, 0.0)
            if v:
                L.append(f"  {k:<10} : {_money(v)}")
        if s.top_payers:
            L.append("")
            L.append("Top payers (issued)")
            L.append("-------------------")
            for name, amt in s.top_payers:
                L.append(f"  {name[:30]:<30}  {_money(amt)}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(L))
        self.text.configure(state="disabled")
