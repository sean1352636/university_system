"""Extracted demographic-reporting behaviour."""
from .. import *

class StudentUiFilterPanelMixin:
    def _load_filter_options(self):
        """Load filter dropdown options from database"""
        try:
            conn = get_connection()
            if conn is None:
                self._set_default_options()
                return

            cursor = conn.cursor()

            # Get distinct values from students table
            cursor.execute("SELECT DISTINCT gender FROM students WHERE gender IS NOT NULL AND gender != ''")
            genders = ['All'] + [row[0] for row in cursor.fetchall()]
            self.gender_combo['values'] = genders

            cursor.execute("SELECT DISTINCT course FROM students WHERE course IS NOT NULL AND course != ''")
            courses = ['All'] + sorted([row[0] for row in cursor.fetchall()])
            self.course_combo['values'] = courses

            cursor.execute("SELECT DISTINCT status FROM students WHERE status IS NOT NULL AND status != ''")
            statuses = ['All'] + [row[0] for row in cursor.fetchall()]
            self.status_combo['values'] = statuses

            # Try to get demographics data
            cursor.execute("SELECT DISTINCT ethnicity FROM student_demographics WHERE ethnicity IS NOT NULL AND ethnicity != ''")
            ethnicities = ['All'] + sorted([row[0] for row in cursor.fetchall()])
            if len(ethnicities) == 1:
                ethnicities = ['All', 'Asian', 'Black', 'Hispanic', 'White', 'Mixed', 'Other', 'Prefer not to say']
            self.ethnicity_combo['values'] = ethnicities

            cursor.execute("SELECT DISTINCT academic_level FROM student_demographics WHERE academic_level IS NOT NULL AND academic_level != ''")
            levels = ['All'] + sorted([row[0] for row in cursor.fetchall()])
            if len(levels) == 1:
                levels = ['All', 'Freshman', 'Sophomore', 'Junior', 'Senior', 'Graduate', 'Postgraduate']
            self.academic_level_combo['values'] = levels

            cursor.execute("SELECT DISTINCT age_group FROM student_demographics WHERE age_group IS NOT NULL AND age_group != ''")
            age_groups = ['All'] + sorted([row[0] for row in cursor.fetchall()])
            if len(age_groups) == 1:
                age_groups = ['All', '18-21', '22-25', '26-30', '31-40', '41-50', '50+']
            self.age_group_combo['values'] = age_groups

            conn.close()

        except Exception as e:
            print_warning(f"Error loading filter options: {e}")
            self._set_default_options()

    def _set_default_options(self):
        """Set default filter options if database is unavailable"""
        self.gender_combo['values'] = ['All', 'Male', 'Female', 'Non-binary', 'Other', 'Prefer not to say']
        self.course_combo['values'] = ['All']
        self.status_combo['values'] = ['All', 'Active', 'Inactive', 'Graduated', 'Suspended']
        self.ethnicity_combo['values'] = ['All', 'Asian', 'Black', 'Hispanic', 'White', 'Mixed', 'Other', 'Prefer not to say']
        self.academic_level_combo['values'] = ['All', 'Freshman', 'Sophomore', 'Junior', 'Senior', 'Graduate', 'Postgraduate']
        self.age_group_combo['values'] = ['All', '18-21', '22-25', '26-30', '31-40', '41-50', '50+']

    def _clear_filters(self):
        """Reset all filters to default"""
        for var in self.filter_vars.values():
            var.set("All")
