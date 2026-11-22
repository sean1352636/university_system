"""Data access mixin for the Student Analytics GUI.

Students and module enrolments come from the services-layer DataAccessMixin,
so the GUI sees the same derived columns as the CLI analytics (gpa,
overall_grade, completion_status, engagement_score, module_grade,
attendance_rate, difficulty_rating). Nothing is simulated: columns with no
source are NaN and an empty table yields an empty frame.
"""
from education_system.systems.university.shell.gui.analytics.student_analytics._imports import (
    pd, plt, datetime,
)
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.shared.analytics.student_analytics.data_access import (
    DataAccessMixin,
)


class AnalyticsDataMixin(DataAccessMixin):
    """Mixin providing data loading, filtering, and plot utilities."""

    def create_directories(self):
        """Create necessary directories for outputs"""
        import os
        os.makedirs(self.plots_dir, exist_ok=True)
        os.makedirs(self.reports_dir, exist_ok=True)

    def get_connection(self):
        """Get database connection"""
        return get_connection()

    def _merged_filters(self, filters):
        return {**(filters or {}), **getattr(self, 'custom_filters', {})}

    def get_all_students(self, filters=None):
        """All students with the derived analytics columns, filtered in pandas."""
        try:
            df = DataAccessMixin.get_all_students(self)
        except Exception as e:
            print(f"Error loading students: {e}")
            return pd.DataFrame()
        if df.empty:
            return df
        return self.apply_filters(df, self._merged_filters(filters))

    def get_all_modules(self, filters=None):
        """All module enrolments with marks/attendance joined, filtered in pandas."""
        try:
            df = DataAccessMixin.get_all_modules(self)
        except Exception as e:
            print(f"Error loading modules: {e}")
            return pd.DataFrame()
        if df.empty:
            return df
        return self.apply_filters(df, self._merged_filters(filters))

    def apply_filters(self, df, filters):
        """Apply filters to dataframe"""
        if not filters:
            return df

        filtered_df = df.copy()

        # Age range filter
        if 'age_range' in filters:
            min_age, max_age = filters['age_range']
            if 'age' in filtered_df.columns:
                filtered_df = filtered_df[(filtered_df['age'] >= min_age) & (filtered_df['age'] <= max_age)]

        # GPA range filter
        if 'gpa_range' in filters:
            min_gpa, max_gpa = filters['gpa_range']
            if 'gpa' in filtered_df.columns:
                filtered_df = filtered_df[(filtered_df['gpa'] >= min_gpa) & (filtered_df['gpa'] <= max_gpa)]

        # Course filter
        if 'course' in filters and 'course' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['course'] == filters['course']]

        # Gender filter
        if 'gender' in filters and 'gender' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['gender'] == filters['gender']]

        return filtered_df

    def safe_plot_data(self, x_data, y_data):
        """Safely plot data with error handling for GUI"""
        if len(x_data) == 0 or len(y_data) == 0:
            print("Warning: No data to plot")
            return False
        return True

    def save_or_display_plot(self, plt_figure, plot_type, export_format='png'):
        """Save plot for GUI compatibility"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{self.plots_dir}/{plot_type}_{timestamp}.{export_format}"

        try:
            plt.tight_layout()
            plt.savefig(filename, dpi=300, bbox_inches='tight')
            print(f"Plot saved: {filename}")
            # Don't call plt.show() in GUI mode - let the GUI handle display
        except Exception as e:
            print(f"Error saving plot: {e}")
