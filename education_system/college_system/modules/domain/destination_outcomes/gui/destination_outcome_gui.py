"""Destination Outcome GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.college_system.modules.domain.destination_outcomes.services.destination_outcome_service import (
    DestinationOutcomeService,
)
from education_system.college_system.core.i18n import t


class DestinationOutcomeFrame(tk.Frame):
    """GUI for destination outcome tracking."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = DestinationOutcomeService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text=t("destination_outcomes.title", "Destination Outcome Tracking"),
            font=("Helvetica", 15, "bold"),
            bg="#2c3e50",
            fg="white",
        ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_outcomes_tab()
        self._build_neet_tab()
        self._build_employment_tab()
        self._build_university_tab()
        self._build_surveys_tab()

    # ── Outcomes Tab ──

    def _build_outcomes_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("destination_outcomes.outcomes", "Outcomes"))

        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text=t("destination_outcomes.year", "Year:"), bg="#ecf0f1").pack(side="left", padx=2)
        self._out_year = ttk.Entry(toolbar, width=12)
        self._out_year.pack(side="left", padx=2)

        tk.Label(toolbar, text=t("destination_outcomes.type", "Type:"), bg="#ecf0f1").pack(side="left", padx=2)
        self._out_type = ttk.Combobox(
            toolbar,
            values=["", "university", "apprenticeship", "employment", "further_education",
                    "gap_year", "neet", "unknown", "volunteering"],
            width=16, state="readonly",
        )
        self._out_type.set("")
        self._out_type.pack(side="left", padx=2)

        ttk.Button(toolbar, text=t("destination_outcomes.search", "Search"), command=self._load_outcomes).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("destination_outcomes.new", "New Outcome"), command=self._new_outcome_dialog).pack(side="left", padx=5)

        cols = ("id", "student_id", "academic_year", "outcome_type", "institution_name",
                "employer_name", "verified", "sustained_at_3m", "sustained_at_6m")
        self._outcomes_tree = ttk.Treeview(tab, columns=cols, show="headings", height=12)
        for c in cols:
            self._outcomes_tree.heading(c, text=c.replace("_", " ").title())
            self._outcomes_tree.column(c, width=110)
        self._outcomes_tree.pack(fill="both", expand=True, padx=5, pady=5)

        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", padx=5, pady=5)
        ttk.Button(btn_frame, text=t("destination_outcomes.verify", "Verify Selected"), command=self._verify_selected).pack(side="left", padx=5)
        ttk.Button(btn_frame, text=t("destination_outcomes.sustained_3m", "Mark Sustained 3m"), command=lambda: self._mark_sustained(3)).pack(side="left", padx=5)
        ttk.Button(btn_frame, text=t("destination_outcomes.sustained_6m", "Mark Sustained 6m"), command=lambda: self._mark_sustained(6)).pack(side="left", padx=5)

    def _load_outcomes(self):
        for row in self._outcomes_tree.get_children():
            self._outcomes_tree.delete(row)
        try:
            yr = self._out_year.get().strip() or None
            ot = self._out_type.get() or None
            outcomes = self._svc.list_outcomes(academic_year=yr, outcome_type=ot)
            for o in outcomes:
                self._outcomes_tree.insert("", "end", values=(
                    o["id"], o["student_id"], o.get("academic_year", ""),
                    o["outcome_type"], o.get("institution_name", ""),
                    o.get("employer_name", ""), "Yes" if o.get("verified") else "No",
                    "Yes" if o.get("sustained_at_3m") else "No",
                    "Yes" if o.get("sustained_at_6m") else "No",
                ))
        except Exception as exc:
            messagebox.showerror(t("destination_outcomes.error", "Error"), str(exc))

    def _new_outcome_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title(t("destination_outcomes.new_outcome", "New Outcome"))
        dlg.geometry("450x400")
        dlg.transient(self)

        fields = {}
        labels = [
            ("Student ID:", "student_id"), ("Academic Year:", "academic_year"),
            ("Outcome Type:", "outcome_type"), ("Leaving Date:", "leaving_date"),
            ("Institution:", "institution_name"), ("Course Title:", "course_title"),
            ("Employer:", "employer_name"), ("Job Title:", "job_title"),
            ("Notes:", "notes"),
        ]
        for i, (label, key) in enumerate(labels):
            tk.Label(dlg, text=label).grid(row=i, column=0, padx=10, pady=3, sticky="e")
            if key == "outcome_type":
                w = ttk.Combobox(dlg, values=[
                    "university", "apprenticeship", "employment", "further_education",
                    "gap_year", "neet", "unknown", "volunteering",
                ], state="readonly", width=20)
                w.set("university")
            else:
                w = ttk.Entry(dlg, width=22)
            w.grid(row=i, column=1, padx=10, pady=3)
            fields[key] = w

        def _save():
            try:
                sid = int(fields["student_id"].get().strip())
                self._svc.record_outcome(
                    student_id=sid,
                    academic_year=fields["academic_year"].get().strip(),
                    outcome_type=fields["outcome_type"].get(),
                    leaving_date=fields["leaving_date"].get().strip() or None,
                    institution_name=fields["institution_name"].get().strip() or None,
                    course_title=fields["course_title"].get().strip() or None,
                    employer_name=fields["employer_name"].get().strip() or None,
                    job_title=fields["job_title"].get().strip() or None,
                    notes=fields["notes"].get().strip() or None,
                )
                dlg.destroy()
                self._load_outcomes()
                messagebox.showinfo(t("destination_outcomes.success", "Success"), t("destination_outcomes.outcome_recorded", "Outcome recorded."))
            except Exception as exc:
                messagebox.showerror(t("destination_outcomes.error", "Error"), str(exc))

        ttk.Button(dlg, text=t("destination_outcomes.save", "Save"), command=_save).grid(row=len(labels), column=0, columnspan=2, pady=15)

    def _get_selected_id(self):
        sel = self._outcomes_tree.selection()
        if not sel:
            messagebox.showwarning(t("destination_outcomes.warning", "Warning"), t("destination_outcomes.select_row", "Select an outcome."))
            return None
        return self._outcomes_tree.item(sel[0], "values")[0]

    def _verify_selected(self):
        oid = self._get_selected_id()
        if oid is None:
            return
        try:
            user_id = self._auth.get("user_id", 0) if self._auth else 0
            self._svc.verify_outcome(int(oid), user_id)
            self._load_outcomes()
        except Exception as exc:
            messagebox.showerror(t("destination_outcomes.error", "Error"), str(exc))

    def _mark_sustained(self, months):
        oid = self._get_selected_id()
        if oid is None:
            return
        try:
            self._svc.mark_sustained(int(oid), months)
            self._load_outcomes()
        except Exception as exc:
            messagebox.showerror(t("destination_outcomes.error", "Error"), str(exc))

    # ── NEET Dashboard Tab ──

    def _build_neet_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("destination_outcomes.neet_dashboard", "NEET Dashboard"))

        frame = tk.Frame(tab, bg="#ecf0f1")
        frame.pack(padx=20, pady=20, fill="x")

        tk.Label(frame, text=t("destination_outcomes.year", "Academic Year:"), bg="#ecf0f1").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self._neet_year = ttk.Entry(frame, width=12)
        self._neet_year.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(frame, text=t("destination_outcomes.calculate", "Calculate"), command=self._calc_neet).grid(row=0, column=2, padx=5, pady=5)

        self._neet_output = tk.Text(tab, height=10, wrap="word")
        self._neet_output.pack(fill="both", expand=True, padx=20, pady=10)

    def _calc_neet(self):
        yr = self._neet_year.get().strip()
        if not yr:
            messagebox.showwarning(t("destination_outcomes.warning", "Warning"), "Enter an academic year.")
            return
        try:
            data = self._svc.get_neet_rate(yr)
            self._neet_output.delete("1.0", "end")
            self._neet_output.insert("end", f"NEET Rate for {yr}\n{'='*40}\n")
            self._neet_output.insert("end", f"Total leavers:  {data['total']}\n")
            self._neet_output.insert("end", f"NEET count:     {data['neet_count']}\n")
            self._neet_output.insert("end", f"NEET rate:      {data['rate']}%\n")
        except Exception as exc:
            messagebox.showerror(t("destination_outcomes.error", "Error"), str(exc))

    # ── Employment Stats Tab ──

    def _build_employment_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("destination_outcomes.employment", "Employment Stats"))

        frame = tk.Frame(tab, bg="#ecf0f1")
        frame.pack(padx=20, pady=20, fill="x")

        tk.Label(frame, text=t("destination_outcomes.year", "Academic Year:"), bg="#ecf0f1").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self._emp_year = ttk.Entry(frame, width=12)
        self._emp_year.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(frame, text=t("destination_outcomes.calculate", "Calculate"), command=self._calc_employment).grid(row=0, column=2, padx=5, pady=5)

        self._emp_output = tk.Text(tab, height=10, wrap="word")
        self._emp_output.pack(fill="both", expand=True, padx=20, pady=10)

    def _calc_employment(self):
        yr = self._emp_year.get().strip()
        if not yr:
            messagebox.showwarning(t("destination_outcomes.warning", "Warning"), "Enter an academic year.")
            return
        try:
            data = self._svc.get_employment_stats(yr)
            self._emp_output.delete("1.0", "end")
            self._emp_output.insert("end", f"Employment Stats for {yr}\n{'='*40}\n")
            self._emp_output.insert("end", f"Total leavers:      {data['total']}\n")
            self._emp_output.insert("end", f"Employed:            {data['employed']}\n")
            self._emp_output.insert("end", f"Apprenticeships:     {data['apprenticeships']}\n")
            self._emp_output.insert("end", f"Employment rate:     {data['employment_rate']}%\n")
            self._emp_output.insert("end", f"Sustained at 6m:     {data['sustained_6m']}\n")
        except Exception as exc:
            messagebox.showerror(t("destination_outcomes.error", "Error"), str(exc))

    # ── University Progression Tab ──

    def _build_university_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("destination_outcomes.university", "University Progression"))

        frame = tk.Frame(tab, bg="#ecf0f1")
        frame.pack(padx=20, pady=20, fill="x")

        tk.Label(frame, text=t("destination_outcomes.year", "Academic Year:"), bg="#ecf0f1").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self._uni_year = ttk.Entry(frame, width=12)
        self._uni_year.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(frame, text=t("destination_outcomes.calculate", "Calculate"), command=self._calc_university).grid(row=0, column=2, padx=5, pady=5)

        self._uni_output = tk.Text(tab, height=15, wrap="word")
        self._uni_output.pack(fill="both", expand=True, padx=20, pady=10)

    def _calc_university(self):
        yr = self._uni_year.get().strip()
        if not yr:
            messagebox.showwarning(t("destination_outcomes.warning", "Warning"), "Enter an academic year.")
            return
        try:
            data = self._svc.get_university_progression(yr)
            self._uni_output.delete("1.0", "end")
            self._uni_output.insert("end", f"University Progression for {yr}\n{'='*40}\n")
            self._uni_output.insert("end", f"Total leavers:       {data['total']}\n")
            self._uni_output.insert("end", f"University entrants:  {data['university_count']}\n")
            self._uni_output.insert("end", f"Progression rate:     {data['progression_rate']}%\n\n")
            if data.get("top_institutions"):
                self._uni_output.insert("end", "Top Institutions:\n")
                for inst in data["top_institutions"]:
                    self._uni_output.insert("end", f"  {inst['institution']}: {inst['count']}\n")
        except Exception as exc:
            messagebox.showerror(t("destination_outcomes.error", "Error"), str(exc))

    # ── Surveys Tab ──

    def _build_surveys_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("destination_outcomes.surveys", "Surveys"))

        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text=t("destination_outcomes.year", "Year:"), bg="#ecf0f1").pack(side="left", padx=2)
        self._srv_year = ttk.Entry(toolbar, width=12)
        self._srv_year.pack(side="left", padx=2)

        tk.Label(toolbar, text=t("destination_outcomes.survey_type", "Type:"), bg="#ecf0f1").pack(side="left", padx=2)
        self._srv_type = ttk.Combobox(toolbar, values=["", "3_month", "6_month", "12_month"], width=12, state="readonly")
        self._srv_type.set("")
        self._srv_type.pack(side="left", padx=2)

        ttk.Button(toolbar, text=t("destination_outcomes.search", "Search"), command=self._load_surveys).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("destination_outcomes.new_survey", "New Survey"), command=self._new_survey_dialog).pack(side="left", padx=5)

        cols = ("id", "student_id", "academic_year", "survey_type", "sent_date", "response_date", "current_status", "satisfaction_rating")
        self._surveys_tree = ttk.Treeview(tab, columns=cols, show="headings", height=10)
        for c in cols:
            self._surveys_tree.heading(c, text=c.replace("_", " ").title())
            self._surveys_tree.column(c, width=110)
        self._surveys_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _load_surveys(self):
        for row in self._surveys_tree.get_children():
            self._surveys_tree.delete(row)
        try:
            yr = self._srv_year.get().strip() or None
            st = self._srv_type.get() or None
            surveys = self._svc.list_surveys(academic_year=yr, survey_type=st)
            for s in surveys:
                self._surveys_tree.insert("", "end", values=(
                    s["id"], s["student_id"], s.get("academic_year", ""),
                    s["survey_type"], s.get("sent_date", ""), s.get("response_date", ""),
                    s.get("current_status", ""), s.get("satisfaction_rating", ""),
                ))
        except Exception as exc:
            messagebox.showerror(t("destination_outcomes.error", "Error"), str(exc))

    def _new_survey_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title(t("destination_outcomes.new_survey", "New Survey"))
        dlg.geometry("350x200")
        dlg.transient(self)

        tk.Label(dlg, text="Student ID:").grid(row=0, column=0, padx=10, pady=8, sticky="e")
        sid_entry = ttk.Entry(dlg, width=20)
        sid_entry.grid(row=0, column=1, padx=10, pady=8)

        tk.Label(dlg, text="Academic Year:").grid(row=1, column=0, padx=10, pady=8, sticky="e")
        yr_entry = ttk.Entry(dlg, width=20)
        yr_entry.grid(row=1, column=1, padx=10, pady=8)

        tk.Label(dlg, text="Survey Type:").grid(row=2, column=0, padx=10, pady=8, sticky="e")
        type_combo = ttk.Combobox(dlg, values=["3_month", "6_month", "12_month"], state="readonly", width=18)
        type_combo.set("3_month")
        type_combo.grid(row=2, column=1, padx=10, pady=8)

        def _save():
            try:
                self._svc.create_survey(
                    int(sid_entry.get().strip()),
                    yr_entry.get().strip(),
                    type_combo.get(),
                )
                dlg.destroy()
                self._load_surveys()
                messagebox.showinfo(t("destination_outcomes.success", "Success"), t("destination_outcomes.survey_created", "Survey created."))
            except Exception as exc:
                messagebox.showerror(t("destination_outcomes.error", "Error"), str(exc))

        ttk.Button(dlg, text=t("destination_outcomes.save", "Save"), command=_save).grid(row=3, column=0, columnspan=2, pady=15)

    def refresh(self):
        """Reload data in all tabs."""
        self._load_outcomes()
        self._load_surveys()
