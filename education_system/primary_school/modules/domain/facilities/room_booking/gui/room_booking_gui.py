"""Room booking management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.facilities.room_booking.services.room_booking_service import RoomBookingService
import traceback


class _BookingDialog(tk.Toplevel):
    """Add / Edit room booking dialog."""

    def __init__(self, parent, db_path, record=None):
        super().__init__(parent)
        self.result = None
        self._record = record
        self.title("Edit Booking" if record else "Add Booking")
        self.geometry("450x360")
        self.resizable(False, False)
        self.grab_set()

        self._entries = {}

        self._add_field("room_name", "Room Name *")
        self._add_field("booked_by", "Booked By *")
        self._add_field("purpose", "Purpose")
        self._add_field("booking_date", "Date (YYYY-MM-DD) *")
        self._add_field("start_time", "Start Time (HH:MM) *")
        self._add_field("end_time", "End Time (HH:MM) *")
        self._add_check("recurring", "Recurring")

        # Buttons
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", pady=10, padx=10)
        tk.Button(btn_frame, text="Save", command=self._save, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=self.destroy, width=12).pack(side="right", padx=5)

        if record:
            for key, widget in self._entries.items():
                val = record.get(key)
                if val is None:
                    continue
                if isinstance(widget, tk.BooleanVar):
                    widget.set(bool(val))
                else:
                    widget.delete(0, tk.END)
                    widget.insert(0, str(val))

        self.transient(parent)
        self.wait_visibility()
        self.grab_set()

    def _add_field(self, key, label, default=""):
        frm = tk.Frame(self)
        frm.pack(fill="x", padx=10, pady=2)
        tk.Label(frm, text=label, width=20, anchor="w").pack(side="left")
        entry = tk.Entry(frm, width=30)
        entry.pack(side="left", fill="x", expand=True)
        if default:
            entry.insert(0, default)
        self._entries[key] = entry

    def _add_check(self, key, label, default=False):
        frm = tk.Frame(self)
        frm.pack(fill="x", padx=10, pady=2)
        var = tk.BooleanVar(value=default)
        tk.Checkbutton(frm, text=label, variable=var).pack(anchor="w")
        self._entries[key] = var

    def _save(self):
        data = {}
        for key, widget in self._entries.items():
            if isinstance(widget, tk.BooleanVar):
                data[key] = int(widget.get())
            else:
                data[key] = widget.get().strip()
        if not data.get("room_name"):
            messagebox.showwarning("Validation", "Room name is required.", parent=self)
            return
        if not data.get("booked_by"):
            messagebox.showwarning("Validation", "Booked by is required.", parent=self)
            return
        if not data.get("booking_date"):
            messagebox.showwarning("Validation", "Date is required.", parent=self)
            return
        if not data.get("start_time") or not data.get("end_time"):
            messagebox.showwarning("Validation", "Start and end times are required.", parent=self)
            return
        self.result = data
        self.destroy()


class RoomBookingFrame(tk.Frame):
    """Main room booking management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = RoomBookingService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Room Bookings", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Add Booking", command=self._on_add).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Label(toolbar, text="Room:", bg="#d5dbdb").pack(side="left")
        self._room_filter = tk.Entry(toolbar, width=12)
        self._room_filter.pack(side="left", padx=3)

        tk.Label(toolbar, text="Date:", bg="#d5dbdb").pack(side="left", padx=(10, 0))
        self._date_filter = tk.Entry(toolbar, width=12)
        self._date_filter.pack(side="left", padx=3)

        tk.Button(toolbar, text="Filter", command=self._load_items).pack(side="left", padx=3)

        # Treeview
        columns = ("booking_id", "room_name", "booked_by", "purpose",
                   "booking_date", "start_time", "end_time", "status")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=110)
        self._tree.column("booking_id", width=70)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, anchor="w", bg="#ecf0f1",
                 padx=10).pack(fill="x", side="bottom")

        self._load_items()

    def refresh(self):
        self._load_items()

    def _load_items(self):
        for item in self._tree.get_children():
            self._tree.delete(item)
        room = self._room_filter.get().strip() or None
        date_val = self._date_filter.get().strip() or None
        try:
            records = self._service.list_bookings(room_name=room, booking_date=date_val)
            for r in records:
                rid = r.get("booking_id", r.get("id"))
                self._tree.insert("", tk.END, iid=rid, values=(
                    rid, r.get("room_name", ""), r.get("booked_by", ""),
                    r.get("purpose", ""), r.get("booking_date", ""),
                    r.get("start_time", ""), r.get("end_time", ""),
                    r.get("status", ""),
                ))
            self._status_var.set(f"{len(records)} booking(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load bookings: {e}")

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a booking first.")
            return None
        return sel[0]

    def _on_add(self):
        dlg = _BookingDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.create_booking(**dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit(self):
        rid = self._selected_id()
        if not rid:
            return
        record = self._service.get_booking(rid)
        if not record:
            messagebox.showerror("Error", "Booking not found.")
            return
        dlg = _BookingDialog(self, self._db_path, record=record)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_booking(rid, **dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete(self):
        rid = self._selected_id()
        if not rid:
            return
        if not messagebox.askyesno("Confirm", f"Delete booking {rid}?"):
            return
        try:
            self._service.delete_booking(rid)
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))
