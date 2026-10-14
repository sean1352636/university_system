"""Assignment statistics dashboard"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk
from education_system.systems.university.domains.academics.interfaces.gui.assignment_system._dialogs import messagebox
from education_system.systems.university.domains.academics.interfaces.gui.assignment_system._dialogs import make_toplevel
from education_system.systems.university.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH


class StatisticsMixin:
    """Assignment statistics operations"""

    def show_assignment_statistics(self):
        """Show statistics for all assignments"""
        try:
            stats_window = make_toplevel(self.root)
            stats_window.title(_t('gui.academics.assignment_system.assignment_manager.statistics.windows.assignment_statistics', default="Assignment Statistics"))
            stats_window.geometry("900x600")
            stats_window.transient(self.root)

            ttk.Label(stats_window, text=_t('gui.academics.assignment_system.assignment_manager.statistics.labels.assignment_statistics_dashboard', default="Assignment Statistics Dashboard"),
                     font=('TkDefaultFont', 14, 'bold')).pack(pady=10)

            # Summary statistics
            summary_frame = ttk.LabelFrame(stats_window, text=_t('gui.academics.assignment_system.assignment_manager.statistics.labels.summary', default="Summary"), padding=10)
            summary_frame.pack(fill='x', padx=10, pady=10)

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()

                # Total assignments
                cursor.execute("SELECT COUNT(*) FROM assignments")
                total_assignments = cursor.fetchone()[0]

                # Active assignments
                cursor.execute("SELECT COUNT(*) FROM assignments WHERE is_active = 1")
                active_assignments = cursor.fetchone()[0]

                # Total submissions
                cursor.execute("SELECT COUNT(*) FROM assignment_submissions")
                total_submissions = cursor.fetchone()[0]

                # Average grade
                cursor.execute("SELECT AVG(grade) FROM assignment_submissions WHERE grade IS NOT NULL")
                avg_grade = cursor.fetchone()[0] or 0

            finally:
                conn.close()

            summary_text = f"""
            Total Assignments: {total_assignments}
            Active Assignments: {active_assignments}
            Total Submissions: {total_submissions}
            Average Grade: {avg_grade:.2f}%
            """

            ttk.Label(summary_frame, text=summary_text, font=('TkDefaultFont', 10)).pack()

            # Detailed statistics table
            details_frame = ttk.LabelFrame(stats_window, text=_t('gui.academics.assignment_system.assignment_manager.statistics.labels.assignment_details', default="Assignment Details"), padding=10)
            details_frame.pack(fill='both', expand=True, padx=10, pady=10)

            columns = ('Assignment', 'Module', 'Submissions', 'Avg Grade', 'Late %')
            stats_tree = ttk.Treeview(details_frame, columns=columns, show='headings', height=15)

            for col in columns:
                stats_tree.heading(col, text=col)
                stats_tree.column(col, width=150)

            stats_tree.pack(fill='both', expand=True)

            # Load detailed statistics
            self.load_assignment_statistics(stats_tree)

            ttk.Button(stats_window, text=_t('gui.academics.assignment_system.assignment_manager.statistics.buttons.close', default="Close"), command=stats_window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.assignment_manager.statistics.dialogs.error', default="Error"), f"Failed to show statistics: {e}")


    def load_assignment_statistics(self, tree):
        """Load detailed assignment statistics"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT a.title, a.module_code,
                   COUNT(s.id) as submission_count,
                   AVG(s.grade) as avg_grade,
                   (COUNT(CASE WHEN s.late_submission = 1 THEN 1 END) * 100.0 / COUNT(s.id)) as late_percentage
            FROM assignments a
            LEFT JOIN assignment_submissions s ON a.id = s.assignment_id
            GROUP BY a.id
            ORDER BY a.title
            ''')

            stats = cursor.fetchall()
            conn.close()

            for stat in stats:
                title, module, subs, avg, late = stat
                avg_grade = f"{avg:.1f}%" if avg else "N/A"
                late_pct = f"{late:.1f}%" if late else "0%"
                tree.insert('', 'end', values=(title, module, subs, avg_grade, late_pct))

        except Exception as e:
            print(f"Error loading statistics: {e}")
