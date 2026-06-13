"""Tkinter views for Primary School Trips & Payments."""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, ttk
from typing import Callable
from education_system.primarysch_system.modules.domain.staff import staff
from education_system.primarysch_system.modules.domain import _pupils_bridge as students
from education_system.primarysch_system.modules.domain.staff import staff as staff_data
from education_system.primarysch_system.modules.domain import _pupils_bridge as student_data
from education_system.primarysch_system.modules.domain.trips import trips as data
from education_system.shared import branding
from education_system.primarysch_system.modules.domain.trips.trips import (
    BOOKING_STATUSES,
    Booking,
    CURRENCY_SYMBOL,
    DEFAULT_BOOKING_STATUS,
    DEFAULT_METHOD,
    DEFAULT_PAYMENT_STATUS,
    DEFAULT_TRIP_STATUS,
    DEFAULT_YEAR_GROUP,
    PAYMENT_METHODS,
    PAYMENT_STATES,
    PAYMENT_STATUSES,
    Payment,
    TRIP_STATUSES,
    Trip,
    ValidationError,
    YEAR_GROUPS,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_trips_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Trips & Payments — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)
    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    trips_tab = TripsTab(nb)
    bookings_tab = BookingsTab(nb)
    PaymentsTab(nb)
    SummaryTab(nb)
    trips_tab.on_change = bookings_tab.refresh_trips


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


# ══ Trips tab ══════════════════════════════════════════════════════

class TripsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Trips")
        self.on_change: Callable[[], None] | None = None
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Year:").pack(side="left")
        self.f_year = ttk.Combobox(bar, values=("",) + YEAR_GROUPS,
                                      state="readonly", width=10)
        self.f_year.current(0)
        self.f_year.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + TRIP_STATUSES,
                                        state="readonly", width=22)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 10))
        self.f_open = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Open only",
                          variable=self.f_open,
                          command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(10, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "start", "end", "name", "destination",
                "year", "cost", "deposit", "cap", "status")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = {"id": 50, "start": 90, "end": 90, "name": 240,
                  "destination": 180, "year": 70, "cost": 80,
                  "deposit": 80, "cap": 60, "status": 150}
        for c in cols:
            self.tree.heading(c, text=c.capitalize())
            anchor = "e" if c in ("cost", "deposit", "cap") else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Cancelled", foreground="#888")
        self.tree.tag_configure("Open for Booking",
                                  background="#e6f7e0")
        self.tree.bind("<Double-1>", lambda _e: self._view_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
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
        ttk.Button(bar, text="Status",
                    command=self._status_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.f_year.current(0)
        self.f_status.current(0)
        self.f_open.set(False)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_trips(
                year_group=self.f_year.get() or None,
                status=self.f_status.get() or None,
                open_only=self.f_open.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        for t in rows:
            tags = [t.status] if t.status in (
                "Cancelled", "Open for Booking") else []
            self.tree.insert("", "end", iid=str(t.trip_id), values=(
                t.trip_id, t.start_date, t.end_date or "—",
                t.name, t.destination or "—", t.year_group,
                _money(t.cost_per_place), _money(t.deposit),
                t.capacity or "—", t.status,
            ), tags=tuple(tags))
        self.count_var.set(f"{len(rows)} trip(s).")
        self._build_actions()
        if self.on_change:
            self.on_change()

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _view_selected(self) -> None:
        tid = self._selected_id()
        if tid is None:
            messagebox.showinfo("View", "Select a trip first.")
            return
        tv = data.view_trip(tid)
        if tv is None:
            return
        t = tv.trip
        lines = [
            f"Trip         : #{t.trip_id}",
            f"Name         : {t.name}",
            f"Destination  : {t.destination or '—'}",
            f"Dates        : {t.start_date}"
            + (f" → {t.end_date}" if t.end_date else ""),
            f"Year         : {t.year_group}",
            f"Cost / place : {_money(t.cost_per_place)}",
            f"Deposit      : {_money(t.deposit)}",
            f"Capacity     : {t.capacity or '—'}",
            f"Payment due  : {t.payment_due or '—'}",
            f"Status       : {t.status}",
            f"Lead staff   : {t.lead_staff_id or '—'}",
            "",
            f"Active bookings : {tv.total_active}"
            + (f"  ({tv.capacity_used_pct}% of capacity)"
                if tv.capacity_used_pct is not None else ""),
            f"  Confirmed   : {tv.confirmed}",
            f"  Interested  : {tv.interested}",
            f"  Waitlist    : {tv.waitlist}",
            f"  Cancelled   : {tv.cancelled}",
            "",
            f"Charged (active): {_money(tv.total_charged)}",
            f"Paid            : {_money(tv.total_paid)}",
            f"Outstanding     : {_money(tv.total_balance)}",
        ]
        if t.description:
            lines.extend(["", "Description:", t.description])
        if t.notes:
            lines.extend(["", "Notes:", t.notes])
        messagebox.showinfo(f"Trip #{t.trip_id}", "\n".join(lines))

    def _new(self) -> None:
        TripDialog(self.frame.winfo_toplevel(),
                    existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        tid = self._selected_id()
        if tid is None:
            messagebox.showinfo("Edit", "Select a trip first.")
            return
        t = data.get_trip(tid)
        if t is None:
            return
        TripDialog(self.frame.winfo_toplevel(),
                    existing=t, on_save=self.refresh)

    def _status_selected(self) -> None:
        tid = self._selected_id()
        if tid is None:
            messagebox.showinfo("Status", "Select a trip first.")
            return
        t = data.get_trip(tid)
        if t is None:
            return
        StatusDialog(self.frame.winfo_toplevel(),
                      title=f"Trip #{tid} status",
                      current=t.status, options=list(TRIP_STATUSES),
                      on_save=lambda s:
                          self._save_status(tid, s))

    def _save_status(self, tid: int, status: str) -> None:
        try:
            data.set_trip_status(tid, status)
        except ValidationError as e:
            messagebox.showerror("Failed", str(e))
            return
        self.refresh()

    def _delete_selected(self) -> None:
        tid = self._selected_id()
        if tid is None:
            messagebox.showinfo("Delete", "Select a trip first.")
            return
        t = data.get_trip(tid)
        if t is None:
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete trip #{tid} ({t.name})?\n\n"
                f"This deletes all bookings and payments."):
            return
        try:
            data.delete_trip(tid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


class TripDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: Trip | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Trip" if existing else "New Trip")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        r = 0

        def label(t: str):
            nonlocal r
            ttk.Label(form, text=t).grid(row=r, column=0,
                                           sticky="e", pady=3)

        label("Name:")
        self.name_e = ttk.Entry(form, width=40)
        if self.existing:
            self.name_e.insert(0, self.existing.name)
        self.name_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Destination:")
        self.dest_e = ttk.Entry(form, width=40)
        if self.existing and self.existing.destination:
            self.dest_e.insert(0, self.existing.destination)
        self.dest_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Start date:")
        self.start_e = ttk.Entry(form, width=14)
        self.start_e.insert(0, self.existing.start_date
                                if self.existing
                                else _date.today().isoformat())
        self.start_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("End date:")
        self.end_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.end_date:
            self.end_e.insert(0, self.existing.end_date)
        self.end_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Year group:")
        self.year_cb = ttk.Combobox(form, values=YEAR_GROUPS,
                                       state="readonly", width=10)
        self.year_cb.set(self.existing.year_group if self.existing
                            else DEFAULT_YEAR_GROUP)
        self.year_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label(f"Cost / place ({CURRENCY_SYMBOL}):")
        self.cost_e = ttk.Entry(form, width=12)
        self.cost_e.insert(0,
                              f"{self.existing.cost_per_place:.2f}"
                              if self.existing else "0.00")
        self.cost_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label(f"Deposit ({CURRENCY_SYMBOL}):")
        self.dep_e = ttk.Entry(form, width=12)
        self.dep_e.insert(0,
                              f"{self.existing.deposit:.2f}"
                              if self.existing else "0.00")
        self.dep_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Capacity:")
        self.cap_e = ttk.Entry(form, width=8)
        if self.existing and self.existing.capacity is not None:
            self.cap_e.insert(0, str(self.existing.capacity))
        self.cap_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Payment due:")
        self.due_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.payment_due:
            self.due_e.insert(0, self.existing.payment_due)
        self.due_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Status:")
        self.status_cb = ttk.Combobox(form, values=TRIP_STATUSES,
                                          state="readonly", width=22)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_TRIP_STATUS)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Lead staff:")
        opts = _staff_options()
        labels = ["(none)"] + [l for _, l in opts]
        ids = [None] + [s for s, _ in opts]
        self._lead_ids = ids
        self.lead_cb = ttk.Combobox(form, values=labels,
                                        state="readonly", width=42)
        seed = (self.existing.lead_staff_id
                 if self.existing and self.existing.lead_staff_id
                 else None)
        if seed in ids:
            self.lead_cb.current(ids.index(seed))
        else:
            self.lead_cb.current(0)
        self.lead_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Description:")
        self.desc_text = tk.Text(form, width=50, height=3, wrap="word")
        if self.existing and self.existing.description:
            self.desc_text.insert("1.0", self.existing.description)
        self.desc_text.grid(row=r, column=1, sticky="w", padx=6)
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
        idx = self.lead_cb.current()
        lead = self._lead_ids[idx] if idx > 0 else ""
        payload = {
            "name":           self.name_e.get().strip(),
            "destination":    self.dest_e.get().strip(),
            "start_date":     self.start_e.get().strip(),
            "end_date":       self.end_e.get().strip(),
            "year_group":     self.year_cb.get(),
            "cost_per_place": self.cost_e.get().strip(),
            "deposit":        self.dep_e.get().strip(),
            "capacity":       self.cap_e.get().strip(),
            "payment_due":    self.due_e.get().strip(),
            "status":         self.status_cb.get(),
            "lead_staff_id":  lead,
            "description":    self.desc_text.get("1.0",
                                                    "end").strip(),
            "notes":          self.notes_text.get("1.0",
                                                     "end").strip(),
        }
        try:
            if self.existing:
                data.update_trip(self.existing.trip_id, payload)
            else:
                data.create_trip(payload)
        except ValidationError as e:
            messagebox.showerror("Validation", str(e))
            return
        except Exception as e:
            logger.exception("save trip failed")
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class StatusDialog:
    def __init__(self, parent: tk.Misc, *,
                 title: str, current: str, options: list[str],
                 on_save: Callable[[str], None]) -> None:
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(title)
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        ttk.Label(form, text="New status:").grid(row=0, column=0,
                                                    sticky="e", pady=4)
        self.cb = ttk.Combobox(form, values=options, state="readonly",
                                  width=22)
        self.cb.set(current)
        self.cb.grid(row=0, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=1, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        v = self.cb.get()
        self.win.destroy()
        self.on_save(v)


# ══ Bookings tab ═══════════════════════════════════════════════════

class BookingsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Bookings")
        self._build()
        self.refresh_trips()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Trip:").pack(side="left")
        self.trip_cb = ttk.Combobox(bar, state="readonly", width=60)
        self.trip_cb.pack(side="left", padx=(2, 10))
        self.trip_cb.bind("<<ComboboxSelected>>",
                              lambda _e: self.refresh())
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + BOOKING_STATUSES,
                                        state="readonly", width=14)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Payment:").pack(side="left")
        self.f_pay = ttk.Combobox(bar, values=("",) + PAYMENT_STATES,
                                     state="readonly", width=12)
        self.f_pay.current(0)
        self.f_pay.pack(side="left", padx=(2, 10))
        self.f_consent = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Consent missing",
                          variable=self.f_consent,
                          command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(10, 4))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "student", "name", "booked", "status", "consent",
                "paid", "balance", "state", "notes")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = {"id": 50, "student": 90, "name": 200, "booked": 90,
                  "status": 100, "consent": 70, "paid": 80,
                  "balance": 80, "state": 90, "notes": 280}
        headings = {"id": "#", "student": "Student", "name": "Name",
                    "booked": "Booked", "status": "Status",
                    "consent": "Consent", "paid": "Paid",
                    "balance": "Balance", "state": "Payment",
                    "notes": "Notes"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "e" if c in ("paid", "balance") else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Cancelled", foreground="#888")
        self.tree.tag_configure("Withdrawn", foreground="#888")
        self.tree.tag_configure("Unpaid", background="#ffe0e0")
        self.tree.tag_configure("Paid", background="#e6f7e0")
        self.tree.tag_configure("Waitlist", background="#fff7d0")
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
        ttk.Button(bar, text="Status",
                    command=self._status_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Add Payment",
                    command=self._add_payment).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

    def refresh_trips(self) -> None:
        trips = data.list_trips()
        self._trip_ids = [t.trip_id for t in trips]
        labels = [f"#{t.trip_id}  {t.start_date}  {t.name}  "
                   f"({t.status})" for t in trips]
        cur = self._selected_trip_id()
        self.trip_cb["values"] = labels
        if labels:
            if cur is not None and cur in self._trip_ids:
                self.trip_cb.current(self._trip_ids.index(cur))
            else:
                self.trip_cb.current(0)
        else:
            self.trip_cb.set("")
        self.refresh()

    def _selected_trip_id(self) -> int | None:
        idx = self.trip_cb.current()
        if idx < 0 or idx >= len(self._trip_ids):
            return None
        return self._trip_ids[idx]

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        tid = self._selected_trip_id()
        if tid is None:
            self.totals_var.set("(no trips)")
            self._build_actions()
            return
        try:
            rows = data.list_booking_views(
                trip_id=tid,
                status=self.f_status.get() or None,
                payment_state=self.f_pay.get() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        if self.f_consent.get():
            rows = [v for v in rows if not v.booking.consent_received]
        paid_t = bal_t = 0.0
        for v in rows:
            paid_t += v.paid
            bal_t  += v.balance if v.is_active else 0
            tags = []
            if v.booking.status in ("Cancelled", "Withdrawn", "Waitlist"):
                tags.append(v.booking.status)
            if v.payment_state in ("Unpaid", "Paid"):
                tags.append(v.payment_state)
            self.tree.insert("", "end", iid=str(v.booking.booking_id),
                                values=(
                v.booking.booking_id, v.booking.student_id,
                v.student_name, v.booking.booking_date,
                v.booking.status,
                "Y" if v.booking.consent_received else "—",
                _money(v.paid), _money(v.balance),
                v.payment_state,
                (v.booking.notes or "").replace("\n", " ⏎ "),
            ), tags=tuple(tags))
        self.totals_var.set(
            f"{len(rows)} booking(s).  "
            f"Paid {_money(round(paid_t, 2))}    "
            f"Active balance {_money(round(bal_t, 2))}")
        self._build_actions()

    def _selected_booking(self) -> Booking | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return data.get_booking(int(sel[0]))

    def _view_selected(self) -> None:
        b = self._selected_booking()
        if b is None:
            messagebox.showinfo("View", "Select a booking first.")
            return
        v = data.view_booking(b.booking_id)
        if v is None:
            return
        lines = [
            f"Booking      : #{b.booking_id}",
            f"Trip         : #{v.trip.trip_id}  {v.trip.name}  "
            f"({v.trip.start_date})",
            f"Student      : {b.student_id} — {v.student_name}",
            f"Booked       : {b.booking_date}",
            f"Status       : {b.status}",
            f"Consent      : "
            f"{'Yes' if b.consent_received else 'No'}"
            + (f"  ({b.consent_note})" if b.consent_note else ""),
            f"Medical      : {b.medical_note or '—'}",
            f"Dietary      : {b.dietary_note or '—'}",
            "",
            f"Cost         : {_money(v.trip.cost_per_place)}",
            f"Deposit      : {_money(v.trip.deposit)}",
            f"Paid         : {_money(v.paid)}",
            f"Balance      : {_money(v.balance)}",
            f"Payment state: {v.payment_state}",
        ]
        if b.notes:
            lines.extend(["", "Notes:", b.notes])
        payments = data.list_payments(booking_id=b.booking_id)
        if payments:
            lines.extend(["", f"Payments ({len(payments)}):"])
            for p in payments:
                lines.append(
                    f"  #{p.payment_id}  {p.paid_on}  "
                    f"{_money(p.amount)}  {p.method:<14}  {p.status}"
                    + (f"  ref={p.reference}" if p.reference else ""))
        messagebox.showinfo(f"Booking #{b.booking_id}",
                              "\n".join(lines))

    def _new(self) -> None:
        tid = self._selected_trip_id()
        if tid is None:
            messagebox.showinfo("New", "Pick a trip first.")
            return
        t = data.get_trip(tid)
        if t is None:
            return
        BookingDialog(self.frame.winfo_toplevel(),
                        trip=t, existing=None,
                        on_save=self.refresh)

    def _edit_selected(self) -> None:
        b = self._selected_booking()
        if b is None:
            messagebox.showinfo("Edit", "Select a booking first.")
            return
        t = data.get_trip(b.trip_id)
        if t is None:
            return
        BookingDialog(self.frame.winfo_toplevel(),
                        trip=t, existing=b,
                        on_save=self.refresh)

    def _status_selected(self) -> None:
        b = self._selected_booking()
        if b is None:
            messagebox.showinfo("Status", "Select a booking first.")
            return
        StatusDialog(self.frame.winfo_toplevel(),
                      title=f"Booking #{b.booking_id} status",
                      current=b.status, options=list(BOOKING_STATUSES),
                      on_save=lambda s:
                          self._save_status(b.booking_id, s))

    def _save_status(self, bid: int, status: str) -> None:
        try:
            data.set_booking_status(bid, status)
        except ValidationError as e:
            messagebox.showerror("Failed", str(e))
            return
        self.refresh()

    def _add_payment(self) -> None:
        b = self._selected_booking()
        if b is None:
            messagebox.showinfo("Payment", "Select a booking first.")
            return
        v = data.view_booking(b.booking_id)
        if v is None:
            return
        PaymentDialog(self.frame.winfo_toplevel(),
                        booking_view=v, existing=None,
                        on_save=self.refresh)

    def _delete_selected(self) -> None:
        b = self._selected_booking()
        if b is None:
            messagebox.showinfo("Delete", "Select a booking first.")
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete booking #{b.booking_id}?\n\n"
                f"This also deletes its payments."):
            return
        try:
            data.delete_booking(b.booking_id)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


class BookingDialog:
    def __init__(self, parent: tk.Misc, *,
                 trip: Trip, existing: Booking | None,
                 on_save: Callable[[], None]) -> None:
        self.trip = trip
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Booking" if existing else "New Booking")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        r = 0
        ttk.Label(form,
                   text=f"Trip #{self.trip.trip_id}  {self.trip.name}\n"
                        f"({self.trip.start_date}, "
                        f"cost {_money(self.trip.cost_per_place)})",
                   justify="left", foreground="#444").grid(
            row=r, column=0, columnspan=2, sticky="w", pady=(0, 8))
        r += 1

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

        ttk.Label(form, text="Booking date:").grid(row=r, column=0,
                                                       sticky="e", pady=3)
        self.bd_e = ttk.Entry(form, width=14)
        self.bd_e.insert(0, self.existing.booking_date
                              if self.existing
                              else _date.today().isoformat())
        self.bd_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Status:").grid(row=r, column=0,
                                                sticky="e", pady=3)
        self.status_cb = ttk.Combobox(form, values=BOOKING_STATUSES,
                                          state="readonly", width=14)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_BOOKING_STATUS)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Consent:").grid(row=r, column=0,
                                                sticky="e", pady=3)
        self.consent_var = tk.BooleanVar(
            value=self.existing.consent_received if self.existing
            else False)
        ttk.Checkbutton(form, text="Received",
                          variable=self.consent_var).grid(
            row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Consent note:").grid(row=r, column=0,
                                                      sticky="e", pady=3)
        self.cn_e = ttk.Entry(form, width=50)
        if self.existing and self.existing.consent_note:
            self.cn_e.insert(0, self.existing.consent_note)
        self.cn_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Medical note:").grid(row=r, column=0,
                                                      sticky="ne", pady=3)
        self.med_text = tk.Text(form, width=50, height=2, wrap="word")
        if self.existing and self.existing.medical_note:
            self.med_text.insert("1.0", self.existing.medical_note)
        self.med_text.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Dietary note:").grid(row=r, column=0,
                                                       sticky="ne", pady=3)
        self.diet_text = tk.Text(form, width=50, height=2, wrap="word")
        if self.existing and self.existing.dietary_note:
            self.diet_text.insert("1.0", self.existing.dietary_note)
        self.diet_text.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                              sticky="ne", pady=3)
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
        payload = {
            "student_id":       sid,
            "booking_date":     self.bd_e.get().strip(),
            "status":           self.status_cb.get(),
            "consent_received": self.consent_var.get(),
            "consent_note":     self.cn_e.get().strip(),
            "medical_note":     self.med_text.get("1.0",
                                                     "end").strip(),
            "dietary_note":     self.diet_text.get("1.0",
                                                      "end").strip(),
            "notes":            self.notes_text.get("1.0",
                                                       "end").strip(),
        }
        try:
            if self.existing:
                data.update_booking(
                    self.existing.booking_id, payload)
            else:
                data.create_booking(self.trip.trip_id, payload)
        except ValidationError as e:
            messagebox.showerror("Validation", str(e))
            return
        except Exception as e:
            logger.exception("save booking failed")
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class PaymentDialog:
    def __init__(self, parent: tk.Misc, *,
                 booking_view: data.BookingView | None,
                 existing: Payment | None,
                 on_save: Callable[[], None]) -> None:
        self.bv = booking_view
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Payment" if existing
                          else "Record Payment")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        r = 0
        if self.bv:
            ttk.Label(form,
                       text=f"Booking #{self.bv.booking.booking_id} "
                            f"({self.bv.trip.name})\n"
                            f"Cost: {_money(self.bv.trip.cost_per_place)}    "
                            f"Paid: {_money(self.bv.paid)}    "
                            f"Balance: {_money(self.bv.balance)}",
                       justify="left", foreground="#444").grid(
                row=r, column=0, columnspan=2, sticky="w", pady=(0, 8))
            r += 1
        elif self.existing:
            ttk.Label(form,
                       text=f"Editing payment for booking "
                            f"#{self.existing.booking_id}").grid(
                row=r, column=0, columnspan=2, sticky="w", pady=(0, 8))
            r += 1

        ttk.Label(form,
                   text=f"Amount ({CURRENCY_SYMBOL}):").grid(
            row=r, column=0, sticky="e", pady=3)
        self.amt_e = ttk.Entry(form, width=12)
        if self.existing:
            self.amt_e.insert(0, f"{self.existing.amount:.2f}")
        elif self.bv and self.bv.balance > 0:
            self.amt_e.insert(0, f"{self.bv.balance:.2f}")
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
                data.update_payment(self.existing.payment_id, payload)
            else:
                data.add_payment(self.bv.booking.booking_id, payload)
        except ValidationError as e:
            messagebox.showerror("Validation", str(e))
            return
        except Exception as e:
            logger.exception("save payment failed")
            messagebox.showerror("Save failed", str(e))
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
        ttk.Label(bar, text="Trip ID:").pack(side="left")
        self.f_trip = ttk.Entry(bar, width=8)
        self.f_trip.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Student:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Method:").pack(side="left")
        self.f_method = ttk.Combobox(bar,
                                        values=("",) + PAYMENT_METHODS,
                                        state="readonly", width=16)
        self.f_method.current(0)
        self.f_method.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar,
                                        values=("",) + PAYMENT_STATUSES,
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
        cols = ("id", "booking", "paid_on", "amount", "method",
                "status", "ref", "by", "notes")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = {"id": 50, "booking": 60, "paid_on": 100, "amount": 80,
                  "method": 130, "status": 90, "ref": 160, "by": 120,
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
        self.tree.tag_configure("Refunded", foreground="#888")
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
        self.f_trip.delete(0, "end")
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
            tid = self.f_trip.get().strip()
            rows = data.list_payments(
                trip_id=int(tid) if tid else None,
                student_id=self.f_student.get().strip() or None,
                method=self.f_method.get() or None,
                status=self.f_status.get() or None,
                date_from=self.f_from.get().strip() or None,
                date_to=self.f_to.get().strip() or None,
            )
        except (ValidationError, ValueError) as e:
            messagebox.showerror("Filter error", str(e))
            return
        cleared = 0.0
        for p in rows:
            tags = (p.status,) if p.status in (
                "Pending", "Failed", "Refunded") else ()
            if p.status == "Cleared":
                cleared += p.amount
            self.tree.insert("", "end", iid=str(p.payment_id), values=(
                p.payment_id, p.booking_id, p.paid_on,
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

    def _edit(self) -> None:
        p = self._selected()
        if p is None:
            messagebox.showinfo("Edit", "Select a payment first.")
            return
        v = data.view_booking(p.booking_id)
        PaymentDialog(self.frame.winfo_toplevel(),
                        booking_view=v, existing=p,
                        on_save=self.refresh)

    def _delete(self) -> None:
        p = self._selected()
        if p is None:
            messagebox.showinfo("Delete", "Select a payment first.")
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete payment #{p.payment_id} "
                f"({_money(p.amount)})?"):
            return
        try:
            data.delete_payment(p.payment_id)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


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
        L.append("Trips")
        L.append("-----")
        L.append(f"  Total              : {s.total_trips}")
        L.append(f"  Upcoming           : {s.upcoming_trips}")
        L.append(f"  Open for booking   : {s.open_for_booking}")
        L.append(f"  Completed          : {s.completed}")
        L.append(f"  Cancelled          : {s.cancelled}")
        if s.next_trip:
            t = s.next_trip
            L.append("")
            L.append(f"  Next: #{t.trip_id}  {t.start_date}  "
                      f"{t.name}  ({t.status})")
        L.append("")
        L.append("Bookings")
        L.append("--------")
        L.append(f"  Total              : {s.total_bookings}")
        L.append(f"  Active             : {s.active_bookings}")
        L.append(f"  Waitlist           : {s.waitlist_count}")
        L.append(f"  Consent missing    : {s.consent_missing}")
        L.append("")
        L.append("Money (active bookings)")
        L.append("-----------------------")
        L.append(f"  Charged            : {_money(s.total_charged)}")
        L.append(f"  Paid               : {_money(s.total_paid)}")
        L.append(f"  Outstanding        : {_money(s.total_outstanding)}")
        L.append(f"  Overdue balance    : {_money(s.overdue_balance)}")
        L.append("")
        L.append("Trips by status")
        L.append("---------------")
        for ts in TRIP_STATUSES:
            n = s.by_trip_status.get(ts, 0)
            if n:
                L.append(f"  {ts:<22} : {n}")
        L.append("")
        L.append("Bookings by status")
        L.append("------------------")
        for bs in BOOKING_STATUSES:
            n = s.by_booking_status.get(bs, 0)
            if n:
                L.append(f"  {bs:<14} : {n}")
        L.append("")
        L.append("Payment states (active bookings)")
        L.append("--------------------------------")
        for ps in PAYMENT_STATES:
            n = s.by_payment_state.get(ps, 0)
            if n:
                L.append(f"  {ps:<10} : {n}")
        L.append("")
        L.append("Payments by method")
        L.append("------------------")
        for m in PAYMENT_METHODS:
            v = s.by_method.get(m, 0.0)
            if v:
                L.append(f"  {m:<18} : {_money(v)}")
        if s.top_trips_by_revenue:
            L.append("")
            L.append("Top trips by revenue")
            L.append("--------------------")
            for tid, name, rev in s.top_trips_by_revenue:
                L.append(f"  #{tid:<3}  {name[:30]:<30}  {_money(rev)}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(L))
        self.text.configure(state="disabled")
