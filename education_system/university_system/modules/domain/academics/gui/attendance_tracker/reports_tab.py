import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext
from education_system.university_system.infrastructure.database.db import sqlite3
import datetime
import threading
import pandas as pd

# Import internationalization support
from education_system.university_system.modules.shared.utils.i18n import get_text as _, init_i18n
init_i18n()

# Import path constants
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH

# Import main database connection
try:
    from education_system.university_system.infrastructure.database.db import get_db_connection
    MAIN_DB_AVAILABLE = True
except ImportError:
    MAIN_DB_AVAILABLE = False

# Import all original functions and classes
try:
    from education_system.university_system.modules.domain.academics.services.attendance.attendance_tracker import (
        generate_executive_summary_report, get_modules, get_student_attendance, get_module_attendance
    )
    ORIGINAL_FUNCTIONS_AVAILABLE = True
except ImportError:
    ORIGINAL_FUNCTIONS_AVAILABLE = False

# Import attendance notification service
try:
    from education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications import (
        AttendanceNotificationService, check_and_notify_low_attendance
    )
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = True
except ImportError:
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = False

# Import window classes
try:
    from education_system.university_system.modules.domain.academics.gui.attendance_tracker.misc_windows import ReportPreviewWindow, CustomReportDialog, ReportWindow, CustomReportWindow
    WINDOWS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import window classes: {e}")
    ReportPreviewWindow = None
    CustomReportDialog = None
    ReportWindow = None
    CustomReportWindow = None
    WINDOWS_AVAILABLE = False


def generate_module_report(self):
        """Generate module attendance report"""
        selected = self.module_var.get()
        if not selected:
            messagebox.showwarning(_("common.warning"), _("attendance.messages.select_module_first"))
            return

        module_code = selected.split(' - ')[0]

        try:
            if not ORIGINAL_FUNCTIONS_AVAILABLE:
                report_content = f"Sample Module Report for {module_code}\n\n"
                report_content += "Total Students: 25\n"
                report_content += "Total Sessions: 20\n"
                report_content += "Overall Attendance Rate: 87.5%\n\n"
                report_content += "Student Details:\n"
                report_content += "S001 - John Doe: 90.0%\n"
                report_content += "S002 - Jane Smith: 85.0%\n"

                # Open in new window or show in preview
                if ReportWindow is not None:
                    ReportWindow(self.root, f"Module Report - {module_code}",
                               report_content, "Module Attendance")
                else:
                    self.report_preview.delete(1.0, tk.END)
                    self.report_preview.insert(tk.END, report_content)
                return

            stats = get_module_attendance(module_code)

            if not stats['students']:
                messagebox.showwarning(_("common.warning"), _("attendance.messages.no_attendance_data_module").format(module=module_code))
                return

            # Build report content
            report_content = f"MODULE ATTENDANCE REPORT: {module_code}\n"
            report_content += "=" * 50 + "\n\n"
            report_content += f"Total Students: {stats['total_students']}\n"
            report_content += f"Total Sessions: {stats['total_sessions']}\n"
            report_content += f"Overall Attendance Rate: {stats['overall_percentage']:.1f}%\n\n"

            report_content += "Student Details:\n"
            report_content += "-" * 50 + "\n"

            for student in stats['students']:
                report_content += f"{student['student_id']} - {student['name']}: {student['percentage']:.1f}%\n"

            # Open in new window or show in preview
            if ReportWindow is not None:
                ReportWindow(self.root, f"Module Report - {module_code}",
                           report_content, "Module Attendance")
            else:
                self.report_preview.delete(1.0, tk.END)
                self.report_preview.insert(tk.END, report_content)

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to generate report: {e}")

