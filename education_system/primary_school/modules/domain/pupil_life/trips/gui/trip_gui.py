"""Trip management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.pupil_life.trips.services.trip_service import TripService
import traceback


class _AttendeesDialog(tk.Toplevel):
    """Dialog to manage trip attendees."""

    def __init__(self, parent, service, trip_id):
        super().__init__(parent)
        self.title("Manage Attendees")
        self.geometry("400x400")
        self.resizable(False, False)
        self.grab_set()
        self._service = service
        self._trip_id = trip_id

        tk.Label(self, text="Trip Attendees", font=("Helvetica", 11, "bold")).pack(pady=5)

        list_frame = tk.Frame(self)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self._listbox = tk.Listbox(list_frame)
        self._listbox.pack(side="left", fill="both", expand=True)
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(btn_frame, text="Pupil ID:").pack(side="left")
        self._pupil_entry = tk.Entry(btn_frame, width=15)
        self._pupil_entry.pack(side="left", padx=5)
        tk.Button(btn_frame, text="Add", command=self._add_attendee).pack(side="left", padx=3)
        tk.Button(btn_frame, text="Remove Selected", command=self._remove_attendee).pack(side="left", padx=3)

        tk.Button(self, text="Close", command=self.destroy, width=12).pack(pady=10)

        self._load_attendees()
        self.transient(parent)
        self.wait_visibility()
        self.grab_set()

    def _load_attendees(self):
        self._listbox.delete(0, tk.END)
        try:
            attendees = self._service.list_trip_attendees(self._trip_id)
            for a in attendees:
                self._listbox.insert(tk.END, a.get("pupil_id", a.get("id", "")))
        except Exception:
            traceback.print_exc()
            pass

    def _add_attendee(self):
        pupil_id = self._pupil_entry.get().strip()
        if not pupil_id:
            messagebox.showwarning("Validation", "Enter a Pupil ID.", parent=self)
            return
        try:
            self._service.add_trip_attendee(self._trip_id, pupil_id)
            self._pupil_entry.delete(0, tk.END)
            self._load_attendees()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e), parent=self)

    def _remove_attendee(self):
        sel = self._listbox.curselection()
        if not sel:
            messagebox.showwarning("Selection", "Select an attendee first.", parent=self)
            return
        pupil_id = self._listbox.get(sel[0])
        try:
            self._service.remove_trip_attendee(self._trip_id, pupil_id)
            self._load_attendees()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e), parent=self)


class _TripDialog(tk.Toplevel):
    """Add / Edit trip dialog."""

    def __init__(self, parent, db_path, record=None):
        super().__init__(parent)
        self.result = None
        self._record = record
        self.title("Edit Trip" if record else "Add Trip")
        self.geometry("480x480")
        self.resizable(False, False)
        self.grab_set()

        self._entries = {}

        self._add_field("trip_name", "Trip Name *")
        self._add_field("destination", "Destination *")
        self._add_field("description", "Description")
        self._add_field("trip_date", "Trip Date (YYYY-MM-DD) *")
        self._add_field("return_date", "Return Date (YYYY-MM-DD)")
        self._add_field("year_groups", "Year Groups")
        self._add_field("lead_staff_id", "Lead Staff ID")
        self._add_field("cost", "Cost")
        self._add_field("max_places", "Max Places")
        self._add_check("risk_assessment", "Risk Assessment Completed")

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
                elif isinstance(widget, ttk.Combobox):
                    widget.set(str(val))
                else:
                    widget.delete(0, tk.END)
                    widget.insert(0, str(val))

        self.transient(parent)
        self.wait_visibility()
        self.grab_set()

    def _add_field(self, key, label, default=""):
        frm = tk.Frame(self)
        frm.pack(fill="x", padx=10, pady=2)
        tk.Label(frm, text=label, width=24, anchor="w").pack(side="left")
        entry = tk.Entry(frm, width=30)
        entry.pack(side="left", fill="x", expand=True)
        if default:
            entry.insert(0, default)
        self._entries[key] = entry

    def _add_combo(self, key, label, values):
        frm = tk.Frame(self)
        frm.pack(fill="x", padx=10, pady=2)
        tk.Label(frm, text=label, width=24, anchor="w").pack(side="left")
        combo = ttk.Combobox(frm, values=values, state="readonly", width=27)
        combo.pack(side="left", fill="x", expand=True)
        if values:
            combo.set(values[0])
        self._entries[key] = combo

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
            elif isinstance(widget, ttk.Combobox):
                data[key] = widget.get()
            else:
                data[key] = widget.get().strip()
        if not data.get("trip_name"):
            messagebox.showwarning("Validation", "Trip name is required.", parent=self)
            return
        if not data.get("destination"):
            messagebox.showwarning("Validation", "Destination is required.", parent=self)
            return
        if not data.get("trip_date"):
            messagebox.showwarning("Validation", "Trip date is required.", parent=self)
            return
        self.result = data
        self.destroy()


class TripFrame(tk.Frame):
    """Main trip management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = TripService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Trip Management", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Add Trip", command=self._on_add).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Button(toolbar, text="Manage Attendees", command=self._on_manage_attendees).pack(side="left", padx=3)

        # Treeview
        columns = ("trip_id", "trip_name", "destination", "trip_date",
                   "year_groups", "cost", "status")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=110)
        self._tree.column("trip_id", width=70)
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
        try:
            records = self._service.list_trips()
            for r in records:
                rid = r.get("trip_id", r.get("id"))
                self._tree.insert("", tk.END, iid=rid, values=(
                    rid, r.get("trip_name", ""), r.get("destination", ""),
                    r.get("trip_date", ""), r.get("year_groups", ""),
                    r.get("cost", ""), r.get("status", ""),
                ))
            self._status_var.set(f"{len(records)} trip(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load trips: {e}")

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a trip first.")
            return None
        return sel[0]

    def _on_add(self):
        dlg = _TripDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.create_trip(**dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit(self):
        rid = self._selected_id()
        if not rid:
            return
        record = self._service.get_trip(rid)
        if not record:
            messagebox.showerror("Error", "Trip not found.")
            return
        dlg = _TripDialog(self, self._db_path, record=record)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_trip(rid, **dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete(self):
        rid = self._selected_id()
        if not rid:
            return
        if not messagebox.askyesno("Confirm", f"Delete trip {rid}?"):
            return
        try:
            self._service.delete_trip(rid)
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))

    def _on_manage_attendees(self):
        rid = self._selected_id()
        if not rid:
            return
        dlg = _AttendeesDialog(self, self._service, rid)
        self.wait_window(dlg)
