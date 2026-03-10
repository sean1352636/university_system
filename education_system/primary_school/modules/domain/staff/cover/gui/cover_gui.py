"""Cover management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.staff.cover.services.cover_service import CoverService
import traceback

COVER_STATUSES = ["Pending", "Confirmed", "Completed"]


class _CoverDialog(tk.Toplevel):
    """Add / Edit cover record dialog."""

    def __init__(self, parent, db_path, record=None):
        super().__init__(parent)
        self.result = None
        self._record = record
        self.title("Edit Cover" if record else "Add Cover")
        self.geometry("480x440")
        self.resizable(False, False)
        self.grab_set()

        self._entries = {}

        self._add_field("absent_staff_id", "Absent Staff ID *")
        self._add_field("cover_staff_id", "Cover Staff ID *")
        self._add_field("class_name", "Class Name *")
        self._add_field("date", "Date (YYYY-MM-DD) *")
        self._add_field("period", "Period")
        self._add_field("subject_code", "Subject Code")
        self._add_field("cover_notes", "Cover Notes")
        self._add_combo("status", "Status", COVER_STATUSES)

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
        if not data.get("absent_staff_id"):
            messagebox.showwarning("Validation", "Absent staff ID is required.", parent=self)
            return
        if not data.get("cover_staff_id"):
            messagebox.showwarning("Validation", "Cover staff ID is required.", parent=self)
            return
        if not data.get("class_name"):
            messagebox.showwarning("Validation", "Class name is required.", parent=self)
            return
        if not data.get("date"):
            messagebox.showwarning("Validation", "Date is required.", parent=self)
            return
        self.result = data
        self.destroy()


class CoverFrame(tk.Frame):
    """Main cover management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = CoverService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Cover Management", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Add Cover", command=self._on_add).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Label(toolbar, text="Date:", bg="#d5dbdb").pack(side="left")
        self._date_var = tk.StringVar()
        date_entry = tk.Entry(toolbar, textvariable=self._date_var, width=12)
        date_entry.pack(side="left", padx=3)

        tk.Label(toolbar, text="Status:", bg="#d5dbdb").pack(side="left", padx=(10, 0))
        self._status_filter = ttk.Combobox(toolbar, values=["All"] + COVER_STATUSES,
                                            state="readonly", width=12)
        self._status_filter.set("All")
        self._status_filter.pack(side="left", padx=3)
        self._status_filter.bind("<<ComboboxSelected>>", lambda e: self._load_items())

        tk.Button(toolbar, text="Go", command=self._load_items).pack(side="left", padx=3)

        # Treeview
        columns = ("cover_id", "date", "absent_staff_id", "cover_staff_id",
                    "class_name", "period", "status")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=110)
        self._tree.column("cover_id", width=70)
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
        status = self._status_filter.get()
        status_val = None if status == "All" else status
        date_val = self._date_var.get().strip() or None
        try:
            records = self._service.get_covers(date=date_val, status=status_val)
            for r in records:
                self._tree.insert("", tk.END, iid=r.get("cover_id", r.get("id")), values=(
                    r.get("cover_id", r.get("id")), r.get("date", ""),
                    r.get("absent_staff_id", ""), r.get("cover_staff_id", ""),
                    r.get("class_name", ""), r.get("period", ""),
                    r.get("status", ""),
                ))
            self._status_var.set(f"{len(records)} cover record(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load cover records: {e}")

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a record first.")
            return None
        return sel[0]

    def _on_add(self):
        dlg = _CoverDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.create_cover(**dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit(self):
        rid = self._selected_id()
        if not rid:
            return
        results = self._service.get_covers()
        record = next((r for r in results if str(r.get("id")) == str(rid)), None)
        if not record:
            messagebox.showerror("Error", "Cover record not found.")
            return
        dlg = _CoverDialog(self, self._db_path, record=record)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_cover(rid, **dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete(self):
        rid = self._selected_id()
        if not rid:
            return
        if not messagebox.askyesno("Confirm", f"Delete cover record {rid}?"):
            return
        try:
            self._service.delete_cover(rid)
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))