def create_reports_tab(self):
        """Create reports tab"""
        reports_frame = ttk.Frame(self.notebook)
        self.notebook.add(reports_frame, text=_("attendance.tabs.reports"))

        # Report types frame
        types_frame = ttk.LabelFrame(reports_frame, text=_("attendance.reports.report_types"), padding=10)
        types_frame.pack(fill=tk.X, pady=(0, 10))

        # Report buttons grid
        reports_grid = ttk.Frame(types_frame)
        reports_grid.pack(fill=tk.X)

        report_buttons = [
            (_("attendance.reports.student_attendance_report"), self.generate_student_report),
            (_("attendance.reports.module_attendance_report"), self.generate_module_report),
            (_("attendance.reports.executive_summary"), self.generate_executive_report),
            (_("attendance.reports.at_risk_students"), self.generate_at_risk_report),
            (_("attendance.reports.attendance_trends"), self.generate_trends_report),
            (_("attendance.reports.custom_report"), self.generate_custom_report)
        ]

        for i, (text, command) in enumerate(report_buttons):
            row = i // 3
            col = i % 3
            btn = ttk.Button(reports_grid, text=text, command=command, style='Primary.TButton')
            btn.grid(row=row, column=col, padx=5, pady=5, sticky="ew")
            reports_grid.grid_columnconfigure(col, weight=1)

        # Report parameters frame
        params_frame = ttk.LabelFrame(reports_frame, text=_("attendance.reports.report_parameters"), padding=10)
        params_frame.pack(fill=tk.X, pady=(0, 10))

        # Parameters grid
        params_grid = ttk.Frame(params_frame)
        params_grid.pack(fill=tk.X)

        # Date range
        ttk.Label(params_grid, text=_("attendance.labels.from_date")).grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.report_from_var = tk.StringVar(value=(datetime.date.today() - datetime.timedelta(days=30)).isoformat())
        ttk.Entry(params_grid, textvariable=self.report_from_var, width=15).grid(row=0, column=1, padx=(0, 10))

        ttk.Label(params_grid, text=_("attendance.labels.to_date")).grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        self.report_to_var = tk.StringVar(value=datetime.date.today().isoformat())
        ttk.Entry(params_grid, textvariable=self.report_to_var, width=15).grid(row=0, column=3, padx=(0, 10))

        # Output format
        ttk.Label(params_grid, text=_("attendance.labels.format")).grid(row=0, column=4, sticky=tk.W, padx=(0, 5))
        self.report_format_var = tk.StringVar(value="Excel")
        format_combo = ttk.Combobox(params_grid, textvariable=self.report_format_var, 
                                   values=["Excel", "PDF", "CSV"], state="readonly", width=10)
        format_combo.grid(row=0, column=5)

        # Report preview frame
        preview_frame = ttk.LabelFrame(reports_frame, text=_("attendance.reports.report_preview"), padding=10)
        preview_frame.pack(fill=tk.BOTH, expand=True)

        # Preview text widget
        self.report_preview = tk.Text(preview_frame, wrap=tk.WORD, height=15)
        preview_scrollbar = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=self.report_preview.yview)
        self.report_preview.configure(yscrollcommand=preview_scrollbar.set)

        self.report_preview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        preview_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

def generate_executive_report(self):
        """Generate executive summary report"""
        try:
            date_from = self.report_from_var.get()
            date_to = self.report_to_var.get()

            if ORIGINAL_FUNCTIONS_AVAILABLE:
                success = generate_executive_summary_report(date_from, date_to)
                if success:
                    messagebox.showinfo(_("common.success"), _("attendance.messages.executive_report_success"))
                else:
                    messagebox.showerror(_("common.error"), _("attendance.messages.executive_report_failed"))
            else:
                messagebox.showinfo(_("common.info"), _("attendance.messages.executive_report_demo"))

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to generate executive report: {e}")

def _send_attendance_alert_emails(self, at_risk_students, threshold):
        """Send email alerts to students with low attendance"""
        try:
            if not at_risk_students:
                return

            for student in at_risk_students:
                student_id = student['student_id']
                name = student['name']
                email = student['email']
                attendance_rate = student['attendance_rate']

                if not email:
                    print(f"No email address found for student {student_id}")
                    continue

                from education_system.university_system.infrastructure.email.template_utils import render_template

                subject, message = render_template('attendance_alert', {
                    'student_name': name,
                    'student_id': student_id,
                    'module_name': 'All Modules',
                    'attendance_rate': f'{attendance_rate:.1f}',
                    'required_attendance': threshold,
                    'attendance_status': '⚠️ BELOW THRESHOLD',
                    'alert_message': f"Your attendance has fallen below the required {threshold}% threshold."
                })

                if not (subject and message):
                    print("Failed to load attendance alert template")
                    continue

                # Try to send via email GUI if available
                success = self._send_email_via_gui(email, subject, message)

                if success:
                    print(f"Attendance alert sent to {name} ({email}) - {attendance_rate:.1f}% attendance")
                else:
                    # Fallback: show email details for manual sending
                    self._show_attendance_email_fallback(name, email, subject, message, attendance_rate)

            # Show summary to administrator
            messagebox.showinfo(_("attendance.messages.email_alerts_sent"),
                _("attendance.messages.email_alerts_sent_message").format(count=len(at_risk_students), threshold=threshold))

        except Exception as e:
            print(f"Failed to send attendance alert emails: {e}")
            messagebox.showerror(_("attendance.messages.email_error"),
                _("attendance.messages.email_error_message"))

