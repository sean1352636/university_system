"""Settings management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.admin.settings.services.settings_service import SettingsService
import traceback


CATEGORIES = ["General", "Academic", "Communication", "System"]


class _SettingsDialog(tk.Toplevel):
    """Add / Edit setting dialog."""

    def __init__(self, parent, db_path, setting=None):
        super().__init__(parent)
        self.result = None
        self._setting = setting
        self.title("Edit Setting" if setting else "Add Setting")
        self.geometry("450x320")
        self.resizable(False, False)
        self.grab_set()

        self._entries = {}

        frm = tk.Frame(self, padx=15, pady=10)
        frm.pack(fill="both", expand=True)

        self._add_field(frm, "key", "Key *")
        self._add_field(frm, "value", "Value *")
        self._add_combo(frm, "category", "Category", CATEGORIES)
        self._add_field(frm, "description", "Description")

        # Buttons
        btn_frame = tk.Frame(frm)
        btn_frame.pack(fill="x", pady=15)
        tk.Button(btn_frame, text="Save", command=self._save, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=self.destroy, width=12).pack(side="right", padx=5)

        # Pre-fill for edit
        if setting:
            for key, widget in self._entries.items():
                val = setting.get(key)
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

    def _add_field(self, parent, key, label):
        frm = tk.Frame(parent)
        frm.pack(fill="x", pady=3)
        tk.Label(frm, text=label, width=20, anchor="w").pack(side="left")
        entry = tk.Entry(frm, width=30)
        entry.pack(side="left", fill="x", expand=True)
        self._entries[key] = entry

    def _add_combo(self, parent, key, label, values):
        frm = tk.Frame(parent)
        frm.pack(fill="x", pady=3)
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
        if not data.get("key"):
            messagebox.showwarning("Validation", "Key is required.", parent=self)
            return
        if not data.get("value"):
            messagebox.showwarning("Validation", "Value is required.", parent=self)
            return
        self.result = data
        self.destroy()


class SettingsFrame(tk.Frame):
    """Main settings management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = SettingsService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="System Settings", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Add Setting", command=self._on_add).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Label(toolbar, text="Category:", bg="#d5dbdb").pack(side="left")
        self._cat_filter = ttk.Combobox(toolbar, values=["All"] + CATEGORIES,
                                         state="readonly", width=16)
        self._cat_filter.set("All")
        self._cat_filter.pack(side="left", padx=3)
        self._cat_filter.bind("<<ComboboxSelected>>", lambda e: self._load_items())

        # Treeview
        columns = ("key", "value", "category", "description")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=150)
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
        cat = self._cat_filter.get()
        category = None if cat == "All" else cat
        try:
            settings = self._service.get_all_settings(category=category)
            for s in settings:
                self._tree.insert("", tk.END, iid=s.get("key"), values=(
                    s.get("key", ""), s.get("value", ""),
                    s.get("category", ""), s.get("description", ""),
                ))
            self._status_var.set(f"{len(settings)} setting(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load settings: {e}")

    def _selected_key(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a setting first.")
            return None
        return sel[0]

    def _on_add(self):
        dlg = _SettingsDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.set_setting(**dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit(self):
        key = self._selected_key()
        if not key:
            return
        all_settings = self._service.get_all_settings()
        setting = next((s for s in all_settings if s.get("key") == key), None)
        if not setting:
            messagebox.showerror("Error", "Setting not found.")
            return
        dlg = _SettingsDialog(self, self._db_path, setting=setting)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.set_setting(**dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete(self):
        key = self._selected_key()
        if not key:
            return
        if not messagebox.askyesno("Confirm", f"Delete setting '{key}'?"):
            return
        try:
            self._service.delete_setting(key)
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))
