"""First Aid GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.first_aid.services.first_aid_service import FirstAidService


class FirstAidFrame(tk.Frame):
    """First Aid incident management screen."""

    _SEVERITIES = ("minor", "moderate", "severe", "emergency")
    _STATUSES = ("open", "treated", "referred", "closed")

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = FirstAidService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        # Header
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="First Aid",
                 font=("Helvetica", 15, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        # Notebook
        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Report tab ---
        report_tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(report_tab, text="Report Incident")

        fields_frame = tk.Frame(report_tab, bg="#ecf0f1")
        fields_frame.pack(fill="x", pady=5)

        tk.Label(fields_frame, text="Student ID:", bg="#ecf0f1").grid(
            row=0, column=0, sticky="w", padx=5, pady=3)
        self._report_student_var = tk.StringVar()
        ttk.Entry(fields_frame, textvariable=self._report_student_var,
                  width=15).grid(row=0, column=1, sticky="w", padx=5, pady=3)
        tk.Label(fields_frame, text="(optional)", font=("Helvetica", 8),
                 fg="#7f8c8d", bg="#ecf0f1").grid(row=0, column=2, sticky="w")

        tk.Label(fields_frame, text="Location:", bg="#ecf0f1").grid(
            row=1, column=0, sticky="w", padx=5, pady=3)
        self._report_location_var = tk.StringVar()
        ttk.Entry(fields_frame, textvariable=self._report_location_var,
                  width=25).grid(row=1, column=1, sticky="w", padx=5, pady=3)

        tk.Label(fields_frame, text="Severity:", bg="#ecf0f1").grid(
            row=2, column=0, sticky="w", padx=5, pady=3)
        self._report_severity_var = tk.StringVar(value="minor")
        ttk.Combobox(fields_frame, textvariable=self._report_severity_var,
                     values=list(self._SEVERITIES), state="readonly",
                     width=12).grid(row=2, column=1, sticky="w", padx=5, pady=3)

        tk.Label(fields_frame, text="Time (HH:MM):", bg="#ecf0f1").grid(
            row=3, column=0, sticky="w", padx=5, pady=3)
        self._report_time_var = tk.StringVar()
        ttk.Entry(fields_frame, textvariable=self._report_time_var,
                  width=10).grid(row=3, column=1, sticky="w", padx=5, pady=3)

        tk.Label(fields_frame, text="Description:", bg="#ecf0f1").grid(
            row=4, column=0, sticky="nw", padx=5, pady=3)
        self._report_desc = tk.Text(fields_frame, width=40, height=5)
        self._report_desc.grid(row=4, column=1, columnspan=2, sticky="w",
                               padx=5, pady=3)

        ttk.Button(fields_frame, text="Submit Report",
                   command=self._on_submit_report).grid(
            row=5, column=1, sticky="w", padx=5, pady=10)

        # --- Log tab ---
        log_tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(log_tab, text="Incident Log")

        # Filter row
        filter_row = tk.Frame(log_tab, bg="#ecf0f1")
        filter_row.pack(fill="x", pady=(0, 5))
        tk.Label(filter_row, text="Status:", bg="#ecf0f1").pack(side="left")
        self._filter_status_var = tk.StringVar(value="All")
        ttk.Combobox(filter_row, textvariable=self._filter_status_var,
                     values=["All"] + list(self._STATUSES), state="readonly",
                     width=12).pack(side="left", padx=5)
        ttk.Button(filter_row, text="Load",
                   command=self._load_incidents).pack(side="left", padx=5)

        # Treeview
        tree_frame = tk.Frame(log_tab, bg="#ecf0f1")
        tree_frame.pack(fill="both", expand=True)

        columns = ("id", "date", "student", "severity", "status", "treated_by")
        self._tree = ttk.Treeview(tree_frame, columns=columns,
                                  show="headings", selectmode="browse")
        for col, heading, w in [
            ("id", "ID", 40), ("date", "Date", 90),
            ("student", "Student", 140), ("severity", "Severity", 80),
            ("status", "Status", 80), ("treated_by", "Treated By", 100),
        ]:
            self._tree.heading(col, text=heading)
            self._tree.column(col, width=w, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                            command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._tree.bind("<<TreeviewSelect>>", self._on_select_incident)

        # Detail + update panel
        detail_frame = tk.LabelFrame(log_tab, text="Incident Details",
                                     bg="#ecf0f1", font=("Helvetica", 10, "bold"))
        detail_frame.pack(fill="x", pady=(5, 0))

        self._detail_text = tk.Text(detail_frame, height=4, wrap="word",
                                    state="disabled", font=("Helvetica", 9))
        self._detail_text.pack(fill="x", padx=5, pady=(5, 2))

        update_row = tk.Frame(detail_frame, bg="#ecf0f1")
        update_row.pack(fill="x", padx=5, pady=(0, 5))

        tk.Label(update_row, text="Status:", bg="#ecf0f1").pack(side="left")
        self._update_status_var = tk.StringVar(value="open")
        ttk.Combobox(update_row, textvariable=self._update_status_var,
                     values=list(self._STATUSES), state="readonly",
                     width=10).pack(side="left", padx=5)

        tk.Label(update_row, text="Treatment:", bg="#ecf0f1").pack(side="left", padx=(10, 0))
        self._update_treatment_var = tk.StringVar()
        ttk.Entry(update_row, textvariable=self._update_treatment_var,
                  width=20).pack(side="left", padx=5)

        ttk.Button(update_row, text="Update",
                   command=self._on_update_incident).pack(side="left", padx=5)

    def refresh(self):
        self._load_incidents()

    def _get_user_id(self) -> int:
        if self._auth and self._auth.current_user:
            return self._auth.current_user["user_id"]
        return 0

    def _on_submit_report(self):
        description = self._report_desc.get("1.0", "end").strip()
        if not description:
            messagebox.showwarning("Input", "Description is required.")
            return

        student_id = None
        sid_str = self._report_student_var.get().strip()
        if sid_str:
            from education_system.college_system.modules.domain.students.services.student_service import StudentService
            student_svc = StudentService(self._db_path)
            student = student_svc.get_student_by_student_id(sid_str)
            if not student:
                messagebox.showerror("Error", f"Student '{sid_str}' not found.")
                return
            student_id = student["id"]

        try:
            self._svc.report_incident(
                reported_by=self._get_user_id(),
                student_id=student_id,
                description=description,
                location=self._report_location_var.get().strip() or None,
                severity=self._report_severity_var.get(),
                incident_time=self._report_time_var.get().strip() or None,
            )
            messagebox.showinfo("Success", "Incident reported.")
            self._report_desc.delete("1.0", "end")
            self._report_student_var.set("")
            self._report_location_var.set("")
            self._report_time_var.set("")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_incidents(self):
        self._tree.delete(*self._tree.get_children())
        try:
            status_filter = self._filter_status_var.get()
            status = None if status_filter == "All" else status_filter
            incidents = self._svc.list_incidents(status=status)
            for inc in incidents:
                student_name = ""
                if inc.get("first_name"):
                    student_name = f"{inc['first_name']} {inc.get('last_name', '')}"
                self._tree.insert("", "end", values=(
                    inc["id"], inc["incident_date"], student_name.strip(),
                    inc["severity"], inc["status"],
                    inc.get("treated_by") or "",
                ))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_select_incident(self, event=None):
        sel = self._tree.selection()
        if not sel:
            return
        incident_id = int(self._tree.item(sel[0], "values")[0])
        try:
            inc = self._svc.get_incident(incident_id)
        except Exception:
            return

        self._detail_text.configure(state="normal")
        self._detail_text.delete("1.0", "end")
        student_name = ""
        if inc.get("first_name"):
            student_name = f"{inc['first_name']} {inc.get('last_name', '')}"
        self._detail_text.insert("end",
            f"ID: {inc['id']} | Date: {inc['incident_date']} | "
            f"Student: {student_name or 'N/A'}\n"
            f"Severity: {inc['severity']} | Status: {inc['status']} | "
            f"Location: {inc.get('location') or 'N/A'}\n"
            f"Description: {inc['description']}\n"
            f"Treatment: {inc.get('treatment') or 'None'} | "
            f"Notes: {inc.get('notes') or 'None'}")
        self._detail_text.configure(state="disabled")

        self._update_status_var.set(inc["status"])
        self._update_treatment_var.set(inc.get("treatment") or "")

    def _on_update_incident(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select an incident first.")
            return
        incident_id = int(self._tree.item(sel[0], "values")[0])

        updates = {}
        status = self._update_status_var.get()
        if status:
            updates["status"] = status
        treatment = self._update_treatment_var.get().strip()
        if treatment:
            updates["treatment"] = treatment
            username = ""
            if self._auth and self._auth.current_user:
                username = self._auth.current_user.get("username", "")
            updates["treated_by"] = username

        if not updates:
            return

        try:
            self._svc.update_incident(incident_id, **updates)
            messagebox.showinfo("Success", "Incident updated.")
            self._load_incidents()
        except Exception as e:
            messagebox.showerror("Error", str(e))
