"""
University Intervention Support System
A GUI application for tracking and managing student interventions,
academic support, and at-risk student monitoring.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
import json
import os


class InterventionSupportSystem:
    def __init__(self, root):
        self.root = root
        self.root.title("University Intervention Support System")
        self.root.geometry("1100x700")
        self.root.configure(bg="#f0f4f8")

        # Data storage
        self.data_file = "intervention_data.json"
        self.students = self.load_data()

        # Style configuration
        self.setup_styles()

        # Build UI
        self.create_header()
        self.create_main_layout()
        self.refresh_student_list()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Header.TLabel",
                        font=("Segoe UI", 18, "bold"),
                        background="#1e3a5f",
                        foreground="white",
                        padding=15)

        style.configure("SubHeader.TLabel",
                        font=("Segoe UI", 11, "bold"),
                        background="#f0f4f8",
                        foreground="#1e3a5f")

        style.configure("TButton",
                        font=("Segoe UI", 10),
                        padding=6)

        style.configure("Accent.TButton",
                        font=("Segoe UI", 10, "bold"),
                        background="#2563eb",
                        foreground="white")

        style.configure("Danger.TButton",
                        font=("Segoe UI", 10),
                        background="#dc2626",
                        foreground="white")

        style.configure("Treeview",
                        font=("Segoe UI", 10),
                        rowheight=28)

        style.configure("Treeview.Heading",
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
                                    values=["All", "Low", "Medium", "High", "Critical"],
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
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=18)

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
                                  values=["Low", "Medium", "High", "Critical"],
                                  state="readonly",
                                  width=26)
        risk_combo.grid(row=5, column=1, pady=3, padx=5, sticky="ew")

        # Status
        tk.Label(form_frame, text="Status:",
                 bg="#ffffff", font=("Segoe UI", 10)).grid(row=6, column=0, sticky="w", pady=3)
        self.form_vars["status"] = tk.StringVar(value="Active")
        status_combo = ttk.Combobox(form_frame,
                                    textvariable=self.form_vars["status"],
                                    values=["Active", "Monitoring", "Resolved", "Referred"],
                                    state="readonly",
                                    width=26)
        status_combo.grid(row=6, column=1, pady=3, padx=5, sticky="ew")

        # Intervention Type
        tk.Label(form_frame, text="Intervention:",
                 bg="#ffffff", font=("Segoe UI", 10)).grid(row=7, column=0, sticky="w", pady=3)
        self.form_vars["intervention"] = tk.StringVar(value="Academic Advising")
        intervention_combo = ttk.Combobox(form_frame,
                                          textvariable=self.form_vars["intervention"],
                                          values=["Academic Advising", "Tutoring",
                                                  "Counseling", "Financial Aid",
                                                  "Mental Health Support", "Disability Services",
                                                  "Career Services", "Peer Mentoring"],
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

        for student in self.students:
            # Apply filters
            if search and search not in student.get("name", "").lower() \
                    and search not in student.get("student_id", "").lower():
                continue
            if risk_filter != "All" and student.get("risk") != risk_filter:
                continue

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

    def add_student(self):
        data = self.get_form_data()
        if not data["student_id"] or not data["name"]:
            messagebox.showwarning("Missing Information",
                                   "Student ID and Name are required.")
            return

        if any(s.get("student_id") == data["student_id"] for s in self.students):
            messagebox.showerror("Duplicate ID",
                                 f"Student ID {data['student_id']} already exists.")
            return

        data["last_contact"] = datetime.now().strftime("%Y-%m-%d")
        self.students.append(data)
        self.save_data()
        self.refresh_student_list()
        self.clear_form()
        messagebox.showinfo("Success", f"Student {data['name']} added successfully.")

    def update_student(self):
        data = self.get_form_data()
        if not data["student_id"]:
            messagebox.showwarning("Missing ID", "Please select a student to update.")
            return

        for i, s in enumerate(self.students):
            if s.get("student_id") == data["student_id"]:
                data["last_contact"] = datetime.now().strftime("%Y-%m-%d")
                self.students[i] = data
                self.save_data()
                self.refresh_student_list()
                messagebox.showinfo("Updated", "Student record updated.")
                return

        messagebox.showerror("Not Found", "Student record not found.")

    def delete_student(self):
        student_id = self.form_vars["student_id"].get()
        if not student_id:
            messagebox.showwarning("No Selection", "Please select a student.")
            return

        if messagebox.askyesno("Confirm Delete",
                               f"Delete record for student {student_id}?"):
            self.students = [s for s in self.students
                             if s.get("student_id") != student_id]
            self.save_data()
            self.refresh_student_list()
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

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        current = self.notes_text.get("1.0", "end").strip()
        new_entry = f"\n[{timestamp}] Contact logged by advisor.\n"
        self.notes_text.delete("1.0", "end")
        self.notes_text.insert("1.0", current + new_entry)

        # Update last contact in data
        for s in self.students:
            if s.get("student_id") == student_id:
                s["last_contact"] = datetime.now().strftime("%Y-%m-%d")
                s["notes"] = self.notes_text.get("1.0", "end").strip()
                break
        self.save_data()
        self.refresh_student_list()
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

        # Build report
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        report = f"UNIVERSITY INTERVENTION SUPPORT REPORT\n"
        report += f"Generated: {now}\n"
        report += "=" * 60 + "\n\n"

        total = len(self.students)
        report += f"Total Student Cases: {total}\n\n"

        # Risk breakdown
        report += "RISK LEVEL BREAKDOWN:\n"
        report += "-" * 40 + "\n"
        for risk in ["Critical", "High", "Medium", "Low"]:
            count = sum(1 for s in self.students if s.get("risk") == risk)
            pct = (count / total * 100) if total else 0
            report += f"  {risk:<10} {count:>4} ({pct:.1f}%)\n"

        # Status breakdown
        report += "\nSTATUS BREAKDOWN:\n"
        report += "-" * 40 + "\n"
        for status in ["Active", "Monitoring", "Resolved", "Referred"]:
            count = sum(1 for s in self.students if s.get("status") == status)
            report += f"  {status:<12} {count:>4}\n"

        # Intervention types
        report += "\nINTERVENTION TYPES:\n"
        report += "-" * 40 + "\n"
        interventions = {}
        for s in self.students:
            itype = s.get("intervention", "Unknown")
            interventions[itype] = interventions.get(itype, 0) + 1
        for itype, count in sorted(interventions.items(), key=lambda x: -x[1]):
            report += f"  {itype:<25} {count:>4}\n"

        # Critical cases
        critical_cases = [s for s in self.students if s.get("risk") == "Critical"]
        if critical_cases:
            report += "\n\nCRITICAL CASES REQUIRING ATTENTION:\n"
            report += "=" * 60 + "\n"
            for s in critical_cases:
                report += f"\n• {s.get('name')} (ID: {s.get('student_id')})\n"
                report += f"  Program: {s.get('program')}\n"
                report += f"  GPA: {s.get('gpa')} | Status: {s.get('status')}\n"
                report += f"  Intervention: {s.get('intervention')}\n"

        report_text.insert("1.0", report)
        report_text.config(state="disabled")

    def load_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r") as f:
                    return json.load(f)
            except:
                pass

        # Sample data for first-time use
        return [
            {"student_id": "S1001", "name": "Emma Thompson",
             "program": "Computer Science", "gpa": "2.1", "email": "e.thompson@uni.edu",
             "risk": "High", "status": "Active", "intervention": "Academic Advising",
             "last_contact": "2026-04-20",
             "notes": "Struggling with core programming courses. Referred to peer tutoring."},
            {"student_id": "S1002", "name": "James Wilson",
             "program": "Biology", "gpa": "1.8", "email": "j.wilson@uni.edu",
             "risk": "Critical", "status": "Active", "intervention": "Counseling",
             "last_contact": "2026-04-22",
             "notes": "Multiple missed classes. Financial difficulties reported."},
            {"student_id": "S1003", "name": "Sofia Martinez",
             "program": "Engineering", "gpa": "2.5", "email": "s.martinez@uni.edu",
             "risk": "Medium", "status": "Monitoring", "intervention": "Tutoring",
             "last_contact": "2026-04-15",
             "notes": "Improvement noted after joining study group."},
            {"student_id": "S1004", "name": "David Chen",
             "program": "Business", "gpa": "3.2", "email": "d.chen@uni.edu",
             "risk": "Low", "status": "Resolved", "intervention": "Career Services",
             "last_contact": "2026-04-10",
             "notes": "Completed career planning sessions successfully."},
            {"student_id": "S1005", "name": "Aisha Patel",
             "program": "Psychology", "gpa": "2.3", "email": "a.patel@uni.edu",
             "risk": "High", "status": "Referred", "intervention": "Mental Health Support",
             "last_contact": "2026-04-18",
             "notes": "Referred to university counseling services."},
        ]

    def save_data(self):
        try:
            with open(self.data_file, "w") as f:
                json.dump(self.students, f, indent=2)
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save data: {e}")


def main():
    root = tk.Tk()
    app = InterventionSupportSystem(root)
    root.mainloop()


if __name__ == "__main__":
    main()
