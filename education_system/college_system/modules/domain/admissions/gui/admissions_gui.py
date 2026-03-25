"""Admissions GUI for managing applications, inductions, and withdrawals."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.admissions.services.admissions_service import AdmissionsService
from education_system.college_system.core.i18n import t


class AdmissionsFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = AdmissionsService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("admissions.management"), font=("Helvetica", 14, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        # Applications tab
        self._apps_tab = tk.Frame(self._nb)
        self._nb.add(self._apps_tab, text=t("admissions.tab_applications", default="Applications"))
        self._build_applications_tab()

        # Inductions tab
        self._ind_tab = tk.Frame(self._nb)
        self._nb.add(self._ind_tab, text=t("admissions.tab_inductions", default="Inductions"))
        self._build_inductions_tab()

        # Withdrawals tab
        self._wd_tab = tk.Frame(self._nb)
        self._nb.add(self._wd_tab, text=t("admissions.tab_withdrawals", default="Withdrawals"))
        self._build_withdrawals_tab()

    def _build_applications_tab(self):
        toolbar = tk.Frame(self._apps_tab)
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text=t("admissions.status_colon", default="Status:")).pack(side="left", padx=5)
        self._app_status_var = tk.StringVar(value="All")
        status_cb = ttk.Combobox(toolbar, textvariable=self._app_status_var,
                                  values=["All", "submitted", "under_review", "interview",
                                          "offered", "accepted", "rejected", "withdrawn"],
                                  state="readonly", width=15)
        status_cb.pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("common.filter"), command=self._load_applications).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("admissions.add"), command=self._new_application).pack(side="right", padx=5)
        ttk.Button(toolbar, text="Export CSV", command=self._export_csv).pack(side="right", padx=5)

        cols = ("id", "name", "dob", "course", "status", "date")
        self._app_tree = ttk.Treeview(self._apps_tab, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (50, 150, 100, 150, 100, 100)):
            self._app_tree.heading(c, text=c.replace("_", " ").title())
            self._app_tree.column(c, width=w)
        self._app_tree.pack(fill="both", expand=True, padx=5, pady=5)

        btn_frame = tk.Frame(self._apps_tab)
        btn_frame.pack(fill="x", padx=5, pady=5)
        ttk.Button(btn_frame, text=t("admissions.update_status", default="Update Status"), command=self._update_app_status).pack(side="left", padx=5)
        ttk.Button(btn_frame, text=t("admissions.view_details", default="View Details"), command=self._view_application).pack(side="left", padx=5)

    def _build_inductions_tab(self):
        toolbar = tk.Frame(self._ind_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        ttk.Button(toolbar, text=t("admissions.schedule_induction", default="Schedule Induction"), command=self._new_induction).pack(side="right", padx=5)
        ttk.Button(toolbar, text=t("common.refresh"), command=self._load_inductions).pack(side="left", padx=5)

        cols = ("id", "student_id", "date", "session_type", "status", "attended")
        self._ind_tree = ttk.Treeview(self._ind_tab, columns=cols, show="headings", height=12)
        for c, w in zip(cols, (50, 80, 100, 120, 100, 80)):
            self._ind_tree.heading(c, text=c.replace("_", " ").title())
            self._ind_tree.column(c, width=w)
        self._ind_tree.pack(fill="both", expand=True, padx=5, pady=5)

        btn_frame = tk.Frame(self._ind_tab)
        btn_frame.pack(fill="x", padx=5, pady=5)
        ttk.Button(btn_frame, text=t("admissions.mark_attended", default="Mark Attended"), command=self._mark_attended).pack(side="left", padx=5)

    def _build_withdrawals_tab(self):
        toolbar = tk.Frame(self._wd_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        ttk.Button(toolbar, text=t("admissions.record_withdrawal", default="Record Withdrawal"), command=self._new_withdrawal).pack(side="right", padx=5)
        ttk.Button(toolbar, text=t("common.refresh"), command=self._load_withdrawals).pack(side="left", padx=5)

        cols = ("id", "student_id", "reason", "date", "destination", "exit_completed")
        self._wd_tree = ttk.Treeview(self._wd_tab, columns=cols, show="headings", height=12)
        for c, w in zip(cols, (50, 80, 150, 100, 150, 100)):
            self._wd_tree.heading(c, text=c.replace("_", " ").title())
            self._wd_tree.column(c, width=w)
        self._wd_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._app_tree, "admissions.csv")

    def refresh(self):
        self._load_applications()
        self._load_inductions()
        self._load_withdrawals()

    def _load_applications(self):
        for item in self._app_tree.get_children():
            self._app_tree.delete(item)
        try:
            status = self._app_status_var.get()
            apps = self._svc.list_applications(status=None if status == "All" else status)
            for a in apps:
                self._app_tree.insert("", "end", values=(
                    a["id"], a.get("applicant_name", ""), a.get("date_of_birth", ""),
                    a.get("course_applied", ""), a.get("status", ""),
                    a.get("application_date", "")))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_inductions(self):
        for item in self._ind_tree.get_children():
            self._ind_tree.delete(item)
        try:
            inductions = self._svc.list_inductions()
            for ind in inductions:
                self._ind_tree.insert("", "end", values=(
                    ind["id"], ind.get("student_id", ""),
                    ind.get("induction_date", ""), ind.get("session_type", ""),
                    ind.get("status", ""), "Yes" if ind.get("attended") else "No"))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_withdrawals(self):
        for item in self._wd_tree.get_children():
            self._wd_tree.delete(item)
        try:
            wds = self._svc.list_withdrawals()
            for w in wds:
                self._wd_tree.insert("", "end", values=(
                    w["id"], w.get("student_id", ""), w.get("reason", ""),
                    w.get("withdrawal_date", ""), w.get("destination", ""),
                    "Yes" if w.get("exit_completed") else "No"))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _new_application(self):
        win = tk.Toplevel(self)
        win.title(t("admissions.add"))
        win.geometry("400x400")
        fields = {}
        for i, (label, key) in enumerate([
            ("Applicant Name*:", "applicant_name"), ("Date of Birth* (YYYY-MM-DD):", "date_of_birth"),
            ("Email:", "email"), ("Phone:", "phone"),
            ("Course Applied:", "course_applied"), ("Previous School:", "previous_school"),
            ("Predicted Grades:", "predicted_grades")]):
            tk.Label(win, text=label).grid(row=i, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=30)
            e.grid(row=i, column=1, padx=10, pady=5)
            fields[key] = e

        def save():
            try:
                self._svc.create_application(
                    applicant_name=fields["applicant_name"].get().strip(),
                    date_of_birth=fields["date_of_birth"].get().strip(),
                    email=fields["email"].get().strip() or None,
                    phone=fields["phone"].get().strip() or None,
                    course_applied=fields["course_applied"].get().strip() or None,
                    previous_school=fields["previous_school"].get().strip() or None,
                    predicted_grades=fields["predicted_grades"].get().strip() or None)
                messagebox.showinfo(t("common.success"), t("admissions.application_created", default="Application created"))
                win.destroy()
                self._load_applications()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(win, text=t("common.submit"), command=save).grid(row=len(fields), column=0, columnspan=2, pady=15)

    def _update_app_status(self):
        sel = self._app_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("admissions.select_application", default="Select an application"))
            return
        app_id = self._app_tree.item(sel[0], "values")[0]
        win = tk.Toplevel(self)
        win.title(t("admissions.update_status", default="Update Status"))
        win.geometry("300x150")
        tk.Label(win, text=t("admissions.new_status", default="New Status:")).pack(padx=10, pady=10)
        status_var = tk.StringVar(value="under_review")
        ttk.Combobox(win, textvariable=status_var,
                      values=["submitted", "under_review", "interview", "offered",
                              "accepted", "rejected", "withdrawn"],
                      state="readonly").pack(padx=10)

        def save():
            try:
                self._svc.update_application_status(int(app_id), status_var.get())
                win.destroy()
                self._load_applications()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))
        ttk.Button(win, text=t("common.update"), command=save).pack(pady=15)

    def _view_application(self):
        sel = self._app_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("admissions.select_application", default="Select an application"))
            return
        app_id = self._app_tree.item(sel[0], "values")[0]
        try:
            app = self._svc.get_application(int(app_id))
            details = "\n".join(f"{k}: {v}" for k, v in app.items())
            messagebox.showinfo(t("admissions.application_details", default="Application Details"), details)
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _new_induction(self):
        win = tk.Toplevel(self)
        win.title(t("admissions.schedule_induction", default="Schedule Induction"))
        win.geometry("350x250")
        fields = {}
        for i, (label, key) in enumerate([
            ("Student ID*:", "student_id"), ("Date* (YYYY-MM-DD):", "induction_date"),
            ("Session Type:", "session_type"), ("Location:", "location")]):
            tk.Label(win, text=label).grid(row=i, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=25)
            e.grid(row=i, column=1, padx=10, pady=5)
            fields[key] = e
        fields["session_type"].insert(0, "full_day")

        def save():
            try:
                self._svc.create_induction(
                    student_id=int(fields["student_id"].get().strip()),
                    induction_date=fields["induction_date"].get().strip(),
                    session_type=fields["session_type"].get().strip() or "full_day",
                    location=fields["location"].get().strip() or None)
                messagebox.showinfo(t("common.success"), t("admissions.induction_scheduled", default="Induction scheduled"))
                win.destroy()
                self._load_inductions()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))
        ttk.Button(win, text=t("common.save"), command=save).grid(row=4, column=0, columnspan=2, pady=15)

    def _mark_attended(self):
        sel = self._ind_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("admissions.select_induction", default="Select an induction"))
            return
        ind_id = self._ind_tree.item(sel[0], "values")[0]
        try:
            self._svc.update_induction(int(ind_id), attended=1, status="completed")
            self._load_inductions()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _new_withdrawal(self):
        win = tk.Toplevel(self)
        win.title(t("admissions.record_withdrawal", default="Record Withdrawal"))
        win.geometry("350x250")
        fields = {}
        for i, (label, key) in enumerate([
            ("Student ID*:", "student_id"), ("Reason*:", "reason"),
            ("Date (YYYY-MM-DD):", "withdrawal_date"), ("Destination:", "destination")]):
            tk.Label(win, text=label).grid(row=i, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=25)
            e.grid(row=i, column=1, padx=10, pady=5)
            fields[key] = e

        def save():
            try:
                self._svc.create_withdrawal(
                    student_id=int(fields["student_id"].get().strip()),
                    reason=fields["reason"].get().strip(),
                    withdrawal_date=fields["withdrawal_date"].get().strip() or None,
                    destination=fields["destination"].get().strip() or None)
                messagebox.showinfo(t("common.success"), t("admissions.withdrawal_recorded", default="Withdrawal recorded"))
                win.destroy()
                self._load_withdrawals()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))
        ttk.Button(win, text=t("common.save"), command=save).grid(row=4, column=0, columnspan=2, pady=15)
