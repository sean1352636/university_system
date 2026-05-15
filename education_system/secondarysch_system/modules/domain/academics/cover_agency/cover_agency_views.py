"""Tk views for cover-agency staff and bookings."""

from __future__ import annotations

import datetime as _dt
import functools
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from education_system.secondarysch_system.modules.domain.academics.cover_agency import (
    cover_agency as data,
)
from education_system.secondarysch_system.modules.domain.academics.cover_agency.cover_agency import (
    BOOKING_STATUSES, MIN_PERIOD, MAX_PERIOD,
)
from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
    ValidationError,
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
                messagebox.showerror("Cover Agency", str(e),
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


def _today() -> str:
    return _dt.date.today().isoformat()


# ── Staff dialog ──────────────────────────────────────────────────

def _staff_dialog(host, title: str, initial: dict[str, Any] | None = None
                  ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("460x440")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    name_var   = tk.StringVar(value=str(initial.get("full_name") or ""))
    agency_var = tk.StringVar(value=str(initial.get("agency_name") or ""))
    role_var   = tk.StringVar(value=str(initial.get("role") or ""))
    rate_var   = tk.StringVar(value=str(initial.get("hourly_rate") or ""))
    email_var  = tk.StringVar(value=str(initial.get("contact_email") or ""))
    phone_var  = tk.StringVar(value=str(initial.get("contact_phone") or ""))
    dbs_var    = tk.BooleanVar(value=bool(initial.get("dbs_cleared")))
    active_var = tk.BooleanVar(
        value=True if initial.get("is_active") is None
        else bool(initial.get("is_active")))

    rows: list[tuple[str, tk.Widget]] = [
        ("Full name:", ttk.Entry(frm, textvariable=name_var, width=30)),
        ("Agency:",    ttk.Entry(frm, textvariable=agency_var, width=30)),
        ("Role:",      ttk.Entry(frm, textvariable=role_var, width=30)),
        ("Hourly rate £:", ttk.Entry(frm, textvariable=rate_var, width=10)),
        ("Email:",     ttk.Entry(frm, textvariable=email_var, width=30)),
        ("Phone:",     ttk.Entry(frm, textvariable=phone_var, width=20)),
        ("DBS cleared:", ttk.Checkbutton(frm, variable=dbs_var)),
        ("Active:",      ttk.Checkbutton(frm, variable=active_var)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w", pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    ttk.Label(frm, text="Notes:").grid(row=len(rows), column=0,
                                        sticky="nw", pady=2)
    notes_w = tk.Text(frm, width=36, height=4, wrap="word")
    notes_w.insert("1.0", str(initial.get("notes") or ""))
    notes_w.grid(row=len(rows), column=1, sticky="ew", pady=2)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "full_name":     name_var.get().strip(),
            "agency_name":   agency_var.get().strip(),
            "role":          role_var.get().strip(),
            "hourly_rate":   rate_var.get().strip(),
            "contact_email": email_var.get().strip(),
            "contact_phone": phone_var.get().strip(),
            "dbs_cleared":   bool(dbs_var.get()),
            "is_active":     bool(active_var.get()),
            "notes":         notes_w.get("1.0", "end").strip(),
        }
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=len(rows) + 1, column=0, columnspan=2, sticky="e",
              pady=(12, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


# ── Booking dialog ────────────────────────────────────────────────

def _booking_dialog(host, title: str, initial: dict[str, Any] | None = None
                    ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("460x400")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass

    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    try:
        staff_list = [s for s in data.list_staff(active_only=True)
                       if s.dbs_cleared]
    except Exception:
        staff_list = []
    staff_labels = [f"#{s.staff_id} {s.full_name} "
                    f"({s.agency_name or '-'})"
                    for s in staff_list]
    staff_var = tk.StringVar(value="")
    initial_staff = initial.get("staff_id")
    if initial_staff is not None:
        for s in staff_list:
            if s.staff_id == int(initial_staff):
                staff_var.set(f"#{s.staff_id} {s.full_name} "
                              f"({s.agency_name or '-'})")
                break

    date_var   = tk.StringVar(value=str(initial.get("date") or _today()))
    period_var = tk.StringVar(value=str(initial.get("period") or
                                          MIN_PERIOD))
    cover_var  = tk.StringVar(value=str(initial.get("cover_id") or ""))
    rate_var   = tk.StringVar(value=str(initial.get("rate_charged") or ""))
    status_var = tk.StringVar(value=str(initial.get("status") or "Booked"))

    rows: list[tuple[str, tk.Widget]] = [
        ("Staff:",    ttk.Combobox(frm, textvariable=staff_var,
                                    values=staff_labels,
                                    state="readonly", width=44)),
        ("Date:",     ttk.Entry(frm, textvariable=date_var, width=14)),
        ("Period:",   ttk.Spinbox(frm, from_=MIN_PERIOD, to=MAX_PERIOD,
                                   textvariable=period_var, width=6)),
        ("Cover ID (optional):",
                       ttk.Entry(frm, textvariable=cover_var, width=10)),
        ("Rate charged £:", ttk.Entry(frm, textvariable=rate_var, width=10)),
        ("Status:",   ttk.Combobox(frm, textvariable=status_var,
                                    values=list(BOOKING_STATUSES),
                                    state="readonly", width=14)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w", pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    ttk.Label(frm, text="Notes:").grid(row=len(rows), column=0,
                                        sticky="nw", pady=2)
    notes_w = tk.Text(frm, width=36, height=4, wrap="word")
    notes_w.insert("1.0", str(initial.get("notes") or ""))
    notes_w.grid(row=len(rows), column=1, sticky="ew", pady=2)

    result: dict[str, Any] | None = None

    def _parse_staff(label: str) -> str:
        label = (label or "").strip()
        if not label.startswith("#"):
            return ""
        return label.split()[0][1:]

    def _save() -> None:
        nonlocal result
        result = {
            "staff_id":     _parse_staff(staff_var.get()),
            "date":         date_var.get().strip(),
            "period":       period_var.get().strip(),
            "cover_id":     cover_var.get().strip(),
            "rate_charged": rate_var.get().strip(),
            "status":       status_var.get().strip(),
            "notes":        notes_w.get("1.0", "end").strip(),
        }
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=len(rows) + 1, column=0, columnspan=2, sticky="e",
              pady=(12, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


# ── Main view ─────────────────────────────────────────────────────

@_safe_view
def open_cover_agency(host) -> None:
    logger.debug("GUI: open_cover_agency")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Cover Agency",
              font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

    summary_var = tk.StringVar()
    ttk.Label(root, textvariable=summary_var, foreground="#666").pack(
        anchor="w", pady=(0, 8))

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True)

    # ── Staff tab ────────────────────────────────────────
    staff_tab = ttk.Frame(nb, padding=4)
    nb.add(staff_tab, text="Staff")

    s_bar = ttk.Frame(staff_tab)
    s_bar.pack(fill="x", pady=(0, 6))
    only_active_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(s_bar, text="Active only",
                    variable=only_active_var,
                    command=lambda: _refresh_staff()).pack(
        side="left", padx=(0, 8))
    ttk.Button(s_bar, text="Add",
               command=lambda: _new_staff(host, on_done=_refresh_staff)
               ).pack(side="left", padx=2)
    ttk.Button(s_bar, text="Edit",
               command=lambda: _edit_staff(host, staff_tree,
                                            on_done=_refresh_staff)
               ).pack(side="left", padx=2)
    ttk.Button(s_bar, text="Toggle active",
               command=lambda: _toggle_staff(host, staff_tree,
                                              on_done=_refresh_staff)
               ).pack(side="left", padx=2)
    ttk.Button(s_bar, text="Delete",
               command=lambda: _delete_staff(host, staff_tree,
                                              on_done=_refresh_staff)
               ).pack(side="left", padx=2)
    ttk.Button(s_bar, text="Refresh",
               command=lambda: _refresh_staff()).pack(side="left", padx=2)

    staff_cols = ("id", "name", "agency", "role", "rate", "email",
                  "phone", "dbs", "active")
    staff_tree = ttk.Treeview(staff_tab, columns=staff_cols,
                               show="headings", height=14)
    for c, label, w in [
        ("id", "ID", 50), ("name", "Name", 180),
        ("agency", "Agency", 150), ("role", "Role", 120),
        ("rate", "Rate £/h", 80), ("email", "Email", 180),
        ("phone", "Phone", 120),
        ("dbs", "DBS", 50), ("active", "Active", 60),
    ]:
        staff_tree.heading(c, text=label)
        staff_tree.column(c, width=w, anchor="w")
    staff_tree.pack(fill="both", expand=True)

    # ── Bookings tab ────────────────────────────────────
    book_tab = ttk.Frame(nb, padding=4)
    nb.add(book_tab, text="Bookings")

    b_bar = ttk.Frame(book_tab)
    b_bar.pack(fill="x", pady=(0, 6))
    ttk.Label(b_bar, text="Date:").pack(side="left", padx=(0, 4))
    book_date_var = tk.StringVar(value="")
    ttk.Entry(b_bar, textvariable=book_date_var, width=12).pack(
        side="left", padx=(0, 6))
    ttk.Label(b_bar, text="Status:").pack(side="left", padx=(0, 4))
    book_status_var = tk.StringVar(value="")
    ttk.Combobox(b_bar, textvariable=book_status_var,
                 values=["", *BOOKING_STATUSES], state="readonly",
                 width=10).pack(side="left", padx=(0, 8))
    ttk.Button(b_bar, text="Apply",
               command=lambda: _refresh_bookings()).pack(side="left", padx=2)
    ttk.Button(b_bar, text="New",
               command=lambda: _new_booking(host, on_done=_refresh_bookings)
               ).pack(side="left", padx=2)
    ttk.Button(b_bar, text="Set status",
               command=lambda: _status_booking(host, book_tree,
                                                 on_done=_refresh_bookings)
               ).pack(side="left", padx=2)
    ttk.Button(b_bar, text="Delete",
               command=lambda: _delete_booking(host, book_tree,
                                                 on_done=_refresh_bookings)
               ).pack(side="left", padx=2)
    ttk.Button(b_bar, text="Refresh",
               command=lambda: _refresh_bookings()).pack(side="left", padx=2)

    book_cols = ("id", "date", "p", "staff", "agency", "cov", "rate",
                 "status")
    book_tree = ttk.Treeview(book_tab, columns=book_cols,
                              show="headings", height=14)
    for c, label, w in [
        ("id", "ID", 50), ("date", "Date", 100), ("p", "P", 40),
        ("staff", "Staff", 200), ("agency", "Agency", 140),
        ("cov", "Cover#", 60), ("rate", "Rate £", 70),
        ("status", "Status", 90),
    ]:
        book_tree.heading(c, text=label)
        book_tree.column(c, width=w, anchor="w")
    book_tree.pack(fill="both", expand=True)

    # ── Refresh helpers ────────────────────────────────
    def _refresh_summary() -> None:
        try:
            s = data.staff_summary()
            summary_var.set(
                f"Staff: {s['total']}   active: {s['active']}   "
                f"DBS-cleared: {s['dbs']}   agencies: {s['agencies']}    "
                + "    ".join(f"{k}: {v}" for k, v in s["bookings"].items()))
        except Exception:
            logger.exception("agency summary failed")
            summary_var.set("(summary unavailable)")

    def _refresh_staff() -> None:
        for i in staff_tree.get_children():
            staff_tree.delete(i)
        try:
            rows = data.list_staff(active_only=bool(only_active_var.get()))
        except Exception as e:
            logger.exception("staff refresh failed")
            messagebox.showerror("Cover Agency",
                                 f"Could not load staff:\n\n{e}",
                                 parent=host.root)
            return
        for s in rows:
            rate = (f"£{s.hourly_rate:.2f}"
                    if s.hourly_rate is not None else "-")
            staff_tree.insert("", "end", iid=str(s.staff_id), values=(
                s.staff_id, s.full_name, s.agency_name or "-",
                s.role or "-", rate,
                s.contact_email or "-", s.contact_phone or "-",
                "Yes" if s.dbs_cleared else "No",
                "Yes" if s.is_active else "No",
            ))
        _refresh_summary()
        host.status_var.set(f"Cover Agency: {len(rows)} staff")

    def _refresh_bookings() -> None:
        for i in book_tree.get_children():
            book_tree.delete(i)
        try:
            rows = data.list_bookings(
                date=book_date_var.get().strip() or None,
                status=book_status_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Cover Agency", str(e), parent=host.root)
            return
        except Exception as e:
            logger.exception("bookings refresh failed")
            messagebox.showerror("Cover Agency",
                                 f"Could not load bookings:\n\n{e}",
                                 parent=host.root)
            return
        for b in rows:
            rate = (f"£{b.rate_charged:.2f}"
                    if b.rate_charged is not None else "-")
            book_tree.insert("", "end", iid=str(b.booking_id), values=(
                b.booking_id, b.date, b.period,
                b.staff_name or "-", b.agency_name or "-",
                b.cover_id if b.cover_id else "-",
                rate, b.status,
            ))
        _refresh_summary()
        host.status_var.set(f"Cover Agency: {len(rows)} booking(s)")

    staff_tree.bind("<Double-1>",
                     lambda _e: _edit_staff(host, staff_tree,
                                              on_done=_refresh_staff))
    book_tree.bind("<Double-1>",
                    lambda _e: _status_booking(host, book_tree,
                                                  on_done=_refresh_bookings))

    _refresh_staff()
    _refresh_bookings()


def _selected_id(tree: ttk.Treeview, host, label: str) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Cover Agency", f"Select a {label} first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new_staff(host, *, on_done=None) -> None:
    fields = _staff_dialog(host, "Add staff")
    if not fields:
        return
    rec = data.create_staff(fields)
    messagebox.showinfo("Cover Agency",
                        f"Added {rec.full_name} "
                        f"({rec.agency_name or '-'})",
                        parent=host.root)
    if on_done:
        on_done()


@_safe_view
def _edit_staff(host, tree: ttk.Treeview, *, on_done=None) -> None:
    sid = _selected_id(tree, host, "staff member")
    if sid is None:
        return
    existing = data.get_staff(sid)
    if existing is None:
        return
    initial = {
        "full_name": existing.full_name,
        "agency_name": existing.agency_name,
        "role": existing.role,
        "hourly_rate": existing.hourly_rate,
        "contact_email": existing.contact_email,
        "contact_phone": existing.contact_phone,
        "dbs_cleared": existing.dbs_cleared,
        "is_active": existing.is_active,
        "notes": existing.notes,
    }
    fields = _staff_dialog(host, f"Edit staff #{sid}", initial=initial)
    if not fields:
        return
    data.update_staff(sid, fields)
    if on_done:
        on_done()


@_safe_view
def _toggle_staff(host, tree: ttk.Treeview, *, on_done=None) -> None:
    sid = _selected_id(tree, host, "staff member")
    if sid is None:
        return
    rec = data.toggle_active(sid)
    messagebox.showinfo(
        "Cover Agency",
        f"{rec.full_name} is now "
        f"{'active' if rec.is_active else 'inactive'}.",
        parent=host.root,
    )
    if on_done:
        on_done()


@_safe_view
def _delete_staff(host, tree: ttk.Treeview, *, on_done=None) -> None:
    sid = _selected_id(tree, host, "staff member")
    if sid is None:
        return
    existing = data.get_staff(sid)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete staff",
            f"Delete {existing.full_name}?",
            parent=host.root):
        return
    data.delete_staff(sid)
    if on_done:
        on_done()


@_safe_view
def _new_booking(host, *, on_done=None) -> None:
    fields = _booking_dialog(host, "New booking")
    if not fields:
        return
    b = data.create_booking(fields)
    messagebox.showinfo("Cover Agency",
                        f"Booked {b.staff_name} on "
                        f"{b.date} P{b.period}",
                        parent=host.root)
    if on_done:
        on_done()


@_safe_view
def _status_booking(host, tree: ttk.Treeview, *, on_done=None) -> None:
    bid = _selected_id(tree, host, "booking")
    if bid is None:
        return
    b = data.get_booking(bid)
    if b is None:
        return
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Status — booking #{bid}")
    dlg.transient(host.root)
    dlg.geometry("340x150")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm,
              text=f"{b.staff_name} — {b.date} P{b.period}").pack(
        anchor="w")
    ttk.Label(frm, text=f"Current status: {b.status}",
              foreground="#666").pack(anchor="w", pady=(0, 8))
    new_var = tk.StringVar(value=b.status)
    ttk.Combobox(frm, textvariable=new_var,
                 values=list(BOOKING_STATUSES),
                 state="readonly").pack(fill="x")

    def _save() -> None:
        try:
            data.set_booking_status(bid, new_var.get())
        except ValidationError as e:
            messagebox.showerror("Cover Agency", str(e), parent=dlg)
            return
        dlg.destroy()
        if on_done:
            on_done()

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(10, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")


@_safe_view
def _delete_booking(host, tree: ttk.Treeview, *, on_done=None) -> None:
    bid = _selected_id(tree, host, "booking")
    if bid is None:
        return
    b = data.get_booking(bid)
    if b is None:
        return
    if not messagebox.askyesno(
            "Delete booking",
            f"Delete booking #{bid} ({b.staff_name} on "
            f"{b.date} P{b.period})?",
            parent=host.root):
        return
    data.delete_booking(bid)
    if on_done:
        on_done()
