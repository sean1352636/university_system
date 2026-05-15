"""Tk views for dinner money."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from education_system.primarysch_system.modules.domain.dinner_money import (
    dinner_money as data,
)
from education_system.primarysch_system.modules.domain.dinner_money.dinner_money import (
    KINDS, KIND_LABELS, LedgerEntry, MEAL_TYPES, MEAL_TYPE_LABELS,
    format_pence,
)
from education_system.primarysch_system.modules.domain.pupils import (
    pupils as pupils_data,
)
from education_system.primarysch_system.modules.domain.pupils.pupils import (
    ValidationError, YEAR_GROUPS,
)

logger = logging.getLogger(__name__)


def _safe_view(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(host, *args, **kwargs):
        try:
            return func(host, *args, **kwargs)
        except ValidationError as e:
            logger.warning("%s validation: %s", func.__name__, e)
            try:
                messagebox.showerror("Dinner Money", str(e),
                                     parent=getattr(host, "root", None))
            except Exception:
                pass
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            try:
                messagebox.showerror(
                    "Error",
                    f"An unexpected error occurred:\n\n{e}\n\nSee logs for details.",
                    parent=getattr(host, "root", None),
                )
            except Exception:
                pass
    return wrapper


@_safe_view
def open_dinner_money(host) -> None:
    logger.debug("GUI: open_dinner_money")

    win = tk.Toplevel(host.root)
    win.title("Dinner Money")
    win.transient(host.root)
    win.geometry("1180x640")

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    entries_tab = ttk.Frame(nb, padding=10)
    balances_tab = ttk.Frame(nb, padding=10)
    nb.add(entries_tab, text="Ledger entries")
    nb.add(balances_tab, text="Pupil balances")

    # --- Entries tab ----------------------------------------------------
    summary_var = tk.StringVar()
    ttk.Label(entries_tab, textvariable=summary_var,
              font=("Segoe UI", 10, "bold")).pack(anchor="w")

    filt = ttk.Frame(entries_tab)
    filt.pack(fill="x", pady=(6, 6))
    ttk.Label(filt, text="Pupil ID:").pack(side="left")
    pupil_var = tk.StringVar()
    ttk.Entry(filt, textvariable=pupil_var, width=12).pack(
        side="left", padx=(4, 10))
    ttk.Label(filt, text="Kind:").pack(side="left")
    kind_var = tk.StringVar(value="All")
    ttk.Combobox(filt, textvariable=kind_var,
                 values=["All"] + list(KINDS),
                 state="readonly", width=12).pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="Meal:").pack(side="left")
    meal_var = tk.StringVar(value="All")
    ttk.Combobox(filt, textvariable=meal_var,
                 values=["All"] + list(MEAL_TYPES),
                 state="readonly", width=10).pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="From:").pack(side="left")
    from_var = tk.StringVar()
    ttk.Entry(filt, textvariable=from_var, width=12).pack(
        side="left", padx=(4, 10))
    ttk.Label(filt, text="To:").pack(side="left")
    to_var = tk.StringVar()
    ttk.Entry(filt, textvariable=to_var, width=12).pack(
        side="left", padx=(4, 10))

    cols = ("entry_id", "date", "pupil_id", "name", "kind", "meal_type",
            "amount", "description")
    tree = ttk.Treeview(entries_tab, columns=cols, show="headings", height=16)
    for col, label, width, anchor in [
        ("entry_id", "#", 50, "center"),
        ("date", "Date", 100, "center"),
        ("pupil_id", "Pupil ID", 90, "w"),
        ("name", "Name", 200, "w"),
        ("kind", "Kind", 100, "w"),
        ("meal_type", "Meal", 80, "w"),
        ("amount", "Amount", 90, "e"),
        ("description", "Description", 280, "w"),
    ]:
        tree.heading(col, text=label)
        tree.column(col, width=width, anchor=anchor)
    tree.tag_configure("charge", foreground="#a32118")
    tree.tag_configure("credit", foreground="#1e7c1e")
    tree.pack(fill="both", expand=True, pady=(0, 6))

    e_btns = ttk.Frame(entries_tab)
    e_btns.pack(fill="x")

    def _refresh_entries() -> None:
        try:
            rows = data.list_entries(
                pupil_id=pupil_var.get().strip() or None,
                kind=None if kind_var.get() == "All" else kind_var.get(),
                meal_type=None if meal_var.get() == "All" else meal_var.get(),
                from_date=from_var.get().strip() or None,
                to_date=to_var.get().strip() or None,
                limit=500,
            )
        except ValidationError as e:
            messagebox.showerror("Dinner Money", str(e), parent=win)
            return
        except Exception:
            logger.exception("dinner_money list failed")
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=win)
            return
        for iid in tree.get_children():
            tree.delete(iid)
        for entry, pupil in rows:
            tag = "charge" if entry.amount_pence < 0 else (
                "credit" if entry.amount_pence > 0 else "")
            tree.insert("", "end", iid=str(entry.entry_id), values=(
                entry.entry_id, entry.entry_date, entry.pupil_id,
                pupil.full_name if pupil else "(unknown)",
                entry.kind, entry.meal_type or "",
                entry.amount_display, entry.description or "",
            ), tags=(tag,) if tag else ())
        try:
            s = data.summary(
                from_date=from_var.get().strip() or None,
                to_date=to_var.get().strip() or None,
            )
        except Exception:
            s = {"entries": 0, "total_credits_pence": 0,
                 "total_charges_pence": 0, "pupils_owing": 0,
                 "pupils_in_credit": 0, "total_owed_pence": 0}
        summary_var.set(
            f"Entries: {s['entries']}   "
            f"Credits: {format_pence(s['total_credits_pence'])}   "
            f"Charges: {format_pence(s['total_charges_pence'])}   "
            f"Pupils owing: {s['pupils_owing']}   "
            f"Total owed: {format_pence(s['total_owed_pence'])}"
        )

    def _selected_id() -> int | None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Dinner Money", "Select an entry first.",
                                parent=win)
            return None
        return int(sel[0])

    def _add() -> None:
        _open_entry_dialog(win, entry_id=None,
                           on_saved=_refresh_all,
                           default_pupil=pupil_var.get().strip())

    def _edit() -> None:
        eid = _selected_id()
        if eid is None:
            return
        _open_entry_dialog(win, entry_id=eid, on_saved=_refresh_all)

    def _delete() -> None:
        eid = _selected_id()
        if eid is None:
            return
        if not messagebox.askyesno("Delete entry",
                                   f"Delete entry #{eid}?", parent=win):
            return
        try:
            data.delete(eid)
        except Exception:
            logger.exception("delete(%s) failed", eid)
            messagebox.showerror("Error", "Could not delete — see logs.",
                                 parent=win)
            return
        _refresh_all()

    def _statement() -> None:
        pid = pupil_var.get().strip()
        if not pid:
            messagebox.showinfo("Dinner Money",
                                "Enter a pupil ID in the filter first.",
                                parent=win)
            return
        _open_statement_dialog(win, pid)

    ttk.Button(e_btns, text="New entry...", command=_add).pack(side="left")
    ttk.Button(e_btns, text="Edit", command=_edit).pack(
        side="left", padx=(8, 0))
    ttk.Button(e_btns, text="Delete", command=_delete).pack(
        side="left", padx=(8, 0))
    ttk.Button(e_btns, text="Pupil statement...",
               command=_statement).pack(side="left", padx=(8, 0))
    ttk.Button(e_btns, text="Refresh",
               command=_refresh_entries).pack(side="left", padx=(8, 0))
    tree.bind("<Double-Button-1>", lambda _e: _edit())

    for v in (pupil_var, kind_var, meal_var, from_var, to_var):
        v.trace_add("write", lambda *_: _refresh_entries())

    # --- Balances tab ---------------------------------------------------
    b_filt = ttk.Frame(balances_tab)
    b_filt.pack(fill="x", pady=(0, 6))
    ttk.Label(b_filt, text="Year:").pack(side="left")
    by_year_var = tk.StringVar(value="All")
    ttk.Combobox(b_filt, textvariable=by_year_var,
                 values=["All"] + list(YEAR_GROUPS),
                 state="readonly", width=6).pack(side="left", padx=(4, 10))
    owing_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(b_filt, text="Owing only",
                    variable=owing_var).pack(side="left")

    b_cols = ("pupil_id", "name", "year", "balance")
    btree = ttk.Treeview(balances_tab, columns=b_cols, show="headings",
                         height=18)
    for col, label, width, anchor in [
        ("pupil_id", "Pupil ID", 100, "w"),
        ("name", "Name", 280, "w"),
        ("year", "Year", 70, "center"),
        ("balance", "Balance", 120, "e"),
    ]:
        btree.heading(col, text=label)
        btree.column(col, width=width, anchor=anchor)
    btree.tag_configure("owing", foreground="#a32118")
    btree.tag_configure("credit", foreground="#1e7c1e")
    btree.pack(fill="both", expand=True, pady=(0, 6))

    def _refresh_balances() -> None:
        try:
            rows = data.balances(
                year_group=None if by_year_var.get() == "All"
                else by_year_var.get(),
                owing_only=owing_var.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Dinner Money", str(e), parent=win)
            return
        except Exception:
            logger.exception("balances failed")
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=win)
            return
        for iid in btree.get_children():
            btree.delete(iid)
        for p, bal in rows:
            tag = "owing" if bal < 0 else ("credit" if bal > 0 else "")
            btree.insert("", "end", iid=p.pupil_id, values=(
                p.pupil_id, p.full_name, p.year_group, format_pence(bal),
            ), tags=(tag,) if tag else ())

    def _open_selected_statement() -> None:
        sel = btree.selection()
        if not sel:
            messagebox.showinfo("Dinner Money", "Select a pupil first.",
                                parent=win)
            return
        _open_statement_dialog(win, sel[0])

    b_btns = ttk.Frame(balances_tab)
    b_btns.pack(fill="x")
    ttk.Button(b_btns, text="View statement...",
               command=_open_selected_statement).pack(side="left")
    ttk.Button(b_btns, text="Refresh",
               command=_refresh_balances).pack(side="left", padx=(8, 0))
    btree.bind("<Double-Button-1>", lambda _e: _open_selected_statement())
    by_year_var.trace_add("write", lambda *_: _refresh_balances())
    owing_var.trace_add("write", lambda *_: _refresh_balances())

    ttk.Button(win, text="Close",
               command=win.destroy).pack(anchor="e", padx=12, pady=(0, 10))

    def _refresh_all() -> None:
        _refresh_entries()
        _refresh_balances()

    _refresh_all()


def _open_entry_dialog(parent, *, entry_id: int | None,
                       on_saved: Callable[[], None],
                       default_pupil: str = "") -> None:
    existing: LedgerEntry | None = None
    if entry_id is not None:
        try:
            existing = data.get(entry_id)
        except Exception:
            logger.exception("get(%s) failed", entry_id)
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=parent)
            return
        if existing is None:
            messagebox.showerror("Dinner Money",
                                 f"No entry #{entry_id}", parent=parent)
            return

    dlg = tk.Toplevel(parent)
    dlg.title("Entry" if existing else "New ledger entry")
    dlg.transient(parent)
    dlg.geometry("500x440")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    pupil_var = tk.StringVar(
        value=existing.pupil_id if existing else default_pupil)
    pupil_label = tk.StringVar(value="")
    ttk.Label(frm, text="Pupil ID *").grid(row=0, column=0, sticky="w", pady=3)
    ttk.Entry(frm, textvariable=pupil_var, width=14).grid(
        row=0, column=1, sticky="w", pady=3)
    ttk.Label(frm, textvariable=pupil_label, foreground="#666").grid(
        row=0, column=2, sticky="w", padx=(8, 0))

    def _lookup_pupil(*_a) -> None:
        pid = pupil_var.get().strip()
        if not pid:
            pupil_label.set("")
            return
        try:
            p = pupils_data.get_pupil(pid)
        except Exception:
            pupil_label.set("(error)")
            return
        if p is None:
            pupil_label.set("(unknown)")
            return
        try:
            bal = data.pupil_balance(pid)
            pupil_label.set(
                f"{p.full_name} (year {p.year_group})   "
                f"balance: {format_pence(bal)}")
        except Exception:
            pupil_label.set(f"{p.full_name} (year {p.year_group})")
    pupil_var.trace_add("write", _lookup_pupil)
    _lookup_pupil()

    ttk.Label(frm, text="Date (YYYY-MM-DD)").grid(
        row=1, column=0, sticky="w", pady=3)
    date_var = tk.StringVar(value=existing.entry_date if existing else "")
    ttk.Entry(frm, textvariable=date_var, width=14).grid(
        row=1, column=1, sticky="w", pady=3)
    ttk.Label(frm, text="(blank = today)",
              foreground="#888").grid(row=1, column=2, sticky="w", padx=(8, 0))

    ttk.Label(frm, text="Kind *").grid(row=2, column=0, sticky="w", pady=3)
    kind_var = tk.StringVar(value=existing.kind if existing else "charge")
    ttk.Combobox(frm, textvariable=kind_var, values=list(KINDS),
                 state="readonly", width=14).grid(
        row=2, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Meal type").grid(row=3, column=0, sticky="w", pady=3)
    meal_var = tk.StringVar(
        value=existing.meal_type or "" if existing else "")
    ttk.Combobox(frm, textvariable=meal_var,
                 values=[""] + list(MEAL_TYPES),
                 state="readonly", width=14).grid(
        row=3, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Amount (£) *").grid(
        row=4, column=0, sticky="w", pady=3)
    amount_default = ""
    if existing:
        amount_default = f"{abs(existing.amount_pence)/100:.2f}"
    amount_var = tk.StringVar(value=amount_default)
    ttk.Entry(frm, textvariable=amount_var, width=10).grid(
        row=4, column=1, sticky="w", pady=3)
    ttk.Label(frm,
              text="(sign flipped automatically for charge)",
              foreground="#888").grid(
        row=4, column=2, sticky="w", padx=(8, 0))

    ttk.Label(frm, text="Description").grid(
        row=5, column=0, sticky="w", pady=3)
    desc_var = tk.StringVar(
        value=existing.description or "" if existing else "")
    ttk.Entry(frm, textvariable=desc_var, width=40).grid(
        row=5, column=1, columnspan=2, sticky="ew", pady=3)

    ttk.Label(frm, text="Recorded by").grid(
        row=6, column=0, sticky="w", pady=3)
    by_var = tk.StringVar(value=existing.recorded_by or "" if existing else "")
    ttk.Entry(frm, textvariable=by_var, width=20).grid(
        row=6, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Notes").grid(row=7, column=0, sticky="w", pady=3)
    notes_var = tk.StringVar(value=existing.notes or "" if existing else "")
    ttk.Entry(frm, textvariable=notes_var, width=40).grid(
        row=7, column=1, columnspan=2, sticky="ew", pady=3)
    frm.columnconfigure(2, weight=1)

    def _save() -> None:
        payload = {
            "pupil_id": pupil_var.get(),
            "entry_date": date_var.get(),
            "kind": kind_var.get(),
            "meal_type": meal_var.get(),
            "amount_pounds": amount_var.get(),
            "description": desc_var.get(),
            "recorded_by": by_var.get(),
            "notes": notes_var.get(),
        }
        try:
            if existing is None:
                data.record(payload)
            else:
                data.update(existing.entry_id, payload)
        except ValidationError as e:
            messagebox.showerror("Dinner Money", str(e), parent=dlg)
            return
        except Exception:
            logger.exception("save entry failed")
            messagebox.showerror("Error", "Could not save — see logs.",
                                 parent=dlg)
            return
        on_saved()
        dlg.destroy()

    btn_row = ttk.Frame(frm)
    btn_row.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(14, 0))
    ttk.Button(btn_row, text="Save", command=_save).pack(side="right")
    ttk.Button(btn_row, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=(0, 8))


def _open_statement_dialog(parent, pupil_id: str) -> None:
    try:
        s = data.pupil_statement(pupil_id)
    except ValidationError as e:
        messagebox.showerror("Dinner Money", str(e), parent=parent)
        return
    except Exception:
        logger.exception("pupil_statement(%s) failed", pupil_id)
        messagebox.showerror("Error", "Could not load — see logs.",
                             parent=parent)
        return
    pupil = pupils_data.get_pupil(pupil_id)
    name = pupil.full_name if pupil else "(unknown)"

    dlg = tk.Toplevel(parent)
    dlg.title(f"Statement — {name}")
    dlg.transient(parent)
    dlg.geometry("780x540")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm,
              text=f"{name}  ({pupil_id})",
              font=("Segoe UI", 12, "bold")).pack(anchor="w")
    summary_colour = ("#a32118" if s["balance_pence"] < 0
                      else ("#1e7c1e" if s["balance_pence"] > 0 else "#444"))
    ttk.Label(frm,
              text=f"Credits: {format_pence(s['total_credits_pence'])}   "
                   f"Charges: {format_pence(s['total_charges_pence'])}   "
                   f"Balance: {format_pence(s['balance_pence'])}"
                   + (" (owing)" if s['balance_pence'] < 0
                      else " (in credit)" if s['balance_pence'] > 0
                      else " (settled)"),
              foreground=summary_colour,
              font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(4, 8))

    cols = ("entry_id", "date", "kind", "meal_type", "amount",
            "description")
    tree = ttk.Treeview(frm, columns=cols, show="headings", height=14)
    for col, label, width, anchor in [
        ("entry_id", "#", 50, "center"),
        ("date", "Date", 100, "center"),
        ("kind", "Kind", 100, "w"),
        ("meal_type", "Meal", 80, "w"),
        ("amount", "Amount", 90, "e"),
        ("description", "Description", 300, "w"),
    ]:
        tree.heading(col, text=label)
        tree.column(col, width=width, anchor=anchor)
    tree.tag_configure("charge", foreground="#a32118")
    tree.tag_configure("credit", foreground="#1e7c1e")
    tree.pack(fill="both", expand=True)
    for entry in s["entries"]:
        tag = "charge" if entry.amount_pence < 0 else (
            "credit" if entry.amount_pence > 0 else "")
        tree.insert("", "end", values=(
            entry.entry_id, entry.entry_date, entry.kind,
            entry.meal_type or "", entry.amount_display,
            entry.description or "",
        ), tags=(tag,) if tag else ())

    ttk.Button(frm, text="Close",
               command=dlg.destroy).pack(anchor="e", pady=(10, 0))
