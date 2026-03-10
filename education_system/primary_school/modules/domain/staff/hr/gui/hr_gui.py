"""HR management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.staff.hr.services.hr_service import HRService
import traceback

STAFF_ROLES = ["Teacher", "TA", "Admin", "Support"]


class _HRDialog(tk.Toplevel):
    """Add / Edit staff record dialog."""

    def __init__(self, parent, db_path, record=None):
        super().__init__(parent)
        self.result = None
        self._record = record
        self.title("Edit Staff Member" if record else "Add Staff Member")
        self.geometry("520x620")
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

        self._section(scroll_frame, "Personal Details")
        self._add_field(scroll_frame, "first_name", "First Name *")
        self._add_field(scroll_frame, "last_name", "Last Name *")
        self._add_combo(scroll_frame, "role", "Role *", STAFF_ROLES)
        self._add_field(scroll_frame, "email", "Email")
        self._add_field(scroll_frame, "phone", "Phone")
        self._add_field(scroll_frame, "class_teacher_of", "Class Teacher Of")
        self._add_field(scroll_frame, "department", "Department")

        self._section(scroll_frame, "DBS & Qualifications")
        self._add_field(scroll_frame, "dbs_check_date", "DBS Check Date (YYYY-MM-DD)")
        self._add_field(scroll_frame, "dbs_certificate_number", "DBS Certificate Number")
        self._add_field(scroll_frame, "qualifications", "Qualifications")

        self._section(scroll_frame, "Emergency Contact")
        self._add_field(scroll_frame, "emergency_contact_name", "Emergency Contact Name")
        self._add_field(scroll_frame, "emergency_contact_phone", "Emergency Contact Phone")

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

    def _section(self, parent, title):
        lbl = tk.Label(parent, text=title, font=("Helvetica", 11, "bold"), anchor="w")
        lbl.pack(fill="x", padx=10, pady=(10, 2))
        ttk.Separator(parent).pack(fill="x", padx=10)

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
        if not data.get("first_name"):
            messagebox.showwarning("Validation", "First name is required.", parent=self)
            return
        if not data.get("last_name"):
            messagebox.showwarning("Validation", "Last name is required.", parent=self)
            return
        if not data.get("role"):
            messagebox.showwarning("Validation", "Role is required.", parent=self)
            return
        self.result = data
        self.destroy()


class HRFrame(tk.Frame):
    """Main HR management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = HRService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="HR Management", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Add Staff", command=self._on_add).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Label(toolbar, text="Role:", bg="#d5dbdb").pack(side="left")
        self._role_filter = ttk.Combobox(toolbar, values=["All"] + STAFF_ROLES,
                                          state="readonly", width=12)
        self._role_filter.set("All")
        self._role_filter.pack(side="left", padx=3)
        self._role_filter.bind("<<ComboboxSelected>>", lambda e: self._load_items())

        tk.Label(toolbar, text="Search:", bg="#d5dbdb").pack(side="left", padx=(10, 0))
        self._search_var = tk.StringVar()
        search_entry = tk.Entry(toolbar, textvariable=self._search_var, width=18)
        search_entry.pack(side="left", padx=3)
        tk.Button(toolbar, text="Go", command=self._load_items).pack(side="left")
        tk.Button(toolbar, text="Clear", command=self._clear_search).pack(side="left", padx=3)

        # Treeview
        columns = ("staff_id", "first_name", "last_name", "role",
                    "class_teacher_of", "email", "status")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=110)
        self._tree.column("staff_id", width=80)
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
        role = self._role_filter.get()
        role_val = None if role == "All" else role
        search = self._search_var.get().strip() or None
        try:
            records = self._service.list_staff(role=role_val, search=search)
            for r in records:
                self._tree.insert("", tk.END, iid=r.get("staff_id", r.get("id")), values=(
                    r.get("staff_id", r.get("id")), r.get("first_name", ""),
                    r.get("last_name", ""), r.get("role", ""),
                    r.get("class_teacher_of", ""), r.get("email", ""),
                    r.get("status", ""),
                ))
            self._status_var.set(f"{len(records)} staff member(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load staff: {e}")

    def _clear_search(self):
        self._search_var.set("")
        self._role_filter.set("All")
        self._load_items()

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a staff member first.")
            return None
        return sel[0]

    def _on_add(self):
        dlg = _HRDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.create_staff(**dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit(self):
        rid = self._selected_id()
        if not rid:
            return
        record = self._service.get_staff(rid)
        if not record:
            messagebox.showerror("Error", "Staff member not found.")
            return
        dlg = _HRDialog(self, self._db_path, record=record)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_staff(rid, **dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete(self):
        rid = self._selected_id()
        if not rid:
            return
        if not messagebox.askyesno("Confirm", f"Delete staff member {rid}?"):
            return
        try:
            self._service.delete_staff(rid)
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))
