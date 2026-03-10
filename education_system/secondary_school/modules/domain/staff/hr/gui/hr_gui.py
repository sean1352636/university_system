"""HR management GUI."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.secondary_school.modules.domain.staff.hr.services.hr_service import (
    HRService, CONTRACT_TYPES, LEAVE_TYPES, JOB_TITLES,
)
from education_system.secondary_school.core.exceptions import HRError

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class HRFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = HRService(db_path)
        self._current_tab = "staff"
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)

        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="HR Management", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)

        # Tab bar
        tab_bar = tk.Frame(self, bg=MAIN_BG, pady=4)
        tab_bar.pack(fill="x", padx=15)
        self._tab_btns = {}
        for label in ("Staff Records", "Leave Management"):
            btn = ttk.Button(tab_bar, text=label,
                             command=lambda l=label: self._switch_tab(l))
            btn.pack(side="left", padx=4)
            self._tab_btns[label] = btn

        # Toolbar — staff
        self._staff_toolbar = tk.Frame(self, bg=MAIN_BG, pady=4)
        ttk.Button(self._staff_toolbar, text="Add Staff", command=self._on_add_staff).pack(side="left", padx=4)
        ttk.Button(self._staff_toolbar, text="Edit Staff", command=self._on_edit_staff).pack(side="left", padx=4)
        ttk.Button(self._staff_toolbar, text="Delete Staff", command=self._on_delete_staff).pack(side="left", padx=4)

        # Toolbar — leave
        self._leave_toolbar = tk.Frame(self, bg=MAIN_BG, pady=4)
        ttk.Button(self._leave_toolbar, text="Request Leave", command=self._on_request_leave).pack(side="left", padx=4)
        ttk.Button(self._leave_toolbar, text="Approve", command=self._on_approve_leave).pack(side="left", padx=4)
        ttk.Button(self._leave_toolbar, text="Reject", command=self._on_reject_leave).pack(side="left", padx=4)

        # Staff tree
        self._staff_frame = tk.Frame(self)
        staff_cols = ("staff_id", "name", "job_title", "department", "contract", "salary", "status")
        self._staff_tree = ttk.Treeview(self._staff_frame, columns=staff_cols,
                                        show="headings", selectmode="browse")
        for col, heading, w in [
            ("staff_id", "ID", 60), ("name", "Name", 150),
            ("job_title", "Job Title", 130), ("department", "Department", 100),
            ("contract", "Contract", 80), ("salary", "Salary", 80),
            ("status", "Status", 60),
        ]:
            self._staff_tree.heading(col, text=heading)
            self._staff_tree.column(col, width=w, anchor="center")
        vsb1 = ttk.Scrollbar(self._staff_frame, orient="vertical", command=self._staff_tree.yview)
        self._staff_tree.configure(yscrollcommand=vsb1.set)
        self._staff_tree.pack(side="left", fill="both", expand=True)
        vsb1.pack(side="right", fill="y")

        # Leave tree
        self._leave_frame = tk.Frame(self)
        leave_cols = ("staff", "type", "start", "end", "days", "reason", "status", "approved_by")
        self._leave_tree = ttk.Treeview(self._leave_frame, columns=leave_cols,
                                        show="headings", selectmode="browse")
        for col, heading, w in [
            ("staff", "Staff", 140), ("type", "Type", 80),
            ("start", "Start", 85), ("end", "End", 85),
            ("days", "Days", 40), ("reason", "Reason", 150),
            ("status", "Status", 70), ("approved_by", "Approved By", 90),
        ]:
            self._leave_tree.heading(col, text=heading)
            self._leave_tree.column(col, width=w, anchor="center")
        vsb2 = ttk.Scrollbar(self._leave_frame, orient="vertical", command=self._leave_tree.yview)
        self._leave_tree.configure(yscrollcommand=vsb2.set)
        self._leave_tree.pack(side="left", fill="both", expand=True)
        vsb2.pack(side="right", fill="y")

        self._status_var = tk.StringVar(value="Ready")
        self._status_label = tk.Label(self, textvariable=self._status_var, bg=MAIN_BG,
                                      anchor="w", font=("Helvetica", 9), fg="#7f8c8d")
        self._status_label.pack(fill="x", padx=15, pady=(0, 8), side="bottom")

        self._switch_tab("Staff Records")

    def _switch_tab(self, tab):
        self._staff_toolbar.pack_forget()
        self._leave_toolbar.pack_forget()
        self._staff_frame.pack_forget()
        self._leave_frame.pack_forget()

        if tab == "Staff Records":
            self._current_tab = "staff"
            self._staff_toolbar.pack(fill="x", padx=15)
            self._staff_frame.pack(fill="both", expand=True, padx=15, pady=(0, 5))
            self._load_staff()
        else:
            self._current_tab = "leave"
            self._leave_toolbar.pack(fill="x", padx=15)
            self._leave_frame.pack(fill="both", expand=True, padx=15, pady=(0, 5))
            self._load_leave()

    def refresh(self):
        if self._current_tab == "staff":
            self._load_staff()
        else:
            self._load_leave()

    def _load_staff(self):
        self._staff_tree.delete(*self._staff_tree.get_children())
        try:
            staff = self._svc.list_staff()
            for s in staff:
                sal = f"\u00a3{s['salary']:,.0f}" if s.get("salary") else ""
                self._staff_tree.insert("", "end", iid=s["id"], values=(
                    s["staff_id"],
                    f"{s.get('title', '')} {s['first_name']} {s['last_name']}",
                    s.get("job_title", ""),
                    s.get("department", "") or "",
                    s.get("contract_type", ""),
                    sal,
                    s["status"],
                ))
            self._status_var.set(f"{len(staff)} staff member(s)")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _load_leave(self):
        self._leave_tree.delete(*self._leave_tree.get_children())
        try:
            leaves = self._svc.list_leave()
            for lv in leaves:
                self._leave_tree.insert("", "end", iid=lv["id"], values=(
                    f"{lv['first_name']} {lv['last_name']}",
                    lv["leave_type"],
                    lv["start_date"],
                    lv["end_date"],
                    lv["days"],
                    lv.get("reason", "") or "",
                    lv["status"],
                    lv.get("approved_by", "") or "",
                ))
            self._status_var.set(f"{len(leaves)} leave request(s)")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_add_staff(self):
        dlg = tk.Toplevel(self)
        dlg.title("Add Staff Member")
        dlg.resizable(False, False)

        pad = {"padx": 10, "pady": 4}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()

        vars_ = {}
        fields = [
            ("Title", "title", "Mr", ["Mr", "Mrs", "Ms", "Miss", "Dr", "Prof"]),
            ("First Name", "first_name", "", None),
            ("Last Name", "last_name", "", None),
            ("Email", "email", "", None),
            ("Phone", "phone", "", None),
            ("Address", "address", "", None),
            ("Department", "department", "", None),
            ("Job Title", "job_title", "Teacher", list(JOB_TITLES)),
            ("Contract", "contract_type", "permanent", list(CONTRACT_TYPES)),
            ("Salary (\u00a3)", "salary", "", None),
            ("Start Date", "start_date", "", None),
            ("DBS Check Date", "dbs_check_date", "", None),
            ("Emergency Name", "emergency_name", "", None),
            ("Emergency Phone", "emergency_phone", "", None),
        ]

        for row, (label, key, default, values) in enumerate(fields):
            tk.Label(c, text=label, font=("Helvetica", 9, "bold")).grid(
                row=row, column=0, sticky="w", **pad)
            vars_[key] = tk.StringVar(value=default)
            if values:
                ttk.Combobox(c, textvariable=vars_[key], values=values,
                             state="readonly", width=28).grid(row=row, column=1, **pad)
            else:
                ttk.Entry(c, textvariable=vars_[key], width=30).grid(row=row, column=1, **pad)

        result = [None]

        def save():
            fn = vars_["first_name"].get().strip()
            ln = vars_["last_name"].get().strip()
            if not fn or not ln:
                messagebox.showwarning("Validation", "First and last name are required.")
                return
            result[0] = {k: v.get().strip() for k, v in vars_.items()}
            dlg.destroy()

        btn = tk.Frame(c)
        btn.grid(row=len(fields), column=0, columnspan=2, pady=(12, 0))
        ttk.Button(btn, text="Save", command=save).pack(side="left", padx=5)
        ttk.Button(btn, text="Cancel", command=dlg.destroy).pack(side="left", padx=5)

        self.wait_window(dlg)
        if result[0] is None:
            return

        d = result[0]
        try:
            sal = float(d["salary"]) if d["salary"] else None
        except ValueError:
            sal = None

        try:
            self._svc.create_staff(
                first_name=d["first_name"], last_name=d["last_name"],
                title=d["title"] or "Mr",
                email=d["email"] or None, phone=d["phone"] or None,
                address=d["address"] or None, department=d["department"] or None,
                job_title=d["job_title"] or "Teacher",
                contract_type=d["contract_type"] or "permanent",
                salary=sal, start_date=d["start_date"] or None,
                dbs_check_date=d["dbs_check_date"] or None,
                emergency_contact_name=d["emergency_name"] or None,
                emergency_contact_phone=d["emergency_phone"] or None,
            )
            messagebox.showinfo("Success", "Staff member added.")
            self._load_staff()
        except HRError as exc:
            messagebox.showerror("Error", str(exc))

    def _on_edit_staff(self):
        sel = self._staff_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a staff member first.")
            return

        staff = self._svc.get_staff(int(sel[0]))
        if not staff:
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Edit — {staff['first_name']} {staff['last_name']}")
        dlg.resizable(False, False)

        pad = {"padx": 10, "pady": 4}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()

        vars_ = {}
        fields = [
            ("Title", "title", staff.get("title", "Mr"), ["Mr", "Mrs", "Ms", "Miss", "Dr", "Prof"]),
            ("First Name", "first_name", staff["first_name"], None),
            ("Last Name", "last_name", staff["last_name"], None),
            ("Email", "email", staff.get("email", "") or "", None),
            ("Phone", "phone", staff.get("phone", "") or "", None),
            ("Department", "department", staff.get("department", "") or "", None),
            ("Job Title", "job_title", staff.get("job_title", "Teacher"), list(JOB_TITLES)),
            ("Contract", "contract_type", staff.get("contract_type", "permanent"), list(CONTRACT_TYPES)),
            ("Salary (\u00a3)", "salary", str(staff["salary"]) if staff.get("salary") else "", None),
            ("Status", "status", staff["status"], ["active", "on_leave", "resigned", "terminated"]),
        ]

        for row, (label, key, default, values) in enumerate(fields):
            tk.Label(c, text=label, font=("Helvetica", 9, "bold")).grid(
                row=row, column=0, sticky="w", **pad)
            vars_[key] = tk.StringVar(value=default)
            if values:
                ttk.Combobox(c, textvariable=vars_[key], values=values,
                             state="readonly", width=28).grid(row=row, column=1, **pad)
            else:
                ttk.Entry(c, textvariable=vars_[key], width=30).grid(row=row, column=1, **pad)

        result = [None]

        def save():
            result[0] = {k: v.get().strip() for k, v in vars_.items()}
            dlg.destroy()

        btn = tk.Frame(c)
        btn.grid(row=len(fields), column=0, columnspan=2, pady=(12, 0))
        ttk.Button(btn, text="Save", command=save).pack(side="left", padx=5)
        ttk.Button(btn, text="Cancel", command=dlg.destroy).pack(side="left", padx=5)

        self.wait_window(dlg)
        if result[0] is None:
            return

        d = result[0]
        try:
            sal = float(d["salary"]) if d["salary"] else None
        except ValueError:
            sal = None
        d["salary"] = sal

        # Remove empty strings
        updates = {k: (v if v else None) for k, v in d.items()}
        try:
            self._svc.update_staff(int(sel[0]), **updates)
            messagebox.showinfo("Success", "Staff record updated.")
            self._load_staff()
        except HRError as exc:
            messagebox.showerror("Error", str(exc))

    def _on_delete_staff(self):
        sel = self._staff_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a staff member first.")
            return
        if not messagebox.askyesno("Confirm", "Delete this staff record and all related leave?"):
            return
        self._svc.delete_staff(int(sel[0]))
        self._load_staff()

    def _on_request_leave(self):
        staff_list = self._svc.list_staff(status="active")
        if not staff_list:
            messagebox.showwarning("Warning", "No active staff members.")
            return

        dlg = tk.Toplevel(self)
        dlg.title("Request Leave")
        dlg.resizable(False, False)

        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()

        vars_ = {}
        row = 0

        tk.Label(c, text="Staff Member", font=("Helvetica", 9, "bold")).grid(
            row=row, column=0, sticky="w", **pad)
        staff_names = [f"{s['staff_id']} - {s['first_name']} {s['last_name']}" for s in staff_list]
        vars_["staff"] = tk.StringVar()
        ttk.Combobox(c, textvariable=vars_["staff"], values=staff_names,
                     state="readonly", width=30).grid(row=row, column=1, **pad)

        for label, key, default, values in [
            ("Leave Type", "leave_type", "annual", list(LEAVE_TYPES)),
            ("Start Date (YYYY-MM-DD)", "start_date", "", None),
            ("End Date (YYYY-MM-DD)", "end_date", "", None),
            ("Days", "days", "1", None),
            ("Reason", "reason", "", None),
        ]:
            row += 1
            tk.Label(c, text=label, font=("Helvetica", 9, "bold")).grid(
                row=row, column=0, sticky="w", **pad)
            vars_[key] = tk.StringVar(value=default)
            if values:
                ttk.Combobox(c, textvariable=vars_[key], values=values,
                             state="readonly", width=30).grid(row=row, column=1, **pad)
            else:
                ttk.Entry(c, textvariable=vars_[key], width=32).grid(row=row, column=1, **pad)

        result = [None]

        def save():
            sv = vars_["staff"].get()
            sd = vars_["start_date"].get().strip()
            ed = vars_["end_date"].get().strip()
            if not sv or not sd or not ed:
                messagebox.showwarning("Validation", "Staff, start and end dates are required.")
                return
            sid = sv.split(" - ")[0]
            staff_pk = None
            for s in staff_list:
                if s["staff_id"] == sid:
                    staff_pk = s["id"]
                    break
            result[0] = {
                "staff_hr_id": staff_pk,
                "leave_type": vars_["leave_type"].get(),
                "start_date": sd, "end_date": ed,
                "days": vars_["days"].get().strip(),
                "reason": vars_["reason"].get().strip(),
            }
            dlg.destroy()

        row += 1
        btn = tk.Frame(c)
        btn.grid(row=row, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(btn, text="Submit", command=save).pack(side="left", padx=5)
        ttk.Button(btn, text="Cancel", command=dlg.destroy).pack(side="left", padx=5)

        self.wait_window(dlg)
        if result[0] is None:
            return

        d = result[0]
        try:
            days = int(d["days"]) if d["days"] else 1
        except ValueError:
            days = 1

        try:
            self._svc.request_leave(
                staff_hr_id=d["staff_hr_id"],
                leave_type=d["leave_type"],
                start_date=d["start_date"],
                end_date=d["end_date"],
                days=days,
                reason=d["reason"] or None,
            )
            messagebox.showinfo("Success", "Leave request submitted.")
            self._load_leave()
        except HRError as exc:
            messagebox.showerror("Error", str(exc))

    def _on_approve_leave(self):
        sel = self._leave_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a leave request first.")
            return
        approver = self._auth.get("username", "admin") if self._auth else "admin"
        self._svc.approve_leave(int(sel[0]), approved_by=approver)
        messagebox.showinfo("Approved", "Leave approved.")
        self._load_leave()

    def _on_reject_leave(self):
        sel = self._leave_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a leave request first.")
            return
        self._svc.reject_leave(int(sel[0]))
        messagebox.showinfo("Rejected", "Leave rejected.")
        self._load_leave()