def _send_email_via_gui(self, to_email, subject, message):
        """Try to send email via email GUI"""
        try:
            # Try to import and use email GUI
            from education_system.university_system.modules.shared.gui.email.email_gui import EmailManagerGUI as EmailGUI

            # Create email GUI instance (note: may need auth parameter)
            email_gui = EmailGUI(self.root, None)  # May need to pass auth if available

            # Send email through email GUI
            email_gui.send_email(
                to_email=to_email,
                subject=subject,
                message=message
            )

            return True

        except ImportError:
            return False
        except Exception as e:
            print(f"Error sending email via GUI: {e}")
            return False

def generate_quick_report(self):
        """Generate quick report for current module and date"""
        selected = self.module_var.get()
        if not selected:
            messagebox.showwarning(_("common.warning"), _("attendance.messages.select_module_first"))
            return

        module_code = selected.split(' - ')[0]
        date = self.date_var.get()

        try:
            report_text = f"Quick Report - {module_code} on {date}\n"
            report_text += "=" * 50 + "\n\n"

            # Count attendance for the day
            present_count = 0
            total_count = 0

            for item in self.student_tree.get_children():
                values = self.student_tree.item(item)['values']
                status = values[2]
                total_count += 1
                if status in ['Present', 'Late']:
                    present_count += 1

            attendance_rate = (present_count / total_count * 100) if total_count > 0 else 0

            report_text += f"Total Students: {total_count}\n"
            report_text += f"Present/Late: {present_count}\n"
            report_text += f"Attendance Rate: {attendance_rate:.1f}%\n\n"

            # Show in preview
            self.report_preview.delete(1.0, tk.END)
            self.report_preview.insert(tk.END, report_text)

            # Switch to reports tab
            self.notebook.select(3)  # Reports tab index

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to generate quick report: {e}")

def generate_student_report(self):
        """Generate student attendance report"""
        student_id = simpledialog.askstring(_("attendance.dialogs.student_report"), _("attendance.messages.enter_student_id"))
        if not student_id:
            return

        try:
            if not ORIGINAL_FUNCTIONS_AVAILABLE:
                report_content = f"Sample Student Report for {student_id}\n\n"
                report_content += "Module: CS101 - Introduction to Programming\n"
                report_content += "Total Sessions: 20\n"
                report_content += "Attended: 18\n"
                report_content += "Attendance Rate: 90.0%\n\n"
                report_content += "Overall Attendance Rate: 90.0%\n"

                # Open in new window or show in preview
                if ReportWindow is not None:
                    ReportWindow(self.root, f"Student Report - {student_id}",
                               report_content, "Student Attendance")
                else:
                    self.report_preview.delete(1.0, tk.END)
                    self.report_preview.insert(tk.END, report_content)
                return

            stats = get_student_attendance(student_id)

            if not stats:
                messagebox.showwarning(_("common.warning"), _("attendance.messages.no_attendance_data_student").format(student_id=student_id))
                return

            # Build report content
            report_content = f"ATTENDANCE REPORT: {student_id}\n"
            report_content += "=" * 50 + "\n\n"

            for module_code, data in stats.items():
                report_content += f"Module: {module_code}\n"
                report_content += f"Total Sessions: {data['total_sessions']}\n"
                report_content += f"Attended: {data['attended']}\n"
                report_content += f"Attendance Rate: {data['percentage']:.1f}%\n\n"

            overall_rate = sum(data['percentage'] for data in stats.values()) / len(stats)
            report_content += f"Overall Attendance Rate: {overall_rate:.1f}%\n"

            # Open in new window or show in preview
            if ReportWindow is not None:
                ReportWindow(self.root, f"Student Report - {student_id}",
                           report_content, "Student Attendance")
            else:
                self.report_preview.delete(1.0, tk.END)
                self.report_preview.insert(tk.END, report_content)

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to generate report: {e}")

