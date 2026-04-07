"""GUI for absence requests management."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.absence_requests.services.absence_requests_service import (
    AbsenceRequestService, ABSENCE_TYPES, VALID_STATUSES,
)
from education_system.college_system.core.exceptions import AbsenceRequestError
from education_system.college_system.core.i18n import t
from education_system.shared.auth.role_manager import RoleManager


def _is_staff_or_above(auth) -> bool:
    """Check if user has staff or admin role for the college system."""
    if not auth or not auth.is_logged_in:
        return False
    role = auth.get_role_for_system("college")
    if not role:
        return False
    rm = RoleManager()
    return rm.has_minimum_role(role, "staff")


def _get_staff_id(auth) -> int | None:
    """Extract staff/user ID from the auth's current user."""
    if not auth or not auth.current_user:
        return None
    user = auth.current_user
    return user.get("user_id") or user.get("id")


class _RequestDialog(tk.Toplevel):
    """Modal dialog for adding or editing a request."""

    def __init__(self, parent, title="Request", item=None, is_manager=False):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.result: dict | None = None
        self._item = item
        self._is_manager = is_manager
        self._build_ui()
        self._center(parent)

    def _center(self, parent):
        self.update_idletasks()
        pw = parent.winfo_rootx() + parent.winfo_width() // 2
        ph = parent.winfo_rooty() + parent.winfo_height() // 2
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{pw - w // 2}+{ph - h // 2}")

    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}
        container = tk.Frame(self, padx=20, pady=15)
        container.pack(fill="both", expand=True)
        self._vars: dict[str, tk.StringVar] = {}

        row = 0
        # Staff ID - shown but read-only for non-managers
        tk.Label(container, text=t("common.staff_id"), anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
        var = tk.StringVar(value=str(self._item.get("staff_id", "")) if self._item else "")
        entry = ttk.Entry(container, textvariable=var, width=36)
        if not self._is_manager and self._item:
            entry.configure(state="readonly")
        entry.grid(row=row, column=1, sticky="ew", **pad)
        self._vars["staff_id"] = var

        # Absence type - dropdown
        row += 1
        tk.Label(container, text=t("common.type"), anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("absence_type", "") if self._item else "")
        combo = ttk.Combobox(container, textvariable=var, values=ABSENCE_TYPES,
                             state="readonly", width=34)
        combo.grid(row=row, column=1, sticky="ew", **pad)
        self._vars["absence_type"] = var

        # Start date
        row += 1
        tk.Label(container, text="Start Date (YYYY-MM-DD)", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("start_date", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=row, column=1, sticky="ew", **pad)
        self._vars["start_date"] = var

        # End date
        row += 1
        tk.Label(container, text="End Date (YYYY-MM-DD)", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("end_date", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=row, column=1, sticky="ew", **pad)
        self._vars["end_date"] = var

        # Reason
        row += 1
        tk.Label(container, text=t("absence_requests.reason"), anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("reason", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=row, column=1, sticky="ew", **pad)
        self._vars["reason"] = var

        # Status - only editable by managers
        if self._is_manager:
            row += 1
            tk.Label(container, text=t("common.status"), anchor="w",
                     font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            var = tk.StringVar(value=self._item.get("status", "pending") if self._item else "pending")
            combo = ttk.Combobox(container, textvariable=var, values=VALID_STATUSES,
                                 state="readonly", width=34)
            combo.grid(row=row, column=1, sticky="ew", **pad)
            self._vars["status"] = var

        btn_frame = tk.Frame(container)
        btn_frame.grid(row=99, column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn_frame, text=t("common.save"), command=self._on_save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text=t("common.cancel"), command=self.destroy).pack(side="left", padx=5)

    def _on_save(self):
        data = {k: v.get().strip() for k, v in self._vars.items()}
        # Client-side validation
        if not data.get("absence_type"):
            messagebox.showwarning("Validation", "Absence type is required.")
            return
        if not data.get("start_date"):
            messagebox.showwarning("Validation", "Start date is required.")
            return
        if not data.get("end_date"):
            messagebox.showwarning("Validation", "End date is required.")
            return
        # Date format check
        import re
        date_pattern = r"^\d{4}-\d{2}-\d{2}$"
        if not re.match(date_pattern, data["start_date"]):
            messagebox.showwarning("Validation", "Start date must be in YYYY-MM-DD format.")
            return
        if not re.match(date_pattern, data["end_date"]):
            messagebox.showwarning("Validation", "End date must be in YYYY-MM-DD format.")
            return
        if data["end_date"] < data["start_date"]:
            messagebox.showwarning("Validation", "End date cannot be before start date.")
            return

        self.result = data
        self.destroy()


_STATUS_COLOURS = {
    "pending": "#f39c12",
    "approved": "#27ae60",
    "rejected": "#e74c3c",
    "cancelled": "#95a5a6",
}


class AbsenceRequestFrame(tk.Frame):
    """Absence Requests management screen."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = AbsenceRequestService(db_path)
        self._is_manager = _is_staff_or_above(auth) if auth else False

        # Check login
        if auth and not auth.is_logged_in:
            self._build_access_denied_ui()
        else:
            self._build_ui()

    def _build_access_denied_ui(self):
        """Show access denied screen when not logged in."""
        self.configure(bg="#ecf0f1")
        frame = tk.Frame(self, bg="#ecf0f1")
        frame.place(relx=0.5, rely=0.4, anchor="center")
        tk.Label(frame, text="Access Denied", font=("Helvetica", 18, "bold"),
                 bg="#ecf0f1", fg="#e74c3c").pack(pady=10)
        tk.Label(frame, text="You must be logged in to access absence requests.",
                 font=("Helvetica", 11), bg="#ecf0f1", fg="#7f8c8d").pack()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        # Header with user info
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("absence_requests.management"),
                 font=("Helvetica", 15, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        if self._auth and self._auth.current_user:
            user = self._auth.current_user
            display = user.get("display_name", user.get("username", ""))
            role = self._auth.get_role_for_system("college") or ""
            info_text = f"{display} ({role})"
            tk.Label(header, text=info_text, font=("Helvetica", 9),
                     bg="#2c3e50", fg="#bdc3c7").pack(side="right", padx=20, pady=10)

        # Toolbar
        toolbar = tk.Frame(self, bg="#ecf0f1", pady=8)
        toolbar.pack(fill="x", padx=15)

        ttk.Button(toolbar, text="Submit Request", command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text="View Details", command=self._on_view_details).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Cancel Request", command=self._on_cancel).pack(side="left", padx=4)

        if self._is_manager:
            sep = ttk.Separator(toolbar, orient="vertical")
            sep.pack(side="left", fill="y", padx=8, pady=2)
            ttk.Button(toolbar, text="Approve", command=self._on_approve).pack(side="left", padx=4)
            ttk.Button(toolbar, text="Reject", command=self._on_reject).pack(side="left", padx=4)
            ttk.Button(toolbar, text=t("common.edit"), command=self._on_edit).pack(side="left", padx=4)
            ttk.Button(toolbar, text=t("common.delete"), command=self._on_delete).pack(side="left", padx=4)

        ttk.Button(toolbar, text=t("common.refresh"), command=self._load_items).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Export CSV", command=self._export_csv).pack(side="left", padx=4)

        # Filter bar
        filter_frame = tk.Frame(self, bg="#ecf0f1")
        filter_frame.pack(fill="x", padx=15, pady=(0, 5))
        tk.Label(filter_frame, text="Filter by status:", bg="#ecf0f1",
                 font=("Helvetica", 9)).pack(side="left", padx=(0, 5))
        self._filter_var = tk.StringVar(value="All")
        filter_combo = ttk.Combobox(filter_frame, textvariable=self._filter_var,
                                    values=["All"] + VALID_STATUSES,
                                    state="readonly", width=15)
        filter_combo.pack(side="left", padx=4)
        filter_combo.bind("<<ComboboxSelected>>", lambda _: self._load_items())

        if not self._is_manager:
            self._my_only_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(filter_frame, text="My requests only",
                            variable=self._my_only_var,
                            command=self._load_items).pack(side="left", padx=10)
        else:
            self._my_only_var = tk.BooleanVar(value=False)

        # Treeview
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        columns = ('id', 'staff_id', 'absence_type', 'start_date', 'end_date', 'reason', 'status')
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")

        self._tree.heading("id", text="ID")
        self._tree.column("id", width=40, anchor="center")
        self._tree.heading("staff_id", text=t("common.staff_id"))
        self._tree.column("staff_id", width=70, anchor="center")
        self._tree.heading("absence_type", text=t("common.type"))
        self._tree.column("absence_type", width=130, anchor="center")
        self._tree.heading("start_date", text="Start Date")
        self._tree.column("start_date", width=100, anchor="center")
        self._tree.heading("end_date", text="End Date")
        self._tree.column("end_date", width=100, anchor="center")
        self._tree.heading("reason", text=t("absence_requests.reason"))
        self._tree.column("reason", width=180, anchor="w")
        self._tree.heading("status", text=t("common.status"))
        self._tree.column("status", width=80, anchor="center")

        # Configure status tag colours
        for status, colour in _STATUS_COLOURS.items():
            self._tree.tag_configure(status, foreground=colour)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._tree.bind("<Double-1>", lambda _: self._on_view_details())

        # Status bar
        self._status_var = tk.StringVar(value=t("common.ready"))
        tk.Label(self, textvariable=self._status_var, bg="#ecf0f1", anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))

    def refresh(self):
        self._load_items()

    def _load_items(self):
        self._tree.delete(*self._tree.get_children())
        try:
            filters = {}
            status_filter = self._filter_var.get()
            if status_filter != "All":
                filters["status"] = status_filter

            if self._my_only_var.get():
                staff_id = _get_staff_id(self._auth)
                if staff_id:
                    filters["staff_id"] = staff_id

            items = self._svc.list_requests(**filters)
            for item in items:
                status = item.get("status", "")
                self._tree.insert("", "end", iid=item["id"], values=(
                    item.get("id", ""),
                    item.get("staff_id", ""),
                    item.get("absence_type", ""),
                    item.get("start_date", ""),
                    item.get("end_date", ""),
                    item.get("reason", ""),
                    status,
                ), tags=(status,))
            self._status_var.set(f"Loaded {len(items)} request(s)")
        except Exception as exc:
            messagebox.showerror(t("common.error"), f"{t('common.failed_to_load')}\n{exc}")

    def _selected_pk(self) -> int | None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection"), t("common.select_item_first"))
            return None
        return int(sel[0])

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._tree, "absence_requests.csv")

    def _on_add(self):
        staff_id = _get_staff_id(self._auth) if self._auth else None
        initial = {"staff_id": staff_id or ""} if staff_id else None
        dlg = _RequestDialog(self, title="Submit Absence Request", item=initial,
                             is_manager=self._is_manager)
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            data = dlg.result
            if not self._is_manager and staff_id:
                data["staff_id"] = staff_id
            self._svc.create_request(**data)
            messagebox.showinfo(t("common.success"), "Absence request submitted (status: pending).")
            self._load_items()
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))

    def _on_view_details(self):
        pk = self._selected_pk()
        if pk is None:
            return
        item = self._svc.get_request(pk)
        if not item:
            messagebox.showerror(t("common.error"), t("absence_requests.not_found"))
            return
        details = "\n".join(f"{k.replace('_', ' ').title()}: {v}" for k, v in item.items())
        messagebox.showinfo(f"Request #{pk} Details", details)

    def _on_cancel(self):
        pk = self._selected_pk()
        if pk is None:
            return
        staff_id = _get_staff_id(self._auth)
        if not staff_id:
            messagebox.showerror(t("common.error"), "Could not determine your user ID.")
            return
        if not messagebox.askyesno("Confirm", f"Cancel request #{pk}?"):
            return
        try:
            self._svc.cancel_request(pk, staff_id)
            messagebox.showinfo(t("common.success"), "Request cancelled.")
            self._load_items()
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))

    def _on_approve(self):
        pk = self._selected_pk()
        if pk is None:
            return
        approver_id = _get_staff_id(self._auth)
        if not approver_id:
            messagebox.showerror(t("common.error"), "Could not determine your user ID.")
            return
        if not messagebox.askyesno("Confirm", f"Approve request #{pk}?"):
            return
        try:
            self._svc.approve_request(pk, approver_id)
            messagebox.showinfo(t("common.success"), f"Request #{pk} approved.")
            self._load_items()
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))

    def _on_reject(self):
        pk = self._selected_pk()
        if pk is None:
            return
        approver_id = _get_staff_id(self._auth)
        if not approver_id:
            messagebox.showerror(t("common.error"), "Could not determine your user ID.")
            return
        if not messagebox.askyesno("Confirm", f"Reject request #{pk}?"):
            return
        try:
            self._svc.reject_request(pk, approver_id)
            messagebox.showinfo(t("common.success"), f"Request #{pk} rejected.")
            self._load_items()
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))

    def _on_edit(self):
        pk = self._selected_pk()
        if pk is None:
            return
        item = self._svc.get_request(pk)
        if not item:
            messagebox.showerror(t("common.error"), t("absence_requests.not_found"))
            return
        dlg = _RequestDialog(self, title=f"Edit Request #{pk}", item=item,
                             is_manager=self._is_manager)
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self._svc.update_request(pk, **dlg.result)
            messagebox.showinfo(t("common.success"), t("absence_requests.updated"))
            self._load_items()
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))

    def _on_delete(self):
        pk = self._selected_pk()
        if pk is None:
            return
        if not messagebox.askyesno(t("common.confirm"), f"Delete request #{pk}? This cannot be undone."):
            return
        try:
            self._svc.delete_request(pk)
            messagebox.showinfo(t("common.success"), t("absence_requests.deleted"))
            self._load_items()
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))
