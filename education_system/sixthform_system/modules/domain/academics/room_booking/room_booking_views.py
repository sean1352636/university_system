"""Tkinter views for Room & Resource Booking.

Single window with three tabs:

* **Bookings** — filterable table (status, resource, date range,
  booked-by), with create / edit / cancel / delete actions. Add /
  edit prompts to override clashes when detected.
* **Resources** — directory CRUD for rooms / AV / sports facilities.
* **Summary** — counts of resources / bookings, today + upcoming
  bookings, status and type breakdowns.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from education_system.shared import branding
from education_system.sixthform_system.modules.domain.academics.room_booking import (
    room_booking as data,
)
from education_system.sixthform_system.modules.domain.academics.room_booking.room_booking import (
    BOOKING_STATUSES,
    Booking,
    ClashError,
    DEFAULT_BOOKING_STATUS,
    DEFAULT_RESOURCE_TYPE,
    RESOURCE_TYPES,
    Resource,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STATUS_TAGS: dict[str, tuple[str, str]] = {
    "Pending":   ("#fff7e6", "#7a5800"),
    "Confirmed": ("#e6f7e6", "#0d6b2a"),
    "Cancelled": ("#eeeeee", "#666666"),
}


def open_directory(parent=None) -> None:
    try:
        data.init_db()
    except Exception:
        logger.exception("Room-booking init_db failed")
        messagebox.showerror(
            "Room Booking",
            "Could not initialise the database. Check logs.")
        return

    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Room Booking — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    resources_tab = ResourcesTab(nb, win)
    bookings_tab = BookingsTab(nb, win)
    resources_tab.set_refresh_callback(bookings_tab.refresh)
    SummaryTab(nb, bookings_tab, resources_tab)


def _resource_options(*, active_only: bool = False
                        ) -> list[tuple[int, str]]:
    rows = data.list_resources(active_only=active_only)
    return [(r.resource_id, f"{r.name} ({r.resource_type})")
            for r in rows]


# ─────────────────────────────────────────────────────────────────
# Bookings tab
# ─────────────────────────────────────────────────────────────────

class BookingsTab:
    def __init__(self, nb: ttk.Notebook, root: tk.Misc) -> None:
        self.root = root
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Bookings")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(
            bar, values=("",) + BOOKING_STATUSES,
            state="readonly", width=12)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="From:").pack(side="left")
        self.f_from = ttk.Entry(bar, width=12)
        self.f_from.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="To:").pack(side="left")
        self.f_to = ttk.Entry(bar, width=12)
        self.f_to.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Booked by:").pack(side="left")
        self.f_by = ttk.Entry(bar, width=16)
        self.f_by.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Today",
                    command=self._filter_today).pack(side="left")
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left", padx=(4, 0))
        ttk.Button(bar, text="New booking",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "date", "start", "end", "resource", "type",
                "by", "purpose", "att", "status")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "date": 100, "start": 60, "end": 60,
                   "resource": 220, "type": 110, "by": 130,
                   "purpose": 260, "att": 60, "status": 90}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "start", "end",
                                                  "att")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _STATUS_TAGS.items():
            self.tree.tag_configure(status, background=bg, foreground=fg)
        self.tree.bind("<Double-Button-1>", lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("View / Edit", self._edit),
                ("Cancel",       self._cancel),
                ("Delete",       self._delete),
                ("Refresh",      self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _clear(self) -> None:
        self.f_status.current(0)
        self.f_from.delete(0, "end")
        self.f_to.delete(0, "end")
        self.f_by.delete(0, "end")
        self.refresh()

    def _filter_today(self) -> None:
        today = _dt.date.today().isoformat()
        self.f_from.delete(0, "end")
        self.f_from.insert(0, today)
        self.f_to.delete(0, "end")
        self.f_to.insert(0, today)
        self.refresh()

    def _filters(self) -> dict[str, Any]:
        f: dict[str, Any] = {}
        if self.f_status.get():
            f["status"] = self.f_status.get()
        if self.f_from.get().strip():
            f["date_from"] = self.f_from.get().strip()
        if self.f_to.get().strip():
            f["date_to"] = self.f_to.get().strip()
        if self.f_by.get().strip():
            f["booked_by_like"] = self.f_by.get().strip()
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.list_bookings_with_detail(**self._filters())
        except ValidationError as e:
            messagebox.showwarning("Room Booking", str(e))
            return
        except Exception as e:
            logger.exception("Bookings refresh failed")
            messagebox.showerror("Room Booking",
                                   f"Could not load bookings: {e}")
            return
        for r in rows:
            b = r.booking
            self.tree.insert(
                "", "end", iid=str(b.booking_id),
                values=(b.booking_id, b.booking_date,
                          b.start_time, b.end_time,
                          r.resource_name, r.resource_type,
                          b.booked_by, b.purpose,
                          b.attendee_count
                              if b.attendee_count is not None else "—",
                          b.status),
                tags=(b.status,),
            )
        self.count.configure(text=f"{len(rows)} booking(s)")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Room Booking",
                                 "Select a booking first.")
            return None
        try:
            return int(sel[0])
        except (TypeError, ValueError):
            return None

    def _new(self) -> None:
        if not data.list_resources(active_only=True):
            messagebox.showinfo(
                "Room Booking",
                "Add at least one active resource first "
                "(Resources tab).")
            return
        BookingDialog(self.root, on_save=lambda _b: self.refresh())

    def _edit(self) -> None:
        bid = self._selected_id()
        if bid is None:
            return
        b = data.get_booking(bid)
        if b is None:
            self.refresh()
            return
        BookingDialog(self.root, booking=b,
                        on_save=lambda _b: self.refresh())

    def _cancel(self) -> None:
        bid = self._selected_id()
        if bid is None:
            return
        if not messagebox.askyesno(
                "Room Booking", f"Cancel booking #{bid}?"):
            return
        try:
            data.cancel_booking(bid)
        except ValidationError as e:
            messagebox.showwarning("Room Booking", str(e))
            return
        except Exception as e:
            logger.exception("cancel_booking failed")
            messagebox.showerror("Room Booking",
                                   f"Cancel failed: {e}")
            return
        self.refresh()

    def _delete(self) -> None:
        bid = self._selected_id()
        if bid is None:
            return
        if not messagebox.askyesno(
                "Room Booking", f"Delete booking #{bid}?"):
            return
        try:
            data.delete_booking(bid)
        except Exception as e:
            logger.exception("delete_booking failed")
            messagebox.showerror("Room Booking",
                                   f"Delete failed: {e}")
            return
        self.refresh()


# ─────────────────────────────────────────────────────────────────
# Booking dialog
# ─────────────────────────────────────────────────────────────────

class BookingDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, *,
                 booking: Booking | None = None,
                 on_save) -> None:
        super().__init__(master)
        self.booking = booking
        self.on_save = on_save
        self.title("Edit Booking" if booking else "New Booking")
        self.geometry("720x680")
        self.transient(master)
        # Defer grab until the window is actually viewable — Tk
        # raises "grab failed: window not viewable" if grab_set runs
        # before the window mapping has been processed. after_idle
        # queues the grab for the next idle slice of the event loop.
        self.after_idle(self._safe_grab)

    def _safe_grab(self) -> None:
        try:
            self.grab_set()
        except Exception:
            pass

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)
        row = 0

        ttk.Label(frm, text="Resource:").grid(
            row=row, column=0, sticky="w", pady=4)
        opts = _resource_options(active_only=booking is None)
        self._resource_map = {lbl: rid for rid, lbl in opts}
        self.cb_resource = ttk.Combobox(
            frm, values=[lbl for _rid, lbl in opts],
            state="readonly")
        if booking:
            current = next(
                (lbl for rid, lbl in opts if rid == booking.resource_id),
                "")
            if not current:
                res = data.get_resource(booking.resource_id)
                if res:
                    current = f"{res.name} ({res.resource_type})"
                    self.cb_resource["values"] = (
                        list(self.cb_resource["values"]) + [current])
                    self._resource_map[current] = booking.resource_id
            self.cb_resource.set(current)
        self.cb_resource.grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Label(frm, text="Date (YYYY-MM-DD):").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_date = ttk.Entry(frm)
        self.e_date.grid(row=row, column=1, sticky="ew", pady=4)
        self.e_date.insert(0, booking.booking_date if booking
                              else _dt.date.today().isoformat())
        row += 1

        ttk.Label(frm, text="Start time (HH:MM):").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_start = ttk.Entry(frm)
        self.e_start.grid(row=row, column=1, sticky="ew", pady=4)
        if booking:
            self.e_start.insert(0, booking.start_time)
        row += 1

        ttk.Label(frm, text="End time (HH:MM):").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_end = ttk.Entry(frm)
        self.e_end.grid(row=row, column=1, sticky="ew", pady=4)
        if booking:
            self.e_end.insert(0, booking.end_time)
        row += 1

        ttk.Label(frm, text="Booked by:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_by = ttk.Entry(frm)
        self.e_by.grid(row=row, column=1, sticky="ew", pady=4)
        if booking:
            self.e_by.insert(0, booking.booked_by)
        row += 1

        ttk.Label(frm, text="Purpose:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_purpose = ttk.Entry(frm)
        self.e_purpose.grid(row=row, column=1, sticky="ew", pady=4)
        if booking:
            self.e_purpose.insert(0, booking.purpose)
        row += 1

        ttk.Label(frm, text="Attendee count:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_att = ttk.Entry(frm)
        self.e_att.grid(row=row, column=1, sticky="ew", pady=4)
        if booking and booking.attendee_count is not None:
            self.e_att.insert(0, str(booking.attendee_count))
        row += 1

        ttk.Label(frm, text="Status:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.cb_status = ttk.Combobox(
            frm, values=BOOKING_STATUSES, state="readonly")
        self.cb_status.set(booking.status if booking
                            else DEFAULT_BOOKING_STATUS)
        self.cb_status.grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Label(frm, text="Notes:").grid(
            row=row, column=0, sticky="nw", pady=4)
        self.t_notes = tk.Text(frm, height=6, wrap="word")
        self.t_notes.grid(row=row, column=1, sticky="ew", pady=4)
        if booking and booking.notes:
            self.t_notes.insert("1.0", booking.notes)
        row += 1

        btns = ttk.Frame(frm)
        btns.grid(row=row, column=0, columnspan=2,
                    sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Cancel",
                    command=self.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="Save",
                    command=self._save).pack(side="right", padx=4)

    def _payload(self) -> dict[str, Any]:
        rid = self._resource_map.get(self.cb_resource.get())
        return {
            "resource_id":     rid,
            "booking_date":    self.e_date.get(),
            "start_time":      self.e_start.get(),
            "end_time":        self.e_end.get(),
            "booked_by":       self.e_by.get(),
            "purpose":         self.e_purpose.get(),
            "attendee_count":  self.e_att.get().strip() or None,
            "status":          self.cb_status.get(),
            "notes":           self.t_notes.get("1.0", "end").strip(),
        }

    def _save(self) -> None:
        try:
            payload = self._payload()
            if self.booking is None:
                try:
                    b = data.create_booking(payload)
                except ClashError as e:
                    if not messagebox.askyesno(
                            "Room Booking — clash",
                            f"{e}\n\nBook anyway (override clash)?",
                            parent=self):
                        return
                    b = data.create_booking(payload, ignore_clashes=True)
            else:
                try:
                    b = data.update_booking(
                        self.booking.booking_id, payload)
                except ClashError as e:
                    if not messagebox.askyesno(
                            "Room Booking — clash",
                            f"{e}\n\nSave anyway (override clash)?",
                            parent=self):
                        return
                    b = data.update_booking(
                        self.booking.booking_id, payload,
                        ignore_clashes=True)
        except ValidationError as e:
            messagebox.showwarning("Room Booking", str(e), parent=self)
            return
        except Exception as e:
            logger.exception("Booking save failed")
            messagebox.showerror("Room Booking",
                                   f"Save failed: {e}", parent=self)
            return
        self.on_save(b)
        self.destroy()


# ─────────────────────────────────────────────────────────────────
# Resources tab
# ─────────────────────────────────────────────────────────────────

class ResourcesTab:
    def __init__(self, nb: ttk.Notebook, root: tk.Misc) -> None:
        self.root = root
        self._refresh_callback = None
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Resources")
        self._build()
        self.refresh()

    def set_refresh_callback(self, cb) -> None:
        self._refresh_callback = cb

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = ttk.Combobox(
            bar, values=("",) + RESOURCE_TYPES,
            state="readonly", width=18)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Name:").pack(side="left")
        self.f_name = ttk.Entry(bar, width=22)
        self.f_name.pack(side="left", padx=(2, 8))
        self.v_active = tk.BooleanVar()
        ttk.Checkbutton(bar, text="Active only",
                         variable=self.v_active,
                         command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="New resource",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "name", "type", "capacity", "location",
                "active")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "name": 260, "type": 140,
                   "capacity": 80, "location": 220, "active": 70}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "capacity",
                                                  "active")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<Double-Button-1>", lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("View / Edit", self._edit),
                ("Delete",       self._delete),
                ("Refresh",      self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _clear(self) -> None:
        self.f_type.current(0)
        self.f_name.delete(0, "end")
        self.v_active.set(False)
        self.refresh()

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            kw: dict[str, Any] = {}
            if self.f_type.get():
                kw["resource_type"] = self.f_type.get()
            if self.f_name.get().strip():
                kw["name_like"] = self.f_name.get().strip()
            if self.v_active.get():
                kw["active_only"] = True
            rows = data.list_resources(**kw)
        except ValidationError as e:
            messagebox.showwarning("Room Booking", str(e))
            return
        except Exception as e:
            logger.exception("Resources refresh failed")
            messagebox.showerror(
                "Room Booking",
                f"Could not load resources: {e}")
            return
        for r in rows:
            self.tree.insert(
                "", "end", iid=str(r.resource_id),
                values=(r.resource_id, r.name, r.resource_type,
                          r.capacity if r.capacity is not None else "—",
                          r.location or "—",
                          "yes" if r.active else "no"),
            )
        self.count.configure(text=f"{len(rows)} resource(s)")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Room Booking",
                                 "Select a resource first.")
            return None
        try:
            return int(sel[0])
        except (TypeError, ValueError):
            return None

    def _new(self) -> None:
        ResourceDialog(self.root, on_save=self._after_save)

    def _edit(self) -> None:
        rid = self._selected_id()
        if rid is None:
            return
        r = data.get_resource(rid)
        if r is None:
            self.refresh()
            return
        ResourceDialog(self.root, resource=r,
                         on_save=self._after_save)

    def _after_save(self, _r) -> None:
        self.refresh()
        if self._refresh_callback is not None:
            self._refresh_callback()

    def _delete(self) -> None:
        rid = self._selected_id()
        if rid is None:
            return
        if not messagebox.askyesno(
                "Room Booking", f"Delete resource #{rid}?"):
            return
        try:
            data.delete_resource(rid)
        except ValidationError as e:
            messagebox.showwarning("Room Booking", str(e))
            return
        except Exception as e:
            logger.exception("delete_resource failed")
            messagebox.showerror("Room Booking",
                                   f"Delete failed: {e}")
            return
        self._after_save(None)


class ResourceDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, *,
                 resource: Resource | None = None,
                 on_save) -> None:
        super().__init__(master)
        self.resource = resource
        self.on_save = on_save
        self.title("Edit Resource" if resource else "New Resource")
        self.geometry("620x560")
        self.transient(master)
        # Defer grab until the window is actually viewable — Tk
        # raises "grab failed: window not viewable" if grab_set runs
        # before the window mapping has been processed. after_idle
        # queues the grab for the next idle slice of the event loop.
        self.after_idle(self._safe_grab)

    def _safe_grab(self) -> None:
        try:
            self.grab_set()
        except Exception:
            pass

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)
        row = 0

        ttk.Label(frm, text="Name:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_name = ttk.Entry(frm)
        self.e_name.grid(row=row, column=1, sticky="ew", pady=4)
        if resource:
            self.e_name.insert(0, resource.name)
        row += 1

        ttk.Label(frm, text="Type:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.cb_type = ttk.Combobox(
            frm, values=RESOURCE_TYPES, state="readonly")
        self.cb_type.set(resource.resource_type if resource
                          else DEFAULT_RESOURCE_TYPE)
        self.cb_type.grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Label(frm, text="Capacity:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_cap = ttk.Entry(frm)
        self.e_cap.grid(row=row, column=1, sticky="ew", pady=4)
        if resource and resource.capacity is not None:
            self.e_cap.insert(0, str(resource.capacity))
        row += 1

        ttk.Label(frm, text="Location:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.e_loc = ttk.Entry(frm)
        self.e_loc.grid(row=row, column=1, sticky="ew", pady=4)
        if resource and resource.location:
            self.e_loc.insert(0, resource.location)
        row += 1

        self.v_active = tk.BooleanVar(
            value=resource.active if resource else True)
        ttk.Checkbutton(frm, text="Active (bookable)",
                         variable=self.v_active).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=4)
        row += 1

        ttk.Label(frm, text="Notes:").grid(
            row=row, column=0, sticky="nw", pady=4)
        self.t_notes = tk.Text(frm, height=8, wrap="word")
        self.t_notes.grid(row=row, column=1, sticky="ew", pady=4)
        if resource and resource.notes:
            self.t_notes.insert("1.0", resource.notes)
        row += 1

        btns = ttk.Frame(frm)
        btns.grid(row=row, column=0, columnspan=2,
                    sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Cancel",
                    command=self.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="Save",
                    command=self._save).pack(side="right", padx=4)

    def _payload(self) -> dict[str, Any]:
        return {
            "name":          self.e_name.get(),
            "resource_type": self.cb_type.get(),
            "capacity":      self.e_cap.get().strip() or None,
            "location":      self.e_loc.get(),
            "active":        self.v_active.get(),
            "notes":         self.t_notes.get("1.0", "end").strip(),
        }

    def _save(self) -> None:
        try:
            payload = self._payload()
            if self.resource is None:
                r = data.create_resource(payload)
            else:
                r = data.update_resource(self.resource.resource_id,
                                            payload)
        except ValidationError as e:
            messagebox.showwarning("Room Booking", str(e), parent=self)
            return
        except Exception as e:
            logger.exception("Resource save failed")
            messagebox.showerror("Room Booking",
                                   f"Save failed: {e}", parent=self)
            return
        self.on_save(r)
        self.destroy()


# ─────────────────────────────────────────────────────────────────
# Summary tab
# ─────────────────────────────────────────────────────────────────

class SummaryTab:
    def __init__(self, nb: ttk.Notebook,
                  bookings_tab: BookingsTab,
                  resources_tab: ResourcesTab) -> None:
        self.bookings_tab = bookings_tab
        self.resources_tab = resources_tab
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._build()
        self.refresh()

    def _build(self) -> None:
        top = ttk.Frame(self.frame, padding=12)
        top.pack(fill="both", expand=True)
        ttk.Button(top, text="Refresh",
                    command=self.refresh).pack(anchor="e")
        self.body = tk.Text(top, wrap="word", font=("Courier", 10),
                             height=30, state="disabled")
        self.body.pack(fill="both", expand=True, pady=(8, 0))

    def refresh(self) -> None:
        try:
            s = data.summary()
        except Exception as e:
            logger.exception("Room-booking summary failed")
            messagebox.showerror("Room Booking",
                                   f"Summary failed: {e}")
            return
        lines: list[str] = []
        lines.append(
            f"Total resources       : {s.total_resources}"
            f"  (active {s.active_resources})")
        lines.append(f"Total bookings        : {s.total_bookings}")
        lines.append(
            f"Today (non-cancelled) : {s.bookings_today}")
        lines.append(
            f"Upcoming (14 d)       : {s.upcoming_bookings}")
        lines.append("")
        lines.append("By status:")
        for st, n in s.by_status.items():
            lines.append(f"  {st:<14} {n:>4}")
        lines.append("")
        lines.append("Resources by type:")
        for t, n in s.by_resource_type.items():
            if n:
                lines.append(f"  {t:<16} {n:>4}")
        self.body.configure(state="normal")
        self.body.delete("1.0", "end")
        self.body.insert("1.0", "\n".join(lines))
        self.body.configure(state="disabled")