def generate_custom_report(self):
        """Generate custom report"""
        if CustomReportWindow is None:
            messagebox.showerror(_("common.error"), "Custom report window is not available.")
            return
        CustomReportWindow(self.root)

def generate_at_risk_report(self):
        """Generate at-risk students report and send email alerts"""
        threshold = simpledialog.askfloat(_("attendance.dialogs.at_risk_threshold"), _("attendance.messages.enter_threshold"), initialvalue=75)
        if threshold is None:
            return

        # Ask if user wants to send email alerts
        send_emails = messagebox.askyesno(_("attendance.dialogs.email_alerts"),
            _("attendance.messages.email_alerts_confirm"))

        try:
            self.report_preview.delete(1.0, tk.END)

            if not ORIGINAL_FUNCTIONS_AVAILABLE:
                self.report_preview.insert(tk.END, f"AT-RISK STUDENTS (Below {threshold}% attendance)\n")
                self.report_preview.insert(tk.END, "=" * 50 + "\n\n")
                self.report_preview.insert(tk.END, "S003 - Bob Wilson: 65.0%\n")
                self.report_preview.insert(tk.END, "S007 - Alice Brown: 70.0%\n")

                if send_emails:
                    # Demo email sending for mock data
                    self._send_attendance_alert_emails([
                        {'student_id': 'S003', 'name': 'Bob Wilson', 'email': 'C123456@tees.ac.uk', 'attendance_rate': 65.0},
                        {'student_id': 'S007', 'name': 'Alice Brown', 'email': 'C789012@tees.ac.uk', 'attendance_rate': 70.0}
                    ], threshold)
                return

            conn = get_db_connection()
            query = '''
            SELECT
                ar.student_id,
                s.first_name || ' ' || s.last_name as name,
                s.email,
                AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100 as attendance_rate,
                COUNT(*) as total_sessions
            FROM attendance_records ar
            JOIN students s ON ar.student_id = s.student_id
            WHERE ar.date >= date('now', '-30 days')
            GROUP BY ar.student_id, s.first_name, s.last_name, s.email
            HAVING attendance_rate < ?
            ORDER BY attendance_rate ASC
            '''

            at_risk_df = pd.read_sql_query(query, conn, params=[threshold])
            conn.close()

            self.report_preview.insert(tk.END, f"AT-RISK STUDENTS (Below {threshold}% attendance)\n")
            self.report_preview.insert(tk.END, "=" * 50 + "\n\n")

            if not at_risk_df.empty:
                for _idx, row in at_risk_df.iterrows():
                    self.report_preview.insert(tk.END,
                        f"{row['student_id']} - {row['name']}: {row['attendance_rate']:.1f}%\n")

                # Send email alerts if requested
                if send_emails:
                    at_risk_students = []
                    for _idx, row in at_risk_df.iterrows():
                        at_risk_students.append({
                            'student_id': row['student_id'],
                            'name': row['name'],
                            'email': row['email'],
                            'attendance_rate': row['attendance_rate']
                        })
                    self._send_attendance_alert_emails(at_risk_students, threshold)
            else:
                self.report_preview.insert(tk.END, f"No students below {threshold}% attendance threshold.\n")

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to generate at-risk report: {e}")

