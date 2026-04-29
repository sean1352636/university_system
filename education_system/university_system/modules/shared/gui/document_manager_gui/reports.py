import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta
import csv
import json
import logging

logger = logging.getLogger(__name__)

try:
    from education_system.university_system.infrastructure.database.db import get_connection
except ImportError:
    from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
    def get_connection():
        return sqlite3.connect(str(DEFAULT_DB_PATH))

try:
    from education_system.university_system.modules.shared.utils.i18n import get_text as _t
except ImportError:
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")


class ReportsManager:
    """Manager for reports-related functionality in the Document Manager GUI."""

    def __init__(self, gui):
        self.gui = gui
        self.root = gui.root

    def show_reports(self):
        """Show reports interface"""
        self.gui.clear_content_area()

        # Create reports frame
        reports_frame = ttk.Frame(self.gui.content_area)
        reports_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        ttk.Label(reports_frame, text="Reports & Analytics", font=('Arial', 18, 'bold')).pack(pady=(0, 20))

        # Create report categories
        self.create_report_categories(reports_frame)

    def create_report_categories(self, parent):
        """Create report category sections"""
        # Standard Reports
        standard_frame = ttk.LabelFrame(parent, text="Standard Reports", padding=15)
        standard_frame.pack(fill='x', pady=(0, 15))

        standard_reports = [
            ("📊 Compliance Report", "Student document compliance overview", self.generate_compliance_report),
            ("📈 Status Report", "Document status distribution", self.generate_status_report),
            ("⏰ Expiry Report", "Documents expiring soon", self.generate_expiry_report),
            ("👥 Student Progress", "Individual student progress", self.generate_student_progress_report),
            ("📅 Monthly Summary", "Monthly activity summary", self.generate_monthly_summary),
        ]

        row = 0
        for title, description, command in standard_reports:
            report_frame = ttk.Frame(standard_frame)
            report_frame.grid(row=row//2, column=row%2, padx=10, pady=5, sticky='ew')

            ttk.Button(report_frame, text=title, command=command, width=25).pack(anchor='w')
            ttk.Label(report_frame, text=description, font=('Arial', 9), foreground='gray').pack(anchor='w')
            row += 1

        # Configure grid weights
        for i in range(3):
            standard_frame.grid_rowconfigure(i, weight=1)
        standard_frame.grid_columnconfigure(0, weight=1)
        standard_frame.grid_columnconfigure(1, weight=1)

        # Custom Reports
        custom_frame = ttk.LabelFrame(parent, text="Custom Reports", padding=15)
        custom_frame.pack(fill='x', pady=(0, 15))

        ttk.Button(custom_frame, text="🔧 Custom Report Builder",
                  command=self.custom_report_builder, width=30).pack(pady=5)
        ttk.Label(custom_frame, text="Build custom reports with flexible filters and fields",
                 font=('Arial', 9), foreground='gray').pack()

        # Export Options
        export_frame = ttk.LabelFrame(parent, text="Export Options", padding=15)
        export_frame.pack(fill='x')

        export_buttons = [
            ("📄 Export to CSV", self.gui.export_to_csv),
            ("📊 Export to Excel", self.gui.export_to_excel),
            ("📋 Export to PDF", self.gui.export_to_pdf),
        ]

        for text, command in export_buttons:
            ttk.Button(export_frame, text=text, command=command, width=20).pack(side='left', padx=10)

    def generate_compliance_report(self):
        """Generate compliance report"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get compliance data
            cursor.execute('''
            SELECT s.student_id, s.first_name, s.last_name, s.course,
                   'N/A' as year,
                   COUNT(DISTINCT req_types.type_id) as required_count,
                   COUNT(DISTINCT submitted_docs.document_id) as submitted_count
            FROM students s
            CROSS JOIN document_types req_types
            LEFT JOIN documents submitted_docs ON s.student_id = submitted_docs.owner_id
                AND submitted_docs.source_type = 'student'
                AND req_types.type_id = CAST(submitted_docs.document_type AS INTEGER)
                AND submitted_docs.is_current_version = 1
            WHERE req_types.is_required = 1
            GROUP BY s.student_id
            ORDER BY s.last_name, s.first_name
            ''')

            compliance_data = cursor.fetchall()
            conn.close()

            # Create report window
            report_window = tk.Toplevel(self.root)
            report_window.title("Compliance Report")
            report_window.geometry("800x600")

            # Report frame
            report_frame = ttk.Frame(report_window, padding=20)
            report_frame.pack(fill='both', expand=True)

            # Title
            title_text = f"Document Compliance Report - Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            ttk.Label(report_frame, text=title_text, font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Summary stats
            summary_frame = ttk.LabelFrame(report_frame, text="Summary", padding=10)
            summary_frame.pack(fill='x', pady=(0, 15))

            total_students = len(compliance_data)
            compliant_students = sum(1 for row in compliance_data if row[5] == row[6])
            compliance_rate = (compliant_students / total_students) * 100 if total_students > 0 else 0

            ttk.Label(summary_frame, text=f"Total Students: {total_students}").grid(row=0, column=0, sticky='w', padx=10)
            ttk.Label(summary_frame, text=f"Compliant Students: {compliant_students}").grid(row=0, column=1, sticky='w', padx=10)
            ttk.Label(summary_frame, text=f"Compliance Rate: {compliance_rate:.1f}%").grid(row=0, column=2, sticky='w', padx=10)

            # Detailed report
            details_frame = ttk.LabelFrame(report_frame, text="Detailed Report", padding=10)
            details_frame.pack(fill='both', expand=True, pady=(0, 15))

            # Create treeview for detailed data
            columns = ('Student ID', 'Name', 'Course', 'Year', 'Status', 'Progress')
            compliance_tree = ttk.Treeview(details_frame, columns=columns, show='headings', height=15)

            for col in columns:
                compliance_tree.heading(col, text=col)
                compliance_tree.column(col, width=100)

            # Add scrollbar
            scrollbar = ttk.Scrollbar(details_frame, orient='vertical', command=compliance_tree.yview)
            compliance_tree.configure(yscrollcommand=scrollbar.set)

            compliance_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            # Populate data
            for row in compliance_data:
                student_id, first_name, last_name, course, year, required, submitted = row
                name = f"{first_name} {last_name}"
                status = "Compliant" if required == submitted else "Non-Compliant"
                progress = f"{submitted}/{required}"

                compliance_tree.insert('', 'end', values=(student_id, name, course, year, status, progress))

            # Export button
            button_frame = ttk.Frame(report_frame)
            button_frame.pack(fill='x')

            # Prepare data for email/export
            report_columns = ('Student ID', 'Name', 'Course', 'Year', 'Status', 'Progress')
            report_data = []
            for row in compliance_data:
                student_id, first_name, last_name, course, year, required, submitted = row
                name = f"{first_name} {last_name}"
                status = "Compliant" if required == submitted else "Non-Compliant"
                progress = f"{submitted}/{required}"
                report_data.append((student_id, name, course, year, status, progress))

            def export_compliance_csv():
                fp = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv")],
                    initialfile=f"compliance_report_{datetime.now().strftime('%Y%m%d')}.csv"
                )
                if fp:
                    try:
                        with open(fp, 'w', newline='', encoding='utf-8') as f:
                            writer = csv.writer(f)
                            writer.writerow(report_columns)
                            writer.writerows(report_data)
                        messagebox.showinfo("Success", f"Report exported to:\n{fp}")
                    except Exception as ex:
                        messagebox.showerror("Error", f"Failed to export: {ex}")

            ttk.Button(button_frame, text="📧 Send to Admin",
                      command=lambda: self.gui.send_report_to_admin("Compliance Report", report_columns, report_data)).pack(side='left', padx=5)
            ttk.Button(button_frame, text="📄 Export to CSV",
                      command=export_compliance_csv).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Close", command=report_window.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Report Error", f"Failed to generate compliance report: {str(e)}")

    def generate_status_report(self):
        """Generate document status distribution report"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT verification_status, COUNT(*) as count
                FROM documents
                WHERE is_current_version = 1
                GROUP BY verification_status
            ''')

            results = cursor.fetchall()
            conn.close()

            # Create report window
            report_window = tk.Toplevel(self.root)
            report_window.title("Document Status Report")
            report_window.geometry("850x600")

            main_frame = ttk.Frame(report_window, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Document Status Distribution",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Create treeview for results
            columns = ('Status', 'Count')
            tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=10)

            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=200)

            for row in results:
                tree.insert('', 'end', values=tuple(row))

            tree.pack(fill='both', expand=True)

            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill='x', pady=(10, 0))

            report_columns = ('Status', 'Count')
            report_data = [tuple(row) for row in results]
            ttk.Button(button_frame, text="📧 Email Report to Admin",
                      command=lambda: self.gui.send_report_to_admin(
                          "Document Status Report", report_columns, report_data
                      )).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Close",
                      command=report_window.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate status report: {e}")

    def generate_expiry_report(self):
        """Generate report of documents expiring soon"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get documents expiring within 30 days
            cursor.execute('''
                SELECT
                    sd.document_id,
                    sd.owner_id as student_id,
                    s.first_name || ' ' || s.last_name as student_name,
                    dt.type_name,
                    sd.upload_date,
                    sd.expiry_date,
                    CAST((julianday(sd.expiry_date) - julianday('now')) AS INTEGER) as days_until_expiry
                FROM documents sd
                JOIN students s ON sd.owner_id = s.student_id
                JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
                WHERE sd.source_type = 'student' AND sd.expiry_date IS NOT NULL
                    AND sd.expiry_date > date('now')
                    AND sd.expiry_date <= date('now', '+30 days')
                ORDER BY sd.expiry_date ASC
            ''')

            results = cursor.fetchall()
            conn.close()

            # Create report window
            report_window = tk.Toplevel(self.root)
            report_window.title("Document Expiry Report")
            report_window.geometry("1000x600")

            main_frame = ttk.Frame(report_window, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Documents Expiring Within 30 Days",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Create treeview for results
            columns = ('Doc ID', 'Student ID', 'Student Name', 'Document Type', 'Upload Date', 'Expiry Date', 'Days Left')
            tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=15)

            # Column widths
            tree.column('Doc ID', width=80)
            tree.column('Student ID', width=100)
            tree.column('Student Name', width=150)
            tree.column('Document Type', width=150)
            tree.column('Upload Date', width=120)
            tree.column('Expiry Date', width=120)
            tree.column('Days Left', width=100)

            for col in columns:
                tree.heading(col, text=col)

            for row in results:
                tree.insert('', 'end', values=tuple(row))

            # Scrollbar
            scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            # Summary and buttons
            bottom_frame = ttk.Frame(report_window, padding=(20, 10))
            bottom_frame.pack(fill='x')

            summary_text = f"Total: {len(results)} document(s) expiring soon"
            ttk.Label(bottom_frame, text=summary_text, font=('Arial', 10)).pack(anchor='w')

            button_frame = ttk.Frame(bottom_frame)
            button_frame.pack(fill='x', pady=(5, 0))

            report_columns = ('Doc ID', 'Student ID', 'Student Name',
                              'Document Type', 'Upload Date', 'Expiry Date', 'Days Left')
            report_data = [tuple(row) for row in results]
            ttk.Button(button_frame, text="📧 Email Report to Admin",
                      command=lambda: self.gui.send_report_to_admin(
                          "Document Expiry Report", report_columns, report_data
                      )).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Close",
                      command=report_window.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate expiry report: {e}")

    def generate_monthly_summary(self):
        """Generate monthly summary report"""
        try:
            # Create dialog
            report_window = tk.Toplevel(self.root)
            report_window.title("Monthly Summary Report")
            report_window.geometry("1000x700")

            main_frame = ttk.Frame(report_window, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Monthly Summary Report",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            conn = get_connection()
            cursor = conn.cursor()

            # Get current month stats
            cursor.execute('''
            SELECT COUNT(*) as total_uploads,
                   SUM(CASE WHEN verification_status = 'Verified' THEN 1 ELSE 0 END) as verified,
                   SUM(CASE WHEN verification_status = 'Pending' THEN 1 ELSE 0 END) as pending,
                   SUM(CASE WHEN verification_status = 'Rejected' THEN 1 ELSE 0 END) as rejected
            FROM documents
            WHERE strftime('%Y-%m', upload_date) = strftime('%Y-%m', 'now')
            ''')

            stats = cursor.fetchone()

            # Stats display
            stats_frame = ttk.LabelFrame(main_frame, text="This Month's Statistics", padding=15)
            stats_frame.pack(fill='x', pady=(0, 15))

            labels = [
                ("Total Uploads:", stats[0]),
                ("Verified:", stats[1]),
                ("Pending:", stats[2]),
                ("Rejected:", stats[3])
            ]

            for i, (label, value) in enumerate(labels):
                ttk.Label(stats_frame, text=label, font=('Arial', 10, 'bold')).grid(row=i, column=0, sticky='w', padx=5, pady=2)
                ttk.Label(stats_frame, text=str(value), font=('Arial', 10)).grid(row=i, column=1, sticky='w', padx=5, pady=2)

            # Monthly breakdown
            cursor.execute('''
            SELECT strftime('%Y-%m', upload_date) as month,
                   COUNT(*) as count
            FROM documents
            WHERE upload_date >= date('now', '-12 months')
            GROUP BY month
            ORDER BY month DESC
            LIMIT 12
            ''')

            monthly_data = cursor.fetchall()
            conn.close()

            # Monthly table
            table_frame = ttk.LabelFrame(main_frame, text="Last 12 Months", padding=15)
            table_frame.pack(fill='both', expand=True)

            columns = ('Month', 'Total Uploads')
            tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=12)

            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=200)

            for row in monthly_data:
                tree.insert('', 'end', values=tuple(row))

            tree.pack(fill='both', expand=True)

            # Export button
            def export_summary():
                try:
                    filename = filedialog.asksaveasfilename(
                        defaultextension=".csv",
                        filetypes=[("CSV files", "*.csv")],
                        initialfile=f"monthly_summary_{datetime.now().strftime('%Y%m%d')}.csv"
                    )
                    if filename:
                        import csv
                        with open(filename, 'w', newline='') as f:
                            writer = csv.writer(f)
                            writer.writerow(['Metric', 'Value'])
                            writer.writerows([
                                ['Total Uploads This Month', stats[0]],
                                ['Verified', stats[1]],
                                ['Pending', stats[2]],
                                ['Rejected', stats[3]]
                            ])
                            writer.writerow([])
                            writer.writerow(['Month', 'Total Uploads'])
                            writer.writerows([tuple(row) for row in monthly_data])
                        messagebox.showinfo("Success", f"Report exported to:\n{filename}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to export: {e}")

            button_frame = ttk.Frame(report_window)
            button_frame.pack(pady=10)

            def email_monthly_summary():
                report_columns = ('Metric', 'Value')
                report_data = [
                    ('Total Uploads This Month', stats[0]),
                    ('Verified', stats[1]),
                    ('Pending', stats[2]),
                    ('Rejected', stats[3]),
                ]
                for row in monthly_data:
                    r = tuple(row)
                    report_data.append((f"Month {r[0]}", r[1]))
                self.gui.send_report_to_admin(
                    "Monthly Summary Report", report_columns, report_data
                )

            ttk.Button(button_frame, text="📧 Email Report to Admin",
                      command=email_monthly_summary).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Export to CSV",
                      command=export_summary).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Close",
                      command=report_window.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate monthly summary: {e}")

    def generate_department_analysis(self):
        """Generate department analysis report"""
        try:
            report_window = tk.Toplevel(self.root)
            report_window.title("Department Analysis Report")
            report_window.geometry("1000x700")

            main_frame = ttk.Frame(report_window, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Department Analysis Report",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            conn = get_connection()
            cursor = conn.cursor()

            # Get department stats
            cursor.execute('''
            SELECT s.course as department,
                   COUNT(DISTINCT sd.owner_id) as total_students,
                   COUNT(sd.document_id) as total_documents,
                   SUM(CASE WHEN sd.verification_status = 'Verified' THEN 1 ELSE 0 END) as verified_docs,
                   ROUND(AVG(sd.file_size)/1024.0, 2) as avg_file_size_kb
            FROM documents sd
            JOIN students s ON sd.owner_id = s.student_id
            WHERE sd.source_type = 'student' AND sd.is_current_version = 1
            GROUP BY s.course
            ORDER BY total_documents DESC
            ''')

            dept_data = cursor.fetchall()
            conn.close()

            # Create table
            columns = ('Department', 'Students', 'Total Docs', 'Verified', 'Avg Size (KB)')
            tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=15)

            widths = [250, 100, 100, 100, 120]
            for i, col in enumerate(columns):
                tree.heading(col, text=col)
                tree.column(col, width=widths[i])

            for row in dept_data:
                tree.insert('', 'end', values=tuple(row))

            scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            # Export button
            def export_dept_analysis():
                try:
                    filename = filedialog.asksaveasfilename(
                        defaultextension=".csv",
                        filetypes=[("CSV files", "*.csv")],
                        initialfile=f"department_analysis_{datetime.now().strftime('%Y%m%d')}.csv"
                    )
                    if filename:
                        import csv
                        with open(filename, 'w', newline='') as f:
                            writer = csv.writer(f)
                            writer.writerow(columns)
                            writer.writerows([tuple(r) for r in dept_data])
                        messagebox.showinfo("Success", f"Report exported to:\n{filename}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to export: {e}")

            button_frame = ttk.Frame(report_window)
            button_frame.pack(pady=10)

            ttk.Button(button_frame, text="Export to CSV", command=export_dept_analysis).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Close", command=report_window.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate department analysis: {e}")

    def generate_student_progress_report(self):
        """
        Generate comprehensive student progress report
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Student Progress Report")
            dialog.geometry("900x750")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Generate Student Progress Report",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Student selection
            student_frame = ttk.LabelFrame(main_frame, text="Select Student", padding=10)
            student_frame.pack(fill='x', pady=(0, 15))

            ttk.Label(student_frame, text="Student:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
            student_combo = ttk.Combobox(student_frame, width=40, state='readonly')
            student_combo.grid(row=0, column=1, padx=5, pady=5, sticky='ew')

            # Load students
            students = self.gui.get_students_list()
            student_combo['values'] = [f"{s[0]} - {s[1]} {s[2]}" for s in students]

            student_frame.grid_columnconfigure(1, weight=1)

            # Report options
            options_frame = ttk.LabelFrame(main_frame, text="Report Options", padding=10)
            options_frame.pack(fill='x', pady=(0, 15))

            include_docs = tk.BooleanVar(value=True)
            include_workflow = tk.BooleanVar(value=True)
            include_requirements = tk.BooleanVar(value=True)
            include_notifications = tk.BooleanVar(value=False)

            ttk.Checkbutton(options_frame, text="Include Documents Summary", variable=include_docs).pack(anchor='w', pady=3)
            ttk.Checkbutton(options_frame, text="Include Workflow Status", variable=include_workflow).pack(anchor='w', pady=3)
            ttk.Checkbutton(options_frame, text="Include Requirements Check", variable=include_requirements).pack(anchor='w', pady=3)
            ttk.Checkbutton(options_frame, text="Include Notifications", variable=include_notifications).pack(anchor='w', pady=3)

            # Report preview
            preview_frame = ttk.LabelFrame(main_frame, text="Report Preview", padding=10)
            preview_frame.pack(fill='both', expand=True, pady=(0, 15))

            preview_text = tk.Text(preview_frame, wrap=tk.WORD, font=('Courier', 9))
            preview_text.pack(fill='both', expand=True)

            scrollbar = ttk.Scrollbar(preview_text, orient='vertical', command=preview_text.yview)
            preview_text.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side='right', fill='y')

            def generate_report():
                if not student_combo.get():
                    messagebox.showerror("Error", "Please select a student")
                    return

                student_id = student_combo.get().split(' - ')[0]

                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    # Get student info
                    cursor.execute('''
                    SELECT first_name, last_name, email_address, course, enrollment_date, status
                    FROM students WHERE student_id = ?
                    ''', (student_id,))
                    student_info = cursor.fetchone()

                    if not student_info:
                        messagebox.showerror("Error", "Student not found")
                        return

                    report = []
                    report.append("=" * 80)
                    report.append("STUDENT PROGRESS REPORT")
                    report.append("=" * 80)
                    report.append(f"\nStudent ID: {student_id}")
                    report.append(f"Name: {student_info[0]} {student_info[1]}")
                    report.append(f"Email: {student_info[2]}")
                    report.append(f"Course: {student_info[3]}")
                    report.append(f"Enrollment Date: {student_info[4]}")
                    report.append(f"Status: {student_info[5]}")
                    report.append(f"\nReport Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    report.append("\n" + "=" * 80 + "\n")

                    # Documents summary
                    if include_docs.get():
                        report.append("\nDOCUMENTS SUMMARY")
                        report.append("-" * 80)
                        cursor.execute('''
                        SELECT dt.type_name, sd.upload_date, sd.verification_status, sd.version_number
                        FROM documents sd
                        JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
                        WHERE sd.owner_id = ? AND sd.source_type = 'student' AND sd.is_current_version = 1
                        ORDER BY sd.upload_date DESC
                        ''', (student_id,))
                        docs = cursor.fetchall()

                        if docs:
                            for doc in docs:
                                report.append(f"\n  \u2022 {doc[0]}")
                                report.append(f"    Uploaded: {doc[1]}")
                                report.append(f"    Status: {doc[2]}")
                                report.append(f"    Version: {doc[3]}")
                        else:
                            report.append("\n  No documents uploaded yet.")

                        cursor.execute("SELECT COUNT(*) FROM documents WHERE owner_id = ? AND source_type = 'student'", (student_id,))
                        total_docs = cursor.fetchone()[0]
                        report.append(f"\n  Total Documents: {total_docs}")

                    # Workflow status
                    if include_workflow.get():
                        report.append("\n\nWORKFLOW STATUS")
                        report.append("-" * 80)
                        cursor.execute('''
                        SELECT dw.step_name, dw.status, dw.assigned_to, dw.completed_date
                        FROM document_workflow dw
                        JOIN documents sd ON dw.document_id = sd.document_id
                        WHERE sd.owner_id = ? AND sd.source_type = 'student'
                        ORDER BY dw.step_order
                        ''', (student_id,))
                        workflows = cursor.fetchall()

                        if workflows:
                            pending = sum(1 for w in workflows if w[1] == 'pending')
                            completed = sum(1 for w in workflows if w[1] == 'completed')
                            report.append(f"\n  Pending Steps: {pending}")
                            report.append(f"  Completed Steps: {completed}")
                            report.append("\n  Recent Workflows:")
                            for wf in workflows[:10]:
                                report.append(f"\n    \u2022 {wf[0]}")
                                report.append(f"      Status: {wf[1]}")
                                report.append(f"      Assigned To: {wf[2]}")
                                if wf[3]:
                                    report.append(f"      Completed: {wf[3]}")
                        else:
                            report.append("\n  No active workflows.")

                    # Requirements check
                    if include_requirements.get():
                        report.append("\n\nREQUIREMENTS CHECK")
                        report.append("-" * 80)
                        cursor.execute('''
                        SELECT dt.type_name, dt.is_required
                        FROM document_types dt
                        WHERE dt.is_required = 1
                        ''')
                        required_docs = cursor.fetchall()

                        if required_docs:
                            report.append("\n  Required Documents:")
                            for req in required_docs:
                                # documents.document_type stores the type_id as TEXT —
                                # cast to INTEGER to match document_types.type_id, the
                                # same shape the dashboard activity query uses.
                                cursor.execute('''
                                SELECT COUNT(*) FROM documents
                                WHERE owner_id = ?
                                  AND source_type = 'student'
                                  AND CAST(document_type AS INTEGER) = (
                                      SELECT type_id FROM document_types WHERE type_name = ?
                                  )
                                ''', (student_id, req[0]))
                                has_doc = cursor.fetchone()[0] > 0
                                status = "\u2713 Submitted" if has_doc else "\u2717 Missing"
                                report.append(f"    {status} - {req[0]}")

                    # Notifications
                    if include_notifications.get():
                        report.append("\n\nRECENT NOTIFICATIONS")
                        report.append("-" * 80)
                        cursor.execute('''
                        SELECT title, message, created_at, is_read
                        FROM notifications
                        WHERE user_id = ?
                        ORDER BY created_at DESC
                        LIMIT 10
                        ''', (student_id,))
                        notifications = cursor.fetchall()

                        if notifications:
                            for notif in notifications:
                                read_status = "[Read]" if notif[3] else "[Unread]"
                                report.append(f"\n  {read_status} {notif[0]}")
                                report.append(f"    Date: {notif[2]}")
                                report.append(f"    Message: {notif[1][:100]}...")
                        else:
                            report.append("\n  No notifications.")

                    conn.close()

                    # Display report
                    preview_text.delete('1.0', tk.END)
                    preview_text.insert('1.0', '\n'.join(report))

                    self.gui.log_event('generate', 'student_report', student_id, {
                        'report_type': 'progress',
                        'options': {
                            'docs': include_docs.get(),
                            'workflow': include_workflow.get(),
                            'requirements': include_requirements.get(),
                            'notifications': include_notifications.get()
                        }
                    })

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to generate report: {e}")

            def export_report():
                if not preview_text.get('1.0', tk.END).strip():
                    messagebox.showwarning("Warning", "Please generate report first")
                    return

                file_path = filedialog.asksaveasfilename(
                    defaultextension=".txt",
                    filetypes=[("Text files", "*.txt"), ("PDF files", "*.pdf"), ("All files", "*.*")],
                    initialfile=f"student_progress_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                )

                if file_path:
                    try:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(preview_text.get('1.0', tk.END))
                        messagebox.showinfo("Success", f"Report exported to:\n{file_path}")
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to export report: {e}")

            # Action buttons
            action_frame = ttk.Frame(main_frame)
            action_frame.pack(fill='x')

            def email_progress_report():
                content = preview_text.get('1.0', tk.END).strip()
                if not content:
                    messagebox.showwarning("Warning", "Please generate report first")
                    return
                report_columns = ('Report Content',)
                report_data = [(line,) for line in content.split('\n') if line.strip()]
                self.gui.send_report_to_admin(
                    "Student Progress Report", report_columns, report_data
                )

            ttk.Button(action_frame, text="Generate Report",
                      command=generate_report).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Export Report",
                      command=export_report).pack(side='left', padx=5)
            ttk.Button(action_frame, text="📧 Email Report to Admin",
                      command=email_progress_report).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Close",
                      command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open report generator: {e}")

    def custom_report_builder(self):
        """
        Custom report builder with flexible options
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Custom Report Builder")
            dialog.geometry("1000x800")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Custom Report Builder",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Left panel - Configuration
            config_panel = ttk.Frame(main_frame)
            config_panel.pack(side='left', fill='both', expand=True, padx=(0, 10))

            # Report type
            type_frame = ttk.LabelFrame(config_panel, text="Report Type", padding=10)
            type_frame.pack(fill='x', pady=(0, 10))

            report_type = tk.StringVar(value="documents")
            ttk.Radiobutton(type_frame, text="Documents Summary", variable=report_type, value="documents").pack(anchor='w', pady=3)
            ttk.Radiobutton(type_frame, text="Student Overview", variable=report_type, value="students").pack(anchor='w', pady=3)
            ttk.Radiobutton(type_frame, text="Workflow Analytics", variable=report_type, value="workflow").pack(anchor='w', pady=3)
            ttk.Radiobutton(type_frame, text="Document Types", variable=report_type, value="doc_types").pack(anchor='w', pady=3)
            ttk.Radiobutton(type_frame, text="Custom Query", variable=report_type, value="custom").pack(anchor='w', pady=3)

            # Filters
            filter_frame = ttk.LabelFrame(config_panel, text="Filters", padding=10)
            filter_frame.pack(fill='x', pady=(0, 10))

            ttk.Label(filter_frame, text="Date Range:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
            date_range = ttk.Combobox(filter_frame, values=['All Time', 'Last 7 Days', 'Last 30 Days', 'Last 90 Days', 'This Year'], width=20, state='readonly')
            date_range.set('All Time')
            date_range.grid(row=0, column=1, padx=5, pady=5, sticky='w')

            ttk.Label(filter_frame, text="Status:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
            status_filter = ttk.Combobox(filter_frame, values=['All', 'Pending', 'Approved', 'Rejected', 'Verified'], width=20, state='readonly')
            status_filter.set('All')
            status_filter.grid(row=1, column=1, padx=5, pady=5, sticky='w')

            # Fields to include
            fields_frame = ttk.LabelFrame(config_panel, text="Fields to Include", padding=10)
            fields_frame.pack(fill='both', expand=True)

            fields_list = tk.Listbox(fields_frame, selectmode='multiple', height=10)
            fields_list.pack(fill='both', expand=True)

            # Populate fields based on report type
            def update_fields(*args):
                fields_list.delete(0, tk.END)
                rtype = report_type.get()
                if rtype == "documents":
                    fields = ['Document ID', 'Student Name', 'Document Type', 'Upload Date', 'Status', 'File Size', 'Version']
                elif rtype == "students":
                    fields = ['Student ID', 'Name', 'Email', 'Course', 'Year', 'Enrollment Date', 'Status', 'Documents Count']
                elif rtype == "workflow":
                    fields = ['Workflow ID', 'Document ID', 'Step Name', 'Assigned To', 'Status', 'Completed Date']
                elif rtype == "doc_types":
                    fields = ['Type ID', 'Type Name', 'Description', 'Required', 'Has Expiry', 'Max Size', 'Formats']
                else:
                    fields = ['Custom - Enter SQL Query']

                for field in fields:
                    fields_list.insert(tk.END, field)
                    if rtype != "custom":
                        fields_list.selection_set(0, tk.END)

            report_type.trace('w', update_fields)
            update_fields()

            # Right panel - Preview
            preview_panel = ttk.Frame(main_frame)
            preview_panel.pack(side='right', fill='both', expand=True)

            preview_label = ttk.Label(preview_panel, text="Report Preview", font=('Arial', 12, 'bold'))
            preview_label.pack(pady=(0, 10))

            # Preview table
            preview_frame = ttk.Frame(preview_panel)
            preview_frame.pack(fill='both', expand=True)

            preview_tree = ttk.Treeview(preview_frame, show='headings', height=25)
            preview_scrollbar_y = ttk.Scrollbar(preview_frame, orient='vertical', command=preview_tree.yview)
            preview_scrollbar_x = ttk.Scrollbar(preview_frame, orient='horizontal', command=preview_tree.xview)
            preview_tree.configure(yscrollcommand=preview_scrollbar_y.set, xscrollcommand=preview_scrollbar_x.set)

            preview_tree.grid(row=0, column=0, sticky='nsew')
            preview_scrollbar_y.grid(row=0, column=1, sticky='ns')
            preview_scrollbar_x.grid(row=1, column=0, sticky='ew')

            preview_frame.grid_rowconfigure(0, weight=1)
            preview_frame.grid_columnconfigure(0, weight=1)

            stats_label = ttk.Label(preview_panel, text="", font=('Arial', 9), foreground='blue')
            stats_label.pack(pady=(10, 0))

            def generate_custom_report():
                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    rtype = report_type.get()
                    selected_fields = [fields_list.get(i) for i in fields_list.curselection()]

                    if not selected_fields and rtype != "custom":
                        messagebox.showwarning("Warning", "Please select at least one field")
                        return

                    # Clear preview
                    for item in preview_tree.get_children():
                        preview_tree.delete(item)

                    # Build query based on report type
                    if rtype == "documents":
                        query = '''
                        SELECT sd.document_id, s.first_name || ' ' || s.last_name as student_name,
                               dt.type_name, sd.upload_date, sd.verification_status, sd.file_size, sd.version_number
                        FROM documents sd
                        JOIN students s ON sd.owner_id = s.student_id
                        JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
                        WHERE sd.source_type = 'student' AND sd.is_current_version = 1
                        '''
                    elif rtype == "students":
                        query = '''
                        SELECT s.student_id, s.first_name || ' ' || s.last_name as name,
                               s.email_address, s.course, 'N/A' as year, s.enrollment_date, s.status,
                               COUNT(sd.document_id) as doc_count
                        FROM students s
                        LEFT JOIN documents sd ON s.student_id = sd.owner_id AND sd.source_type = 'student'
                        GROUP BY s.student_id
                        '''
                    elif rtype == "workflow":
                        query = '''
                        SELECT workflow_id, document_id, step_name, assigned_to, status, completed_date
                        FROM document_workflow
                        '''
                    elif rtype == "doc_types":
                        query = '''
                        SELECT type_id, type_name, description, is_required, has_expiry,
                               max_file_size_mb, allowed_formats
                        FROM document_types
                        WHERE is_active = 1
                        '''
                    else:
                        messagebox.showinfo("Info", "Custom query mode - enter SQL manually")
                        return

                    # Apply filters using parameterized queries
                    params = []

                    if status_filter.get() != 'All':
                        if 'WHERE' in query:
                            query += " AND status = ?"
                        else:
                            query += " WHERE status = ?"
                        params.append(status_filter.get())

                    # Apply date filter
                    date_range_val = date_range.get()
                    if date_range_val != 'All Time' and 'upload_date' in query:
                        days_map = {'Last 7 Days': 7, 'Last 30 Days': 30, 'Last 90 Days': 90, 'This Year': 365}
                        days = days_map.get(date_range_val, 0)
                        if days:
                            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
                            if 'WHERE' in query:
                                query += " AND upload_date >= ?"
                            else:
                                query += " WHERE upload_date >= ?"
                            params.append(cutoff)

                    query += " LIMIT 1000"

                    cursor.execute(query, params)
                    results = cursor.fetchall()
                    conn.close()

                    if results:
                        # Set columns
                        columns = selected_fields if selected_fields else [f"Col{i}" for i in range(len(results[0]))]
                        preview_tree['columns'] = columns

                        for col in columns:
                            preview_tree.heading(col, text=col)
                            preview_tree.column(col, width=120)

                        # Insert data
                        for row in results:
                            preview_tree.insert('', 'end', values=tuple(row))

                        stats_label.config(text=f"Total Records: {len(results)}")
                    else:
                        stats_label.config(text="No records found")

                    self.gui.log_event('generate', 'custom_report', None, {
                        'report_type': rtype,
                        'records_count': len(results)
                    })

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to generate report: {e}")

            def export_custom_report():
                if len(preview_tree.get_children()) == 0:
                    messagebox.showwarning("Warning", "Please generate report first")
                    return

                file_path = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("Excel files", "*.xlsx"), ("All files", "*.*")],
                    initialfile=f"custom_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                )

                if file_path:
                    try:
                        with open(file_path, 'w', newline='', encoding='utf-8') as f:
                            writer = csv.writer(f)
                            # Write headers
                            writer.writerow(preview_tree['columns'])
                            # Write data
                            for item in preview_tree.get_children():
                                writer.writerow(preview_tree.item(item)['values'])

                        messagebox.showinfo("Success", f"Report exported to:\n{file_path}")
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to export: {e}")

            # Bottom buttons
            button_frame = ttk.Frame(config_panel)
            button_frame.pack(fill='x', pady=(10, 0))

            def email_custom_report():
                if len(preview_tree.get_children()) == 0:
                    messagebox.showwarning("Warning", "Please generate report first")
                    return
                report_columns = tuple(preview_tree['columns'])
                report_data = [
                    tuple(preview_tree.item(item)['values'])
                    for item in preview_tree.get_children()
                ]
                self.gui.send_report_to_admin(
                    "Custom Report", report_columns, report_data
                )

            ttk.Button(button_frame, text="Generate",
                      command=generate_custom_report).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Export",
                      command=export_custom_report).pack(side='left', padx=5)
            ttk.Button(button_frame, text="📧 Email to Admin",
                      command=email_custom_report).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Close",
                      command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open custom report builder: {e}")

    def student_document_summary(self):
        """Generate student document summary"""
        if not self.gui.ensure_login():
            return

        # Create summary window
        summary_window = tk.Toplevel(self.root)
        summary_window.title("Student Document Summary")
        summary_window.geometry("800x600")
        summary_window.transient(self.root)
        summary_window.grab_set()

        ttk.Label(summary_window, text="Student Document Summary",
                 font=("Arial", 14, "bold")).pack(pady=10)

        # Student selection
        select_frame = ttk.Frame(summary_window)
        select_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(select_frame, text="Student ID:").pack(side='left', padx=5)
        student_entry = ttk.Entry(select_frame, width=20)
        student_entry.pack(side='left', padx=5)

        def generate_summary():
            student_id = student_entry.get().strip()
            if not student_id:
                messagebox.showwarning("Input Required", "Please enter a student ID")
                return

            try:
                with get_connection() as conn:
                    cursor = conn.cursor()

                    # Get student documents
                    cursor.execute("""
                        SELECT
                            COUNT(*) as total,
                            SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) as pending,
                            SUM(CASE WHEN status = 'Approved' THEN 1 ELSE 0 END) as approved,
                            SUM(CASE WHEN status = 'Rejected' THEN 1 ELSE 0 END) as rejected,
                            SUM(CASE WHEN DATE(expiry_date) < DATE('now') THEN 1 ELSE 0 END) as expired
                        FROM documents
                        WHERE student_id = ?
                    """, (student_id,))
                    stats = cursor.fetchone()

                    # Get document list
                    cursor.execute("""
                        SELECT document_type, file_name, status, upload_date, expiry_date
                        FROM documents
                        WHERE student_id = ?
                        ORDER BY upload_date DESC
                    """, (student_id,))
                    documents = cursor.fetchall()

                if stats[0] == 0:
                    messagebox.showinfo("No Documents", f"No documents found for student {student_id}")
                    return

                # Create summary display
                summary_text = tk.Text(summary_window, width=80, height=25, wrap='word')
                summary_text.pack(fill='both', expand=True, padx=10, pady=5)

                summary_content = f"""
STUDENT DOCUMENT SUMMARY REPORT
================================================================================
Student ID: {student_id}
Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

DOCUMENT STATISTICS
--------------------------------------------------------------------------------
Total Documents:      {stats[0]}
Pending Approval:     {stats[1]}
Approved:             {stats[2]}
Rejected:             {stats[3]}
Expired:              {stats[4]}

DOCUMENT LIST
--------------------------------------------------------------------------------
"""
                for doc in documents:
                    doc_type, file_name, status, upload_date, expiry_date = doc
                    summary_content += f"\nDocument Type: {doc_type}\n"
                    summary_content += f"  File: {file_name}\n"
                    summary_content += f"  Status: {status}\n"
                    summary_content += f"  Uploaded: {upload_date}\n"
                    summary_content += f"  Expiry: {expiry_date or 'N/A'}\n"

                summary_text.insert('1.0', summary_content)
                summary_text.config(state='disabled')

                # Export button
                def export_summary():
                    file_path = filedialog.asksaveasfilename(
                        defaultextension=".txt",
                        filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
                        initialfile=f"student_{student_id}_summary.txt"
                    )
                    if file_path:
                        with open(file_path, 'w') as f:
                            f.write(summary_content)
                        messagebox.showinfo("Export Successful", f"Summary exported to:\n{file_path}")

                ttk.Button(summary_window, text="Export to File",
                          command=export_summary).pack(pady=5)

                self.gui.log_event('generate', 'student_summary',
                              details=f'Generated summary for student {student_id}')

            except Exception as e:
                messagebox.showerror("Error", f"Failed to generate summary: {e}")

        ttk.Button(select_frame, text="Generate Summary",
                  command=generate_summary).pack(side='left', padx=5)

        ttk.Button(summary_window, text="Close",
                  command=summary_window.destroy).pack(pady=10)

    def student_compliance_report(self):
        """Generate student compliance report"""
        # This is handled by export_compliance_report()
        self.gui.export_compliance_report()

    def document_statistics_report(self):
        """Generate document statistics report"""
        if not self.gui.ensure_login():
            return

        # Create statistics window
        stats_window = tk.Toplevel(self.root)
        stats_window.title("Document Statistics Report")
        stats_window.geometry("1000x750")
        stats_window.transient(self.root)
        stats_window.grab_set()

        ttk.Label(stats_window, text="Document Statistics Report",
                 font=("Arial", 14, "bold")).pack(pady=10)

        # Create notebook
        notebook = ttk.Notebook(stats_window)
        notebook.pack(fill='both', expand=True, padx=10, pady=5)

        # Tab 1: Overall Statistics
        overall_frame = ttk.Frame(notebook, padding=10)
        notebook.add(overall_frame, text="Overall Stats")

        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Get overall stats
                cursor.execute("""
                    SELECT
                        COUNT(*) as total,
                        COUNT(DISTINCT student_id) as unique_students,
                        COUNT(DISTINCT document_type) as unique_types,
                        SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) as pending,
                        SUM(CASE WHEN status = 'Approved' THEN 1 ELSE 0 END) as approved,
                        SUM(CASE WHEN status = 'Rejected' THEN 1 ELSE 0 END) as rejected,
                        SUM(CASE WHEN DATE(expiry_date) < DATE('now') THEN 1 ELSE 0 END) as expired,
                        AVG(file_size) as avg_size,
                        SUM(file_size) as total_size
                    FROM documents
                """)
                stats = cursor.fetchone()

                stats_text = tk.Text(overall_frame, width=80, height=25, wrap='word')
                stats_text.pack(fill='both', expand=True)

                report_content = f"""
OVERALL DOCUMENT STATISTICS
================================================================================

Total Documents:              {stats[0]:,}
Unique Students:              {stats[1]:,}
Unique Document Types:        {stats[2]:,}

STATUS BREAKDOWN
--------------------------------------------------------------------------------
Pending Approval:             {stats[3]:,} ({stats[3]/stats[0]*100:.1f}%)
Approved:                     {stats[4]:,} ({stats[4]/stats[0]*100:.1f}%)
Rejected:                     {stats[5]:,} ({stats[5]/stats[0]*100:.1f}%)
Expired:                      {stats[6]:,} ({stats[6]/stats[0]*100:.1f}%)

STORAGE STATISTICS
--------------------------------------------------------------------------------
Average File Size:            {stats[7]/1024/1024:.2f} MB
Total Storage Used:           {stats[8]/1024/1024/1024:.2f} GB
"""

                # Get document type breakdown
                cursor.execute("""
                    SELECT document_type, COUNT(*) as count
                    FROM documents
                    GROUP BY document_type
                    ORDER BY count DESC
                """)
                type_stats = cursor.fetchall()

                report_content += "\nDOCUMENT TYPE BREAKDOWN\n"
                report_content += "-" * 80 + "\n"
                for doc_type, count in type_stats:
                    report_content += f"{doc_type:30} {count:10,} ({count/stats[0]*100:6.1f}%)\n"

                # Get monthly upload trends
                cursor.execute("""
                    SELECT strftime('%Y-%m', upload_date) as month, COUNT(*) as count
                    FROM documents
                    GROUP BY month
                    ORDER BY month DESC
                    LIMIT 12
                """)
                monthly_stats = cursor.fetchall()

                report_content += "\nMONTHLY UPLOAD TRENDS (Last 12 Months)\n"
                report_content += "-" * 80 + "\n"
                for month, count in monthly_stats:
                    bar_char = '\u2588'
                    bar = bar_char * int(count/10)
                    padding = ' ' * (50 - int(count/10))
                    report_content += f"{month}:  {bar}{padding} {count:,} documents\n"

                stats_text.insert('1.0', report_content)
                stats_text.config(state='disabled')

        except Exception as e:
            ttk.Label(overall_frame, text=f"Error loading statistics: {e}").pack()

        # Tab 2: Charts (Placeholder)
        charts_frame = ttk.Frame(notebook, padding=10)
        notebook.add(charts_frame, text="Visual Charts")

        ttk.Label(charts_frame, text="Visual charts would be displayed here using matplotlib",
                 font=("Arial", 11)).pack(pady=20)

        # Export button
        def export_stats():
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
                initialfile="document_statistics.txt"
            )
            if file_path:
                with open(file_path, 'w') as f:
                    f.write(report_content)
                messagebox.showinfo("Export Successful", f"Statistics exported to:\n{file_path}")

        ttk.Button(stats_window, text="Export Report",
                  command=export_stats).pack(pady=5)
        ttk.Button(stats_window, text="Close",
                  command=stats_window.destroy).pack(pady=5)

        self.gui.log_event('generate', 'statistics_report', details='Generated document statistics report')

    def scheduled_reports(self):
        """Manage scheduled reports"""
        if not self.gui.ensure_login('admin'):
            return

        # Create scheduled reports window
        reports_window = tk.Toplevel(self.root)
        reports_window.title("Scheduled Reports")
        reports_window.geometry("900x650")
        reports_window.transient(self.root)
        reports_window.grab_set()

        ttk.Label(reports_window, text="Scheduled Reports Management",
                 font=("Arial", 14, "bold")).pack(pady=10)

        # Reports list
        list_frame = ttk.LabelFrame(reports_window, text="Scheduled Reports", padding=10)
        list_frame.pack(fill='both', expand=True, padx=10, pady=5)

        tree = ttk.Treeview(list_frame,
                           columns=('Name', 'Type', 'Schedule', 'Recipients', 'Last Run', 'Status'),
                           show='headings', height=15)
        tree.heading('Name', text='Report Name')
        tree.heading('Type', text='Report Type')
        tree.heading('Schedule', text='Schedule')
        tree.heading('Recipients', text='Recipients')
        tree.heading('Last Run', text='Last Run')
        tree.heading('Status', text='Status')

        tree.column('Name', width=150)
        tree.column('Type', text='Report Type', width=120)
        tree.column('Schedule', width=120)
        tree.column('Recipients', width=150)
        tree.column('Last Run', width=120)
        tree.column('Status', width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Sample scheduled reports
        sample_reports = [
            ('Weekly Compliance Report', 'Compliance', 'Every Monday 9:00 AM', 'admin@university.edu', '2024-11-04', 'Active'),
            ('Monthly Statistics', 'Statistics', 'First day of month', 'management@university.edu', '2024-11-01', 'Active'),
            ('Daily Pending Documents', 'Pending Summary', 'Daily 8:00 AM', 'staff@university.edu', '2024-11-07', 'Active'),
        ]

        for report in sample_reports:
            tree.insert('', 'end', values=report)

        # Button frame
        button_frame = ttk.Frame(reports_window)
        button_frame.pack(fill='x', padx=10, pady=10)

        def add_schedule():
            messagebox.showinfo("Add Schedule",
                              "Feature to add new scheduled report.\n\n"
                              "Would configure:\n"
                              "- Report type\n"
                              "- Schedule (daily/weekly/monthly)\n"
                              "- Recipients\n"
                              "- Delivery method")

        def edit_schedule():
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("No Selection", "Please select a scheduled report")
                return
            messagebox.showinfo("Edit Schedule", "Edit selected scheduled report configuration")

        def delete_schedule():
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("No Selection", "Please select a scheduled report")
                return
            if messagebox.askyesno("Confirm Delete", "Delete selected scheduled report?"):
                tree.delete(selected)

        def run_now():
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("No Selection", "Please select a scheduled report")
                return
            messagebox.showinfo("Run Now", "Report generation started. You will receive it via email shortly.")

        ttk.Button(button_frame, text="Add Schedule",
                  command=add_schedule).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Edit",
                  command=edit_schedule).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Delete",
                  command=delete_schedule).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Run Now",
                  command=run_now).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Close",
                  command=reports_window.destroy).pack(side='right', padx=5)

        self.gui.log_event('view', 'scheduled_reports', details='Viewed scheduled reports management')
