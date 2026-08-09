"""Extracted demographic-reporting behaviour."""

from education_system.systems.university.infrastructure.i18n import get_text as _t
from .. import *

class StudentUiResultsTableMixin:
    def _perform_search(self):
        """Execute demographic search based on filters"""
        try:
            conn = get_connection()
            if conn is None:
                messagebox.showerror(_t("advanced_search.error_title"), _t("advanced_search.demographics.database_connection_failed"))
                return

            cursor = conn.cursor()

            # Build query with LEFT JOIN to demographics
            query = """
                SELECT
                    s.student_id,
                    COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, '') as full_name,
                    COALESCE(d.gender, s.gender, '') as gender,
                    COALESCE(s.age, 0) as age,
                    COALESCE(s.course, '') as course,
                    COALESCE(s.status, 'Unknown') as status,
                    COALESCE(d.ethnicity, '') as ethnicity,
                    COALESCE(d.academic_level, '') as academic_level,
                    COALESCE(d.age_group, '') as age_group
                FROM students s
                LEFT JOIN student_demographics d ON s.student_id = d.student_id
                WHERE 1=1
            """
            params = []

            # Apply filters
            if self.filter_vars['gender'].get() != 'All':
                query += " AND (d.gender = ? OR s.gender = ?)"
                params.extend([self.filter_vars['gender'].get()] * 2)

            if self.filter_vars['age_group'].get() != 'All':
                query += " AND d.age_group = ?"
                params.append(self.filter_vars['age_group'].get())

            if self.filter_vars['ethnicity'].get() != 'All':
                query += " AND d.ethnicity = ?"
                params.append(self.filter_vars['ethnicity'].get())

            if self.filter_vars['academic_level'].get() != 'All':
                query += " AND d.academic_level = ?"
                params.append(self.filter_vars['academic_level'].get())

            if self.filter_vars['course'].get() != 'All':
                query += " AND s.course = ?"
                params.append(self.filter_vars['course'].get())

            if self.filter_vars['status'].get() != 'All':
                query += " AND s.status = ?"
                params.append(self.filter_vars['status'].get())

            query += " ORDER BY s.last_name, s.first_name"

            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()

            # Store results and update display
            self.report_data = results
            self._display_results(results)
            self._update_statistics(results)

            # Log activity
            try:
                from education_system.systems.university.infrastructure.activity_logger import log_activity
                log_activity('search', 'demographic_report', details={
                    'filters': {k: v.get() for k, v in self.filter_vars.items()},
                    'result_count': len(results)
                })
            except ImportError:
                pass

        except Exception as e:
            messagebox.showerror(_t('gui.shell.advanced_search.demographic_reporting.ui.results_table.dialogs.search_error', default="Search Error"), f"Failed to search: {str(e)}")

    def _display_results(self, results):
        """Display search results in treeview"""
        # Clear existing results
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)

        # Insert new results
        for row in results:
            # row: student_id, full_name, gender, age, course, status, ethnicity, academic_level, age_group
            display_row = (
                row[0],  # student_id
                row[1].strip(),  # full_name
                row[2] or 'N/A',  # gender
                row[3] or 'N/A',  # age
                row[4] or 'N/A',  # course
                row[5] or 'N/A',  # status
                row[6] or 'N/A',  # ethnicity
                row[7] or 'N/A'   # academic_level
            )
            self.results_tree.insert('', tk.END, values=display_row)

        self.results_label.config(text=f"Found {len(results)} student(s)")

    def _update_statistics(self, results):
        """Calculate and display summary statistics"""
        if not results:
            self.stats_text.config(state=tk.NORMAL)
            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(tk.END, "No results to analyze.")
            self.stats_text.config(state=tk.DISABLED)
            return

        # Calculate statistics
        total = len(results)

        # Gender distribution
        gender_counts = {}
        for row in results:
            gender = row[2] or 'Unknown'
            gender_counts[gender] = gender_counts.get(gender, 0) + 1

        # Status distribution
        status_counts = {}
        for row in results:
            status = row[5] or 'Unknown'
            status_counts[status] = status_counts.get(status, 0) + 1

        # Build stats text
        stats = f"Total Students: {total}\n"
        stats += f"Gender Distribution: {', '.join(f'{k}: {v}' for k, v in sorted(gender_counts.items()))}\n"
        stats += f"Status Distribution: {', '.join(f'{k}: {v}' for k, v in sorted(status_counts.items()))}"

        self.stats_text.config(state=tk.NORMAL)
        self.stats_text.delete(1.0, tk.END)
        self.stats_text.insert(tk.END, stats)
        self.stats_text.config(state=tk.DISABLED)
