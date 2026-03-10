"""
Overview Mixin for Student Dashboard

Provides the welcome header, stat cards, today's schedule, and recent grades
sections for the student dashboard portal.
"""

from .common_imports import *


class OverviewMixin:
    """Mixin that adds the overview section to the student dashboard."""

    def show_overview(self, parent):
        """
        Build the overview section with welcome header, stat cards,
        today's schedule, and recent grades.

        Args:
            parent: Parent frame to pack widgets into
        """
        self._build_welcome_header(parent)
        self._build_stat_cards(parent)
        self._build_todays_schedule(parent)
        self._build_recent_grades(parent)

    # ------------------------------------------------------------------
    # Welcome header
    # ------------------------------------------------------------------

    def _build_welcome_header(self, parent):
        """Display a personalised welcome banner."""
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill='x', padx=20, pady=(20, 10))

        name = self.student_name or 'Student'
        welcome_text = _t('dashboard.welcome', f'Welcome back, {name}!')
        # If the i18n string doesn't contain the name, substitute it
        if '{name}' in welcome_text:
            welcome_text = welcome_text.replace('{name}', name)
        elif name not in welcome_text:
            welcome_text = f'Welcome back, {name}!'

        ttk.Label(
            header_frame,
            text=welcome_text,
            font=('Arial', 20, 'bold'),
            foreground=COLORS['primary'],
        ).pack(anchor='w')

        today_str = datetime.now().strftime('%A, %B %d, %Y')
        ttk.Label(
            header_frame,
            text=today_str,
            font=('Arial', 11),
            foreground=COLORS['secondary'],
        ).pack(anchor='w', pady=(2, 0))

    # ------------------------------------------------------------------
    # Stat cards
    # ------------------------------------------------------------------

    def _build_stat_cards(self, parent):
        """Display a row of summary statistic cards."""
        cards_frame = ttk.Frame(parent)
        cards_frame.pack(fill='x', padx=20, pady=10)
        for col in range(4):
            cards_frame.columnconfigure(col, weight=1)

        gpa = self._fetch_gpa()
        enrolled = self._fetch_enrolled_count()
        exams = self._fetch_upcoming_exams()
        fines = self._fetch_outstanding_fines()

        card_data = [
            (_t('dashboard.gpa', 'Current GPA'), gpa, 'info'),
            (_t('dashboard.enrolled', 'Enrolled Modules'), enrolled, 'success'),
            (_t('dashboard.exams', 'Upcoming Exams'), exams, 'warning'),
            (_t('dashboard.fines', 'Outstanding Fines'), fines, 'danger'),
        ]

        for idx, (title, value, color) in enumerate(card_data):
            card = create_stat_card(cards_frame, title, str(value), color)
            card.grid(row=0, column=idx, padx=8, pady=5, sticky='nsew')

    def _fetch_gpa(self) -> str:
        """Retrieve the current GPA for the student."""
        try:
            from education_system.university_system.modules.domain.academics.grading.grade_calculation import (
                calculate_student_gpa,
            )
            conn = get_connection()
            cursor = conn.cursor()
            gpa, _credits, _details = calculate_student_gpa(cursor, self.student_id)
            conn.close()
            return f"{gpa:.2f}" if gpa is not None else "N/A"
        except Exception as exc:
            logger.debug("Could not fetch GPA: %s", exc)
            return "N/A"

    def _fetch_enrolled_count(self) -> str:
        """Count the number of modules the student is currently enrolled in."""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM student_modules "
                "WHERE student_id = ? AND status = 'Enrolled'",
                (self.student_id,),
            )
            count = cursor.fetchone()[0]
            conn.close()
            return str(count)
        except Exception as exc:
            logger.debug("Could not fetch enrolled count: %s", exc)
            return "0"

    def _fetch_upcoming_exams(self) -> str:
        """Count upcoming exams for modules the student is enrolled in."""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            # Try to filter by enrolled modules first
            try:
                cursor.execute(
                    "SELECT COUNT(*) FROM exams e "
                    "JOIN student_modules sm ON e.module_code = sm.module_code "
                    "WHERE sm.student_id = ? AND sm.status = 'Enrolled' "
                    "AND e.exam_date >= date('now')",
                    (self.student_id,),
                )
            except Exception:
                # Fallback: just count all upcoming exams
                cursor.execute(
                    "SELECT COUNT(*) FROM exams WHERE exam_date >= date('now')"
                )
            count = cursor.fetchone()[0]
            conn.close()
            return str(count)
        except Exception as exc:
            logger.debug("Could not fetch upcoming exams: %s", exc)
            return "0"

    def _fetch_outstanding_fines(self) -> str:
        """Sum outstanding library fines for the student."""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM library_fines "
                "WHERE student_id = ? AND status = 'unpaid'",
                (self.student_id,),
            )
            total = cursor.fetchone()[0]
            conn.close()
            if total and float(total) > 0:
                return f"${float(total):.2f}"
            return "$0.00"
        except Exception as exc:
            logger.debug("Could not fetch outstanding fines: %s", exc)
            return "$0.00"

    # ------------------------------------------------------------------
    # Today's schedule
    # ------------------------------------------------------------------

    def _build_todays_schedule(self, parent):
        """Show today's class schedule."""
        schedule_frame = ttk.LabelFrame(
            parent,
            text=_t('dashboard.todays_schedule', "Today's Schedule"),
        )
        schedule_frame.pack(fill='x', padx=20, pady=10)

        rows = self._fetch_todays_schedule()
        if not rows:
            ttk.Label(
                schedule_frame,
                text=_t('dashboard.no_classes', 'No classes scheduled for today.'),
                font=('Arial', 10),
                foreground=COLORS['secondary'],
            ).pack(padx=15, pady=10)
            return

        # Header
        header = ttk.Frame(schedule_frame)
        header.pack(fill='x', padx=10, pady=(8, 2))
        for col, (text, w) in enumerate([('Time', 15), ('Module', 30), ('Room', 15)]):
            ttk.Label(header, text=text, font=('Arial', 10, 'bold'), width=w).pack(side='left')

        ttk.Separator(schedule_frame, orient='horizontal').pack(fill='x', padx=10)

        for start_time, module_name, room in rows:
            row = ttk.Frame(schedule_frame)
            row.pack(fill='x', padx=10, pady=2)
            ttk.Label(row, text=str(start_time or ''), width=15).pack(side='left')
            ttk.Label(row, text=str(module_name or ''), width=30).pack(side='left')
            ttk.Label(row, text=str(room or ''), width=15).pack(side='left')

        # Bottom padding
        ttk.Frame(schedule_frame).pack(pady=5)

    def _fetch_todays_schedule(self) -> list:
        """Query today's schedule from module_schedule."""
        try:
            today = datetime.now().strftime('%A')
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT ms.start_time, ms.module_code, ms.room "
                "FROM module_schedule ms "
                "JOIN student_modules sm ON ms.module_code = sm.module_code "
                "WHERE sm.student_id = ? AND sm.status = 'Enrolled' "
                "AND ms.day = ? "
                "ORDER BY ms.start_time",
                (self.student_id, today),
            )
            rows = cursor.fetchall()
            conn.close()
            return rows
        except Exception as exc:
            logger.debug("Could not fetch today's schedule: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Recent grades
    # ------------------------------------------------------------------

    def _build_recent_grades(self, parent):
        """Show the last 5 grades the student received."""
        grades_frame = ttk.LabelFrame(
            parent,
            text=_t('dashboard.recent_grades', 'Recent Grades'),
        )
        grades_frame.pack(fill='x', padx=20, pady=10)

        rows = self._fetch_recent_grades()
        if not rows:
            ttk.Label(
                grades_frame,
                text=_t('dashboard.no_grades', 'No grades recorded yet.'),
                font=('Arial', 10),
                foreground=COLORS['secondary'],
            ).pack(padx=15, pady=10)
            return

        # Header
        header = ttk.Frame(grades_frame)
        header.pack(fill='x', padx=10, pady=(8, 2))
        for col, (text, w) in enumerate([('Module', 25), ('Grade', 10), ('Date', 15)]):
            ttk.Label(header, text=text, font=('Arial', 10, 'bold'), width=w).pack(side='left')

        ttk.Separator(grades_frame, orient='horizontal').pack(fill='x', padx=10)

        for module_code, grade, date_val in rows:
            row = ttk.Frame(grades_frame)
            row.pack(fill='x', padx=10, pady=2)
            ttk.Label(row, text=str(module_code or ''), width=25).pack(side='left')
            grade_str = f"{grade:.1f}" if isinstance(grade, (int, float)) else str(grade or 'N/A')
            ttk.Label(
                row, text=grade_str, width=10,
                foreground=COLORS['success'] if isinstance(grade, (int, float)) and grade >= 50 else COLORS['danger'],
            ).pack(side='left')
            ttk.Label(row, text=str(date_val or ''), width=15).pack(side='left')

        # Bottom padding
        ttk.Frame(grades_frame).pack(pady=5)

    def _fetch_recent_grades(self) -> list:
        """Fetch the last 5 grades from module_grades."""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT module_code, grade, date_recorded "
                "FROM module_grades "
                "WHERE student_id = ? "
                "ORDER BY date_recorded DESC "
                "LIMIT 5",
                (self.student_id,),
            )
            rows = cursor.fetchall()
            conn.close()
            return rows
        except Exception as exc:
            logger.debug("Could not fetch recent grades: %s", exc)
            return []
