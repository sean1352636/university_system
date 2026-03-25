from education_system.university_system.modules.domain.academics.gui.course_management_gui.core._imports import (
    _, datetime, filedialog, messagebox, simpledialog, tk, ttk,
    Toplevel, ScrolledText, sqlite3, DEFAULT_DB_PATH,
    send_email, EMAIL_AVAILABLE,
)

try:
    from education_system.university_system.modules.domain.academics.gui.course_management_gui.analytics.analytics import EnrollmentReportDialog
except ImportError:
    EnrollmentReportDialog = None


# Helper SQL fragments to avoid repetition
_COURSE_CODE = "COALESCE(c.course_code, c.code)"
_COURSE_NAME = "COALESCE(c.course_name, c.name)"
_VALID_COURSE = (
    f"WHERE {_COURSE_CODE} IS NOT NULL AND {_COURSE_NAME} IS NOT NULL"
    " AND COALESCE(c.course_type, '') = 'Degree Program'"
)
_ACTIVE_COURSE = (
    f"{_VALID_COURSE} AND LOWER(COALESCE(c.status, 'active')) = 'active'"
)
# Join enrollment via students.course matching the course code
_ENROLLMENT_JOIN = (
    "LEFT JOIN students s ON UPPER(s.course) = UPPER(COALESCE(c.course_code, c.code))"
)


def _enrollment_count(cursor):
    """Get total enrolled students across all degree-programme courses."""
    cursor.execute(
        "SELECT COUNT(*) FROM students s "
        "JOIN courses c ON UPPER(s.course) = UPPER(COALESCE(c.course_code, c.code)) "
        "WHERE COALESCE(c.course_type, '') = 'Degree Program'"
    )
    return cursor.fetchone()[0] or 0


