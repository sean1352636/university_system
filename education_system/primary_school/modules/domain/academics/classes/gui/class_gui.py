"""Class management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.academics.classes.services.class_service import ClassService
from education_system.primary_school.core.defaults import YEAR_GROUPS
import traceback


class _ClassDialog(tk.Toplevel):
    """Add / Edit class dialog."""

    def __init__(self, parent, db_path, class_data=None):
        super().__init__(parent)
        self.result = None
        self._class_data = class_data
        self.title("Edit Class" if class_data else "Add Class")
        self.geometry("450x400")
        self.resizable(False, False)
        self.grab_set()

        self._entries = {}

        frm = tk.Frame(self, padx=15, pady=10)
        frm.pack(fill="both", expand=True)

        self._add_field(frm, "class_name", "Class Name *")
        self._add_combo(frm, "year_group", "Year Group *", YEAR_GROUPS)
        self._add_field(frm, "teacher_staff_id", "Teacher Staff ID")
        self._add_field(frm, "teaching_assistant_staff_id", "Teaching Assistant Staff ID")
        self._add_field(frm, "room", "Room")
        self._add_field(frm, "capacity", "Capacity")

        # Buttons
        btn_frame = tk.Frame(frm)
        btn_frame.pack(fill="x", pady=10)
        tk.Button(btn_frame, text="Save", command=self._save, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=self.destroy, width=12).pack(side="right", padx=5)

        # Pre-fill for edit
        if class_data:
            for key, widget in self._entries.items():
                val = class_data.get(key)
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

    def _add_field(self, parent, key, label, default=""):
        frm = tk.Frame(parent)
        frm.pack(fill="x", padx=10, pady=2)
        tk.Label(frm, text=label, width=28, anchor="w").pack(side="left")
        entry = tk.Entry(frm, width=30)
        entry.pack(side="left", fill="x", expand=True)
        if default:
            entry.insert(0, default)
        self._entries[key] = entry

    def _add_combo(self, parent, key, label, values):
        frm = tk.Frame(parent)
        frm.pack(fill="x", padx=10, pady=2)
        tk.Label(frm, text=label, width=28, anchor="w").pack(side="left")
        combo = ttk.Combobox(frm, values=values, state="readonly", width=27)
        combo.pack(side="left", fill="x", expand=True)
        if values:
            combo.set(values[0])
        self._entries[key] = combo

    def _add_check(self, parent, key, label, default=False):
        frm = tk.Frame(parent)
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
        if not data.get("class_name"):
            messagebox.showwarning("Validation", "Class name is required.", parent=self)
            return
        if not data.get("year_group"):
            messagebox.showwarning("Validation", "Year group is required.", parent=self)
            return
        self.result = data
        self.destroy()


class ClassFrame(tk.Frame):
    """Main class management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = ClassService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Class Management", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Add Class", command=self._on_add).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Label(toolbar, text="Year Group:", bg="#d5dbdb").pack(side="left")
        self._year_filter = ttk.Combobox(toolbar, values=["All"] + YEAR_GROUPS,
                                          state="readonly", width=12)
        self._year_filter.set("All")
        self._year_filter.pack(side="left", padx=3)
        self._year_filter.bind("<<ComboboxSelected>>", lambda e: self._load_items())

        tk.Label(toolbar, text="Search:", bg="#d5dbdb").pack(side="left", padx=(10, 0))
        self._search_var = tk.StringVar()
        search_entry = tk.Entry(toolbar, textvariable=self._search_var, width=18)
        search_entry.pack(side="left", padx=3)
        tk.Button(toolbar, text="Go", command=self._load_items).pack(side="left")
        tk.Button(toolbar, text="Clear", command=self._clear_search).pack(side="left", padx=3)

        # Treeview
        columns = ("class_name", "year_group", "teacher", "room", "capacity")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=120)
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
        yg = self._year_filter.get()
        year_group = None if yg == "All" else yg
        search = self._search_var.get().strip() or None
        try:
            classes = self._service.list_classes(year_group=year_group)
            for c in classes:
                self._tree.insert("", tk.END, iid=c.get("class_id", ""), values=(
                    c.get("class_name", ""),
                    c.get("year_group", ""),
                    c.get("teacher", c.get("teacher_staff_id", "")),
                    c.get("room", ""),
                    c.get("capacity", ""),
                ))
            self._status_var.set(f"{len(classes)} class(es) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load classes: {e}")

    def _clear_search(self):
        self._search_var.set("")
        self._year_filter.set("All")
        self._load_items()

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a class first.")
            return None
        return sel[0]

    def _on_add(self):
        dlg = _ClassDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.create_class(**dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit(self):
        cid = self._selected_id()
        if not cid:
            return
        class_data = self._service.get_class(cid)
        if not class_data:
            messagebox.showerror("Error", "Class not found.")
            return
        dlg = _ClassDialog(self, self._db_path, class_data=class_data)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_class(cid, **dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete(self):
        cid = self._selected_id()
        if not cid:
            return
        if not messagebox.askyesno("Confirm", f"Delete class {cid} and all related records?"):
            return
        try:
            self._service.delete_class(cid)
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))