def generate_trends_report(self):
        """Generate attendance trends report in a separate window with export/email"""
        trends_window = tk.Toplevel(self.root)
        trends_window.title(_("attendance.trends.title"))
        trends_window.geometry("900x750")
        trends_window.transient(self.root)

        # Title
        title_frame = ttk.Frame(trends_window)
        title_frame.pack(fill='x', padx=20, pady=(15, 10))
        ttk.Label(title_frame, text=_("attendance.trends.header"), font=('Arial', 14, 'bold')).pack(side=tk.LEFT)

        # Controls
        controls_frame = ttk.LabelFrame(trends_window, text=_("attendance.trends.parameters"), padding=10)
        controls_frame.pack(fill='x', padx=20, pady=(0, 10))

        ttk.Label(controls_frame, text=_("attendance.trends.period")).grid(row=0, column=0, sticky='w', padx=(0, 10))
        period_var = tk.StringVar(value="Last 30 Days")
        ttk.Combobox(controls_frame, textvariable=period_var,
                    values=["Last 7 Days", "Last 30 Days", "Last Semester", "Academic Year"],
                    width=20, state='readonly').grid(row=0, column=1, sticky='w')

        ttk.Label(controls_frame, text=_("attendance.trends.module_filter")).grid(row=0, column=2, sticky='w', padx=(20, 10))
        module_filter_var = tk.StringVar(value="All Modules")

        # Load actual modules for filter
        module_values = ["All Modules"]
        try:
            if ORIGINAL_FUNCTIONS_AVAILABLE:
                for code, name in get_modules():
                    module_values.append(f"{code} - {name}")
        except Exception:
            pass
        ttk.Combobox(controls_frame, textvariable=module_filter_var,
                    values=module_values, width=25, state='readonly').grid(row=0, column=3, sticky='w')

        # Results area
        results_frame = ttk.LabelFrame(trends_window, text=_("attendance.trends.results"), padding=10)
        results_frame.pack(fill='both', expand=True, padx=20, pady=(0, 10))

        report_text = scrolledtext.ScrolledText(results_frame, wrap='word', height=20)
        report_text.pack(fill='both', expand=True)

        # Store report content for export/email
        self._trends_report_content = ""

        def generate_analysis():
            report_text.config(state='normal')
            report_text.delete('1.0', tk.END)

            period = period_var.get()
            mod_filter = module_filter_var.get()
            now = datetime.datetime.now()

            # Try to generate from real data
            report_lines = []
            report_lines.append("ATTENDANCE TRENDS ANALYSIS REPORT")
            report_lines.append("=" * 50)
            report_lines.append(f"\nAnalysis Period: {period}")
            report_lines.append(f"Module Filter: {mod_filter}")
            report_lines.append(f"Generated: {now.strftime('%Y-%m-%d %H:%M:%S')}\n")

            try:
                conn = get_db_connection() if MAIN_DB_AVAILABLE else None
                if conn:
                    cursor = conn.cursor()

                    # Determine date range
                    if "7" in period:
                        days_back = 7
                    elif "30" in period:
                        days_back = 30
                    elif "Semester" in period:
                        days_back = 120
                    else:
                        days_back = 365

                    start_date = (now - datetime.timedelta(days=days_back)).strftime('%Y-%m-%d')

                    # Overall stats
                    query = "SELECT COUNT(*) as total, SUM(CASE WHEN status IN ('Present', 'Late') THEN 1 ELSE 0 END) as attended FROM attendance_records WHERE date >= ?"
                    params = [start_date]
                    if mod_filter != "All Modules":
                        mod_code = mod_filter.split(' - ')[0]
                        query += " AND module_code = ?"
                        params.append(mod_code)

                    cursor.execute(query, params)
                    row = cursor.fetchone()
                    total = row[0] or 0
                    attended = row[1] or 0
                    rate = (attended / total * 100) if total > 0 else 0

                    report_lines.append("OVERALL STATISTICS:")
                    report_lines.append(f"  Total Records: {total}")
                    report_lines.append(f"  Attended: {attended}")
                    report_lines.append(f"  Average Attendance Rate: {rate:.1f}%\n")

                    # Module breakdown
                    cursor.execute(f"""
                        SELECT module_code,
                               COUNT(*) as total,
                               SUM(CASE WHEN status IN ('Present', 'Late') THEN 1 ELSE 0 END) as attended
                        FROM attendance_records
                        WHERE date >= ?
                        GROUP BY module_code
                        ORDER BY module_code
                    """, (start_date,))

                    report_lines.append("MODULE PERFORMANCE:")
                    for mrow in cursor.fetchall():
                        m_total = mrow[1] or 0
                        m_att = mrow[2] or 0
                        m_rate = (m_att / m_total * 100) if m_total > 0 else 0
                        rating = "Excellent" if m_rate >= 90 else "Good" if m_rate >= 80 else "Fair" if m_rate >= 70 else "Needs Attention"
                        report_lines.append(f"  {mrow[0]}: {m_rate:.1f}% ({rating}) - {m_total} sessions")

                    # At-risk students
                    report_lines.append("\nAT-RISK STUDENTS (below 70%):")
                    cursor.execute(f"""
                        SELECT student_id,
                               COUNT(*) as total,
                               SUM(CASE WHEN status IN ('Present', 'Late') THEN 1 ELSE 0 END) as attended
                        FROM attendance_records
                        WHERE date >= ?
                        GROUP BY student_id
                        HAVING (CAST(attended AS REAL) / total) < 0.7
                        ORDER BY (CAST(attended AS REAL) / total) ASC
                    """, (start_date,))
                    at_risk = cursor.fetchall()
                    if at_risk:
                        for sr in at_risk:
                            s_rate = (sr[2] / sr[1] * 100) if sr[1] > 0 else 0
                            report_lines.append(f"  {sr[0]}: {s_rate:.1f}% ({sr[2]}/{sr[1]} sessions)")
                    else:
                        report_lines.append("  No students below 70% threshold.")

                    conn.close()
                else:
                    report_lines.append("DATABASE NOT AVAILABLE - showing sample data\n")
                    report_lines.append("MODULE PERFORMANCE:")
                    report_lines.append("  CS101: 88.7% (Good)")
                    report_lines.append("  MATH201: 91.2% (Excellent)")
                    report_lines.append("  ENG102: 85.1% (Fair)")

            except Exception as e:
                report_lines.append(f"\nError generating report: {e}")

            report_lines.append(f"\n{'=' * 50}")
            report_lines.append(f"Report generated at {now.strftime('%Y-%m-%d %H:%M:%S')}")

            content = "\n".join(report_lines)
            self._trends_report_content = content
            report_text.insert('1.0', content)
            report_text.config(state='disabled')

        # Buttons
        btn_frame = ttk.Frame(trends_window)
        btn_frame.pack(fill='x', padx=20, pady=(0, 15))

        ttk.Button(btn_frame, text=_("attendance.trends.generate"), command=generate_analysis).pack(side=tk.LEFT, padx=(0, 10))

        def export_txt():
            if not self._trends_report_content:
                messagebox.showwarning(_("common.warning"), "Generate a report first.", parent=trends_window)
                return
            filename = filedialog.asksaveasfilename(
                title="Export Trends Report",
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                parent=trends_window)
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self._trends_report_content)
                messagebox.showinfo(_("common.success"), f"Report exported to {filename}", parent=trends_window)

        ttk.Button(btn_frame, text="Export as TXT", command=export_txt).pack(side=tk.LEFT, padx=(0, 10))

        def email_to_admin():
            if not self._trends_report_content:
                messagebox.showwarning(_("common.warning"), "Generate a report first.", parent=trends_window)
                return
            try:
                from education_system.university_system.infrastructure.email.email_service import queue_email
                queue_email(
                    to="admin@university.ac.uk",
                    subject=f"Attendance Trends Report - {datetime.datetime.now().strftime('%Y-%m-%d')}",
                    body=self._trends_report_content)
                messagebox.showinfo(_("common.success"), "Report emailed to admin.", parent=trends_window)
            except ImportError:
                messagebox.showerror(_("common.error"), "Email service not available.", parent=trends_window)
            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to send email: {e}", parent=trends_window)

        ttk.Button(btn_frame, text="Email to Admin", command=email_to_admin).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text=_("common.close"), command=trends_window.destroy).pack(side=tk.RIGHT)

def _show_attendance_email_fallback(self, name, email, subject, message, attendance_rate):
        """Show fallback dialog for attendance alert email"""
        try:
            fallback_window = tk.Toplevel(self.root)
            fallback_window.title(_("attendance.dialogs.attendance_alert_email"))
            fallback_window.geometry("700x500")
            fallback_window.transient(self.root)

            ttk.Label(fallback_window,
                     text=f"Attendance alert for {name} ({attendance_rate:.1f}%) - Please send manually:",
                     font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=10, pady=10)

            # Email details
            details_frame = ttk.LabelFrame(fallback_window, text=_("attendance.dialogs.email_details"), padding=10)
            details_frame.pack(fill='both', expand=True, padx=10, pady=10)

            from tkinter.scrolledtext import ScrolledText
            details_text = ScrolledText(details_frame, height=20, width=80)
            details_text.pack(fill='both', expand=True)

            email_details = f"To: {email}\nSubject: {subject}\n\nMessage:\n{message}"

            details_text.insert('1.0', email_details)
            details_text.config(state='disabled')

            ttk.Button(fallback_window, text=_("common.close"),
                      command=fallback_window.destroy).pack(pady=10)
        except Exception as e:
            print(f"Failed to show attendance email fallback: {e}")

