"""Admissions management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.admin.admissions.services.admissions_service import AdmissionsService
from education_system.primary_school.core.defaults import YEAR_GROUPS
import traceback


STATUSES = ["Pending", "Approved", "Rejected", "Waitlisted"]


class _AdmissionsDialog(tk.Toplevel):
    """Add / Edit admission application dialog."""

    def __init__(self, parent, db_path, application=None):
        super().__init__(parent)
        self.result = None
        self._application = application
        self.title("Edit Application" if application else "New Application")
        self.geometry("520x580")
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

        # Pupil details
        self._section(scroll_frame, "Pupil Details")
        self._add_field(scroll_frame, "first_name", "First Name *")
        self._add_field(scroll_frame, "last_name", "Last Name *")
        self._add_field(scroll_frame, "date_of_birth", "Date of Birth (YYYY-MM-DD)")
        self._add_combo(scroll_frame, "gender", "Gender", ["", "Male", "Female", "Other"])
        self._add_combo(scroll_frame, "year_group_applied", "Year Group Applied *", YEAR_GROUPS)

        # Parent / guardian
        self._section(scroll_frame, "Parent / Guardian")
        self._add_field(scroll_frame, "parent_name", "Parent Name *")
        self._add_field(scroll_frame, "parent_email", "Parent Email")
        self._add_field(scroll_frame, "parent_phone", "Parent Phone")

        # Additional
        self._section(scroll_frame, "Additional Information")
        self._add_field(scroll_frame, "address", "Address")
        self._add_field(scroll_frame, "previous_school", "Previous School")
        self._add_field(scroll_frame, "notes", "Notes")

        if application:
            self._section(scroll_frame, "Status")
            self._add_combo(scroll_frame, "status", "Status", STATUSES)

        # Buttons
        btn_frame = tk.Frame(scroll_frame)
        btn_frame.pack(fill="x", pady=10, padx=10)
        tk.Button(btn_frame, text="Save", command=self._save, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=self.destroy, width=12).pack(side="right", padx=5)

        # Pre-fill for edit
        if application:
            for key, widget in self._entries.items():
                val = application.get(key)
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

    def _add_field(self, parent, key, label):
        frm = tk.Frame(parent)
        frm.pack(fill="x", padx=10, pady=2)
        tk.Label(frm, text=label, width=28, anchor="w").pack(side="left")
        entry = tk.Entry(frm, width=30)
        entry.pack(side="left", fill="x", expand=True)
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
        if not data.get("year_group_applied"):
            messagebox.showwarning("Validation", "Year group is required.", parent=self)
            return
        if not data.get("parent_name"):
            messagebox.showwarning("Validation", "Parent name is required.", parent=self)
            return
        self.result = data
        self.destroy()


class AdmissionsFrame(tk.Frame):
    """Main admissions management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = AdmissionsService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Admissions Management", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="New Application", command=self._on_add).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Button(toolbar, text="Approve", command=self._on_approve).pack(side="left", padx=3)
        tk.Button(toolbar, text="Reject", command=self._on_reject).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Label(toolbar, text="Status:", bg="#d5dbdb").pack(side="left")
        self._status_filter = ttk.Combobox(toolbar, values=["All"] + STATUSES,
                                            state="readonly", width=12)
        self._status_filter.set("All")
        self._status_filter.pack(side="left", padx=3)
        self._status_filter.bind("<<ComboboxSelected>>", lambda e: self._load_items())

        tk.Label(toolbar, text="Year:", bg="#d5dbdb").pack(side="left", padx=(8, 0))
        self._year_filter = ttk.Combobox(toolbar, values=["All"] + YEAR_GROUPS,
                                          state="readonly", width=12)
        self._year_filter.set("All")
        self._year_filter.pack(side="left", padx=3)
        self._year_filter.bind("<<ComboboxSelected>>", lambda e: self._load_items())

        # Treeview
        columns = ("id", "first_name", "last_name", "year_group_applied",
                    "parent_name", "application_date", "status")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=120)
        self._tree.column("id", width=50)
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
        status_filter = None if status == "All" else status
        yg = self._year_filter.get()
        year_filter = None if yg == "All" else yg
        try:
            apps = self._service.list_applications(status=status_filter, year_group=year_filter)
            for a in apps:
                self._tree.insert("", tk.END, iid=a.get("id"), values=(
                    a.get("id", ""), a.get("first_name", ""), a.get("last_name", ""),
                    a.get("year_group_applied", ""), a.get("parent_name", ""),
                    a.get("application_date", ""), a.get("status", ""),
                ))
            self._status_var.set(f"{len(apps)} application(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load applications: {e}")

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select an application first.")
            return None
        return sel[0]

    def _on_add(self):
        dlg = _AdmissionsDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.create_application(**dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit(self):
        aid = self._selected_id()
        if not aid:
            return
        app = self._service.get_application(aid)
        if not app:
            messagebox.showerror("Error", "Application not found.")
            return
        dlg = _AdmissionsDialog(self, self._db_path, application=app)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_application(aid, **dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete(self):
        aid = self._selected_id()
        if not aid:
            return
        if not messagebox.askyesno("Confirm", f"Delete application {aid}?"):
            return
        try:
            self._service.delete_application(aid)
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))

    def _on_approve(self):
        aid = self._selected_id()
        if not aid:
            return
        if not messagebox.askyesno("Confirm", "Approve this application?"):
            return
        try:
            self._service.update_application(aid, status="Approved")
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))

    def _on_reject(self):
        aid = self._selected_id()
        if not aid:
            return
        if not messagebox.askyesno("Confirm", "Reject this application?"):
            return
        try:
            self._service.update_application(aid, status="Rejected")
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))
