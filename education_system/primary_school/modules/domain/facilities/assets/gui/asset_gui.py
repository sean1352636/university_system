"""Asset management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.facilities.assets.services.asset_service import AssetService
import traceback


ASSET_TYPES = ["IT", "Furniture", "Sports", "Teaching Resource", "Other"]
CONDITIONS = ["New", "Good", "Fair", "Poor"]


class _AssetDialog(tk.Toplevel):
    """Add / Edit asset dialog."""

    def __init__(self, parent, db_path, record=None):
        super().__init__(parent)
        self.result = None
        self._record = record
        self.title("Edit Asset" if record else "Add Asset")
        self.geometry("480x450")
        self.resizable(False, False)
        self.grab_set()

        self._entries = {}

        self._add_field("asset_name", "Asset Name *")
        self._add_combo("asset_type", "Asset Type", ASSET_TYPES)
        self._add_field("serial_number", "Serial Number")
        self._add_field("location", "Location")
        self._add_field("assigned_to", "Assigned To")
        self._add_field("purchase_date", "Purchase Date (YYYY-MM-DD)")
        self._add_field("purchase_cost", "Purchase Cost")
        self._add_combo("condition", "Condition", CONDITIONS)
        self._add_field("notes", "Notes")

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

    def _save(self):
        data = {}
        for key, widget in self._entries.items():
            if isinstance(widget, ttk.Combobox):
                data[key] = widget.get()
            else:
                data[key] = widget.get().strip()
        if not data.get("asset_name"):
            messagebox.showwarning("Validation", "Asset name is required.", parent=self)
            return
        self.result = data
        self.destroy()


class AssetFrame(tk.Frame):
    """Main asset management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = AssetService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Asset Management", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Add Asset", command=self._on_add).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Label(toolbar, text="Type:", bg="#d5dbdb").pack(side="left")
        self._type_filter = ttk.Combobox(toolbar, values=["All"] + ASSET_TYPES,
                                          state="readonly", width=15)
        self._type_filter.set("All")
        self._type_filter.pack(side="left", padx=3)
        self._type_filter.bind("<<ComboboxSelected>>", lambda e: self._load_items())

        tk.Label(toolbar, text="Status:", bg="#d5dbdb").pack(side="left", padx=(10, 0))
        self._status_filter = ttk.Combobox(toolbar, values=["All", "Active", "Disposed",
                                                              "Under Repair", "Lost"],
                                            state="readonly", width=12)
        self._status_filter.set("All")
        self._status_filter.pack(side="left", padx=3)
        self._status_filter.bind("<<ComboboxSelected>>", lambda e: self._load_items())

        # Treeview
        columns = ("asset_id", "asset_name", "asset_type", "serial_number",
                   "location", "condition", "status")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=110)
        self._tree.column("asset_id", width=70)
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
        asset_type = None if type_val == "All" else type_val
        status_val = self._status_filter.get()
        status = None if status_val == "All" else status_val
        try:
            records = self._service.list_assets(asset_type=asset_type, status=status)
            for r in records:
                rid = r.get("asset_id", r.get("id"))
                self._tree.insert("", tk.END, iid=rid, values=(
                    rid, r.get("asset_name", ""), r.get("asset_type", ""),
                    r.get("serial_number", ""), r.get("location", ""),
                    r.get("condition", ""), r.get("status", ""),
                ))
            self._status_var.set(f"{len(records)} asset(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load assets: {e}")

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select an asset first.")
            return None
        return sel[0]

    def _on_add(self):
        dlg = _AssetDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.create_asset(**dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit(self):
        rid = self._selected_id()
        if not rid:
            return
        record = self._service.get_asset(rid)
        if not record:
            messagebox.showerror("Error", "Asset not found.")
            return
        dlg = _AssetDialog(self, self._db_path, record=record)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_asset(rid, **dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete(self):
        rid = self._selected_id()
        if not rid:
            return
        if not messagebox.askyesno("Confirm", f"Delete asset {rid}?"):
            return
        try:
            self._service.delete_asset(rid)
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))
