from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.core._imports import (
    _, datetime, filedialog, messagebox, simpledialog, tk, ttk,
    Toplevel, ScrolledText, sqlite3, DEFAULT_DB_PATH,
    send_email, EMAIL_AVAILABLE,
)

try:
    from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.analytics.analytics import EnrollmentReportDialog
except ImportError:
    EnrollmentReportDialog = None


# Helper SQL fragments to avoid repetition
_COURSE_CODE = "COALESCE(c.course_code, c.code)"
_COURSE_NAME = "COALESCE(c.course_name, c.name)"
_VALID_COURSE = (
    f"WHERE {_COURSE_CODE} IS NOT NULL AND {_COURSE_NAME} IS NOT NULL"
)
# 8.117.88: dropped ``COALESCE(c.course_type, '') = 'Degree Program'``
# from _VALID_COURSE — that filter silently excluded courses whose
# course_type was 'Bachelors', 'Masters', 'Certificate', etc., so the
# enrollment report reported zeros even when the Course List tab
# showed real rows. _enrollment_count below had the same filter inline.
_ACTIVE_COURSE = (
    f"{_VALID_COURSE} AND LOWER(COALESCE(NULLIF(c.status, ''), 'active')) = 'active'"
)
# Join enrollment via students.course matching the course code
_ENROLLMENT_JOIN = (
    "LEFT JOIN students s ON UPPER(s.course) = UPPER(COALESCE(c.course_code, c.code))"
)


def _enrollment_count(cursor):
    """Total enrolled students across courses (any type)."""
    cursor.execute(
        "SELECT COUNT(*) FROM students s "
        "JOIN courses c ON UPPER(s.course) = UPPER(COALESCE(c.course_code, c.code))"
    )
    return cursor.fetchone()[0] or 0


