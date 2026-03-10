"""Parents evening management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.communication.parents_evening.services.parents_evening_service import ParentsEveningService
import traceback


class _EventDialog(tk.Toplevel):
    """Add / Edit parents evening event dialog."""

    def __init__(self, parent, db_path, record=None):
        super().__init__(parent)
        self.result = None
        self._record = record
        self.title("Edit Event" if record else "Add Parents Evening")
        self.geometry("450x320")
        self.resizable(False, False)
        self.grab_set()

        self._entries = {}

        self._add_field("title", "Title *")
        self._add_field("event_date", "Event Date (YYYY-MM-DD) *")
        self._add_field("start_time", "Start Time (HH:MM)")
        self._add_field("end_time", "End Time (HH:MM)")
        self._add_field("slot_duration", "Slot Duration (mins)", default="10")
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

    def _save(self):
        data = {}
        for key, widget in self._entries.items():
            data[key] = widget.get().strip()
        if not data.get("title"):
            messagebox.showwarning("Validation", "Title is required.", parent=self)
            return
        if not data.get("event_date"):
            messagebox.showwarning("Validation", "Event date is required.", parent=self)
            return
        self.result = data
        self.destroy()


class ParentsEveningFrame(tk.Frame):
    """Main parents evening management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = ParentsEveningService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Parents Evening", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Add Event", command=self._on_add_event).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Event", command=self._on_edit_event).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Event", command=self._on_delete_event).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Button(toolbar, text="Book Slot", command=self._on_book_slot).pack(side="left", padx=3)

        # Events treeview
        tk.Label(self, text="Events", font=("Helvetica", 11, "bold"),
                 anchor="w").pack(fill="x", padx=10, pady=(5, 2))

        event_columns = ("event_id", "title", "event_date", "slot_duration",
                         "year_groups", "status")
        event_frame = tk.Frame(self)
        event_frame.pack(fill="x", padx=5, pady=2)
        self._event_tree = ttk.Treeview(event_frame, columns=event_columns,
                                         show="headings", selectmode="browse", height=6)
        for col in event_columns:
            self._event_tree.heading(col, text=col.replace("_", " ").title())
            self._event_tree.column(col, width=110)
        self._event_tree.column("event_id", width=70)
        vsb1 = ttk.Scrollbar(event_frame, orient="vertical", command=self._event_tree.yview)
        self._event_tree.configure(yscrollcommand=vsb1.set)
        self._event_tree.pack(side="left", fill="x", expand=True)
        vsb1.pack(side="right", fill="y")
        self._event_tree.bind("<<TreeviewSelect>>", self._on_event_selected)

        # Slots treeview
        tk.Label(self, text="Slots", font=("Helvetica", 11, "bold"),
                 anchor="w").pack(fill="x", padx=10, pady=(5, 2))

        slot_columns = ("slot_id", "teacher", "slot_time", "pupil", "parent", "status")
        slot_frame = tk.Frame(self)
        slot_frame.pack(fill="both", expand=True, padx=5, pady=2)
        self._slot_tree = ttk.Treeview(slot_frame, columns=slot_columns,
                                        show="headings", selectmode="browse")
        for col in slot_columns:
            self._slot_tree.heading(col, text=col.replace("_", " ").title())
            self._slot_tree.column(col, width=110)
        self._slot_tree.column("slot_id", width=70)
        vsb2 = ttk.Scrollbar(slot_frame, orient="vertical", command=self._slot_tree.yview)
        self._slot_tree.configure(yscrollcommand=vsb2.set)
        self._slot_tree.pack(side="left", fill="both", expand=True)
        vsb2.pack(side="right", fill="y")

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, anchor="w", bg="#ecf0f1",
                 padx=10).pack(fill="x", side="bottom")

        self._load_events()

    def refresh(self):
        self._load_events()

    def _load_events(self):
        for item in self._event_tree.get_children():
            self._event_tree.delete(item)
        try:
            records = self._service.list_events()
            for r in records:
                rid = r.get("event_id", r.get("id"))
                self._event_tree.insert("", tk.END, iid=rid, values=(
                    rid, r.get("title", ""), r.get("event_date", ""),
                    r.get("slot_duration", ""), r.get("year_groups", ""),
                    r.get("status", ""),
                ))
            self._status_var.set(f"{len(records)} event(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load events: {e}")

    def _on_event_selected(self, event=None):
        sel = self._event_tree.selection()
        if not sel:
            return
        self._load_slots(sel[0])

    def _load_slots(self, event_id):
        for item in self._slot_tree.get_children():
            self._slot_tree.delete(item)
        try:
            records = self._service.list_slots(event_id)
            for r in records:
                rid = r.get("slot_id", r.get("id"))
                self._slot_tree.insert("", tk.END, iid=rid, values=(
                    rid, r.get("teacher", ""), r.get("slot_time", ""),
                    r.get("pupil", ""), r.get("parent", ""),
                    r.get("status", ""),
                ))
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load slots: {e}")

    def _selected_event_id(self):
        sel = self._event_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select an event first.")
            return None
        return sel[0]

    def _on_add_event(self):
        dlg = _EventDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.create_event(**dlg.result)
                self._load_events()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit_event(self):
        rid = self._selected_event_id()
        if not rid:
            return
        record = self._service.get_event(rid)
        if not record:
            messagebox.showerror("Error", "Event not found.")
            return
        dlg = _EventDialog(self, self._db_path, record=record)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_event(rid, **dlg.result)
                self._load_events()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete_event(self):
        rid = self._selected_event_id()
        if not rid:
            return
        if not messagebox.askyesno("Confirm", f"Delete event {rid}?"):
            return
        try:
            self._service.delete_event(rid)
            self._load_events()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))

    def _on_book_slot(self):
        rid = self._selected_event_id()
        if not rid:
            return

        dlg = tk.Toplevel(self)
        dlg.title("Book Slot")
        dlg.geometry("380x250")
        dlg.resizable(False, False)
        dlg.grab_set()

        entries = {}
        for key, label in [("teacher", "Teacher *"), ("slot_time", "Slot Time (HH:MM) *"),
                           ("pupil", "Pupil ID *"), ("parent", "Parent Name")]:
            frm = tk.Frame(dlg)
            frm.pack(fill="x", padx=10, pady=2)
            tk.Label(frm, text=label, width=18, anchor="w").pack(side="left")
            e = tk.Entry(frm, width=25)
            e.pack(side="left", fill="x", expand=True)
            entries[key] = e

        def save():
            data = {k: v.get().strip() for k, v in entries.items()}
            if not data.get("teacher") or not data.get("slot_time") or not data.get("pupil"):
                messagebox.showwarning("Validation", "Teacher, time and pupil are required.", parent=dlg)
                return
            try:
                self._service.book_slot(rid, **data)
                dlg.destroy()
                self._load_slots(rid)
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e), parent=dlg)

        btn_frame = tk.Frame(dlg)
        btn_frame.pack(fill="x", pady=10, padx=10)
        tk.Button(btn_frame, text="Book", command=save, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=dlg.destroy, width=12).pack(side="right", padx=5)

        dlg.transient(self)
        dlg.wait_visibility()
        dlg.grab_set()
