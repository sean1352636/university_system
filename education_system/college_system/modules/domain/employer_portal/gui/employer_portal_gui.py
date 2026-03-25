"""Apprenticeship employer portal GUI frame."""
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.employer_portal.services.employer_portal_service import (
    EmployerPortalService,
)
from education_system.college_system.core.i18n import t


class EmployerPortalFrame(tk.Frame):
    """GUI for apprenticeship employer portal."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = EmployerPortalService(db_path)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text=t("employer_portal.title", "Employer Portal"),
            font=("Helvetica", 15, "bold"),
            bg="#2c3e50",
            fg="white",
        ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_employers_tab()
        self._build_links_tab()
        self._build_reviews_tab()
        self._build_signoff_tab()
        self._build_dashboard_tab()

    # -- Employers Tab --

    def _build_employers_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("employer_portal.employers_tab", "Employers"))

        form = tk.LabelFrame(tab, text=t("employer_portal.register", "Register Employer"), bg="#ecf0f1")
        form.pack(fill="x", padx=10, pady=5)

        labels = ["Company Name", "Contact Name", "Email", "Phone", "Sector", "Size", "Levy Payer"]
        self._emp_vars = {}
        for i, lbl in enumerate(labels):
            tk.Label(form, text=lbl + ":", bg="#ecf0f1").grid(row=i // 4, column=(i % 4) * 2, padx=5, pady=2, sticky="e")
            var = tk.StringVar()
            if lbl == "Size":
                var.set("small")
                widget = ttk.Combobox(form, textvariable=var, values=["small", "medium", "large"], width=10)
            elif lbl == "Levy Payer":
                var.set("0")
                widget = ttk.Combobox(form, textvariable=var, values=["0", "1"], width=5)
            else:
                widget = tk.Entry(form, textvariable=var, width=18)
            widget.grid(row=i // 4, column=(i % 4) * 2 + 1, padx=5, pady=2)
            self._emp_vars[lbl] = var

        btn_frame = tk.Frame(form, bg="#ecf0f1")
        btn_frame.grid(row=3, column=0, columnspan=8, pady=5)
        tk.Button(btn_frame, text=t("common.add", "Add"), command=self._add_employer).pack(side="left", padx=5)
        tk.Button(btn_frame, text=t("common.refresh", "Refresh"), command=self._load_employers).pack(side="left", padx=5)

        cols = ("id", "company_name", "contact_name", "contact_email", "sector", "company_size", "levy_payer", "is_active")
        self._emp_tree = ttk.Treeview(tab, columns=cols, show="headings", height=12)
        for c in cols:
            self._emp_tree.heading(c, text=c.replace("_", " ").title())
            self._emp_tree.column(c, width=110)
        self._emp_tree.pack(fill="both", expand=True, padx=10, pady=5)

    def _add_employer(self):
        try:
            v = self._emp_vars
            self._svc.register_employer(
                company_name=v["Company Name"].get(),
                contact_name=v["Contact Name"].get(),
                contact_email=v["Email"].get(),
                contact_phone=v["Phone"].get(),
                sector=v["Sector"].get(),
                company_size=v["Size"].get(),
                levy_payer=int(v["Levy Payer"].get()),
            )
            messagebox.showinfo(t("common.success", "Success"), t("employer_portal.employer_added", "Employer registered."))
            self._load_employers()
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def _load_employers(self):
        for row in self._emp_tree.get_children():
            self._emp_tree.delete(row)
        try:
            for e in self._svc.list_employers(active_only=False):
                self._emp_tree.insert("", "end", values=(
                    e["id"], e["company_name"], e.get("contact_name", ""),
                    e.get("contact_email", ""), e.get("sector", ""),
                    e.get("company_size", ""), "Yes" if e.get("levy_payer") else "No",
                    "Yes" if e.get("is_active") else "No",
                ))
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    # -- Learner Links Tab --

    def _build_links_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("employer_portal.links_tab", "Learner Links"))

        form = tk.LabelFrame(tab, text=t("employer_portal.link_learner", "Link Learner"), bg="#ecf0f1")
        form.pack(fill="x", padx=10, pady=5)

        labels = ["Employer ID", "Student ID", "Apprenticeship Standard", "Start Date",
                  "Expected End", "Mentor Name", "Mentor Email"]
        self._link_vars = {}
        for i, lbl in enumerate(labels):
            tk.Label(form, text=lbl + ":", bg="#ecf0f1").grid(row=i // 4, column=(i % 4) * 2, padx=5, pady=2, sticky="e")
            var = tk.StringVar()
            tk.Entry(form, textvariable=var, width=18).grid(row=i // 4, column=(i % 4) * 2 + 1, padx=5, pady=2)
            self._link_vars[lbl] = var

        btn_frame = tk.Frame(form, bg="#ecf0f1")
        btn_frame.grid(row=3, column=0, columnspan=8, pady=5)
        tk.Button(btn_frame, text=t("employer_portal.link", "Link"), command=self._link_learner).pack(side="left", padx=5)
        tk.Button(btn_frame, text=t("common.refresh", "Refresh"), command=self._load_links).pack(side="left", padx=5)

        cols = ("id", "employer_id", "student_id", "apprenticeship_standard",
                "start_date", "expected_end_date", "mentor_name", "status")
        self._links_tree = ttk.Treeview(tab, columns=cols, show="headings", height=12)
        for c in cols:
            self._links_tree.heading(c, text=c.replace("_", " ").title())
            self._links_tree.column(c, width=110)
        self._links_tree.pack(fill="both", expand=True, padx=10, pady=5)

    def _link_learner(self):
        try:
            v = self._link_vars
            self._svc.link_learner(
                employer_id=int(v["Employer ID"].get()),
                student_id=int(v["Student ID"].get()),
                apprenticeship_standard=v["Apprenticeship Standard"].get(),
                start_date=v["Start Date"].get(),
                expected_end_date=v["Expected End"].get(),
                mentor_name=v["Mentor Name"].get() or None,
                mentor_email=v["Mentor Email"].get() or None,
            )
            messagebox.showinfo(t("common.success", "Success"), t("employer_portal.learner_linked", "Learner linked."))
            self._load_links()
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def _load_links(self):
        for row in self._links_tree.get_children():
            self._links_tree.delete(row)
        try:
            eid = self._link_vars["Employer ID"].get()
            for l in self._svc.list_learner_links(
                employer_id=int(eid) if eid else None,
            ):
                self._links_tree.insert("", "end", values=(
                    l["id"], l["employer_id"], l["student_id"],
                    l.get("apprenticeship_standard", ""),
                    l.get("start_date", ""), l.get("expected_end_date", ""),
                    l.get("mentor_name", ""), l.get("status", ""),
                ))
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    # -- Progress Reviews Tab --

    def _build_reviews_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("employer_portal.reviews_tab", "Progress Reviews"))

        # Schedule section
        sched = tk.LabelFrame(tab, text=t("employer_portal.schedule_review", "Schedule Review"), bg="#ecf0f1")
        sched.pack(fill="x", padx=10, pady=5)

        tk.Label(sched, text="Link ID:", bg="#ecf0f1").grid(row=0, column=0, padx=5, pady=2, sticky="e")
        self._rev_link_var = tk.StringVar()
        tk.Entry(sched, textvariable=self._rev_link_var, width=8).grid(row=0, column=1, padx=5, pady=2)

        tk.Label(sched, text="Date:", bg="#ecf0f1").grid(row=0, column=2, padx=5, pady=2, sticky="e")
        self._rev_date_var = tk.StringVar()
        tk.Entry(sched, textvariable=self._rev_date_var, width=12).grid(row=0, column=3, padx=5, pady=2)

        tk.Label(sched, text="Type:", bg="#ecf0f1").grid(row=0, column=4, padx=5, pady=2, sticky="e")
        self._rev_type_var = tk.StringVar(value="monthly")
        ttk.Combobox(sched, textvariable=self._rev_type_var,
                      values=["monthly", "tripartite", "gateway", "epa_readiness"], width=12).grid(row=0, column=5, padx=5, pady=2)

        tk.Button(sched, text=t("employer_portal.schedule", "Schedule"), command=self._schedule_review).grid(row=0, column=6, padx=10)

        # Complete review section
        comp = tk.LabelFrame(tab, text=t("employer_portal.complete_review", "Complete Review"), bg="#ecf0f1")
        comp.pack(fill="x", padx=10, pady=5)

        comp_labels = ["Review ID", "On Track (0/1)", "KSBM Progress", "OTJ Hours", "Employer Feedback", "Next Review Date"]
        self._comp_vars = {}
        for i, lbl in enumerate(comp_labels):
            tk.Label(comp, text=lbl + ":", bg="#ecf0f1").grid(row=i // 3, column=(i % 3) * 2, padx=5, pady=2, sticky="e")
            var = tk.StringVar()
            tk.Entry(comp, textvariable=var, width=18).grid(row=i // 3, column=(i % 3) * 2 + 1, padx=5, pady=2)
            self._comp_vars[lbl] = var

        tk.Button(comp, text=t("employer_portal.complete", "Complete"), command=self._complete_review).grid(row=2, column=5, padx=10, pady=5)

        tk.Button(tab, text=t("common.refresh", "Refresh"), command=self._load_reviews).pack(padx=10, pady=2, anchor="w")

        cols = ("id", "learner_link_id", "review_date", "review_type", "on_track",
                "off_the_job_hours", "employer_signed", "learner_signed", "assessor_signed", "status")
        self._rev_tree = ttk.Treeview(tab, columns=cols, show="headings", height=8)
        for c in cols:
            self._rev_tree.heading(c, text=c.replace("_", " ").title())
            self._rev_tree.column(c, width=100)
        self._rev_tree.pack(fill="both", expand=True, padx=10, pady=5)

    def _schedule_review(self):
        try:
            self._svc.schedule_review(
                learner_link_id=int(self._rev_link_var.get()),
                review_date=self._rev_date_var.get(),
                review_type=self._rev_type_var.get(),
            )
            messagebox.showinfo(t("common.success", "Success"), t("employer_portal.review_scheduled", "Review scheduled."))
            self._load_reviews()
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def _complete_review(self):
        try:
            v = self._comp_vars
            self._svc.complete_review(
                review_id=int(v["Review ID"].get()),
                on_track=int(v["On Track (0/1)"].get()),
                ksbm_progress=v["KSBM Progress"].get(),
                off_the_job_hours=float(v["OTJ Hours"].get() or 0),
                employer_feedback=v["Employer Feedback"].get(),
                next_review_date=v["Next Review Date"].get() or None,
            )
            messagebox.showinfo(t("common.success", "Success"), t("employer_portal.review_completed", "Review completed."))
            self._load_reviews()
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def _load_reviews(self):
        for row in self._rev_tree.get_children():
            self._rev_tree.delete(row)
        try:
            lid = self._rev_link_var.get()
            for r in self._svc.list_reviews(
                learner_link_id=int(lid) if lid else None,
            ):
                self._rev_tree.insert("", "end", values=(
                    r["id"], r["learner_link_id"], r.get("review_date", ""),
                    r.get("review_type", ""), "Yes" if r.get("on_track") else "No",
                    r.get("off_the_job_hours", 0),
                    "Yes" if r.get("employer_signed") else "No",
                    "Yes" if r.get("learner_signed") else "No",
                    "Yes" if r.get("assessor_signed") else "No",
                    r.get("status", ""),
                ))
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    # -- Sign-Off Tracking Tab --

    def _build_signoff_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("employer_portal.signoff_tab", "Sign-Off Tracking"))

        form = tk.LabelFrame(tab, text=t("employer_portal.sign_off", "Sign Off Review"), bg="#ecf0f1")
        form.pack(fill="x", padx=10, pady=5)

        tk.Label(form, text="Review ID:", bg="#ecf0f1").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self._so_review_var = tk.StringVar()
        tk.Entry(form, textvariable=self._so_review_var, width=8).grid(row=0, column=1, padx=5, pady=5)

        tk.Label(form, text="Signer Type:", bg="#ecf0f1").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self._so_type_var = tk.StringVar(value="employer")
        ttk.Combobox(form, textvariable=self._so_type_var, values=["employer", "learner", "assessor"], width=10).grid(row=0, column=3, padx=5, pady=5)

        tk.Label(form, text="Signer Name:", bg="#ecf0f1").grid(row=0, column=4, padx=5, pady=5, sticky="e")
        self._so_name_var = tk.StringVar()
        tk.Entry(form, textvariable=self._so_name_var, width=18).grid(row=0, column=5, padx=5, pady=5)

        tk.Label(form, text="Comments:", bg="#ecf0f1").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self._so_comment_var = tk.StringVar()
        tk.Entry(form, textvariable=self._so_comment_var, width=50).grid(row=1, column=1, columnspan=4, padx=5, pady=5, sticky="w")

        tk.Button(form, text=t("employer_portal.sign", "Sign Off"), command=self._sign_off).grid(row=1, column=5, padx=10)

        # Overdue reviews
        tk.Button(tab, text=t("employer_portal.show_overdue", "Show Overdue Reviews"), command=self._show_overdue).pack(padx=10, pady=5, anchor="w")

        cols = ("id", "learner_link_id", "review_date", "review_type", "student_id", "apprenticeship_standard", "status")
        self._overdue_tree = ttk.Treeview(tab, columns=cols, show="headings", height=10)
        for c in cols:
            self._overdue_tree.heading(c, text=c.replace("_", " ").title())
            self._overdue_tree.column(c, width=120)
        self._overdue_tree.pack(fill="both", expand=True, padx=10, pady=5)

    def _sign_off(self):
        try:
            self._svc.sign_off_review(
                review_id=int(self._so_review_var.get()),
                signer_type=self._so_type_var.get(),
                signer_name=self._so_name_var.get(),
                comments=self._so_comment_var.get() or None,
            )
            messagebox.showinfo(t("common.success", "Success"), t("employer_portal.signed_off", "Review signed off."))
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def _show_overdue(self):
        for row in self._overdue_tree.get_children():
            self._overdue_tree.delete(row)
        try:
            for r in self._svc.get_overdue_reviews():
                self._overdue_tree.insert("", "end", values=(
                    r["id"], r["learner_link_id"], r.get("review_date", ""),
                    r.get("review_type", ""), r.get("student_id", ""),
                    r.get("apprenticeship_standard", ""), r.get("status", ""),
                ))
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    # -- Dashboard Tab --

    def _build_dashboard_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("employer_portal.dashboard_tab", "Dashboard"))

        ctrl = tk.Frame(tab, bg="#ecf0f1")
        ctrl.pack(fill="x", padx=10, pady=5)

        tk.Label(ctrl, text="Employer ID:", bg="#ecf0f1").pack(side="left", padx=5)
        self._dash_emp_var = tk.StringVar()
        tk.Entry(ctrl, textvariable=self._dash_emp_var, width=8).pack(side="left", padx=5)
        tk.Button(ctrl, text=t("employer_portal.load_dashboard", "Load Dashboard"), command=self._load_dashboard).pack(side="left", padx=5)

        tk.Label(ctrl, text="  Student ID:", bg="#ecf0f1").pack(side="left", padx=5)
        self._dash_student_var = tk.StringVar()
        tk.Entry(ctrl, textvariable=self._dash_student_var, width=8).pack(side="left", padx=5)
        tk.Button(ctrl, text=t("employer_portal.learner_progress", "Learner Progress"), command=self._load_learner_progress).pack(side="left", padx=5)

        tk.Label(ctrl, text="  Link ID:", bg="#ecf0f1").pack(side="left", padx=5)
        self._dash_link_var = tk.StringVar()
        tk.Entry(ctrl, textvariable=self._dash_link_var, width=8).pack(side="left", padx=5)
        tk.Button(ctrl, text=t("employer_portal.epa_check", "EPA Readiness"), command=self._check_epa).pack(side="left", padx=5)

        self._dash_info = tk.Text(tab, height=20, width=80, state="disabled")
        self._dash_info.pack(fill="both", expand=True, padx=10, pady=10)

    def _load_dashboard(self):
        try:
            eid = int(self._dash_emp_var.get())
            data = self._svc.get_employer_dashboard(eid)
            self._dash_info.config(state="normal")
            self._dash_info.delete("1.0", "end")
            self._dash_info.insert("end", f"Employer Dashboard (ID: {eid})\n")
            self._dash_info.insert("end", "=" * 50 + "\n\n")
            self._dash_info.insert("end", f"Total Learners: {data.get('total_learners', 0)}\n")
            self._dash_info.insert("end", f"Active Learners: {data.get('active_learners', 0)}\n\n")
            for s in data.get("learner_summaries", []):
                self._dash_info.insert("end", f"Student {s['student_id']} - {s.get('apprenticeship_standard', '')}\n")
                self._dash_info.insert("end", f"  Status: {s.get('status', '')}\n")
                rs = s.get("review_summary", {})
                self._dash_info.insert("end", f"  Reviews: {rs.get('completed', 0)}/{rs.get('total', 0)}\n")
                self._dash_info.insert("end", f"  OTJ Hours: {rs.get('total_otj', 0)}\n\n")
            self._dash_info.config(state="disabled")
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def _load_learner_progress(self):
        try:
            sid = int(self._dash_student_var.get())
            data = self._svc.get_learner_progress(sid)
            self._dash_info.config(state="normal")
            self._dash_info.delete("1.0", "end")
            self._dash_info.insert("end", f"Learner Progress (Student: {sid})\n")
            self._dash_info.insert("end", "=" * 50 + "\n\n")
            self._dash_info.insert("end", f"Completion: {data.get('completion_pct', 0)}%\n")
            self._dash_info.insert("end", f"OTJ Hours: {data.get('total_otj_hours', 0)} / {data.get('otj_target', 0)}\n")
            self._dash_info.insert("end", f"Total Reviews: {data.get('num_reviews', 0)}\n\n")
            for r in data.get("reviews", []):
                self._dash_info.insert("end", f"  {r.get('review_date', '')} ({r.get('review_type', '')}): "
                                       f"{'On Track' if r.get('on_track') else 'Off Track'}\n")
            self._dash_info.config(state="disabled")
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def _check_epa(self):
        try:
            lid = int(self._dash_link_var.get())
            data = self._svc.get_epa_readiness(lid)
            self._dash_info.config(state="normal")
            self._dash_info.delete("1.0", "end")
            self._dash_info.insert("end", f"EPA Readiness Check (Link: {lid})\n")
            self._dash_info.insert("end", "=" * 50 + "\n\n")
            for key, val in data.items():
                label = key.replace("_", " ").title()
                self._dash_info.insert("end", f"{label}: {val}\n")
            ready = data.get("ready_for_epa", False)
            self._dash_info.insert("end", f"\nOverall: {'READY for EPA' if ready else 'NOT READY for EPA'}\n")
            self._dash_info.config(state="disabled")
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def refresh(self):
        """Refresh all data."""
        self._load_employers()
