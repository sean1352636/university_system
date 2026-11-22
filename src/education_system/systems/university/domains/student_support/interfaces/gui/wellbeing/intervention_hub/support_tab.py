"""Interventions window — Support Cases tab.

The former standalone Intervention Support app (``domain/wellbeing/
student_wellbeing/intervention_support.py``), unchanged on screen. It now
embeds in the Interventions window (or any Frame) instead of owning a Tk
root, and its records go through ``InterventionRecordsService`` so the
CLI shares them.

Persistence: the central ``student_records.db`` table
``intervention_records``. Write actions are stamped with the signed-in
user.
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from education_system.systems.university.domains.student_support.domain.wellbeing.student_wellbeing.services.intervention_records import (
    INTERVENTION_TYPES, RISK_LEVELS, STATUSES,
    InterventionRecordsError, InterventionRecordsService, build_report,
)

logger = logging.getLogger(__name__)

__all__ = ["InterventionSupportSystem"]


def _user_display_name(user):
    if not user:
        return 'Guest'
    return (user.get('username') or user.get('email') or
            user.get('user_id') or user.get('id') or 'Unknown')


class InterventionSupportSystem:
    def __init__(self, root, user=None, on_overview=None):
        self.root = root
        # Early Warning & Interventions passes this to add Student Overview.
        self._on_overview = on_overview
        # A Tk/Toplevel gets the old window sizing; a Frame (a tab) doesn't.
        if hasattr(self.root, "wm_title"):
            self.root.title("University Intervention Support System")
            self.root.geometry("1400x900+%d+%d" % ((self.root.winfo_screenwidth() - 1400) // 2, (self.root.winfo_screenheight() - 900) // 2))
            self.root.minsize(1200, 800)
        self.root.configure(bg="#f0f4f8")

        self.user = user
        self.user_display = _user_display_name(self.user)
        logger.info("Intervention Support starting user=%s role=%s",
                    self.user_display,
                    (self.user or {}).get('role') or 'none')

        self.service = InterventionRecordsService(actor=self.user_display)
        self.students = self.service.load_all()

        self.setup_styles()

        self.create_header()
        self.create_main_layout()
        self.refresh_student_list()

    def setup_styles(self):
        # Scoped to this tab's tree; the old app restyled every ttk
        # Treeview/TButton, which was harmless in its own process but
        # would leak into the main window now it embeds.
        style = ttk.Style()
        style.configure("Intervention.Treeview",
                        font=("Segoe UI", 10),
                        rowheight=28)
        style.configure("Intervention.Treeview.Heading",
                        font=("Segoe UI", 10, "bold"),
                        background="#1e3a5f",
                        foreground="white")

    def create_header(self):
        header = tk.Frame(self.root, bg="#1e3a5f", height=70)
        header.pack(fill="x")
        header.pack_propagate(False)

        title = tk.Label(header,
                         text="🎓 University Intervention Support System",
                         font=("Segoe UI", 18, "bold"),
                         bg="#1e3a5f",
                         fg="white")
        title.pack(side="left", padx=20, pady=15)

        subtitle = tk.Label(header,
                            text="Academic Success & Student Wellbeing",
                            font=("Segoe UI", 10, "italic"),
                            bg="#1e3a5f",
                            fg="#cbd5e1")
        subtitle.pack(side="left", pady=20)

        role = (self.user or {}).get('role') or ('—' if self.user else 'not signed in')
        tk.Label(header,
                 text=f"Signed in: {self.user_display}  ({role})",
                 font=("Segoe UI", 9),
                 bg="#1e3a5f", fg="#cbd5e1").pack(side="right", padx=20, pady=20)

    def create_main_layout(self):
        main_frame = tk.Frame(self.root, bg="#f0f4f8")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Left panel - Student list and filters
        left_panel = tk.Frame(main_frame, bg="#ffffff", relief="solid", bd=1)
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 5))

        self.create_left_panel(left_panel)

        # Right panel - Details and actions
        right_panel = tk.Frame(main_frame, bg="#ffffff", relief="solid", bd=1, width=420)
        right_panel.pack(side="right", fill="both", padx=(5, 0))
        right_panel.pack_propagate(False)

        self.create_right_panel(right_panel)

    def create_left_panel(self, parent):
        # Title
        tk.Label(parent,
                 text="Student Intervention Records",
                 font=("Segoe UI", 13, "bold"),
                 bg="#ffffff",
                 fg="#1e3a5f").pack(anchor="w", padx=15, pady=(15, 5))

        # Search and filter bar
        filter_frame = tk.Frame(parent, bg="#ffffff")
        filter_frame.pack(fill="x", padx=15, pady=5)

        tk.Label(filter_frame, text="Search:",
                 bg="#ffffff", font=("Segoe UI", 10)).pack(side="left")

        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *args: self.refresh_student_list())
        search_entry = tk.Entry(filter_frame,
                                textvariable=self.search_var,
                                font=("Segoe UI", 10),
                                width=25)
        search_entry.pack(side="left", padx=5)

        tk.Label(filter_frame, text="Risk Level:",
                 bg="#ffffff", font=("Segoe UI", 10)).pack(side="left", padx=(15, 5))

        self.filter_var = tk.StringVar(value="All")
        filter_combo = ttk.Combobox(filter_frame,
                                    textvariable=self.filter_var,
                                    values=["All", *RISK_LEVELS],
                                    state="readonly",
                                    width=10)
        filter_combo.pack(side="left")
        filter_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_student_list())

        # Summary stats
        self.stats_frame = tk.Frame(parent, bg="#ffffff")
        self.stats_frame.pack(fill="x", padx=15, pady=10)

        # Treeview for students
        tree_frame = tk.Frame(parent, bg="#ffffff")
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(5, 15))

        columns = ("ID", "Name", "Program", "Risk", "GPA", "Status", "Last Contact")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=18,
                                 style="Intervention.Treeview")

        col_widths = {"ID": 70, "Name": 150, "Program": 140,
                      "Risk": 80, "GPA": 60, "Status": 110, "Last Contact": 110}

        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=col_widths.get(col, 100), anchor="w")

        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.bind("<<TreeviewSelect>>", self.on_student_select)

        # Configure tags for risk-level row coloring
        self.tree.tag_configure("critical", background="#fee2e2")
        self.tree.tag_configure("high", background="#fef3c7")
        self.tree.tag_configure("medium", background="#e0f2fe")
        self.tree.tag_configure("low", background="#dcfce7")

    def create_right_panel(self, parent):
        # Title
        tk.Label(parent,
                 text="Student Details & Actions",
                 font=("Segoe UI", 13, "bold"),
                 bg="#ffffff",
                 fg="#1e3a5f").pack(anchor="w", padx=15, pady=(15, 10))

        # Form frame
        form_frame = tk.Frame(parent, bg="#ffffff")
        form_frame.pack(fill="x", padx=15)

        self.form_vars = {}

        fields = [
            ("Student ID:", "student_id"),
            ("Full Name:", "name"),
            ("Program:", "program"),
            ("GPA:", "gpa"),
            ("Email:", "email"),
        ]

        for i, (label, key) in enumerate(fields):
            tk.Label(form_frame, text=label,
                     bg="#ffffff", font=("Segoe UI", 10),
                     anchor="w").grid(row=i, column=0, sticky="w", pady=3)
            var = tk.StringVar()
            self.form_vars[key] = var
            entry = tk.Entry(form_frame, textvariable=var,
                             font=("Segoe UI", 10), width=28)
            entry.grid(row=i, column=1, pady=3, padx=5, sticky="ew")

        # Risk Level
        tk.Label(form_frame, text="Risk Level:",
                 bg="#ffffff", font=("Segoe UI", 10)).grid(row=5, column=0, sticky="w", pady=3)
        self.form_vars["risk"] = tk.StringVar(value="Low")
        risk_combo = ttk.Combobox(form_frame,
                                  textvariable=self.form_vars["risk"],
                                  values=list(RISK_LEVELS),
                                  state="readonly",
                                  width=26)
        risk_combo.grid(row=5, column=1, pady=3, padx=5, sticky="ew")

        # Status
        tk.Label(form_frame, text="Status:",
                 bg="#ffffff", font=("Segoe UI", 10)).grid(row=6, column=0, sticky="w", pady=3)
        self.form_vars["status"] = tk.StringVar(value="Active")
        status_combo = ttk.Combobox(form_frame,
                                    textvariable=self.form_vars["status"],
                                    values=list(STATUSES),
                                    state="readonly",
                                    width=26)
        status_combo.grid(row=6, column=1, pady=3, padx=5, sticky="ew")

        # Intervention Type
        tk.Label(form_frame, text="Intervention:",
                 bg="#ffffff", font=("Segoe UI", 10)).grid(row=7, column=0, sticky="w", pady=3)
        self.form_vars["intervention"] = tk.StringVar(value="Academic Advising")
        intervention_combo = ttk.Combobox(form_frame,
                                          textvariable=self.form_vars["intervention"],
                                          values=list(INTERVENTION_TYPES),
                                          state="readonly",
                                          width=26)
        intervention_combo.grid(row=7, column=1, pady=3, padx=5, sticky="ew")

        # Notes
        tk.Label(parent, text="Notes / Case History:",
                 bg="#ffffff", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=15, pady=(15, 5))

        self.notes_text = scrolledtext.ScrolledText(parent,
                                                    font=("Segoe UI", 10),
                                                    height=8,
                                                    wrap="word",
                                                    relief="solid",
                                                    bd=1)
        self.notes_text.pack(fill="both", padx=15, pady=(0, 10))

        # Action buttons
        btn_frame = tk.Frame(parent, bg="#ffffff")
        btn_frame.pack(fill="x", padx=15, pady=10)

        tk.Button(btn_frame, text="➕ Add New",
                  command=self.add_student,
                  bg="#2563eb", fg="white",
                  font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=12, pady=6,
                  cursor="hand2").pack(side="left", padx=2)

        tk.Button(btn_frame, text="💾 Update",
                  command=self.update_student,
                  bg="#059669", fg="white",
                  font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=12, pady=6,
                  cursor="hand2").pack(side="left", padx=2)

        tk.Button(btn_frame, text="🗑 Delete",
                  command=self.delete_student,
                  bg="#dc2626", fg="white",
                  font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=12, pady=6,
                  cursor="hand2").pack(side="left", padx=2)

        tk.Button(btn_frame, text="🔄 Clear",
                  command=self.clear_form,
                  bg="#6b7280", fg="white",
                  font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=12, pady=6,
                  cursor="hand2").pack(side="left", padx=2)

        # Quick action buttons
        action_frame = tk.Frame(parent, bg="#ffffff")
        action_frame.pack(fill="x", padx=15, pady=(5, 15))

        tk.Button(action_frame, text="📊 Generate Report",
                  command=self.generate_report,
                  bg="#7c3aed", fg="white",
                  font=("Segoe UI", 10),
                  relief="flat", padx=10, pady=5,
                  cursor="hand2").pack(side="left", padx=2)

        tk.Button(action_frame, text="📧 Log Contact",
                  command=self.log_contact,
                  bg="#0891b2", fg="white",
                  font=("Segoe UI", 10),
                  relief="flat", padx=10, pady=5,
                  cursor="hand2").pack(side="left", padx=2)

        if self._on_overview is not None:
            tk.Button(action_frame, text="🔗 Overview",
                      command=self._open_overview,
                      bg="#1e3a5f", fg="white",
                      font=("Segoe UI", 10),
                      relief="flat", padx=10, pady=5,
                      cursor="hand2").pack(side="left", padx=2)

    def update_stats(self):
        # Clear existing stats
        for widget in self.stats_frame.winfo_children():
            widget.destroy()

        total = len(self.students)
        critical = sum(1 for s in self.students if s.get("risk") == "Critical")
        high = sum(1 for s in self.students if s.get("risk") == "High")
        active = sum(1 for s in self.students if s.get("status") == "Active")

        stats = [
            ("Total Cases", total, "#1e3a5f"),
            ("Critical", critical, "#dc2626"),
            ("High Risk", high, "#d97706"),
            ("Active", active, "#059669"),
        ]

        for label, value, color in stats:
            card = tk.Frame(self.stats_frame, bg=color, relief="flat")
            card.pack(side="left", padx=3, fill="x", expand=True)

            tk.Label(card, text=str(value),
                     font=("Segoe UI", 16, "bold"),
                     bg=color, fg="white").pack(pady=(5, 0))

            tk.Label(card, text=label,
                     font=("Segoe UI", 9),
                     bg=color, fg="white").pack(pady=(0, 5))

    def refresh_student_list(self):
        # Clear tree
        for item in self.tree.get_children():
            self.tree.delete(item)

        search = self.search_var.get().lower()
        risk_filter = self.filter_var.get()

        for student in InterventionRecordsService.filter(self.students, search, risk_filter):
            risk = student.get("risk", "Low")
            tag = risk.lower()

            self.tree.insert("", "end", values=(
                student.get("student_id", ""),
                student.get("name", ""),
                student.get("program", ""),
                risk,
                student.get("gpa", ""),
                student.get("status", ""),
                student.get("last_contact", "N/A")
            ), tags=(tag,))

        self.update_stats()

    def on_student_select(self, event):
        selection = self.tree.selection()
        if not selection:
            return

        item = self.tree.item(selection[0])
        student_id = item["values"][0]

        student = next((s for s in self.students
                        if s.get("student_id") == str(student_id)), None)

        if student:
            for key, var in self.form_vars.items():
                var.set(student.get(key, ""))
            self.notes_text.delete("1.0", "end")
            self.notes_text.insert("1.0", student.get("notes", ""))

    def _reload(self):
        self.students = self.service.load_all()
        self.refresh_student_list()

    def reload(self):
        """Re-read the cases (another tab changed one), keeping the form."""
        selected = self.form_vars["student_id"].get()
        self._reload()
        if selected:
            self.select_student(selected)

    def select_student(self, student_id):
        """Select a case in the list and load it into the form."""
        self.search_var.set("")
        self.filter_var.set("All")
        self.refresh_student_list()
        for item in self.tree.get_children():
            if str(self.tree.item(item)["values"][0]) == str(student_id):
                self.tree.selection_set(item)
                self.tree.see(item)
                self.on_student_select(None)
                return True
        return False

    def _open_overview(self):
        student_id = self.form_vars["student_id"].get()
        if not student_id:
            messagebox.showwarning("No Selection", "Please select a student first.")
            return
        self._on_overview(student_id)

    def add_student(self):
        data = self.get_form_data()
        try:
            record = self.service.add(data)
        except InterventionRecordsError as e:
            messagebox.showwarning("Add Student", str(e))
            return
        self._reload()
        self.clear_form()
        messagebox.showinfo("Success", f"Student {record['name']} added successfully.")

    def update_student(self):
        data = self.get_form_data()
        try:
            self.service.update(data)
        except InterventionRecordsError as e:
            messagebox.showwarning("Update Student", str(e))
            return
        self._reload()
        messagebox.showinfo("Updated", "Student record updated.")

    def delete_student(self):
        student_id = self.form_vars["student_id"].get()
        if not student_id:
            messagebox.showwarning("No Selection", "Please select a student.")
            return

        if messagebox.askyesno("Confirm Delete",
                               f"Delete record for student {student_id}?"):
            try:
                self.service.delete(student_id)
            except InterventionRecordsError as e:
                messagebox.showerror("Delete Student", str(e))
                return
            self._reload()
            self.clear_form()
            messagebox.showinfo("Deleted", "Student record deleted.")

    def clear_form(self):
        for var in self.form_vars.values():
            var.set("")
        self.form_vars["risk"].set("Low")
        self.form_vars["status"].set("Active")
        self.form_vars["intervention"].set("Academic Advising")
        self.notes_text.delete("1.0", "end")

    def get_form_data(self):
        data = {key: var.get() for key, var in self.form_vars.items()}
        data["notes"] = self.notes_text.get("1.0", "end").strip()
        return data

    def log_contact(self):
        student_id = self.form_vars["student_id"].get()
        if not student_id:
            messagebox.showwarning("No Selection", "Please select a student first.")
            return

        # Keep unsaved note edits, as the old app did, before stamping.
        notes = self.notes_text.get("1.0", "end").strip()
        try:
            current = self.service.get(student_id)
            if current and notes != (current.get("notes") or ""):
                current["notes"] = notes
                self.service.update(current)
            record = self.service.log_contact(student_id)
        except InterventionRecordsError as e:
            messagebox.showerror("Log Contact", str(e))
            return
        self.notes_text.delete("1.0", "end")
        self.notes_text.insert("1.0", record["notes"])
        self._reload()
        messagebox.showinfo("Contact Logged", "Contact has been logged.")

    def generate_report(self):
        report_window = tk.Toplevel(self.root)
        report_window.title("Intervention Report")
        report_window.geometry("700x500")
        report_window.configure(bg="#ffffff")

        tk.Label(report_window, text="📊 Intervention Support Report",
                 font=("Segoe UI", 16, "bold"),
                 bg="#1e3a5f", fg="white", pady=10).pack(fill="x")

        report_text = scrolledtext.ScrolledText(report_window,
                                                font=("Consolas", 10),
                                                wrap="word")
        report_text.pack(fill="both", expand=True, padx=15, pady=15)
        report_text.insert("1.0", build_report(self.students))
        report_text.config(state="disabled")