class AnalyticsMixin:
    """Analytics generation, enrollment reports, and department statistics."""

    def generate_analytics(self):
        """Generate and display course analytics"""
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                analytics_text = "COURSE ANALYTICS DASHBOARD\n"
                analytics_text += "=" * 50 + "\n\n"

                # Overall statistics
                total_enrolled = _enrollment_count(cursor)
                cursor.execute(f"""
                SELECT
                    COUNT(*) as total_courses,
                    SUM(COALESCE(c.max_enrollment, 0)) as total_capacity
                FROM courses c
                {_ACTIVE_COURSE}
                """)

                stats = cursor.fetchone()
                if stats:
                    total_courses = stats[0] or 0
                    total_capacity = stats[1] or 0
                    avg_enrollment = total_enrolled / max(total_courses, 1)
                    analytics_text += "OVERALL STATISTICS:\n"
                    analytics_text += f"Total Active Courses: {total_courses}\n"
                    analytics_text += f"Total Students Enrolled: {total_enrolled}\n"
                    analytics_text += f"Total System Capacity: {total_capacity}\n"
                    analytics_text += f"Average Enrollment per Course: {avg_enrollment:.1f}\n"
                    if total_capacity > 0:
                        fill_rate = (total_enrolled / total_capacity) * 100
                        analytics_text += f"System Fill Rate: {fill_rate:.1f}%\n"
                    available = total_capacity - total_enrolled
                    analytics_text += f"Available Spots: {available}\n\n"

                # Department breakdown
                cursor.execute(f"""
                SELECT
                    COALESCE(c.department, 'Unknown') as dept,
                    COUNT(DISTINCT c.id) as course_count,
                    COUNT(DISTINCT s.student_id) as total_students
                FROM courses c
                {_ENROLLMENT_JOIN}
                {_ACTIVE_COURSE}
                GROUP BY c.department
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
                cursor.execute(f"""
                SELECT {_COURSE_CODE} as ccode, {_COURSE_NAME} as cname,
                       COUNT(s.student_id) as enrolled
                FROM courses c
                {_ENROLLMENT_JOIN}
                {_ACTIVE_COURSE}
                GROUP BY c.id
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
                cursor.execute(f"""
                SELECT COUNT(*)
                FROM courses c
                {_ACTIVE_COURSE}
                  AND COALESCE(c.max_enrollment, 0) > 0
                """)
                available_count = cursor.fetchone()[0]
                analytics_text += f"COURSE AVAILABILITY:\n"
                analytics_text += f"Courses with Available Spots: {available_count}\n\n"

                # Status breakdown
                cursor.execute(f"""
                SELECT c.status, COUNT(*) FROM courses c
                {_VALID_COURSE}
                GROUP BY c.status
                """)
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
        analytics_text = self._generate_analytics_text()

        if not analytics_text:
            return

        window = tk.Toplevel(self.root)
        window.title(_("course_management.dialogs.course_analytics_report"))
        window.geometry("800x600")
        window.transient(self.root)

        main_frame = ttk.Frame(window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(main_frame, text=_("course_management.dialogs.course_analytics_report"),
                               font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 10))

        text_widget = ScrolledText(main_frame, wrap=tk.WORD, height=30)
        text_widget.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        text_widget.insert(1.0, analytics_text)
        text_widget.config(state='disabled')

        window.analytics_content = analytics_text

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 5))

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

        def email_to_admin():
            try:
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

                if not admin_email:
                    admin_email = tk.simpledialog.askstring(_("course_management.messages.admin_email"),
                        _("course_management.labels.admin_email_address"),
                        parent=window)

                if not admin_email:
                    return

                from education_system.university_system.infrastructure.email.template_utils import render_template

                subject, body = render_template('academics/course_analytics_report', {
                    'report_date': datetime.now().strftime('%Y-%m-%d'),
                    'analytics_content': analytics_text,
                    'generated_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })

                if not subject or not body:
                    subject = f"Course Analytics Report - {datetime.now().strftime('%Y-%m-%d')}"
                    body = analytics_text + f"\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

                send_email(admin_email, subject, body)
                messagebox.showinfo(_("course_management.success.success"), _("course_management.messages.report_sent", admin_email=admin_email))

            except Exception as e:
                messagebox.showerror(_("course_management.success.error"), _("course_management.messages.failed_send_email", error=str(e)))

        ttk.Button(button_frame, text=_("course_management.buttons.email_to_admin"),
                  command=email_to_admin).pack(side=tk.LEFT, padx=5)

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
                total_enrolled = _enrollment_count(cursor)
                cursor.execute(f"""
                SELECT
                    COUNT(*) as total_courses,
                    SUM(COALESCE(c.max_enrollment, 0)) as total_capacity
                FROM courses c
                {_ACTIVE_COURSE}
                """)

                stats = cursor.fetchone()
                if stats:
                    total_courses = stats[0] or 0
                    total_capacity = stats[1] or 0
                    avg_enrollment = total_enrolled / max(total_courses, 1)
                    analytics_text += "OVERALL STATISTICS:\n"
                    analytics_text += f"Total Active Courses: {total_courses}\n"
                    analytics_text += f"Total Students Enrolled: {total_enrolled}\n"
                    analytics_text += f"Total System Capacity: {total_capacity}\n"
                    analytics_text += f"Average Enrollment per Course: {avg_enrollment:.1f}\n"
                    if total_capacity > 0:
                        fill_rate = (total_enrolled / total_capacity) * 100
                        analytics_text += f"System Fill Rate: {fill_rate:.1f}%\n"
                    available = total_capacity - total_enrolled
                    analytics_text += f"Available Spots: {available}\n\n"

                # Department breakdown
                cursor.execute(f"""
                SELECT
                    COALESCE(c.department, 'Unknown') as dept,
                    COUNT(DISTINCT c.id) as course_count,
                    COUNT(DISTINCT s.student_id) as total_students
                FROM courses c
                {_ENROLLMENT_JOIN}
                {_ACTIVE_COURSE}
                GROUP BY c.department
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
                cursor.execute(f"""
                SELECT {_COURSE_CODE} as ccode, {_COURSE_NAME} as cname,
                       COUNT(s.student_id) as enrolled
                FROM courses c
                {_ENROLLMENT_JOIN}
                {_ACTIVE_COURSE}
                GROUP BY c.id
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
                cursor.execute(f"""
                SELECT COUNT(*)
                FROM courses c
                {_ACTIVE_COURSE}
                  AND COALESCE(c.max_enrollment, 0) > 0
                """)
                available_count = cursor.fetchone()[0]
                analytics_text += f"COURSE AVAILABILITY:\n"
                analytics_text += f"Courses with Available Spots: {available_count}\n\n"

                # Status breakdown
                cursor.execute(f"""
                SELECT c.status, COUNT(*) FROM courses c
                {_VALID_COURSE}
                GROUP BY c.status
                """)
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
                    total_enrolled = _enrollment_count(cursor)
                    cursor.execute(f"""
                    SELECT COUNT(*) as total_courses,
                           SUM(COALESCE(c.max_enrollment, 0)) as total_capacity
                    FROM courses c
                    {_ACTIVE_COURSE}
                    """)
                    summary = cursor.fetchone()
                    total_courses = summary[0] or 0
                    total_capacity = summary[1] or 0
                    avg = total_enrolled / max(total_courses, 1)
                    report_text += f"Total Active Courses: {total_courses}\n"
                    report_text += f"Total Students Enrolled: {total_enrolled}\n"
                    report_text += f"Total System Capacity: {total_capacity}\n"
                    report_text += f"Average Enrollment per Course: {avg:.1f}\n"
                    if total_capacity > 0:
                        report_text += f"System Fill Rate: {(total_enrolled/total_capacity*100):.1f}%\n"
                    report_text += f"Available Spots: {total_capacity - total_enrolled}\n"

                elif report_type == "Department":
                    cursor.execute(f"""
                    SELECT
                        COALESCE(c.department, 'Unknown') as dept,
                        COUNT(DISTINCT c.id) as course_count,
                        COUNT(DISTINCT s.student_id) as total_students,
                        SUM(COALESCE(c.max_enrollment, 0)) as total_capacity
                    FROM courses c
                    {_ENROLLMENT_JOIN}
                    {_ACTIVE_COURSE}
                    GROUP BY c.department
                    ORDER BY total_students DESC
                    """)

                    dept_data = cursor.fetchall()
                    report_text += f"{'Department':<20} {'Courses':<10} {'Students':<10} {'Capacity':<10} {'Fill Rate':<10}\n"
                    report_text += "-" * 60 + "\n"

                    for dept, courses, students, capacity in dept_data:
                        fill_rate = f"{(students/capacity*100):.1f}%" if capacity > 0 else "N/A"
                        report_text += f"{dept:<20} {courses:<10} {students:<10} {capacity:<10} {fill_rate:<10}\n"

                elif report_type == "Detailed":
                    cursor.execute(f"""
                    SELECT {_COURSE_CODE}, {_COURSE_NAME}, c.department, c.level,
                           COUNT(s.student_id) as enrolled, COALESCE(c.max_enrollment, 0) as capacity
                    FROM courses c
                    {_ENROLLMENT_JOIN}
                    {_ACTIVE_COURSE}
                    GROUP BY c.id
                    ORDER BY enrolled DESC
                    """)

                    course_data = cursor.fetchall()
                    report_text += f"{'Code':<8} {'Name':<25} {'Dept':<12} {'Level':<12} {'Enrolled':<10} {'Fill Rate':<10}\n"
                    report_text += "-" * 77 + "\n"

                    for code, name, dept, level, enrolled, capacity in course_data:
                        code = code or "N/A"
                        name = name or "N/A"
                        name_short = name[:22] + "..." if len(name) > 25 else name
                        dept_short = dept[:9] + "..." if dept and len(dept) > 12 else dept or "N/A"
                        level_short = level[:9] + "..." if level and len(level) > 12 else level or "N/A"
                        fill_rate = f"{(enrolled/capacity*100):.1f}%" if capacity > 0 else "N/A"
                        enrollment_str = f"{enrolled}/{capacity}"

                        report_text += f"{code:<8} {name_short:<25} {dept_short:<12} {level_short:<12} {enrollment_str:<10} {fill_rate:<10}\n"

                elif report_type == "Capacity":
                    cursor.execute(f"""
                    SELECT {_COURSE_CODE}, {_COURSE_NAME}, c.department,
                           COUNT(s.student_id) as enrolled,
                           COALESCE(c.max_enrollment, 0) as capacity
                    FROM courses c
                    {_ENROLLMENT_JOIN}
                    {_ACTIVE_COURSE}
                    GROUP BY c.id
                    ORDER BY (COALESCE(c.max_enrollment, 0) - COUNT(s.student_id)) DESC
                    """)

                    capacity_data = cursor.fetchall()
                    report_text += f"{'Code':<8} {'Name':<30} {'Department':<15} {'Enrolled':<10} {'Capacity':<10} {'Available':<10}\n"
                    report_text += "-" * 83 + "\n"

                    for code, name, dept, enrolled, capacity in capacity_data:
                        code = code or "N/A"
                        name = name or "N/A"
                        available = capacity - enrolled
                        name_short = name[:27] + "..." if len(name) > 30 else name
                        dept_short = dept[:12] + "..." if dept and len(dept) > 15 else dept or "N/A"
                        report_text += f"{code:<8} {name_short:<30} {dept_short:<15} {enrolled:<10} {capacity:<10} {available:<10}\n"

            self.last_report_data = {
                'type': report_type,
                'text': report_text,
            }

            # Display report in analytics tab
            self.notebook.select(2)  # Analytics tab
            self.analytics_text.delete(1.0, tk.END)
            self.analytics_text.insert(1.0, report_text)

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
        report_text = self._generate_enrollment_report_text(report_type)

        if not report_text:
            return

        window = tk.Toplevel(self.root)
        window.title(_("course_management.dialogs.enrollment_report_type", type=report_type))
        window.geometry("900x600")
        window.transient(self.root)

        main_frame = ttk.Frame(window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(main_frame, text=_("course_management.dialogs.enrollment_report_type", type=report_type),
                               font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 10))

        text_widget = ScrolledText(main_frame, wrap=tk.WORD, height=30)
        text_widget.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        text_widget.insert(1.0, report_text)
        text_widget.config(state='disabled')

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 5))

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

        def email_to_admin():
            try:
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

                if not admin_email:
                    admin_email = tk.simpledialog.askstring(_("course_management.messages.admin_email"),
                        _("course_management.labels.admin_email_address"),
                        parent=window)

                if not admin_email:
                    return

                from education_system.university_system.infrastructure.email.template_utils import render_template

                subject, body = render_template('academics/enrollment_report', {
                    'report_type': report_type,
                    'report_date': datetime.now().strftime('%Y-%m-%d'),
                    'report_content': report_text
                })

                if not subject or not body:
                    subject = f"Enrollment Report - {report_type} - {datetime.now().strftime('%Y-%m-%d')}"
                    body = report_text

                send_email(admin_email, subject, body)
                messagebox.showinfo(_("course_management.success.success"), _("course_management.messages.report_sent", admin_email=admin_email))

            except Exception as e:
                messagebox.showerror(_("course_management.success.error"), _("course_management.messages.failed_send_email", error=str(e)))

        ttk.Button(button_frame, text=_("course_management.buttons.email_to_admin"),
                  command=email_to_admin).pack(side=tk.LEFT, padx=5)

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
                    total_enrolled = _enrollment_count(cursor)
                    cursor.execute(f"""
                    SELECT COUNT(*) as total_courses,
                           SUM(COALESCE(c.max_enrollment, 0)) as total_capacity
                    FROM courses c
                    {_ACTIVE_COURSE}
                    """)
                    summary = cursor.fetchone()
                    total_courses = summary[0] or 0
                    total_capacity = summary[1] or 0
                    avg = total_enrolled / max(total_courses, 1)
                    report_text += f"Total Active Courses: {total_courses}\n"
                    report_text += f"Total Students Enrolled: {total_enrolled}\n"
                    report_text += f"Total System Capacity: {total_capacity}\n"
                    report_text += f"Average Enrollment per Course: {avg:.1f}\n"
                    if total_capacity > 0:
                        report_text += f"System Fill Rate: {(total_enrolled/total_capacity*100):.1f}%\n"
                    report_text += f"Available Spots: {total_capacity - total_enrolled}\n"

                elif report_type == "Department":
                    cursor.execute(f"""
                    SELECT
                        COALESCE(c.department, 'Unknown') as dept,
                        COUNT(DISTINCT c.id) as course_count,
                        COUNT(DISTINCT s.student_id) as total_students,
                        SUM(COALESCE(c.max_enrollment, 0)) as total_capacity
                    FROM courses c
                    {_ENROLLMENT_JOIN}
                    {_ACTIVE_COURSE}
                    GROUP BY c.department
                    ORDER BY total_students DESC
                    """)

                    dept_data = cursor.fetchall()
                    report_text += f"{'Department':<20} {'Courses':<10} {'Students':<10} {'Capacity':<10} {'Fill Rate':<10}\n"
                    report_text += "-" * 60 + "\n"

                    for dept, courses, students, capacity in dept_data:
                        fill_rate = f"{(students/capacity*100):.1f}%" if capacity > 0 else "N/A"
                        report_text += f"{dept:<20} {courses:<10} {students:<10} {capacity:<10} {fill_rate:<10}\n"

                elif report_type == "Detailed":
                    cursor.execute(f"""
                    SELECT {_COURSE_CODE}, {_COURSE_NAME}, c.department, c.level,
                           COUNT(s.student_id) as enrolled, COALESCE(c.max_enrollment, 0) as capacity
                    FROM courses c
                    {_ENROLLMENT_JOIN}
                    {_ACTIVE_COURSE}
                    GROUP BY c.id
                    ORDER BY enrolled DESC
                    """)

                    course_data = cursor.fetchall()
                    report_text += f"{'Code':<8} {'Name':<25} {'Dept':<12} {'Level':<12} {'Enrolled':<10} {'Fill Rate':<10}\n"
                    report_text += "-" * 77 + "\n"

                    for code, name, dept, level, enrolled, capacity in course_data:
                        code = code or "N/A"
                        name = name or "N/A"
                        name_short = name[:22] + "..." if len(name) > 25 else name
                        dept_short = dept[:9] + "..." if dept and len(dept) > 12 else dept or "N/A"
                        level_short = level[:9] + "..." if level and len(level) > 12 else level or "N/A"
                        fill_rate = f"{(enrolled/capacity*100):.1f}%" if capacity > 0 else "N/A"
                        enrollment_str = f"{enrolled}/{capacity}"

                        report_text += f"{code:<8} {name_short:<25} {dept_short:<12} {level_short:<12} {enrollment_str:<10} {fill_rate:<10}\n"

                elif report_type == "Capacity":
                    cursor.execute(f"""
                    SELECT {_COURSE_CODE}, {_COURSE_NAME}, c.department,
                           COUNT(s.student_id) as enrolled,
                           COALESCE(c.max_enrollment, 0) as capacity
                    FROM courses c
                    {_ENROLLMENT_JOIN}
                    {_ACTIVE_COURSE}
                    GROUP BY c.id
                    ORDER BY (COALESCE(c.max_enrollment, 0) - COUNT(s.student_id)) DESC
                    """)

                    capacity_data = cursor.fetchall()
                    report_text += f"{'Code':<8} {'Name':<30} {'Department':<15} {'Enrolled':<10} {'Capacity':<10} {'Available':<10}\n"
                    report_text += "-" * 83 + "\n"

                    for code, name, dept, enrolled, capacity in capacity_data:
                        code = code or "N/A"
                        name = name or "N/A"
                        available = capacity - enrolled
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
            stats_window = tk.Toplevel(self.root)
            stats_window.title(_("course_management.dialogs.department_stats"))
            stats_window.geometry("800x600")
            stats_window.transient(self.root)

            main_frame = ttk.Frame(stats_window)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            selection_frame = ttk.Frame(main_frame)
            selection_frame.pack(fill=tk.X, pady=5)

            ttk.Label(selection_frame, text=_("course_management.labels.department_colon")).pack(side=tk.LEFT)
            dept_var = tk.StringVar()

            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                SELECT DISTINCT COALESCE(c.department, 'Unknown') as dept
                FROM courses c {_VALID_COURSE} ORDER BY dept
                """)
                departments = ["All Departments"] + [row[0] for row in cursor.fetchall()]

            dept_combo = ttk.Combobox(selection_frame, textvariable=dept_var, values=departments)
            dept_combo.pack(side=tk.LEFT, padx=5)
            dept_combo.set("All Departments")

            stats_text = ScrolledText(main_frame, wrap=tk.WORD)
            stats_text.pack(fill=tk.BOTH, expand=True, pady=5)

            def update_stats():
                selected_dept = dept_var.get()
                stats_text.delete(1.0, tk.END)

                with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                    cursor = conn.cursor()

                    if selected_dept == "All Departments":
                        cursor.execute(f"""
                        SELECT
                            COALESCE(c.department, 'Unknown') as dept,
                            COUNT(DISTINCT c.id) as course_count,
                            COUNT(DISTINCT CASE WHEN LOWER(COALESCE(c.status, 'active')) = 'active' THEN c.id END) as active_courses,
                            COUNT(DISTINCT s.student_id) as total_students,
                            SUM(COALESCE(c.max_enrollment, 0)) as total_capacity
                        FROM courses c
                        {_ENROLLMENT_JOIN}
                        {_VALID_COURSE}
                        GROUP BY c.department
                        ORDER BY total_students DESC
                        """)

                        all_dept_stats = cursor.fetchall()
                        stats_text.insert(tk.END, "ALL DEPARTMENTS OVERVIEW\n")
                        stats_text.insert(tk.END, "=" * 50 + "\n\n")
                        stats_text.insert(tk.END, f"{'Department':<20} {'Courses':<10} {'Active':<8} {'Students':<10} {'Capacity':<10} {'Fill Rate':<10}\n")
                        stats_text.insert(tk.END, "-" * 68 + "\n")

                        for dept_stat in all_dept_stats:
                            dept, courses, active, students, capacity = dept_stat
                            fill_rate = f"{(students/capacity*100):.1f}%" if capacity > 0 else "N/A"
                            stats_text.insert(tk.END, f"{dept:<20} {courses:<10} {active:<8} {students:<10} {capacity:<10} {fill_rate:<10}\n")
                    else:
                        cursor.execute(f"""
                        SELECT
                            COUNT(DISTINCT c.id) as total_courses,
                            COUNT(DISTINCT s.student_id) as total_students,
                            SUM(COALESCE(c.max_enrollment, 0)) as total_capacity,
                            AVG(COALESCE(c.credit_hours, c.credits, 0)) as avg_credits,
                            COUNT(DISTINCT CASE WHEN LOWER(COALESCE(c.status, 'active')) = 'active' THEN c.id END) as active_courses
                        FROM courses c
                        {_ENROLLMENT_JOIN}
                        {_VALID_COURSE} AND c.department = ?
                        """, (selected_dept,))

                        stats = cursor.fetchone()
                        total_courses = stats[0] or 0
                        total_students = stats[1] or 0
                        total_capacity = stats[2] or 0
                        avg_credits = stats[3] or 0.0
                        active_courses = stats[4] or 0

                        stats_text.insert(tk.END, f"STATISTICS FOR {selected_dept.upper()} DEPARTMENT\n")
                        stats_text.insert(tk.END, "=" * 60 + "\n\n")
                        stats_text.insert(tk.END, f"Total Courses: {total_courses}\n")
                        stats_text.insert(tk.END, f"Active Courses: {active_courses}\n")
                        stats_text.insert(tk.END, f"Total Students: {total_students}\n")
                        stats_text.insert(tk.END, f"Total Capacity: {total_capacity}\n")
                        avg_enrollment = total_students / max(total_courses, 1)
                        stats_text.insert(tk.END, f"Average Enrollment: {avg_enrollment:.1f}\n")
                        stats_text.insert(tk.END, f"Average Credit Hours: {avg_credits:.1f}\n")
                        if total_capacity > 0:
                            stats_text.insert(tk.END, f"Department Fill Rate: {(total_students/total_capacity*100):.1f}%\n")

            ttk.Button(selection_frame, text=_("course_management.buttons.update"), command=update_stats).pack(side=tk.LEFT, padx=5)

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

                    if not admin_email:
                        admin_email = tk.simpledialog.askstring("Admin Email",
                            "Enter admin email address:",
                            parent=stats_window)

                    if not admin_email:
                        return

                    from education_system.university_system.infrastructure.email.template_utils import render_template

                    selected_dept = dept_var.get()
                    stats_content = stats_text.get(1.0, tk.END)

                    subject, body = render_template('academics/department_statistics', {
                        'department_name': selected_dept,
                        'report_date': datetime.now().strftime('%Y-%m-%d'),
                        'statistics_content': stats_content,
                        'generated_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })

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
