"""
Dashboard mixin - GPA overview, statistics cards, and quick actions.
"""

from tkinter import ttk
import logging

from education_system.university_system.modules.domain.academics.gui.student_grades.common_imports import (
    get_connection,
    create_stat_card,
    format_grade,
    COLORS,
)

# Backend GPA calculation
try:
    from education_system.university_system.modules.domain.academics.grading.grade_calculation import (
        calculate_student_gpa,
    )
except ImportError:
    calculate_student_gpa = None

logger = logging.getLogger(__name__)


class DashboardMixin:
    """Dashboard display with GPA statistics and quick actions."""

    def show_dashboard(self, parent):
        """
        Display student GPA dashboard.

        Args:
            parent: Parent frame to render into
        """
        # Title
        title_frame = ttk.Frame(parent)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(
            title_frame,
            text='Grades Dashboard',
            font=('Arial', 16, 'bold'),
            foreground=COLORS['primary'],
        ).pack(anchor='w')

        # Statistics cards
        stats_frame = ttk.Frame(parent)
        stats_frame.pack(fill='x', padx=10, pady=10)

        gpa, total_modules, detailed_grades = self._fetch_gpa_data()

        if gpa is None:
            ttk.Label(
                parent,
                text='No grade data available.',
                font=('Arial', 12),
                foreground=COLORS['warning'],
            ).pack(pady=20)
            return

        # Determine highest grade from detailed_grades
        # Each entry is (module_code, module_name, grade, gpa_points)
        highest_grade = 'N/A'
        if detailed_grades:
            best = max(detailed_grades, key=lambda g: g[3])
            highest_grade = format_grade(best[2])

        cards = [
            ('GPA', f'{gpa:.2f}', 'success'),
            ('Modules Completed', str(total_modules), 'info'),
            ('Highest Grade', highest_grade, 'primary'),
        ]

        for i, (title, value, color) in enumerate(cards):
            card = create_stat_card(stats_frame, title, value, color)
            card.grid(row=0, column=i, padx=10, pady=5, sticky='ew')
            stats_frame.grid_columnconfigure(i, weight=1)

        # Quick actions
        actions_frame = ttk.LabelFrame(parent, text='Quick Actions', padding=10)
        actions_frame.pack(fill='x', padx=10, pady=10)

        ttk.Button(
            actions_frame,
            text='View Grades',
            command=lambda: self.notebook.select(1),
            width=20,
        ).pack(side='left', padx=5)

        ttk.Button(
            actions_frame,
            text='View Transcript',
            command=lambda: self.notebook.select(2),
            width=20,
        ).pack(side='left', padx=5)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_gpa_data(self):
        """
        Fetch GPA data for the current student.

        Returns:
            Tuple of (gpa, total_modules, detailed_grades) or (None, 0, [])
        """
        if calculate_student_gpa is None:
            logger.error('calculate_student_gpa could not be imported')
            return None, 0, []

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                return calculate_student_gpa(cursor, self.student_id)
        except Exception as e:
            logger.error(f'Error fetching GPA data: {e}')
            return None, 0, []
