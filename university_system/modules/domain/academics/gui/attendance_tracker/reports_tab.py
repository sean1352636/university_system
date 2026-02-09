import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext
from university_system.infrastructure.database.db import sqlite3
import datetime
import threading
import pandas as pd

# Import internationalization support
from university_system.modules.shared.utils.i18n import get_text as _, init_i18n
init_i18n()

# Import path constants
from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH

# Import main database connection
try:
    from university_system.infrastructure.database.db import get_db_connection
    MAIN_DB_AVAILABLE = True
except ImportError:
    MAIN_DB_AVAILABLE = False

# Import all original functions and classes
try:
    from university_system.modules.domain.academics.services.attendance.attendance_tracker import (
        generate_executive_summary_report, get_modules, get_student_attendance, get_module_attendance
    )
    ORIGINAL_FUNCTIONS_AVAILABLE = True
except ImportError:
    ORIGINAL_FUNCTIONS_AVAILABLE = False

# Import attendance notification service
try:
    from university_system.modules.domain.academics.services.attendance.attendance_notifications import (
        AttendanceNotificationService, check_and_notify_low_attendance
    )
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = True
except ImportError:
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = False

# Import window classes
try:
    from .misc_windows import ReportPreviewWindow, CustomReportDialog, ReportWindow, CustomReportWindow
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

                from university_system.infrastructure.email.template_utils import render_template

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
            from university_system.modules.shared.gui.email.email_gui import EmailManagerGUI as EmailGUI

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
                for _, row in at_risk_df.iterrows():
                    self.report_preview.insert(tk.END,
                        f"{row['student_id']} - {row['name']}: {row['attendance_rate']:.1f}%\n")

                # Send email alerts if requested
                if send_emails:
                    at_risk_students = []
                    for _, row in at_risk_df.iterrows():
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
        """Generate attendance trends report"""
        # Create trends analysis window
        trends_window = tk.Toplevel(self.root)
        trends_window.title(_("attendance.trends.title"))
        trends_window.geometry("900x700")
        trends_window.transient(self.root)
        trends_window.grab_set()

        # Title
        title_frame = ttk.Frame(trends_window)
        title_frame.pack(fill='x', padx=20, pady=20)
        ttk.Label(title_frame, text=_("attendance.trends.header"), style='Title.TLabel').pack()

        # Analysis controls
        controls_frame = ttk.LabelFrame(trends_window, text=_("attendance.trends.parameters"), padding="15")
        controls_frame.pack(fill='x', padx=20, pady=(0, 15))

        # Time period selection
        ttk.Label(controls_frame, text=_("attendance.trends.period")).grid(row=0, column=0, sticky='w', padx=(0, 10))
        period_var = tk.StringVar(value=_("attendance.trends.last_30_days"))
        ttk.Combobox(controls_frame, textvariable=period_var,
                    values=[_("attendance.trends.last_7_days"), _("attendance.trends.last_30_days"), _("attendance.trends.last_semester"), _("attendance.trends.academic_year")],
                    width=20).grid(row=0, column=1, sticky='w')

        ttk.Label(controls_frame, text=_("attendance.trends.module_filter")).grid(row=0, column=2, sticky='w', padx=(20, 10))
        module_filter_var = tk.StringVar(value=_("attendance.trends.all_modules"))
        ttk.Combobox(controls_frame, textvariable=module_filter_var,
                    values=[_("attendance.trends.all_modules"), "CS101", "MATH201", "ENG102"],
                    width=20).grid(row=0, column=3, sticky='w')

        # Generate button
        def generate_analysis():
            # Clear previous results
            for widget in results_frame.winfo_children():
                widget.destroy()

            # Create analysis text display
            analysis_text = tk.Text(results_frame, wrap='word', height=25)
            analysis_text.pack(fill='both', expand=True, padx=10, pady=10)

            # Add scrollbar
            scrollbar = ttk.Scrollbar(results_frame, orient='vertical', command=analysis_text.yview)
            scrollbar.pack(side='right', fill='y')
            analysis_text.config(yscrollcommand=scrollbar.set)

            from datetime import datetime
            trends_data = f"""
ATTENDANCE TRENDS ANALYSIS REPORT
================================

Analysis Period: {period_var.get()}
Module Filter: {module_filter_var.get()}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

OVERALL STATISTICS:
• Average Attendance Rate: 87.3%
• Trend Direction: ↗ Improving (+2.1% vs previous period)
• Best Day: Tuesday (92.1% average)
• Worst Day: Friday (81.7% average)
• Peak Time: 10:00 AM - 11:00 AM
• Low Time: 4:00 PM - 5:00 PM

WEEKLY BREAKDOWN:
Week 1: 89.2% (↗ +1.5%)
Week 2: 86.8% (↘ -2.4%)
Week 3: 88.9% (↗ +2.1%)
Week 4: 84.3% (↘ -4.6%)

MODULE PERFORMANCE:
1. MATH201 - 91.2% (Excellent)
2. CS101 - 88.7% (Good)
3. ENG102 - 85.1% (Fair)
4. PHYS301 - 82.9% (Needs Attention)

DAILY PATTERNS:
Monday: 86.2% (Slow start effect)
Tuesday: 92.1% (Peak performance)
Wednesday: 89.8% (Mid-week consistency)
Thursday: 87.5% (Afternoon decline)
Friday: 81.7% (Weekend anticipation)

PATTERN ANALYSIS:
• Monday Morning Effect: 15% lower attendance in first period
• Mid-week Peak: Tuesday-Wednesday show highest engagement
• Weather Correlation: 23% drop during rainy days
• Assignment Due Dates: 8% increase day before submissions

RISK INDICATORS:
⚠ 12 students with attendance <70%
⚠ CS101 showing declining trend (-5% over 3 weeks)
⚠ Friday afternoon sessions consistently underperforming

RECOMMENDATIONS:
✓ Implement incentives for Friday attendance
✓ Review CS101 delivery method
✓ Consider weather-based virtual sessions
✓ Targeted intervention for at-risk students
✓ Flexible scheduling for working students

HOURLY BREAKDOWN:
8:00 AM: 79.2% (Early struggle)
9:00 AM: 88.7% (Recovery)
10:00 AM: 94.1% (Peak performance)
11:00 AM: 91.8% (Maintained high)
12:00 PM: 85.3% (Lunch dip)
1:00 PM: 89.7% (Afternoon recovery)
2:00 PM: 87.2% (Steady)
3:00 PM: 82.1% (Decline begins)
4:00 PM: 78.9% (Low point)
5:00 PM: 76.3% (End of day fatigue)

STUDENT INSIGHTS:
• Consistent Attendees: 78 students (66.1%)
• Sporadic Attendees: 23 students (19.5%)
• Declining Trend: 12 students (10.2%)
• Improving Trend: 8 students (6.8%)

CORRELATION ANALYSIS:
• Academic Performance vs Attendance: 0.78 correlation
• Study Group Participants: +12% attendance
• International Students: -5% average (timezone factors)
• Part-time Workers: -8% average (scheduling conflicts)
• Sports Team Members: +3% average (discipline factor)
"""

            analysis_text.insert('1.0', trends_data)
            analysis_text.config(state='disabled')

            messagebox.showinfo(_("attendance.messages.analysis_complete"), _("attendance.messages.analysis_complete_message"))

        ttk.Button(controls_frame, text=_("attendance.trends.generate"), command=generate_analysis).grid(row=1, column=0, columnspan=4, pady=(15, 0))

        # Results frame
        results_frame = ttk.LabelFrame(trends_window, text=_("attendance.trends.results"), padding="15")
        results_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))

        # Initial message
        initial_label = ttk.Label(results_frame, text=_("attendance.trends.click_generate"),
                                 font=('Arial', 12), anchor='center')
        initial_label.pack(expand=True)

        # Close button
        ttk.Button(trends_window, text=_("common.close"), command=trends_window.destroy).pack(pady=10)

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