class AnalyticsMixin:
    """Analytics generation, enrollment reports, and department statistics."""

    def _analytics_dashboard_data(self):
        """Gather structured data for the analytics dashboard."""
        with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
            cursor = conn.cursor()

            total_enrolled = _enrollment_count(cursor)
            cursor.execute(f"""
            SELECT COUNT(*) as total_courses,
                   SUM(COALESCE(c.max_enrollment, 0)) as total_capacity
            FROM courses c
            {_ACTIVE_COURSE}
            """)
            stats = cursor.fetchone() or (0, 0)
            total_courses = stats[0] or 0
            total_capacity = stats[1] or 0

            cursor.execute(f"""
            SELECT COALESCE(c.department, 'Unknown') as dept,
                   COUNT(DISTINCT c.id) as course_count,
                   COUNT(DISTINCT s.student_id) as total_students
            FROM courses c
            {_ENROLLMENT_JOIN}
            {_ACTIVE_COURSE}
            GROUP BY c.department
            ORDER BY total_students DESC
            """)
            departments = cursor.fetchall()

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

            cursor.execute(f"""
            SELECT COUNT(*) FROM courses c
            {_ACTIVE_COURSE}
              AND COALESCE(c.max_enrollment, 0) > 0
            """)
            available_count = cursor.fetchone()[0]

            cursor.execute(f"""
            SELECT c.status, COUNT(*) FROM courses c
            {_VALID_COURSE}
            GROUP BY c.status
            """)
            status_data = cursor.fetchall()

        return {
            "total_courses": total_courses,
            "total_enrolled": total_enrolled,
            "total_capacity": total_capacity,
            "avg": total_enrolled / max(total_courses, 1),
            "fill_rate": (total_enrolled / total_capacity * 100) if total_capacity > 0 else None,
            "available": total_capacity - total_enrolled,
            "departments": departments,
            "popular": popular,
            "available_count": available_count,
            "status": status_data,
        }

    def _render_analytics_dashboard(self, d):
        """Render the analytics dashboard as cards/tables on the card surface."""
        inner = self.analytics_container
        for w in inner.winfo_children():
            w.destroy()

        self._report_header(inner, "Course Analytics Dashboard",
                            f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}")

        self._stat_strip(inner, [
            (d["total_courses"], "Active Courses"),
            (d["total_enrolled"], "Students Enrolled"),
            (d["total_capacity"], "Total Capacity"),
            (d["available"], "Available Spots"),
        ])

        util = self._detail_card("System Utilisation", accent="#16a34a", parent=inner)
        if d["fill_rate"] is not None:
            self._fill_bar(util, d["fill_rate"], label="System Fill Rate")
        self._kv_grid(util, [
            ("Average Enrolment / Course", f"{d['avg']:.1f}"),
            ("Courses with Available Spots", d["available_count"]),
        ])

        if d["departments"]:
            self._detail_card("Courses by Department", accent="#3498db", parent=inner)
            rows = [((dept or "Unknown", courses, students), None)
                    for dept, courses, students in d["departments"]]
            self._report_table(
                inner, ["Department", "Courses", "Students"], rows,
                widths={"Department": 300, "Courses": 110, "Students": 110},
                anchors={"Courses": tk.CENTER, "Students": tk.CENTER},
                height=10,
            )

        if d["popular"]:
            self._detail_card("Most Popular Courses (Top 10)", accent="#9b59b6", parent=inner)
            rows = []
            for code, name, enrolled in d["popular"]:
                rows.append(((code or "N/A", name or "N/A", enrolled or 0), None))
            self._report_table(
                inner, ["Code", "Name", "Enrolled"], rows,
                widths={"Code": 100, "Name": 340, "Enrolled": 110},
                anchors={"Enrolled": tk.CENTER}, height=10,
            )

        if d["status"]:
            body = self._detail_card("Course Status Breakdown", accent="#f39c12", parent=inner)
            self._kv_grid(body, [(str(status or "Unknown").title(), count)
                                 for status, count in d["status"]])

    def generate_analytics(self):
        """Generate and display course analytics"""
        try:
            data = self._analytics_dashboard_data()

            # Display in analytics tab (card dashboard surface)
            self.notebook.select(2)  # Analytics tab
            self.show_analytics_cards()
            self._render_analytics_dashboard(data)

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

                from education_system.post_18.university_system.infrastructure.email.template_utils import render_template

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
                analytics_text += "COURSE AVAILABILITY:\n"
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

    def _enrollment_report_data(self, report_type):
        """Return structured data for an enrollment report (for card/table rendering)."""
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

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
                    return {
                        "total_courses": total_courses,
                        "total_enrolled": total_enrolled,
                        "total_capacity": total_capacity,
                        "avg": total_enrolled / max(total_courses, 1),
                        "fill_rate": (total_enrolled / total_capacity * 100) if total_capacity > 0 else None,
                        "available": total_capacity - total_enrolled,
                    }

                if report_type == "Department":
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
                    return cursor.fetchall()

                if report_type == "Detailed":
                    cursor.execute(f"""
                    SELECT {_COURSE_CODE}, {_COURSE_NAME}, c.department, c.level,
                           COUNT(s.student_id) as enrolled, COALESCE(c.max_enrollment, 0) as capacity
                    FROM courses c
                    {_ENROLLMENT_JOIN}
                    {_ACTIVE_COURSE}
                    GROUP BY c.id
                    ORDER BY enrolled DESC
                    """)
                    return cursor.fetchall()

                if report_type == "Capacity":
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
                    return cursor.fetchall()

                return None
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"),
                                 _("course_management.messages.failed_generate_analytics", error=str(e)))
            return None

    def _render_enrollment_report(self, inner, report_type, data):
        """Render structured enrollment-report data as cards/tables on ``inner``."""
        subtitle = f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        if report_type == "Summary":
            self._report_header(inner, "Enrollment Summary", subtitle)
            self._stat_strip(inner, [
                (data["total_courses"], "Active Courses"),
                (data["total_enrolled"], "Students Enrolled"),
                (data["total_capacity"], "Total Capacity"),
                (data["available"], "Available Spots"),
            ])
            body = self._detail_card("System Utilisation", accent="#16a34a", parent=inner)
            if data["fill_rate"] is not None:
                self._fill_bar(body, data["fill_rate"], label="System Fill Rate")
            self._kv_grid(body, [
                ("Average Enrolment / Course", f"{data['avg']:.1f}"),
                ("Fill Rate", f"{data['fill_rate']:.1f}%" if data["fill_rate"] is not None else "N/A"),
            ])
            return

        if report_type == "Department":
            self._report_header(inner, "Department Report", subtitle)
            total_students = sum((r[2] or 0) for r in data)
            total_capacity = sum((r[3] or 0) for r in data)
            self._stat_strip(inner, [
                (len(data), "Departments"),
                (total_students, "Students"),
                (total_capacity, "Capacity"),
            ])
            rows = []
            for dept, courses, students, capacity in data:
                fr = (students / capacity * 100) if capacity else None
                tag = None
                if fr is not None:
                    tag = "_good" if fr < 75 else "_warn" if fr < 95 else "_full"
                rows.append(((dept or "Unknown", courses, students, capacity or 0,
                              f"{fr:.1f}%" if fr is not None else "N/A"), tag))
            self._report_table(
                inner, ["Department", "Courses", "Students", "Capacity", "Fill Rate"], rows,
                widths={"Department": 240, "Courses": 90, "Students": 90, "Capacity": 90, "Fill Rate": 100},
                anchors={"Courses": tk.CENTER, "Students": tk.CENTER, "Capacity": tk.CENTER, "Fill Rate": tk.CENTER},
                tag_colours={"_good": "#16a34a", "_warn": "#d97706", "_full": "#dc2626"},
            )
            return

        if report_type == "Detailed":
            self._report_header(inner, "Detailed Course Report", subtitle)
            self._stat_strip(inner, [
                (len(data), "Courses"),
                (sum((r[4] or 0) for r in data), "Total Enrolled"),
            ])
            rows = []
            for code, name, dept, level, enrolled, capacity in data:
                fr = (enrolled / capacity * 100) if capacity else None
                tag = None
                if fr is not None:
                    tag = "_good" if fr < 75 else "_warn" if fr < 95 else "_full"
                rows.append(((code or "N/A", name or "N/A", dept or "N/A", level or "N/A",
                              f"{enrolled}/{capacity}", f"{fr:.1f}%" if fr is not None else "N/A"), tag))
            self._report_table(
                inner, ["Code", "Name", "Department", "Level", "Enrolled", "Fill Rate"], rows,
                widths={"Code": 80, "Name": 260, "Department": 140, "Level": 120, "Enrolled": 90, "Fill Rate": 90},
                anchors={"Enrolled": tk.CENTER, "Fill Rate": tk.CENTER},
                tag_colours={"_good": "#16a34a", "_warn": "#d97706", "_full": "#dc2626"},
            )
            return

        if report_type == "Capacity":
            self._report_header(inner, "Capacity Analysis", subtitle)
            total_avail = sum((cap - enr) for _c, _n, _d, enr, cap in data)
            self._stat_strip(inner, [
                (len(data), "Courses"),
                (sum((r[3] or 0) for r in data), "Enrolled"),
                (sum((r[4] or 0) for r in data), "Capacity"),
                (total_avail, "Available"),
            ])
            rows = []
            for code, name, dept, enrolled, capacity in data:
                available = capacity - enrolled
                # Flag scarcity: red when full/over, amber when nearly full.
                tag = "_full" if available <= 0 else "_warn" if capacity and available <= capacity * 0.1 else "_good"
                rows.append(((code or "N/A", name or "N/A", dept or "N/A",
                              enrolled, capacity, available), tag))
            self._report_table(
                inner, ["Code", "Name", "Department", "Enrolled", "Capacity", "Available"], rows,
                widths={"Code": 80, "Name": 280, "Department": 160, "Enrolled": 90, "Capacity": 90, "Available": 90},
                anchors={"Enrolled": tk.CENTER, "Capacity": tk.CENTER, "Available": tk.CENTER},
                tag_colours={"_good": "#16a34a", "_warn": "#d97706", "_full": "#dc2626"},
            )
            return

    def open_enrollment_report_window(self, report_type):
        """Open enrollment report in a new window with export and email options"""
        report_text = self._generate_enrollment_report_text(report_type)
        data = self._enrollment_report_data(report_type)

        if not report_text or data is None:
            return

        window = tk.Toplevel(self.root)
        window.title(_("course_management.dialogs.enrollment_report_type", type=report_type))
        window.geometry("960x680")
        window.transient(self.root)
        window.configure(bg=self.DETAIL_BG)

        main_frame = ttk.Frame(window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Scrollable card/table body (falls back to text if rendering fails).
        inner = self._scrollable_area(main_frame)
        try:
            self._render_enrollment_report(inner, report_type, data)
        except Exception:
            text_widget = ScrolledText(inner, wrap=tk.WORD, height=30)
            text_widget.pack(fill=tk.BOTH, expand=True)
            text_widget.insert(1.0, report_text)
            text_widget.config(state='disabled')

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(8, 0))

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

                from education_system.post_18.university_system.infrastructure.email.template_utils import render_template

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

            stats_inner = self._scrollable_area(main_frame)
            self._dept_stats_text = ""

            def update_stats():
                selected_dept = dept_var.get()
                for w in stats_inner.winfo_children():
                    w.destroy()
                subtitle = f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                lines = []  # plain-text mirror kept for export / email

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
                        self._report_header(stats_inner, "All Departments Overview", subtitle)
                        self._stat_strip(stats_inner, [
                            (len(all_dept_stats), "Departments"),
                            (sum((r[3] or 0) for r in all_dept_stats), "Students"),
                            (sum((r[4] or 0) for r in all_dept_stats), "Capacity"),
                        ])
                        lines.append("ALL DEPARTMENTS OVERVIEW")
                        lines.append(f"{'Department':<20} {'Courses':<10} {'Active':<8} {'Students':<10} {'Capacity':<10} {'Fill Rate':<10}")
                        rows = []
                        for dept, courses, active, students, capacity in all_dept_stats:
                            fr = (students / capacity * 100) if capacity else None
                            tag = None
                            if fr is not None:
                                tag = "_good" if fr < 75 else "_warn" if fr < 95 else "_full"
                            fr_txt = f"{fr:.1f}%" if fr is not None else "N/A"
                            rows.append(((dept or "Unknown", courses, active, students, capacity or 0, fr_txt), tag))
                            lines.append(f"{(dept or 'Unknown'):<20} {courses:<10} {active:<8} {students:<10} {(capacity or 0):<10} {fr_txt:<10}")
                        self._report_table(
                            stats_inner,
                            ["Department", "Courses", "Active", "Students", "Capacity", "Fill Rate"], rows,
                            widths={"Department": 220, "Courses": 90, "Active": 80, "Students": 90, "Capacity": 90, "Fill Rate": 100},
                            anchors={"Courses": tk.CENTER, "Active": tk.CENTER, "Students": tk.CENTER, "Capacity": tk.CENTER, "Fill Rate": tk.CENTER},
                            tag_colours={"_good": "#16a34a", "_warn": "#d97706", "_full": "#dc2626"},
                        )
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
                        avg_enrollment = total_students / max(total_courses, 1)
                        fill_rate = (total_students / total_capacity * 100) if total_capacity > 0 else None

                        self._report_header(stats_inner, f"{selected_dept} Department", subtitle)
                        self._stat_strip(stats_inner, [
                            (total_courses, "Total Courses"),
                            (active_courses, "Active Courses"),
                            (total_students, "Students"),
                            (total_capacity, "Capacity"),
                        ])
                        body = self._detail_card("Department Metrics", accent="#16a34a", parent=stats_inner)
                        if fill_rate is not None:
                            self._fill_bar(body, fill_rate, label="Department Fill Rate")
                        self._kv_grid(body, [
                            ("Average Enrolment", f"{avg_enrollment:.1f}"),
                            ("Average Credit Hours", f"{avg_credits:.1f}"),
                        ])

                        lines.append(f"STATISTICS FOR {selected_dept.upper()} DEPARTMENT")
                        lines.append(f"Total Courses: {total_courses}")
                        lines.append(f"Active Courses: {active_courses}")
                        lines.append(f"Total Students: {total_students}")
                        lines.append(f"Total Capacity: {total_capacity}")
                        lines.append(f"Average Enrollment: {avg_enrollment:.1f}")
                        lines.append(f"Average Credit Hours: {avg_credits:.1f}")
                        if fill_rate is not None:
                            lines.append(f"Department Fill Rate: {fill_rate:.1f}%")

                self._dept_stats_text = "\n".join(lines) + "\n"

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
                        stats_content = getattr(self, "_dept_stats_text", "")
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

                    from education_system.post_18.university_system.infrastructure.email.template_utils import render_template

                    selected_dept = dept_var.get()
                    stats_content = getattr(self, "_dept_stats_text", "")

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
