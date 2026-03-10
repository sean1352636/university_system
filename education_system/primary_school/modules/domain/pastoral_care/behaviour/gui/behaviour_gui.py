"""Behaviour management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.pastoral_care.behaviour.services.behaviour_service import BehaviourService
from education_system.primary_school.infrastructure.database.constants import BEHAVIOUR_CATEGORIES
import traceback


class _BehaviourDialog(tk.Toplevel):
    """Add / Edit behaviour record dialog."""

    def __init__(self, parent, db_path, record=None):
        super().__init__(parent)
        self.result = None
        self._record = record
        self.title("Edit Behaviour Record" if record else "Add Behaviour Record")
        self.geometry("480x420")
        self.resizable(False, False)
        self.grab_set()

        self._entries = {}

        self._add_field("pupil_id", "Pupil ID *")
        self._add_combo("type", "Type *", ["positive", "negative"])
        self._add_combo("category", "Category *", list(BEHAVIOUR_CATEGORIES))
        self._add_field("description", "Description")
        self._add_field("points", "Points")
        self._add_field("action_taken", "Action Taken")

        # Buttons
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", pady=10, padx=10)
        tk.Button(btn_frame, text="Save", command=self._save, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=self.destroy, width=12).pack(side="right", padx=5)

        # Pre-fill for edit
        if record:
            for key, widget in self._entries.items():
                val = record.get(key)
                if val is None:
                    continue
                if isinstance(widget, ttk.Combobox):
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
        tk.Label(frm, text=label, width=20, anchor="w").pack(side="left")
        entry = tk.Entry(frm, width=30)
        entry.pack(side="left", fill="x", expand=True)
        if default:
            entry.insert(0, default)
        self._entries[key] = entry

    def _add_combo(self, key, label, values):
        frm = tk.Frame(self)
        frm.pack(fill="x", padx=10, pady=2)
        tk.Label(frm, text=label, width=20, anchor="w").pack(side="left")
        combo = ttk.Combobox(frm, values=values, state="readonly", width=27)
        combo.pack(side="left", fill="x", expand=True)
        if values:
            combo.set(values[0])
        self._entries[key] = combo

    def _save(self):
        data = {}
        for key, widget in self._entries.items():
            if isinstance(widget, ttk.Combobox):
                data[key] = widget.get()
            else:
                data[key] = widget.get().strip()
        if not data.get("pupil_id"):
            messagebox.showwarning("Validation", "Pupil ID is required.", parent=self)
            return
        if not data.get("type"):
            messagebox.showwarning("Validation", "Type is required.", parent=self)
            return
        if not data.get("category"):
            messagebox.showwarning("Validation", "Category is required.", parent=self)
            return
        self.result = data
        self.destroy()


class BehaviourFrame(tk.Frame):
    """Main behaviour management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = BehaviourService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Behaviour Management", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Add Record", command=self._on_add).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Label(toolbar, text="Type:", bg="#d5dbdb").pack(side="left")
        self._type_filter = ttk.Combobox(toolbar, values=["All", "positive", "negative"],
                                          state="readonly", width=12)
        self._type_filter.set("All")
        self._type_filter.pack(side="left", padx=3)
        self._type_filter.bind("<<ComboboxSelected>>", lambda e: self._load_items())

        # Treeview
        columns = ("behaviour_id", "pupil_id", "type", "category", "description",
                    "points", "incident_date")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=110)
        self._tree.column("behaviour_id", width=80)
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
        type_filter = self._type_filter.get()
        behaviour_type = None if type_filter == "All" else type_filter
        try:
            records = self._service.get_records(type=behaviour_type)
            for r in records:
                self._tree.insert("", tk.END, iid=r.get("behaviour_id", r.get("id")), values=(
                    r.get("behaviour_id", r.get("id")), r.get("pupil_id", ""),
                    r.get("type", ""), r.get("category", ""),
                    r.get("description", ""), r.get("points", ""),
                    r.get("incident_date", ""),
                ))
            self._status_var.set(f"{len(records)} record(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load behaviour records: {e}")

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a record first.")
            return None
        return sel[0]

    def _on_add(self):
        dlg = _BehaviourDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.record_behaviour(**dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit(self):
        rid = self._selected_id()
        if not rid:
            return
        results = self._service.get_records()
        record = next((r for r in results if str(r.get("id")) == str(rid)), None)
        if not record:
            messagebox.showerror("Error", "Record not found.")
            return
        dlg = _BehaviourDialog(self, self._db_path, record=record)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_record(rid, **dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete(self):
        rid = self._selected_id()
        if not rid:
            return
        if not messagebox.askyesno("Confirm", f"Delete behaviour record {rid}?"):
            return
        try:
            self._service.delete_record(rid)
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))
