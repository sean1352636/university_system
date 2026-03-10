"""Data quality operations manager for batch operations GUI."""
import os
import json
import datetime
import threading

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

from .constants import _t, logger, sqlite3, DEFAULT_DB_PATH, csv
from .progress_dialog import GUIProgressDialog


class QualityManager:
    """Manages data quality operations for BatchOperationsGUI."""

    def __init__(self, gui):
        self.gui = gui

    def validate_data(self):
        """GUI version of data validation"""
        if messagebox.askyesno("Validate Data",
                              "This will analyze all student records for data quality issues.\n"
                              "Continue?"):
            def validate_worker():
                try:
                    progress_dialog = GUIProgressDialog(self.gui.root, "Data Validation", "Analyzing data quality")

                    issues = self.gui.backend.validate_and_clean_data()

                    progress_dialog.close()
                    self.show_validation_results(issues)

                except Exception as e:
                    messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

            thread = threading.Thread(target=validate_worker)
            thread.daemon = True
            thread.start()

    def show_validation_results(self, issues):
        """Show data validation results"""
        dialog = tk.Toplevel(self.gui.root)
        dialog.title(_t("batch_ops.windows.validation_results"))
        dialog.geometry("700x500")
        dialog.transient(self.gui.root)
        dialog.grab_set()

        # Center dialog
        dialog.geometry("+%d+%d" % (self.gui.root.winfo_rootx() + 50, self.gui.root.winfo_rooty() + 50))

        # Header
        if issues:
            header_text = f"⚠️ Found {len(issues)} data quality issues"
        else:
            header_text = "✅ No data quality issues found"

        header = ttk.Label(dialog, text=header_text, font=("Arial", 14, "bold"))
        header.pack(pady=10)

        if issues:
            # Issues list
            issues_frame = ttk.LabelFrame(dialog, text=_t("batch_ops.labels.issues_found"), padding="10")
            issues_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

            # Treeview for issues
            columns = ("student_id", "name", "issues")
            issues_tree = ttk.Treeview(issues_frame, columns=columns, show="headings", height=15)

            issues_tree.heading("student_id", text=_t("batch_ops.columns.student_id"))
            issues_tree.heading("name", text=_t("batch_ops.columns.name"))
            issues_tree.heading("issues", text=_t("batch_ops.columns.issues"))

            issues_tree.column("student_id", width=100)
            issues_tree.column("name", width=200)
            issues_tree.column("issues", width=300)

            # Add issues data
            for issue in issues:
                issues_tree.insert('', 'end', values=(
                    issue['student_id'],
                    issue['name'],
                    '; '.join(issue['issues'])
                ))

            # Scrollbar
            issues_scrollbar = ttk.Scrollbar(issues_frame, orient="vertical", command=issues_tree.yview)
            issues_tree.configure(yscrollcommand=issues_scrollbar.set)

            issues_tree.pack(side="left", fill="both", expand=True)
            issues_scrollbar.pack(side="right", fill="y")

            # Export button
            def export_issues():
                file_path = filedialog.asksaveasfilename(
                    title="Save validation report",
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
                )
                if file_path:
                    try:
                        with open(file_path, 'w', newline='') as f:
                            writer = csv.writer(f)
                            writer.writerow(["Student ID", "Name", "Issues"])
                            for issue in issues:
                                writer.writerow([issue['student_id'], issue['name'], '; '.join(issue['issues'])])
                        messagebox.showinfo(_t("batch_ops.msg_titles.exported"), f"Validation report saved to {file_path}")
                    except Exception as e:
                        messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

            export_btn = ttk.Button(dialog, text=_t("batch_ops.buttons.export_report"), command=export_issues)
            export_btn.pack(pady=10)

        # Close button
        ttk.Button(dialog, text=_t("batch_ops.buttons.close"), command=dialog.destroy).pack(pady=10)

    def find_duplicates(self):
        """GUI version of find duplicates"""
        if messagebox.askyesno("Find Duplicates",
                              "This will analyze all student records for potential duplicates.\n"
                              "This may take some time for large databases.\n\n"
                              "Continue?"):
            def duplicate_worker():
                try:
                    progress_dialog = GUIProgressDialog(self.gui.root, "Duplicate Detection", "Analyzing for duplicates")

                    duplicates = self.gui.backend.find_duplicate_students()

                    progress_dialog.close()
                    self.show_duplicate_results(duplicates)

                except Exception as e:
                    messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

            thread = threading.Thread(target=duplicate_worker)
            thread.daemon = True
            thread.start()

    def show_duplicate_results(self, duplicates):
        """Show duplicate detection results"""
        dialog = tk.Toplevel(self.gui.root)
        dialog.title(_t("batch_ops.windows.duplicate_detection"))
        dialog.geometry("800x600")
        dialog.transient(self.gui.root)
        dialog.grab_set()

        # Center dialog
        dialog.geometry("+%d+%d" % (self.gui.root.winfo_rootx() + 50, self.gui.root.winfo_rooty() + 50))

        # Header
        if duplicates:
            header_text = f"🔍 Found {len(duplicates)} potential duplicate pairs"
        else:
            header_text = "✅ No duplicates found"

        header = ttk.Label(dialog, text=header_text, font=("Arial", 14, "bold"))
        header.pack(pady=10)

        if duplicates:
            # Duplicates list
            dup_frame = ttk.LabelFrame(dialog, text=_t("batch_ops.labels.potential_duplicates"), padding="10")
            dup_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

            # Treeview for duplicates
            columns = ("student1", "student2", "confidence", "details")
            dup_tree = ttk.Treeview(dup_frame, columns=columns, show="headings", height=15)

            dup_tree.heading("student1", text=_t("batch_ops.columns.student_1"))
            dup_tree.heading("student2", text=_t("batch_ops.columns.student_2"))
            dup_tree.heading("confidence", text=_t("batch_ops.columns.confidence"))
            dup_tree.heading("details", text=_t("batch_ops.columns.details"))

            dup_tree.column("student1", width=200)
            dup_tree.column("student2", width=200)
            dup_tree.column("confidence", width=100)
            dup_tree.column("details", width=200)

            # Add duplicates data
            for dup in duplicates:
                student1_info = f"{dup['student1']['name']} (ID: {dup['student1']['id']})"
                student2_info = f"{dup['student2']['name']} (ID: {dup['student2']['id']})"
                confidence = f"{dup['confidence']:.0%}"
                details = f"Email: {dup['student1']['email']} / {dup['student2']['email']}"

                dup_tree.insert('', 'end', values=(student1_info, student2_info, confidence, details))

            # Scrollbar
            dup_scrollbar = ttk.Scrollbar(dup_frame, orient="vertical", command=dup_tree.yview)
            dup_tree.configure(yscrollcommand=dup_scrollbar.set)

            dup_tree.pack(side="left", fill="both", expand=True)
            dup_scrollbar.pack(side="right", fill="y")

            # Action buttons
            action_frame = ttk.Frame(dialog)
            action_frame.pack(pady=10)

            def merge_duplicates():
                dialog.destroy()
                self.interactive_duplicate_merger(duplicates)

            def export_duplicates():
                file_path = filedialog.asksaveasfilename(
                    title="Save duplicates report",
                    defaultextension=".json",
                    filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
                )
                if file_path:
                    try:
                        with open(file_path, 'w') as f:
                            json.dump(duplicates, f, indent=2, default=str)
                        messagebox.showinfo(_t("batch_ops.msg_titles.exported"), f"Duplicates report saved to {file_path}")
                    except Exception as e:
                        messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

            ttk.Button(action_frame, text=_t("batch_ops.buttons.merge"), command=merge_duplicates).pack(side=tk.LEFT, padx=10)
            ttk.Button(action_frame, text=_t("batch_ops.buttons.export_report"), command=export_duplicates).pack(side=tk.LEFT, padx=10)

        # Close button
        ttk.Button(dialog, text=_t("batch_ops.buttons.close"), command=dialog.destroy).pack(pady=10)

    def interactive_duplicate_merger(self, duplicates):
        """Interactive duplicate merger with GUI"""
        if not duplicates:
            return

        self.gui.current_duplicate_index = 0
        self.gui.duplicates_list = duplicates
        self.show_duplicate_merger_dialog()

    def show_duplicate_merger_dialog(self):
        """Show individual duplicate merger dialog"""
        if self.gui.current_duplicate_index >= len(self.gui.duplicates_list):
            messagebox.showinfo(_t("batch_ops.msg_titles.complete"), "All duplicates have been processed")
            return

        dup = self.gui.duplicates_list[self.gui.current_duplicate_index]

        dialog = tk.Toplevel(self.gui.root)
        dialog.title(f"Merge Duplicate {self.gui.current_duplicate_index + 1} of {len(self.gui.duplicates_list)}")
        dialog.geometry("700x500")
        dialog.transient(self.gui.root)
        dialog.grab_set()

        # Center dialog
        dialog.geometry("+%d+%d" % (self.gui.root.winfo_rootx() + 50, self.gui.root.winfo_rooty() + 50))

        # Header
        header = ttk.Label(dialog, text=f"Potential Duplicate Pair (Confidence: {dup['confidence']:.0%})",
                          font=("Arial", 14, "bold"))
        header.pack(pady=10)

        # Student comparison
        comparison_frame = ttk.Frame(dialog)
        comparison_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Student 1
        student1_frame = ttk.LabelFrame(comparison_frame, text=_t("batch_ops.columns.student_1"), padding="10")
        student1_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        student1_info = f"""ID: {dup['student1']['id']}
Name: {dup['student1']['name']}
Email: {dup['student1']['email']}
DOB: {dup['student1']['dob']}"""

        ttk.Label(student1_frame, text=student1_info, justify=tk.LEFT).pack(anchor='w')

        # Student 2
        student2_frame = ttk.LabelFrame(comparison_frame, text=_t("batch_ops.columns.student_2"), padding="10")
        student2_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))

        student2_info = f"""ID: {dup['student2']['id']}
Name: {dup['student2']['name']}
Email: {dup['student2']['email']}
DOB: {dup['student2']['dob']}"""

        ttk.Label(student2_frame, text=student2_info, justify=tk.LEFT).pack(anchor='w')

        # Action buttons
        action_frame = ttk.Frame(dialog)
        action_frame.pack(pady=20)

        def keep_student1():
            dialog.destroy()
            self.gui.backend.merge_students(dup['student1']['id'], dup['student2']['id'], keep_first=True)
            self.gui.current_duplicate_index += 1
            self.show_duplicate_merger_dialog()

        def keep_student2():
            dialog.destroy()
            self.gui.backend.merge_students(dup['student2']['id'], dup['student1']['id'], keep_first=True)
            self.gui.current_duplicate_index += 1
            self.show_duplicate_merger_dialog()

        def skip_pair():
            dialog.destroy()
            self.gui.current_duplicate_index += 1
            self.show_duplicate_merger_dialog()

        def skip_all():
            dialog.destroy()
            messagebox.showinfo(_t("batch_ops.msg_titles.skipped"), "Remaining duplicates skipped")

        ttk.Button(action_frame, text=_t("batch_ops.buttons.keep_student_1"), command=keep_student1).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_t("batch_ops.buttons.keep_student_2"), command=keep_student2).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Skip This Pair", command=skip_pair).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Skip All Remaining", command=skip_all).pack(side=tk.LEFT, padx=5)

    def clean_data(self):
        """GUI version of data cleaning"""
        if messagebox.askyesno("Clean Data",
                              "This will automatically fix common data issues.\n"
                              "A backup will be created first.\n\n"
                              "Continue?"):
            def clean_worker():
                try:
                    progress_dialog = GUIProgressDialog(self.gui.root, "Data Cleaning", "Cleaning data")

                    fixed_count = self.gui.backend.clean_and_fix_data(progress_callback=progress_dialog.update_progress)

                    progress_dialog.close()
                    messagebox.showinfo(_t("batch_ops.msg_titles.cleaning_complete"), f"Data cleaning complete. {fixed_count} issues fixed.")

                except Exception as e:
                    messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

            thread = threading.Thread(target=clean_worker)
            thread.daemon = True
            thread.start()

    def quality_report(self):
        """Generate and show quality report"""
        def report_worker():
            try:
                self.gui.update_status("Generating quality report...")

                report = self.gui.backend.generate_data_quality_report()

                self.gui.update_status("Ready")
                self.show_quality_report(report)

            except Exception as e:
                messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

        thread = threading.Thread(target=report_worker)
        thread.daemon = True
        thread.start()

    def show_quality_report(self, report):
        """Show data quality report dialog"""
        dialog = tk.Toplevel(self.gui.root)
        dialog.title(_t("batch_ops.windows.data_quality"))
        dialog.geometry("600x500")
        dialog.transient(self.gui.root)
        dialog.grab_set()

        # Center dialog
        dialog.geometry("+%d+%d" % (self.gui.root.winfo_rootx() + 100, self.gui.root.winfo_rooty() + 100))

        # Header
        header = ttk.Label(dialog, text="Data Quality Report", font=("Arial", 14, "bold"))
        header.pack(pady=10)

        # Report content
        report_frame = ttk.Frame(dialog)
        report_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        report_text = scrolledtext.ScrolledText(report_frame, height=25, width=70)
        report_text.pack(fill=tk.BOTH, expand=True)

        # Format and insert report
        report_content = self.format_quality_report(report)
        report_text.insert(tk.END, report_content)
        report_text.config(state='disabled')

        # Export button
        def export_report():
            file_path = filedialog.asksaveasfilename(
                title="Save quality report",
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )
            if file_path:
                try:
                    with open(file_path, 'w') as f:
                        f.write(report_content)
                    messagebox.showinfo(_t("batch_ops.msg_titles.exported"), f"Quality report saved to {file_path}")
                except Exception as e:
                    messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text=_t("batch_ops.buttons.export_report"), command=export_report).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text=_t("batch_ops.buttons.close"), command=dialog.destroy).pack(side=tk.LEFT)

    def format_quality_report(self, report):
        """Format quality report for display"""
        content = f"""DATA QUALITY REPORT
Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

OVERALL STATISTICS
==================
Total Students: {report.get('total_students', 0):,}
Data Completeness: {report.get('completeness_percentage', 0):.1f}%

EMAIL QUALITY
=============
Unique Emails: {report.get('unique_emails', 0):,}
Missing Emails: {report.get('missing_emails', 0):,}
Email Uniqueness: {report.get('email_uniqueness', 0):.1f}%

NAME COMPLETENESS
=================
Complete Names: {report.get('complete_names', 0):,}
Incomplete Names: {report.get('incomplete_names', 0):,}

DATE OF BIRTH
=============
Missing DOB: {report.get('missing_dob', 0):,}
DOB Completeness: {report.get('dob_completeness', 0):.1f}%

MODULE ENROLLMENT
=================
Students without modules: {report.get('students_no_modules', 0):,}
Module enrollment rate: {report.get('module_enrollment_rate', 0):.1f}%

COURSE DISTRIBUTION
==================="""

        for course, count in report.get('course_distribution', {}).items():
            percentage = (count / report.get('total_students', 1)) * 100
            content += f"\n{course}: {count:,} ({percentage:.1f}%)"

        content += "\n\nAGE DISTRIBUTION\n================"
        for age_group, count in report.get('age_distribution', {}).items():
            percentage = (count / report.get('total_students', 1)) * 100
            content += f"\n{age_group}: {count:,} ({percentage:.1f}%)"

        return content

    def refresh_quality_dashboard(self):
        """Refresh the quality dashboard display"""
        def refresh_worker():
            try:
                self.gui.update_status("Refreshing quality dashboard...")

                dashboard_data = self.gui.get_quality_dashboard_data()

                # Update the quality dashboard display
                self.gui.quality_text.config(state='normal')
                self.gui.quality_text.delete(1.0, tk.END)

                dashboard_content = self.format_quality_dashboard(dashboard_data)
                self.gui.quality_text.insert(tk.END, dashboard_content)
                self.gui.quality_text.config(state='disabled')

                self.gui.update_status("Ready")

            except Exception as e:
                messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

        thread = threading.Thread(target=refresh_worker)
        thread.daemon = True
        thread.start()

    def format_quality_dashboard(self, data):
        """Format quality dashboard data for display"""
        return f"""📊 QUALITY DASHBOARD
Last Updated: {datetime.datetime.now().strftime('%H:%M:%S')}

📈 OVERALL HEALTH
Total Students: {data.get('total_students', 0):,}
Quality Score: {data.get('quality_score', 0):.1f}/100

🔍 RECENT ISSUES
Data Validation Errors: {data.get('validation_errors', 0)}
Duplicate Candidates: {data.get('duplicate_candidates', 0)}
Missing Information: {data.get('missing_info', 0)}

📊 COMPLETENESS METRICS
Email Addresses: {data.get('email_completeness', 0):.1f}%
Phone Numbers: {data.get('phone_completeness', 0):.1f}%
Date of Birth: {data.get('dob_completeness', 0):.1f}%

🎓 ENROLLMENT STATUS
Active Students: {data.get('active_students', 0):,}
Students with Modules: {data.get('students_with_modules', 0):,}
Module Enrollment Rate: {data.get('module_rate', 0):.1f}%

📈 TRENDS (Last 30 Days)
New Registrations: {data.get('new_registrations', 0)}
Data Updates: {data.get('data_updates', 0)}
Quality Improvements: {data.get('quality_improvements', 0)}

🚨 ALERTS
{data.get('alerts', ['No alerts'])}"""
