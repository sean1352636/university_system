from ._imports import (
    _, datetime, filedialog, messagebox, simpledialog, tk, ttk,
    Toplevel, ScrolledText, sqlite3, DEFAULT_DB_PATH,
    send_email, EMAIL_AVAILABLE,
)


class AnalyticsMixin:
    """Analytics generation, enrollment reports, and department statistics."""

    def generate_analytics(self):
        """Generate and display course analytics"""
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                analytics_text = "COURSE ANALYTICS DASHBOARD\n"
                analytics_text += "=" * 50 + "\n\n"

                # Overall statistics (using case-insensitive status check)
                cursor.execute("""
                SELECT
                    COUNT(*) as total_courses,
                    SUM(COALESCE(current_enrollment, 0)) as total_students,
                    SUM(COALESCE(max_enrollment, 0)) as total_capacity,
                    AVG(COALESCE(current_enrollment, 0)) as avg_enrollment
                FROM courses
                WHERE LOWER(COALESCE(status, 'active')) = 'active'
                """)

                stats = cursor.fetchone()
                if stats:
                    analytics_text += "OVERALL STATISTICS:\n"
                    analytics_text += f"Total Active Courses: {stats[0] or 0}\n"
                    analytics_text += f"Total Students Enrolled: {stats[1] or 0}\n"
                    analytics_text += f"Total System Capacity: {stats[2] or 0}\n"
                    avg_enrollment = stats[3] if stats[3] is not None else 0.0
                    analytics_text += f"Average Enrollment per Course: {avg_enrollment:.1f}\n"
                    if stats[2] and stats[2] > 0:
                        fill_rate = (stats[1] / stats[2]) * 100
                        analytics_text += f"System Fill Rate: {fill_rate:.1f}%\n"
                    available = (stats[2] or 0) - (stats[1] or 0)
                    analytics_text += f"Available Spots: {available}\n\n"

                # Department breakdown
                cursor.execute("""
                SELECT
                    COALESCE(department, 'Unknown') as dept,
                    COUNT(*) as course_count,
                    SUM(COALESCE(current_enrollment, 0)) as total_students
                FROM courses
                WHERE LOWER(COALESCE(status, 'active')) = 'active'
                GROUP BY department
                ORDER BY total_students DESC
                """)

                dept_stats = cursor.fetchall()
                if dept_stats:
                    analytics_text += "COURSES BY DEPARTMENT:\n"
                    analytics_text += f"{'Department':<20} {'Courses':<10} {'Students':<10}\n"
                    analytics_text += "-" * 40 + "\n"
                    for dept, courses, students in dept_stats:
                        analytics_text += f"{dept:<20} {courses:<10} {students:<10}\n"
                    analytics_text += "\n"

                # Most popular courses
                cursor.execute("""
                SELECT course_code, course_name, COALESCE(current_enrollment, 0) as enrolled
                FROM courses
                WHERE LOWER(COALESCE(status, 'active')) = 'active'
                ORDER BY enrolled DESC
                LIMIT 10
                """)

                popular = cursor.fetchall()
                if popular:
                    analytics_text += "MOST POPULAR COURSES (Top 10):\n"
                    analytics_text += f"{'Code':<10} {'Name':<30} {'Enrolled':<10}\n"
                    analytics_text += "-" * 50 + "\n"
                    for code, name, enrolled in popular:
                        code = code or "N/A"
                        name = name or "N/A"
                        enrolled = enrolled or 0
                        name_short = name[:27] + "..." if len(name) > 30 else name
                        analytics_text += f"{code:<10} {name_short:<30} {enrolled:<10}\n"
                    analytics_text += "\n"

                # Courses with availability
                cursor.execute("""
                SELECT COUNT(*)
                FROM courses
                WHERE LOWER(COALESCE(status, 'active')) = 'active'
                  AND COALESCE(current_enrollment, 0) < COALESCE(max_enrollment, 0)
                """)
                available_count = cursor.fetchone()[0]
                analytics_text += f"COURSE AVAILABILITY:\n"
                analytics_text += f"Courses with Available Spots: {available_count}\n\n"

                # Status breakdown
                cursor.execute("SELECT status, COUNT(*) FROM courses GROUP BY status")
                status_data = cursor.fetchall()
                if status_data:
                    analytics_text += "COURSE STATUS BREAKDOWN:\n"
                    for status, count in status_data:
                        analytics_text += f"  {status}: {count}\n"

            # Display in analytics tab
            self.notebook.select(2)  # Analytics tab
            self.analytics_text.delete(1.0, tk.END)
            self.analytics_text.insert(1.0, analytics_text)

            self.update_status(_("course_management.status.analytics_generated"))

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), _("course_management.messages.failed_generate_analytics", error=str(e)))

    def open_analytics_window(self):
        """Open analytics/statistics in a new window with export and email options"""
        # Generate analytics data
        analytics_text = self._generate_analytics_text()

        if not analytics_text:
            return

        # Create new window
        window = tk.Toplevel(self.root)
        window.title(_("course_management.dialogs.course_analytics_report"))
        window.geometry("800x600")
        window.transient(self.root)

        # Main frame
        main_frame = ttk.Frame(window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(main_frame, text=_("course_management.dialogs.course_analytics_report"),
                               font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 10))

        # Analytics display
        text_widget = ScrolledText(main_frame, wrap=tk.WORD, height=30)
        text_widget.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        text_widget.insert(1.0, analytics_text)
        text_widget.config(state='disabled')

        # Store analytics text for later use
        window.analytics_content = analytics_text

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 5))

        # Export as TXT button
        def export_txt():
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"course_analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )
            if filename:
                try:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(analytics_text)
                        f.write(f"\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    messagebox.showinfo(_("course_management.success.success"), _("course_management.messages.report_saved", filename=filename))
                except Exception as e:
                    messagebox.showerror(_("course_management.success.error"), _("course_management.messages.failed_save_report", error=str(e)))

        ttk.Button(button_frame, text=_("course_management.buttons.export_as_txt"),
                  command=export_txt).pack(side=tk.LEFT, padx=5)

        # Email to Admin button
        def email_to_admin():
            try:
                # Get admin email from database
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Try to get admin email from users table
                cursor.execute("""
                    SELECT email FROM users
                    WHERE role IN ('admin', 'administrator', 'Admin', 'Administrator')
                    AND email IS NOT NULL AND email != ''
                    LIMIT 1
                """)
                result = cursor.fetchone()
                admin_email = result[0] if result else None
                conn.close()

                # If not found, prompt for it
                if not admin_email:
                    admin_email = tk.simpledialog.askstring(_("course_management.messages.admin_email"),
                        _("course_management.labels.admin_email_address"),
                        parent=window)

                if not admin_email:
                    return

                # Render email from template
                from education_system.university_system.infrastructure.email.template_utils import render_template

                subject, body = render_template('academics/course_analytics_report', {
                    'report_date': datetime.now().strftime('%Y-%m-%d'),
                    'analytics_content': analytics_text,
                    'generated_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })

                # Fallback if template not found
                if not subject or not body:
                    subject = f"Course Analytics Report - {datetime.now().strftime('%Y-%m-%d')}"
                    body = analytics_text + f"\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

                send_email(admin_email, subject, body)
                messagebox.showinfo(_("course_management.success.success"), _("course_management.messages.report_sent", admin_email=admin_email))

            except Exception as e:
                messagebox.showerror(_("course_management.success.error"), _("course_management.messages.failed_send_email", error=str(e)))

        ttk.Button(button_frame, text=_("course_management.buttons.email_to_admin"),
                  command=email_to_admin).pack(side=tk.LEFT, padx=5)

        # Close button
        ttk.Button(button_frame, text=_("common.close"),
                  command=window.destroy).pack(side=tk.RIGHT, padx=5)

    def _generate_analytics_text(self):
        """Generate analytics text content (extracted for reuse)"""
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                analytics_text = "COURSE ANALYTICS DASHBOARD\n"
                analytics_text += "=" * 50 + "\n\n"

                # Overall statistics
                cursor.execute("""
                SELECT
                    COUNT(*) as total_courses,
                    SUM(COALESCE(current_enrollment, 0)) as total_students,
                    SUM(COALESCE(max_enrollment, 0)) as total_capacity,
                    AVG(COALESCE(current_enrollment, 0)) as avg_enrollment
                FROM courses
                WHERE LOWER(COALESCE(status, 'active')) = 'active'
                """)

                stats = cursor.fetchone()
                if stats:
                    analytics_text += "OVERALL STATISTICS:\n"
                    analytics_text += f"Total Active Courses: {stats[0] or 0}\n"
                    analytics_text += f"Total Students Enrolled: {stats[1] or 0}\n"
                    analytics_text += f"Total System Capacity: {stats[2] or 0}\n"
                    avg_enrollment = stats[3] if stats[3] is not None else 0.0
                    analytics_text += f"Average Enrollment per Course: {avg_enrollment:.1f}\n"
                    if stats[2] and stats[2] > 0:
                        fill_rate = (stats[1] / stats[2]) * 100
                        analytics_text += f"System Fill Rate: {fill_rate:.1f}%\n"
                    available = (stats[2] or 0) - (stats[1] or 0)
                    analytics_text += f"Available Spots: {available}\n\n"

                # Department breakdown
                cursor.execute("""
                SELECT
                    COALESCE(department, 'Unknown') as dept,
                    COUNT(*) as course_count,
                    SUM(COALESCE(current_enrollment, 0)) as total_students
                FROM courses
                WHERE LOWER(COALESCE(status, 'active')) = 'active'
                GROUP BY department
                ORDER BY total_students DESC
                """)

                dept_stats = cursor.fetchall()
                if dept_stats:
                    analytics_text += "COURSES BY DEPARTMENT:\n"
                    analytics_text += f"{'Department':<20} {'Courses':<10} {'Students':<10}\n"
                    analytics_text += "-" * 40 + "\n"
                    for dept, courses, students in dept_stats:
                        analytics_text += f"{dept:<20} {courses:<10} {students:<10}\n"
                    analytics_text += "\n"

                # Most popular courses
                cursor.execute("""
                SELECT course_code, course_name, COALESCE(current_enrollment, 0) as enrolled
                FROM courses
                WHERE LOWER(COALESCE(status, 'active')) = 'active'
                ORDER BY enrolled DESC
                LIMIT 10
                """)

                popular = cursor.fetchall()
                if popular:
                    analytics_text += "MOST POPULAR COURSES (Top 10):\n"
                    analytics_text += f"{'Code':<10} {'Name':<30} {'Enrolled':<10}\n"
                    analytics_text += "-" * 50 + "\n"
                    for code, name, enrolled in popular:
                        code = code or "N/A"
                        name = name or "N/A"
                        enrolled = enrolled or 0
                        name_short = name[:27] + "..." if len(name) > 30 else name
                        analytics_text += f"{code:<10} {name_short:<30} {enrolled:<10}\n"
                    analytics_text += "\n"

                # Courses with availability
                cursor.execute("""
                SELECT COUNT(*)
                FROM courses
                WHERE LOWER(COALESCE(status, 'active')) = 'active'
                  AND COALESCE(current_enrollment, 0) < COALESCE(max_enrollment, 0)
                """)
                available_count = cursor.fetchone()[0]
                analytics_text += f"COURSE AVAILABILITY:\n"
                analytics_text += f"Courses with Available Spots: {available_count}\n\n"

                # Status breakdown
                cursor.execute("SELECT status, COUNT(*) FROM courses GROUP BY status")
                status_data = cursor.fetchall()
                if status_data:
                    analytics_text += "COURSE STATUS BREAKDOWN:\n"
                    for status, count in status_data:
                        analytics_text += f"  {status}: {count}\n"

                return analytics_text

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to generate analytics: {e}")
            return None

    def show_enrollment_report(self):
        """Show enrollment report dialog"""
        dialog = EnrollmentReportDialog(self.root)
        if dialog.result:
            # Generate selected report type and open in new window
            report_type = dialog.result
            self.open_enrollment_report_window(report_type)

    def generate_enrollment_report(self, report_type):
        """Generate specific enrollment report"""
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                report_text = f"ENROLLMENT REPORT - {report_type.upper()}\n"
                report_text += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                report_text += "=" * 60 + "\n\n"

                if report_type == "Summary":
                    cursor.execute("""
                    SELECT
                        COUNT(*) as total_courses,
                        SUM(COALESCE(current_enrollment, 0)) as total_enrolled,
                        SUM(COALESCE(max_enrollment, 0)) as total_capacity,
                        AVG(COALESCE(current_enrollment, 0)) as avg_enrollment
                    FROM courses
                    WHERE status = 'Active'
                    """)

                    summary = cursor.fetchone()
                    report_text += f"Total Active Courses: {summary[0]}\n"
                    report_text += f"Total Students Enrolled: {summary[1]}\n"
                    report_text += f"Total System Capacity: {summary[2]}\n"
                    report_text += f"Average Enrollment per Course: {summary[3]:.1f}\n"
                    if summary[2] > 0:
                        report_text += f"System Fill Rate: {(summary[1]/summary[2]*100):.1f}%\n"
                    report_text += f"Available Spots: {summary[2] - summary[1]}\n"

                elif report_type == "Department":
                    cursor.execute("""
                    SELECT
                        COALESCE(department, 'Unknown') as dept,
                        COUNT(*) as course_count,
                        SUM(COALESCE(current_enrollment, 0)) as total_students,
                        SUM(COALESCE(max_enrollment, 0)) as total_capacity
                    FROM courses
                    WHERE status = 'Active'
                    GROUP BY department
                    ORDER BY total_students DESC
                    """)

                    dept_data = cursor.fetchall()
                    report_text += f"{'Department':<20} {'Courses':<10} {'Students':<10} {'Capacity':<10} {'Fill Rate':<10}\n"
                    report_text += "-" * 60 + "\n"

                    for dept, courses, students, capacity in dept_data:
                        fill_rate = f"{(students/capacity*100):.1f}%" if capacity > 0 else "N/A"
                        report_text += f"{dept:<20} {courses:<10} {students:<10} {capacity:<10} {fill_rate:<10}\n"

                elif report_type == "Detailed":
                    cursor.execute("""
                    SELECT course_code, course_name, department, level,
                           COALESCE(current_enrollment, 0), COALESCE(max_enrollment, 0),
                           course_type, credit_hours
                    FROM courses
                    WHERE status = 'Active'
                    ORDER BY current_enrollment DESC
                    """)

                    course_data = cursor.fetchall()
                    report_text += f"{'Code':<8} {'Name':<25} {'Dept':<12} {'Level':<12} {'Enrolled':<10} {'Fill Rate':<10}\n"
                    report_text += "-" * 77 + "\n"

                    for course in course_data:
                        code, name, dept, level, enrolled, capacity = course[:6]
                        name_short = name[:22] + "..." if len(name) > 25 else name
                        dept_short = dept[:9] + "..." if dept and len(dept) > 12 else dept or "N/A"
                        level_short = level[:9] + "..." if level and len(level) > 12 else level or "N/A"
                        fill_rate = f"{(enrolled/capacity*100):.1f}%" if capacity > 0 else "N/A"
                        enrollment_str = f"{enrolled}/{capacity}"

                        report_text += f"{code:<8} {name_short:<25} {dept_short:<12} {level_short:<12} {enrollment_str:<10} {fill_rate:<10}\n"

                elif report_type == "Capacity":
                    cursor.execute("""
                    SELECT course_code, course_name, department,
                           COALESCE(current_enrollment, 0) as enrolled,
                           COALESCE(max_enrollment, 0) as capacity,
                           COALESCE(max_enrollment, 0) - COALESCE(current_enrollment, 0) as available
                    FROM courses
                    WHERE status = 'Active'
                    ORDER BY available DESC
                    """)

                    capacity_data = cursor.fetchall()
                    report_text += f"{'Code':<8} {'Name':<30} {'Department':<15} {'Enrolled':<10} {'Capacity':<10} {'Available':<10}\n"
                    report_text += "-" * 83 + "\n"

                    for code, name, dept, enrolled, capacity, available in capacity_data:
                        name_short = name[:27] + "..." if len(name) > 30 else name
                        dept_short = dept[:12] + "..." if dept and len(dept) > 15 else dept or "N/A"
                        report_text += f"{code:<8} {name_short:<30} {dept_short:<15} {enrolled:<10} {capacity:<10} {available:<10}\n"

            # Store report data for visualization and email
            self.last_report_data = {
                'type': report_type,
                'text': report_text,
                'conn': conn
            }

            # Display report in analytics tab
            self.notebook.select(2)  # Analytics tab
            self.analytics_text.delete(1.0, tk.END)
            self.analytics_text.insert(1.0, report_text)

            # Add visualization and email buttons (create if they don't exist)
            if not hasattr(self, 'report_action_frame'):
                self.report_action_frame = ttk.Frame(self.analytics_frame)
                self.report_action_frame.pack(fill=tk.X, pady=5)

                ttk.Button(self.report_action_frame, text=_("course_management.buttons.visualize_report"),
                          command=self.visualize_report).pack(side=tk.LEFT, padx=5)
                ttk.Button(self.report_action_frame, text=_("course_management.buttons.email_report_to_admin"),
                          command=self.email_report).pack(side=tk.LEFT, padx=5)

            self.update_status(_("course_management.status.report_generated"))

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), _("course_management.messages.failed_generate_analytics", error=str(e)))

    def open_enrollment_report_window(self, report_type):
        """Open enrollment report in a new window with export and email options"""
        # Generate report text
        report_text = self._generate_enrollment_report_text(report_type)

        if not report_text:
            return

        # Create new window
        window = tk.Toplevel(self.root)
        window.title(_("course_management.dialogs.enrollment_report_type", type=report_type))
        window.geometry("900x600")
        window.transient(self.root)

        # Main frame
        main_frame = ttk.Frame(window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(main_frame, text=_("course_management.dialogs.enrollment_report_type", type=report_type),
                               font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 10))

        # Report display
        text_widget = ScrolledText(main_frame, wrap=tk.WORD, height=30)
        text_widget.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        text_widget.insert(1.0, report_text)
        text_widget.config(state='disabled')

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 5))

        # Export as TXT button
        def export_txt():
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"enrollment_report_{report_type.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )
            if filename:
                try:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(report_text)
                    messagebox.showinfo(_("course_management.success.success"), _("course_management.messages.report_saved", filename=filename))
                except Exception as e:
                    messagebox.showerror(_("course_management.success.error"), _("course_management.messages.failed_save_report", error=str(e)))

        ttk.Button(button_frame, text=_("course_management.buttons.export_as_txt"),
                  command=export_txt).pack(side=tk.LEFT, padx=5)

        # Email to Admin button
        def email_to_admin():
            try:
                # Get admin email from database
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Try to get admin email from users table
                cursor.execute("""
                    SELECT email FROM users
                    WHERE role IN ('admin', 'administrator', 'Admin', 'Administrator')
                    AND email IS NOT NULL AND email != ''
                    LIMIT 1
                """)
                result = cursor.fetchone()
                admin_email = result[0] if result else None
                conn.close()

                # If not found, prompt for it
                if not admin_email:
                    admin_email = tk.simpledialog.askstring(_("course_management.messages.admin_email"),
                        _("course_management.labels.admin_email_address"),
                        parent=window)

                if not admin_email:
                    return

                # Render email from template
                from education_system.university_system.infrastructure.email.template_utils import render_template

                subject, body = render_template('academics/enrollment_report', {
                    'report_type': report_type,
                    'report_date': datetime.now().strftime('%Y-%m-%d'),
                    'report_content': report_text
                })

                # Fallback if template not found
                if not subject or not body:
                    subject = f"Enrollment Report - {report_type} - {datetime.now().strftime('%Y-%m-%d')}"
                    body = report_text

                send_email(admin_email, subject, body)
                messagebox.showinfo(_("course_management.success.success"), _("course_management.messages.report_sent", admin_email=admin_email))

            except Exception as e:
                messagebox.showerror(_("course_management.success.error"), _("course_management.messages.failed_send_email", error=str(e)))

        ttk.Button(button_frame, text=_("course_management.buttons.email_to_admin"),
                  command=email_to_admin).pack(side=tk.LEFT, padx=5)

        # Close button
        ttk.Button(button_frame, text=_("common.close"),
                  command=window.destroy).pack(side=tk.RIGHT, padx=5)

    def _generate_enrollment_report_text(self, report_type):
        """Generate enrollment report text (extracted for reuse)"""
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                report_text = f"ENROLLMENT REPORT - {report_type.upper()}\n"
                report_text += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                report_text += "=" * 60 + "\n\n"

                if report_type == "Summary":
                    cursor.execute("""
                    SELECT
                        COUNT(*) as total_courses,
                        SUM(COALESCE(current_enrollment, 0)) as total_enrolled,
                        SUM(COALESCE(max_enrollment, 0)) as total_capacity,
                        AVG(COALESCE(current_enrollment, 0)) as avg_enrollment
                    FROM courses
                    WHERE LOWER(COALESCE(status, 'active')) = 'active'
                    """)

                    summary = cursor.fetchone()
                    report_text += f"Total Active Courses: {summary[0] or 0}\n"
                    report_text += f"Total Students Enrolled: {summary[1] or 0}\n"
                    report_text += f"Total System Capacity: {summary[2] or 0}\n"
                    avg_enrollment = summary[3] if summary[3] is not None else 0.0
                    report_text += f"Average Enrollment per Course: {avg_enrollment:.1f}\n"
                    if summary[2] and summary[2] > 0:
                        report_text += f"System Fill Rate: {(summary[1]/summary[2]*100):.1f}%\n"
                    available = (summary[2] or 0) - (summary[1] or 0)
                    report_text += f"Available Spots: {available}\n"

                elif report_type == "Department":
                    cursor.execute("""
                    SELECT
                        COALESCE(department, 'Unknown') as dept,
                        COUNT(*) as course_count,
                        SUM(COALESCE(current_enrollment, 0)) as total_students,
                        SUM(COALESCE(max_enrollment, 0)) as total_capacity
                    FROM courses
                    WHERE LOWER(COALESCE(status, 'active')) = 'active'
                    GROUP BY department
                    ORDER BY total_students DESC
                    """)

                    dept_data = cursor.fetchall()
                    report_text += f"{'Department':<20} {'Courses':<10} {'Students':<10} {'Capacity':<10} {'Fill Rate':<10}\n"
                    report_text += "-" * 60 + "\n"

                    for dept, courses, students, capacity in dept_data:
                        fill_rate = f"{(students/capacity*100):.1f}%" if capacity > 0 else "N/A"
                        report_text += f"{dept:<20} {courses:<10} {students:<10} {capacity:<10} {fill_rate:<10}\n"

                elif report_type == "Detailed":
                    cursor.execute("""
                    SELECT course_code, course_name, department, level,
                           COALESCE(current_enrollment, 0), COALESCE(max_enrollment, 0)
                    FROM courses
                    WHERE LOWER(COALESCE(status, 'active')) = 'active'
                    ORDER BY current_enrollment DESC
                    """)

                    course_data = cursor.fetchall()
                    report_text += f"{'Code':<8} {'Name':<25} {'Dept':<12} {'Level':<12} {'Enrolled':<10} {'Fill Rate':<10}\n"
                    report_text += "-" * 77 + "\n"

                    for code, name, dept, level, enrolled, capacity in course_data:
                        name_short = name[:22] + "..." if len(name) > 25 else name
                        dept_short = dept[:9] + "..." if dept and len(dept) > 12 else dept or "N/A"
                        level_short = level[:9] + "..." if level and len(level) > 12 else level or "N/A"
                        fill_rate = f"{(enrolled/capacity*100):.1f}%" if capacity > 0 else "N/A"
                        enrollment_str = f"{enrolled}/{capacity}"

                        report_text += f"{code:<8} {name_short:<25} {dept_short:<12} {level_short:<12} {enrollment_str:<10} {fill_rate:<10}\n"

                elif report_type == "Capacity":
                    cursor.execute("""
                    SELECT course_code, course_name, department,
                           COALESCE(current_enrollment, 0) as enrolled,
                           COALESCE(max_enrollment, 0) as capacity,
                           COALESCE(max_enrollment, 0) - COALESCE(current_enrollment, 0) as available
                    FROM courses
                    WHERE LOWER(COALESCE(status, 'active')) = 'active'
                    ORDER BY available DESC
                    """)

                    capacity_data = cursor.fetchall()
                    report_text += f"{'Code':<8} {'Name':<30} {'Department':<15} {'Enrolled':<10} {'Capacity':<10} {'Available':<10}\n"
                    report_text += "-" * 83 + "\n"

                    for code, name, dept, enrolled, capacity, available in capacity_data:
                        name_short = name[:27] + "..." if len(name) > 30 else name
                        dept_short = dept[:12] + "..." if dept and len(dept) > 15 else dept or "N/A"
                        report_text += f"{code:<8} {name_short:<30} {dept_short:<15} {enrolled:<10} {capacity:<10} {available:<10}\n"

                return report_text

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), _("course_management.messages.failed_generate_analytics", error=str(e)))
            return None

    def show_department_stats(self):
        """Show department statistics dialog with enhanced GUI display"""
        try:
            # Create department stats window
            stats_window = tk.Toplevel(self.root)
            stats_window.title(_("course_management.dialogs.department_stats"))
            stats_window.geometry("800x600")
            stats_window.transient(self.root)

            main_frame = ttk.Frame(stats_window)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Department selection
            selection_frame = ttk.Frame(main_frame)
            selection_frame.pack(fill=tk.X, pady=5)

            ttk.Label(selection_frame, text=_("course_management.labels.department_colon")).pack(side=tk.LEFT)
            dept_var = tk.StringVar()

            # Get departments list
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT COALESCE(department, 'Unknown') as dept FROM courses ORDER BY dept")
                departments = ["All Departments"] + [row[0] for row in cursor.fetchall()]

            dept_combo = ttk.Combobox(selection_frame, textvariable=dept_var, values=departments)
            dept_combo.pack(side=tk.LEFT, padx=5)
            dept_combo.set("All Departments")

            # Statistics display
            stats_text = ScrolledText(main_frame, wrap=tk.WORD)
            stats_text.pack(fill=tk.BOTH, expand=True, pady=5)

            def update_stats():
                selected_dept = dept_var.get()
                stats_text.delete(1.0, tk.END)

                with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                    cursor = conn.cursor()

                    if selected_dept == "All Departments":
                        # All departments overview
                        cursor.execute("""
                        SELECT
                            COALESCE(department, 'Unknown') as dept,
                            COUNT(*) as course_count,
                            SUM(COALESCE(current_enrollment, 0)) as total_students,
                            SUM(COALESCE(max_enrollment, 0)) as total_capacity,
                            COUNT(CASE WHEN status = 'Active' THEN 1 END) as active_courses
                        FROM courses
                        GROUP BY department
                        ORDER BY total_students DESC
                        """)

                        all_dept_stats = cursor.fetchall()
                        stats_text.insert(tk.END, "ALL DEPARTMENTS OVERVIEW\n")
                        stats_text.insert(tk.END, "=" * 50 + "\n\n")
                        stats_text.insert(tk.END, f"{'Department':<20} {'Courses':<10} {'Active':<8} {'Students':<10} {'Capacity':<10} {'Fill Rate':<10}\n")
                        stats_text.insert(tk.END, "-" * 68 + "\n")

                        for dept_stat in all_dept_stats:
                            dept, courses, students, capacity, active = dept_stat
                            fill_rate = f"{(students/capacity*100):.1f}%" if capacity > 0 else "N/A"
                            stats_text.insert(tk.END, f"{dept:<20} {courses:<10} {active:<8} {students:<10} {capacity:<10} {fill_rate:<10}\n")
                    else:
                        # Single department stats
                        cursor.execute("""
                        SELECT
                            COUNT(*) as total_courses,
                            SUM(COALESCE(current_enrollment, 0)) as total_students,
                            SUM(COALESCE(max_enrollment, 0)) as total_capacity,
                            AVG(COALESCE(current_enrollment, 0)) as avg_enrollment,
                            AVG(credit_hours) as avg_credits,
                            COUNT(CASE WHEN status = 'Active' THEN 1 END) as active_courses
                        FROM courses
                        WHERE department = ?
                        """, (selected_dept,))

                        stats = cursor.fetchone()

                        stats_text.insert(tk.END, f"STATISTICS FOR {selected_dept.upper()} DEPARTMENT\n")
                        stats_text.insert(tk.END, "=" * 60 + "\n\n")
                        stats_text.insert(tk.END, f"Total Courses: {stats[0]}\n")
                        stats_text.insert(tk.END, f"Active Courses: {stats[5]}\n")
                        stats_text.insert(tk.END, f"Total Students: {stats[1]}\n")
                        stats_text.insert(tk.END, f"Total Capacity: {stats[2]}\n")
                        stats_text.insert(tk.END, f"Average Enrollment: {stats[3]:.1f}\n")
                        stats_text.insert(tk.END, f"Average Credit Hours: {stats[4]:.1f}\n")
                        if stats[2] > 0:
                            stats_text.insert(tk.END, f"Department Fill Rate: {(stats[1]/stats[2]*100):.1f}%\n")

            ttk.Button(selection_frame, text=_("course_management.buttons.update"), command=update_stats).pack(side=tk.LEFT, padx=5)

            # Export and email buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X, pady=10)

            def export_stats_txt():
                selected_dept = dept_var.get()
                filename = filedialog.asksaveasfilename(
                    defaultextension=".txt",
                    filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                    initialfile=f"dept_stats_{selected_dept.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                )
                if filename:
                    try:
                        stats_content = stats_text.get(1.0, tk.END)
                        with open(filename, 'w', encoding='utf-8') as f:
                            f.write(stats_content)
                            f.write(f"\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        messagebox.showinfo(_("course_management.success.success"), _("course_management.messages.statistics_saved_to", filename=filename))
                    except Exception as e:
                        messagebox.showerror(_("course_management.success.error"), _("course_management.messages.failed_save_statistics", error=str(e)))

            def email_stats_to_admin():
                try:
                    # Get admin email from database
                    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT email FROM users
                        WHERE role IN ('admin', 'administrator', 'Admin', 'Administrator')
                        AND email IS NOT NULL AND email != ''
                        LIMIT 1
                    """)
                    result = cursor.fetchone()
                    admin_email = result[0] if result else None
                    conn.close()

                    # If not found, prompt for it
                    if not admin_email:
                        admin_email = tk.simpledialog.askstring("Admin Email",
                            "Enter admin email address:",
                            parent=stats_window)

                    if not admin_email:
                        return

                    # Render email from template
                    from education_system.university_system.infrastructure.email.template_utils import render_template

                    selected_dept = dept_var.get()
                    stats_content = stats_text.get(1.0, tk.END)

                    subject, body = render_template('academics/department_statistics', {
                        'department_name': selected_dept,
                        'report_date': datetime.now().strftime('%Y-%m-%d'),
                        'statistics_content': stats_content,
                        'generated_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })

                    # Fallback if template not found
                    if not subject or not body:
                        subject = f"Department Statistics - {selected_dept} - {datetime.now().strftime('%Y-%m-%d')}"
                        body = stats_content + f"\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

                    send_email(admin_email, subject, body)
                    messagebox.showinfo(_("course_management.success.success"), _("course_management.messages.statistics_sent_to", admin_email=admin_email))

                except Exception as e:
                    messagebox.showerror(_("course_management.success.error"), _("course_management.messages.failed_send_email", error=str(e)))

            ttk.Button(button_frame, text=_("course_management.buttons.export_as_txt"),
                      command=export_stats_txt).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text=_("course_management.buttons.email_to_admin"),
                      command=email_stats_to_admin).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text=_("common.close"),
                      command=stats_window.destroy).pack(side=tk.RIGHT, padx=5)

            # Initial load
            update_stats()

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), _("course_management.messages.failed_generate_analytics", error=str(e)))
