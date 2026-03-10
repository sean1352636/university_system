"""SEND management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.pastoral_care.send.services.send_service import SENDService
from education_system.primary_school.infrastructure.database.constants import SEND_STATUSES, SEND_CATEGORIES
import traceback

EHCP_STATUSES = ["None", "Requested", "In Progress", "Issued"]


class _SENDDialog(tk.Toplevel):
    """Add / Edit SEND record dialog."""

    def __init__(self, parent, db_path, record=None):
        super().__init__(parent)
        self.result = None
        self._record = record
        self.title("Edit SEND Record" if record else "Add SEND Record")
        self.geometry("520x560")
        self.resizable(False, False)
        self.grab_set()

        canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = tk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._entries = {}

        self._add_field(scroll_frame, "pupil_id", "Pupil ID *")
        self._add_combo(scroll_frame, "sen_status", "SEN Status *", list(SEND_STATUSES))
        self._add_combo(scroll_frame, "primary_need", "Primary Need *", list(SEND_CATEGORIES))
        self._add_field(scroll_frame, "secondary_need", "Secondary Need")
        self._add_combo(scroll_frame, "ehcp_status", "EHCP Status", EHCP_STATUSES)
        self._add_field(scroll_frame, "ehcp_review_date", "EHCP Review Date (YYYY-MM-DD)")
        self._add_field(scroll_frame, "funding_band", "Funding Band")
        self._add_field(scroll_frame, "key_worker_staff_id", "Key Worker Staff ID")
        self._add_field(scroll_frame, "external_agencies", "External Agencies")
        self._add_field(scroll_frame, "notes", "Notes")

        # Buttons
        btn_frame = tk.Frame(scroll_frame)
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

    def _add_field(self, parent, key, label, default=""):
        frm = tk.Frame(parent)
        frm.pack(fill="x", padx=10, pady=2)
        tk.Label(frm, text=label, width=24, anchor="w").pack(side="left")
        entry = tk.Entry(frm, width=30)
        entry.pack(side="left", fill="x", expand=True)
        if default:
            entry.insert(0, default)
        self._entries[key] = entry

    def _add_combo(self, parent, key, label, values):
        frm = tk.Frame(parent)
        frm.pack(fill="x", padx=10, pady=2)
        tk.Label(frm, text=label, width=24, anchor="w").pack(side="left")
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
        if not data.get("sen_status"):
            messagebox.showwarning("Validation", "SEN status is required.", parent=self)
            return
        if not data.get("primary_need"):
            messagebox.showwarning("Validation", "Primary need is required.", parent=self)
            return
        self.result = data
        self.destroy()


class SENDFrame(tk.Frame):
    """Main SEND management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = SENDService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="SEND Management", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Add Record", command=self._on_add).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Label(toolbar, text="SEN Status:", bg="#d5dbdb").pack(side="left")
        self._status_filter = ttk.Combobox(toolbar, values=["All"] + list(SEND_STATUSES),
                                            state="readonly", width=14)
        self._status_filter.set("All")
        self._status_filter.pack(side="left", padx=3)
        self._status_filter.bind("<<ComboboxSelected>>", lambda e: self._load_items())

        tk.Label(toolbar, text="Primary Need:", bg="#d5dbdb").pack(side="left", padx=(10, 0))
        self._need_filter = ttk.Combobox(toolbar, values=["All"] + list(SEND_CATEGORIES),
                                          state="readonly", width=18)
        self._need_filter.set("All")
        self._need_filter.pack(side="left", padx=3)
        self._need_filter.bind("<<ComboboxSelected>>", lambda e: self._load_items())

        # Treeview
        columns = ("send_id", "pupil_id", "sen_status", "primary_need",
                    "ehcp_status", "key_worker")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=120)
        self._tree.column("send_id", width=80)
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
        need = self._need_filter.get()
        status_val = None if status == "All" else status
        need_val = None if need == "All" else need
        try:
            records = self._service.list_records(sen_status=status_val, primary_need=need_val)
            for r in records:
                self._tree.insert("", tk.END, iid=r.get("send_id", r.get("id")), values=(
                    r.get("send_id", r.get("id")), r.get("pupil_id", ""),
                    r.get("sen_status", ""), r.get("primary_need", ""),
                    r.get("ehcp_status", ""), r.get("key_worker", r.get("key_worker_staff_id", "")),
                ))
            self._status_var.set(f"{len(records)} SEND record(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load SEND records: {e}")

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a record first.")
            return None
        return sel[0]

    def _on_add(self):
        dlg = _SENDDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.create_record(**dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit(self):
        rid = self._selected_id()
        if not rid:
            return
        record = self._service.get_record(rid)
        if not record:
            messagebox.showerror("Error", "SEND record not found.")
            return
        dlg = _SENDDialog(self, self._db_path, record=record)
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
        if not messagebox.askyesno("Confirm", f"Delete SEND record {rid}?"):
            return
        try:
            self._service.delete_record(rid)
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))
