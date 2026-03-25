"""Staff HR GUI for managing HR records."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.staff_hr.services.staff_hr_service import StaffHRService
from education_system.college_system.core.i18n import t


class StaffHRFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = StaffHRService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("staff_hr.management"), font=("Helvetica", 14, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        toolbar = tk.Frame(self)
        toolbar.pack(fill="x", padx=10, pady=5)
        tk.Label(toolbar, text="Department:").pack(side="left", padx=5)
        self._dept_var = tk.StringVar(value="All")
        self._dept_cb = ttk.Combobox(toolbar, textvariable=self._dept_var,
                                      values=["All"], state="readonly", width=15)
        self._dept_cb.pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("common.filter"), command=self._load_records).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("staff_hr.add"), command=self._new_record).pack(side="right", padx=5)

        cols = ("id", "username", "employee_id", "department", "role", "contract", "fte", "status")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=18)
        for c, w in zip(cols, (50, 100, 80, 100, 120, 80, 50, 70)):
            self._tree.heading(c, text=c.replace("_", " ").title())
            self._tree.column(c, width=w)
        self._tree.pack(fill="both", expand=True, padx=10, pady=5)

        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=5)
        ttk.Button(btn_frame, text=t("common.edit"), command=self._edit_record).pack(side="left", padx=5)
        ttk.Button(btn_frame, text=t("common.view"), command=self._view_details).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Export CSV", command=self._export_csv).pack(side="left", padx=5)

    def _load_records(self):
        for item in self._tree.get_children():
            self._tree.delete(item)
        try:
            dept = self._dept_var.get()
            records = self._svc.list_records(
                department=None if dept == "All" else dept)
            for r in records:
                self._tree.insert("", "end", iid=str(r["id"]), values=(
                    r["id"], r.get("username", ""), r.get("employee_id", ""),
                    r.get("department", ""), r.get("role_title", ""),
                    r.get("contract_type", ""), r.get("fte", ""),
                    r.get("status", "")))
            # Refresh department filter
            depts = self._svc.list_departments()
            self._dept_cb["values"] = ["All"] + depts
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _new_record(self):
        win = tk.Toplevel(self)
        win.title(t("staff_hr.management"))
        win.geometry("400x400")
        fields = {}
        row = 0
        for label, key in [("User ID*:", "user_id"), ("Employee ID:", "employee_id"),
                           ("Department:", "department"), ("Role Title:", "role_title"),
                           ("Start Date:", "start_date"), ("FTE:", "fte"),
                           ("Emergency Contact:", "emergency_contact"),
                           ("Qualifications:", "qualifications")]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=4, sticky="e")
            e = tk.Entry(win, width=25)
            e.grid(row=row, column=1, padx=10, pady=4)
            fields[key] = e
            row += 1
        fields["fte"].insert(0, "1.0")
        tk.Label(win, text="Contract:").grid(row=row, column=0, padx=10, pady=4, sticky="e")
        contract_var = tk.StringVar(value="permanent")
        ttk.Combobox(win, textvariable=contract_var,
                      values=["permanent", "fixed_term", "part_time", "agency", "volunteer"],
                      state="readonly", width=22).grid(row=row, column=1, padx=10, pady=4)
        row += 1

        def save():
            try:
                fte = fields["fte"].get().strip()
                self._svc.create_record(
                    user_id=int(fields["user_id"].get().strip()),
                    employee_id=fields["employee_id"].get().strip() or None,
                    department=fields["department"].get().strip() or None,
                    role_title=fields["role_title"].get().strip() or None,
                    contract_type=contract_var.get(),
                    start_date=fields["start_date"].get().strip() or None,
                    fte=float(fte) if fte else 1.0,
                    emergency_contact=fields["emergency_contact"].get().strip() or None,
                    qualifications=fields["qualifications"].get().strip() or None)
                messagebox.showinfo(t("common.success"), t("common.created_success"))
                win.destroy()
                self._load_records()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))
        ttk.Button(win, text=t("common.save"), command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def _edit_record(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("common.select_first"))
            return
        record_id = int(sel[0])
        try:
            rec = self._svc.get_record(record_id)
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
            return
        win = tk.Toplevel(self)
        win.title(t("staff_hr.management"))
        win.geometry("400x300")
        fields = {}
        row = 0
        for label, key in [("Department:", "department"), ("Role Title:", "role_title"),
                           ("FTE:", "fte"), ("DBS Check Date:", "dbs_check_date")]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=25)
            e.insert(0, str(rec.get(key, "") or ""))
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1
        tk.Label(win, text="Status:").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        status_var = tk.StringVar(value=rec.get("status", "active"))
        ttk.Combobox(win, textvariable=status_var,
                      values=["active", "on_leave", "suspended", "terminated"],
                      state="readonly", width=22).grid(row=row, column=1, padx=10, pady=5)
        row += 1

        def save():
            try:
                fte = fields["fte"].get().strip()
                self._svc.update_record(record_id,
                    department=fields["department"].get().strip() or None,
                    role_title=fields["role_title"].get().strip() or None,
                    fte=float(fte) if fte else None,
                    dbs_check_date=fields["dbs_check_date"].get().strip() or None,
                    status=status_var.get())
                win.destroy()
                self._load_records()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))
        ttk.Button(win, text=t("common.save"), command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def _view_details(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("common.select_first"))
            return
        try:
            rec = self._svc.get_record(int(sel[0]))
            details = "\n".join(f"{k}: {v}" for k, v in rec.items())
            messagebox.showinfo(t("common.details"), details)
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._tree, "staff_hr_export.csv")

    def refresh(self):
        self._load_records()
