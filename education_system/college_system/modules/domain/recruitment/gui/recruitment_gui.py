"""Staff Recruitment GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.recruitment.services.recruitment_service import RecruitmentService


class RecruitmentFrame(tk.Frame):
    """Staff Recruitment management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = RecruitmentService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Staff Recruitment",
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_vacancies_tab()
        self._build_applications_tab()
        self._build_stats_tab()

    # ── Vacancies Tab ──────────────────────────────────────────────────

    def _build_vacancies_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Vacancies")

        # Filters
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 8))

        tk.Label(filt, text="Status:", bg="#ecf0f1").pack(side="left")
        self._vac_status_var = tk.StringVar(value="")
        vac_status_cb = ttk.Combobox(filt, textvariable=self._vac_status_var,
                                     values=["", "draft", "open", "closed"],
                                     state="readonly", width=12)
        vac_status_cb.pack(side="left", padx=(4, 12))

        tk.Label(filt, text="Department:", bg="#ecf0f1").pack(side="left")
        self._vac_dept_var = tk.StringVar(value="")
        self._vac_dept_entry = ttk.Entry(filt, textvariable=self._vac_dept_var, width=14)
        self._vac_dept_entry.pack(side="left", padx=(4, 12))

        ttk.Button(filt, text="Filter", command=self._load_vacancies).pack(side="left", padx=4)
        ttk.Button(filt, text="Clear", command=self._clear_vac_filters).pack(side="left")

        # Treeview
        cols = ("id", "job_title", "department", "contract_type", "hours",
                "salary_range", "closing_date", "status")
        self._vac_tree = ttk.Treeview(tab, columns=cols, show="headings",
                                      selectmode="browse")
        for c, h, w in [("id", "ID", 40), ("job_title", "Job Title", 200),
                         ("department", "Department", 120),
                         ("contract_type", "Contract", 90),
                         ("hours", "Hours", 80),
                         ("salary_range", "Salary", 100),
                         ("closing_date", "Closing", 90),
                         ("status", "Status", 70)]:
            self._vac_tree.heading(c, text=h)
            self._vac_tree.column(c, width=w, anchor="center")

        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._vac_tree.yview)
        self._vac_tree.configure(yscrollcommand=vsb.set)
        self._vac_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")

        # Buttons
        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", pady=(8, 0))
        for text, cmd in [("New", self._new_vacancy),
                          ("View", self._view_vacancy),
                          ("Edit", self._edit_vacancy),
                          ("Publish", self._publish_vacancy),
                          ("Close", self._close_vacancy),
                          ("Delete", self._delete_vacancy)]:
            ttk.Button(btn_frame, text=text, command=cmd).pack(side="left", padx=4)

    def _clear_vac_filters(self):
        self._vac_status_var.set("")
        self._vac_dept_var.set("")
        self._load_vacancies()

    def _load_vacancies(self):
        self._vac_tree.delete(*self._vac_tree.get_children())
        try:
            status = self._vac_status_var.get() or None
            dept = self._vac_dept_var.get().strip() or None
            for v in self._svc.list_vacancies(status=status, department=dept):
                self._vac_tree.insert("", "end", iid=v["id"], values=(
                    v["id"], v["job_title"], v.get("department") or "-",
                    v["contract_type"], v["hours"],
                    v.get("salary_range") or "-",
                    v.get("closing_date") or "-", v["status"]))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _selected_vacancy_id(self):
        sel = self._vac_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select a vacancy.")
            return None
        return int(sel[0])

    def _new_vacancy(self):
        dlg = tk.Toplevel(self)
        dlg.title("New Vacancy")
        dlg.geometry("480x520")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        for label, key, default in [
            ("Job Title *", "job_title", ""),
            ("Department", "department", ""),
            ("Contract Type", "contract_type", "permanent"),
            ("Hours", "hours", "full-time"),
            ("Salary Range", "salary_range", ""),
            ("Closing Date (YYYY-MM-DD)", "closing_date", ""),
            ("Start Date (YYYY-MM-DD)", "start_date", ""),
            ("Hiring Manager ID", "hiring_manager_id", ""),
        ]:
            tk.Label(dlg, text=label).pack(anchor="w", padx=10, pady=(6, 0))
            var = tk.StringVar(value=default)
            ttk.Entry(dlg, textvariable=var, width=50).pack(padx=10)
            fields[key] = var

        tk.Label(dlg, text="Description").pack(anchor="w", padx=10, pady=(6, 0))
        desc_txt = tk.Text(dlg, height=4, width=50)
        desc_txt.pack(padx=10)

        tk.Label(dlg, text="Person Specification").pack(anchor="w", padx=10, pady=(6, 0))
        spec_txt = tk.Text(dlg, height=4, width=50)
        spec_txt.pack(padx=10)

        def _save():
            title = fields["job_title"].get().strip()
            if not title:
                messagebox.showerror("Error", "Job title is required.", parent=dlg)
                return
            try:
                hm = fields["hiring_manager_id"].get().strip()
                self._svc.create_vacancy(
                    job_title=title,
                    department=fields["department"].get().strip() or None,
                    contract_type=fields["contract_type"].get().strip() or "permanent",
                    hours=fields["hours"].get().strip() or "full-time",
                    salary_range=fields["salary_range"].get().strip() or None,
                    closing_date=fields["closing_date"].get().strip() or None,
                    start_date=fields["start_date"].get().strip() or None,
                    description=desc_txt.get("1.0", "end-1c").strip() or None,
                    person_spec=spec_txt.get("1.0", "end-1c").strip() or None,
                    hiring_manager_id=int(hm) if hm else None,
                )
                dlg.destroy()
                self._load_vacancies()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Save", command=_save).pack(pady=10)

    def _view_vacancy(self):
        vid = self._selected_vacancy_id()
        if not vid:
            return
        try:
            v = self._svc.get_vacancy(vid)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        if not v:
            messagebox.showinfo("Not Found", "Vacancy not found.")
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Vacancy #{v['id']}")
        dlg.geometry("500x480")
        dlg.transient(self)

        info = tk.Text(dlg, wrap="word")
        info.pack(fill="both", expand=True, padx=10, pady=10)
        lines = [
            f"ID: {v['id']}",
            f"Job Title: {v['job_title']}",
            f"Department: {v.get('department') or '-'}",
            f"Contract: {v['contract_type']}",
            f"Hours: {v['hours']}",
            f"Salary: {v.get('salary_range') or '-'}",
            f"Closing Date: {v.get('closing_date') or '-'}",
            f"Start Date: {v.get('start_date') or '-'}",
            f"Hiring Manager ID: {v.get('hiring_manager_id') or '-'}",
            f"Status: {v['status']}",
            f"Created: {v['created_at']}",
            f"Updated: {v['updated_at']}",
            "",
            "--- Description ---",
            v.get("description") or "(none)",
            "",
            "--- Person Specification ---",
            v.get("person_spec") or "(none)",
        ]
        info.insert("1.0", "\n".join(lines))
        info.configure(state="disabled")

    def _edit_vacancy(self):
        vid = self._selected_vacancy_id()
        if not vid:
            return
        try:
            v = self._svc.get_vacancy(vid)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        if not v:
            messagebox.showinfo("Not Found", "Vacancy not found.")
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Edit Vacancy #{vid}")
        dlg.geometry("480x520")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        for label, key, val in [
            ("Job Title *", "job_title", v["job_title"]),
            ("Department", "department", v.get("department") or ""),
            ("Contract Type", "contract_type", v["contract_type"]),
            ("Hours", "hours", v["hours"]),
            ("Salary Range", "salary_range", v.get("salary_range") or ""),
            ("Closing Date", "closing_date", v.get("closing_date") or ""),
            ("Start Date", "start_date", v.get("start_date") or ""),
            ("Hiring Manager ID", "hiring_manager_id",
             str(v["hiring_manager_id"]) if v.get("hiring_manager_id") else ""),
        ]:
            tk.Label(dlg, text=label).pack(anchor="w", padx=10, pady=(6, 0))
            var = tk.StringVar(value=val)
            ttk.Entry(dlg, textvariable=var, width=50).pack(padx=10)
            fields[key] = var

        tk.Label(dlg, text="Description").pack(anchor="w", padx=10, pady=(6, 0))
        desc_txt = tk.Text(dlg, height=4, width=50)
        desc_txt.pack(padx=10)
        desc_txt.insert("1.0", v.get("description") or "")

        tk.Label(dlg, text="Person Specification").pack(anchor="w", padx=10, pady=(6, 0))
        spec_txt = tk.Text(dlg, height=4, width=50)
        spec_txt.pack(padx=10)
        spec_txt.insert("1.0", v.get("person_spec") or "")

        def _save():
            title = fields["job_title"].get().strip()
            if not title:
                messagebox.showerror("Error", "Job title is required.", parent=dlg)
                return
            try:
                hm = fields["hiring_manager_id"].get().strip()
                self._svc.update_vacancy(
                    vid,
                    job_title=title,
                    department=fields["department"].get().strip() or None,
                    contract_type=fields["contract_type"].get().strip() or "permanent",
                    hours=fields["hours"].get().strip() or "full-time",
                    salary_range=fields["salary_range"].get().strip() or None,
                    closing_date=fields["closing_date"].get().strip() or None,
                    start_date=fields["start_date"].get().strip() or None,
                    description=desc_txt.get("1.0", "end-1c").strip() or None,
                    person_spec=spec_txt.get("1.0", "end-1c").strip() or None,
                    hiring_manager_id=int(hm) if hm else None,
                )
                dlg.destroy()
                self._load_vacancies()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Save", command=_save).pack(pady=10)

    def _publish_vacancy(self):
        vid = self._selected_vacancy_id()
        if not vid:
            return
        try:
            self._svc.publish_vacancy(vid)
            self._load_vacancies()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _close_vacancy(self):
        vid = self._selected_vacancy_id()
        if not vid:
            return
        try:
            self._svc.close_vacancy(vid)
            self._load_vacancies()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _delete_vacancy(self):
        vid = self._selected_vacancy_id()
        if not vid:
            return
        if not messagebox.askyesno("Confirm",
                                   "Delete this vacancy and all its applications?"):
            return
        try:
            self._svc.delete_vacancy(vid)
            self._load_vacancies()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ── Applications Tab ───────────────────────────────────────────────

    def _build_applications_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Applications")

        # Vacancy selector
        sel_frame = tk.Frame(tab, bg="#ecf0f1")
        sel_frame.pack(fill="x", pady=(0, 8))

        tk.Label(sel_frame, text="Vacancy ID:", bg="#ecf0f1").pack(side="left")
        self._app_vac_var = tk.StringVar(value="")
        ttk.Entry(sel_frame, textvariable=self._app_vac_var, width=8).pack(
            side="left", padx=(4, 12))

        tk.Label(sel_frame, text="Status:", bg="#ecf0f1").pack(side="left")
        self._app_status_var = tk.StringVar(value="")
        ttk.Combobox(sel_frame, textvariable=self._app_status_var,
                     values=["", "received", "shortlisted", "interview_scheduled",
                             "interviewed", "offer_made", "rejected", "withdrawn"],
                     state="readonly", width=16).pack(side="left", padx=(4, 12))

        ttk.Button(sel_frame, text="Load", command=self._load_applications).pack(
            side="left", padx=4)

        # Treeview
        cols = ("id", "applicant_name", "email", "application_date",
                "shortlisted", "interview_date", "score", "offer", "status")
        self._app_tree = ttk.Treeview(tab, columns=cols, show="headings",
                                      selectmode="browse")
        for c, h, w in [("id", "ID", 40),
                         ("applicant_name", "Applicant", 160),
                         ("email", "Email", 160),
                         ("application_date", "Applied", 90),
                         ("shortlisted", "Shortlisted", 75),
                         ("interview_date", "Interview", 90),
                         ("score", "Score", 50),
                         ("offer", "Offer", 50),
                         ("status", "Status", 100)]:
            self._app_tree.heading(c, text=h)
            self._app_tree.column(c, width=w, anchor="center")

        asb = ttk.Scrollbar(tab, orient="vertical", command=self._app_tree.yview)
        self._app_tree.configure(yscrollcommand=asb.set)
        self._app_tree.pack(side="left", fill="both", expand=True)
        asb.pack(side="left", fill="y")

        # Buttons
        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", pady=(8, 0))
        for text, cmd in [("New", self._new_application),
                          ("View", self._view_application),
                          ("Edit", self._edit_application),
                          ("Shortlist", self._shortlist_application),
                          ("Delete", self._delete_application)]:
            ttk.Button(btn_frame, text=text, command=cmd).pack(side="left", padx=4)

    def _load_applications(self):
        self._app_tree.delete(*self._app_tree.get_children())
        try:
            vac_str = self._app_vac_var.get().strip()
            vac_id = int(vac_str) if vac_str else None
            status = self._app_status_var.get() or None
            for a in self._svc.list_applications(vacancy_id=vac_id, status=status):
                self._app_tree.insert("", "end", iid=a["id"], values=(
                    a["id"], a["applicant_name"], a.get("email") or "-",
                    a["application_date"],
                    "Yes" if a["shortlisted"] else "No",
                    a.get("interview_date") or "-",
                    a.get("interview_score") if a.get("interview_score") is not None else "-",
                    "Yes" if a.get("offer_made") else "No",
                    a["status"]))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _selected_application_id(self):
        sel = self._app_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select an application.")
            return None
        return int(sel[0])

    def _new_application(self):
        dlg = tk.Toplevel(self)
        dlg.title("New Application")
        dlg.geometry("440x340")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        for label, key, default in [
            ("Vacancy ID *", "vacancy_id", self._app_vac_var.get()),
            ("Applicant Name *", "applicant_name", ""),
            ("Email", "email", ""),
            ("Phone", "phone", ""),
            ("CV Path", "cv_path", ""),
        ]:
            tk.Label(dlg, text=label).pack(anchor="w", padx=10, pady=(6, 0))
            var = tk.StringVar(value=default)
            ttk.Entry(dlg, textvariable=var, width=46).pack(padx=10)
            fields[key] = var

        tk.Label(dlg, text="Cover Letter").pack(anchor="w", padx=10, pady=(6, 0))
        cl_txt = tk.Text(dlg, height=4, width=46)
        cl_txt.pack(padx=10)

        def _save():
            try:
                vid = int(fields["vacancy_id"].get().strip())
            except ValueError:
                messagebox.showerror("Error", "Valid vacancy ID required.", parent=dlg)
                return
            name = fields["applicant_name"].get().strip()
            if not name:
                messagebox.showerror("Error", "Applicant name is required.", parent=dlg)
                return
            try:
                self._svc.create_application(
                    vacancy_id=vid,
                    applicant_name=name,
                    email=fields["email"].get().strip() or None,
                    phone=fields["phone"].get().strip() or None,
                    cv_path=fields["cv_path"].get().strip() or None,
                    cover_letter=cl_txt.get("1.0", "end-1c").strip() or None,
                )
                dlg.destroy()
                self._load_applications()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Save", command=_save).pack(pady=10)

    def _view_application(self):
        aid = self._selected_application_id()
        if not aid:
            return
        try:
            a = self._svc.get_application(aid)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        if not a:
            messagebox.showinfo("Not Found", "Application not found.")
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Application #{a['id']}")
        dlg.geometry("480x420")
        dlg.transient(self)

        info = tk.Text(dlg, wrap="word")
        info.pack(fill="both", expand=True, padx=10, pady=10)
        lines = [
            f"ID: {a['id']}",
            f"Vacancy ID: {a['vacancy_id']}",
            f"Applicant: {a['applicant_name']}",
            f"Email: {a.get('email') or '-'}",
            f"Phone: {a.get('phone') or '-'}",
            f"CV Path: {a.get('cv_path') or '-'}",
            f"Applied: {a['application_date']}",
            f"Shortlisted: {'Yes' if a['shortlisted'] else 'No'}",
            f"Interview Date: {a.get('interview_date') or '-'}",
            f"Interview Score: {a.get('interview_score') if a.get('interview_score') is not None else '-'}",
            f"References Received: {'Yes' if a.get('references_received') else 'No'}",
            f"Offer Made: {'Yes' if a.get('offer_made') else 'No'}",
            f"Offer Accepted: {'Yes' if a.get('offer_accepted') else 'No'}",
            f"Status: {a['status']}",
            "",
            "--- Interview Notes ---",
            a.get("interview_notes") or "(none)",
            "",
            "--- Cover Letter ---",
            a.get("cover_letter") or "(none)",
        ]
        info.insert("1.0", "\n".join(lines))
        info.configure(state="disabled")

    def _edit_application(self):
        aid = self._selected_application_id()
        if not aid:
            return
        try:
            a = self._svc.get_application(aid)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        if not a:
            messagebox.showinfo("Not Found", "Application not found.")
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Edit Application #{aid}")
        dlg.geometry("440x480")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        for label, key, val in [
            ("Applicant Name", "applicant_name", a["applicant_name"]),
            ("Email", "email", a.get("email") or ""),
            ("Phone", "phone", a.get("phone") or ""),
            ("CV Path", "cv_path", a.get("cv_path") or ""),
            ("Interview Date", "interview_date", a.get("interview_date") or ""),
            ("Interview Score", "interview_score",
             str(a["interview_score"]) if a.get("interview_score") is not None else ""),
            ("Status", "status", a["status"]),
        ]:
            tk.Label(dlg, text=label).pack(anchor="w", padx=10, pady=(6, 0))
            var = tk.StringVar(value=val)
            ttk.Entry(dlg, textvariable=var, width=46).pack(padx=10)
            fields[key] = var

        tk.Label(dlg, text="Interview Notes").pack(anchor="w", padx=10, pady=(6, 0))
        notes_txt = tk.Text(dlg, height=4, width=46)
        notes_txt.pack(padx=10)
        notes_txt.insert("1.0", a.get("interview_notes") or "")

        def _save():
            try:
                updates = {}
                updates["applicant_name"] = fields["applicant_name"].get().strip() or None
                updates["email"] = fields["email"].get().strip() or None
                updates["phone"] = fields["phone"].get().strip() or None
                updates["cv_path"] = fields["cv_path"].get().strip() or None
                updates["interview_date"] = fields["interview_date"].get().strip() or None
                score_str = fields["interview_score"].get().strip()
                updates["interview_score"] = float(score_str) if score_str else None
                updates["status"] = fields["status"].get().strip() or None
                notes = notes_txt.get("1.0", "end-1c").strip()
                updates["interview_notes"] = notes or None
                self._svc.update_application(aid, **updates)
                dlg.destroy()
                self._load_applications()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Save", command=_save).pack(pady=10)

    def _shortlist_application(self):
        aid = self._selected_application_id()
        if not aid:
            return
        try:
            self._svc.shortlist_application(aid)
            self._load_applications()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _delete_application(self):
        aid = self._selected_application_id()
        if not aid:
            return
        if not messagebox.askyesno("Confirm", "Delete this application?"):
            return
        try:
            self._svc.delete_application(aid)
            self._load_applications()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ── Statistics Tab ─────────────────────────────────────────────────

    def _build_stats_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Statistics")

        self._stats_text = tk.Text(tab, wrap="word", font=("Courier", 11))
        self._stats_text.pack(fill="both", expand=True)

        ttk.Button(tab, text="Refresh Stats", command=self._load_stats).pack(pady=8)

    def _load_stats(self):
        self._stats_text.configure(state="normal")
        self._stats_text.delete("1.0", "end")
        try:
            s = self._svc.get_stats()
            lines = [
                "=== Recruitment Statistics ===",
                "",
                f"Total Vacancies: {s['total_vacancies']}",
            ]
            for status, cnt in s.get("vacancies_by_status", {}).items():
                lines.append(f"  {status}: {cnt}")
            lines += [
                "",
                f"Total Applications: {s['total_applications']}",
                f"Shortlisted: {s['shortlisted']}",
                f"Offers Made: {s['offers_made']}",
                f"Offers Accepted: {s['offers_accepted']}",
            ]
            self._stats_text.insert("1.0", "\n".join(lines))
        except Exception as e:
            self._stats_text.insert("1.0", f"Error: {e}")
        self._stats_text.configure(state="disabled")

    # ── Refresh ────────────────────────────────────────────────────────

    def refresh(self):
        self._load_vacancies()
        self._load_applications()
        self._load_stats()
