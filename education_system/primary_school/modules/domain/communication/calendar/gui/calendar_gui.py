"""Calendar event management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.communication.calendar.services.calendar_service import CalendarService
import traceback


EVENT_TYPES = ["General", "Assembly", "Sports Day", "Parents Evening",
               "INSET", "Holiday", "Trip", "Other"]


class _CalendarDialog(tk.Toplevel):
    """Add / Edit calendar event dialog."""

    def __init__(self, parent, db_path, record=None):
        super().__init__(parent)
        self.result = None
        self._record = record
        self.title("Edit Event" if record else "Add Event")
        self.geometry("480x480")
        self.resizable(False, False)
        self.grab_set()

        self._entries = {}

        self._add_field("title", "Title *")
        self._add_field("description", "Description")
        self._add_combo("event_type", "Event Type", EVENT_TYPES)
        self._add_field("start_date", "Start Date (YYYY-MM-DD) *")
        self._add_field("end_date", "End Date (YYYY-MM-DD)")
        self._add_field("start_time", "Start Time (HH:MM)")
        self._add_field("end_time", "End Time (HH:MM)")
        self._add_field("location", "Location")
        self._add_check("all_day", "All Day Event")
        self._add_field("year_groups", "Year Groups")

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
        tk.Label(frm, text=label, width=22, anchor="w").pack(side="left")
        entry = tk.Entry(frm, width=30)
        entry.pack(side="left", fill="x", expand=True)
        if default:
            entry.insert(0, default)
        self._entries[key] = entry

    def _add_combo(self, key, label, values):
        frm = tk.Frame(self)
        frm.pack(fill="x", padx=10, pady=2)
        tk.Label(frm, text=label, width=22, anchor="w").pack(side="left")
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
        if not data.get("title"):
            messagebox.showwarning("Validation", "Title is required.", parent=self)
            return
        if not data.get("start_date"):
            messagebox.showwarning("Validation", "Start date is required.", parent=self)
            return
        self.result = data
        self.destroy()


class CalendarFrame(tk.Frame):
    """Main calendar event management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = CalendarService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Calendar Events", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Add Event", command=self._on_add).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Label(toolbar, text="Type:", bg="#d5dbdb").pack(side="left")
        self._type_filter = ttk.Combobox(toolbar, values=["All"] + EVENT_TYPES,
                                          state="readonly", width=15)
        self._type_filter.set("All")
        self._type_filter.pack(side="left", padx=3)
        self._type_filter.bind("<<ComboboxSelected>>", lambda e: self._load_items())

        tk.Label(toolbar, text="From:", bg="#d5dbdb").pack(side="left", padx=(10, 0))
        self._from_date = tk.Entry(toolbar, width=12)
        self._from_date.pack(side="left", padx=3)

        tk.Label(toolbar, text="To:", bg="#d5dbdb").pack(side="left")
        self._to_date = tk.Entry(toolbar, width=12)
        self._to_date.pack(side="left", padx=3)

        tk.Button(toolbar, text="Filter", command=self._load_items).pack(side="left", padx=3)

        # Treeview
        columns = ("event_id", "title", "event_type", "start_date",
                   "end_date", "location", "year_groups", "status")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=110)
        self._tree.column("event_id", width=70)
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
        type_val = self._type_filter.get()
        event_type = None if type_val == "All" else type_val
        from_date = self._from_date.get().strip() or None
        to_date = self._to_date.get().strip() or None
        try:
            records = self._service.list_events(
                event_type=event_type, date_from=from_date, date_to=to_date)
            for r in records:
                rid = r.get("event_id", r.get("id"))
                self._tree.insert("", tk.END, iid=rid, values=(
                    rid, r.get("title", ""), r.get("event_type", ""),
                    r.get("start_date", ""), r.get("end_date", ""),
                    r.get("location", ""), r.get("year_groups", ""),
                    r.get("status", ""),
                ))
            self._status_var.set(f"{len(records)} event(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load events: {e}")

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select an event first.")
            return None
        return sel[0]

    def _on_add(self):
        dlg = _CalendarDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.create_event(**dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit(self):
        rid = self._selected_id()
        if not rid:
            return
        record = self._service.get_event(rid)
        if not record:
            messagebox.showerror("Error", "Event not found.")
            return
        dlg = _CalendarDialog(self, self._db_path, record=record)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_event(rid, **dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete(self):
        rid = self._selected_id()
        if not rid:
            return
        if not messagebox.askyesno("Confirm", f"Delete event {rid}?"):
            return
        try:
            self._service.delete_event(rid)
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))
