"""Data access mixin for the Student Analytics GUI."""
from education_system.university_system.modules.shared.gui.student_analytics_gui._imports import (
    pd, np, plt, DEFAULT_DB_PATH, datetime, CONFIG,
)


class AnalyticsDataMixin:
    """Mixin providing data loading, filtering, simulation, and plot utilities."""

    def create_directories(self):
        """Create necessary directories for outputs"""
        import os
        os.makedirs(self.plots_dir, exist_ok=True)
        os.makedirs(self.reports_dir, exist_ok=True)

    def get_connection(self):
        """Get database connection"""
        from education_system.university_system.infrastructure.database.db import sqlite3
        return sqlite3.connect(str(DEFAULT_DB_PATH))

    def get_all_students(self, filters=None):
        """Get all students data with optional filters"""
        from education_system.university_system.infrastructure.database.db import sqlite3
        try:
            conn = self.get_connection()
            query = "SELECT * FROM students"
            df = pd.read_sql_query(query, conn)
            conn.close()

            if df.empty:
                return df

            # Simulate additional data if needed
            df = self.simulate_additional_data(df)

            # Apply filters if provided
            if filters or self.custom_filters:
                all_filters = {**(filters or {}), **self.custom_filters}
                df = self.apply_filters(df, all_filters)

            return df
        except Exception as e:
            print(f"Error loading students: {e}")
            return pd.DataFrame()

    def get_all_modules(self, filters=None):
        """Get all modules data with optional filters"""
        from education_system.university_system.infrastructure.database.db import sqlite3

        conn = None
        try:
            conn = self.get_connection()
            query = "SELECT * FROM modules"
            df = pd.read_sql_query(query, conn)
        except sqlite3.Error as e:
            # If modules table doesn't exist, create sample data
            print(f"Database error loading modules: {e}")
            df = pd.DataFrame()
        except Exception as e:
            # Other errors
            print(f"Error loading modules: {e}")
            df = pd.DataFrame()
        finally:
            if conn:
                conn.close()

        if df.empty:
            df = self.simulate_module_data(df)

        if filters or self.custom_filters:
            all_filters = {**(filters or {}), **self.custom_filters}
            df = self.apply_filters(df, all_filters)

        return df

    def simulate_additional_data(self, df):
        """Add only missing essential columns based on actual database data"""
        # Try to derive from existing data rather than simulate

        if 'gpa' not in df.columns and 'grade' in df.columns:
            # Calculate GPA from grades if possible
            grade_map = {'A': 4.0, 'B': 3.0, 'C': 2.0, 'D': 1.0, 'F': 0.0}
            df['gpa'] = df['grade'].map(grade_map).fillna(3.0)

        if 'completion_status' not in df.columns and 'status' in df.columns:
            # Use existing status column
            df['completion_status'] = df['status']
        elif 'completion_status' not in df.columns:
            # Default to Active if no status
            df['completion_status'] = 'Active'

        return df

    def simulate_module_data(self, df):
        """Simulate module data if not available"""
        modules = ['Mathematics', 'Physics', 'Chemistry', 'Biology', 'Computer Science',
                   'Literature', 'History', 'Economics', 'Psychology', 'Art']

        data = {
            'module_id': range(1, len(modules) + 1),
            'module_name': modules,
            'credits': np.random.choice([3, 4, 6], len(modules)),
            'difficulty_level': np.random.choice(['Beginner', 'Intermediate', 'Advanced'], len(modules)),
            'enrollment_count': np.random.randint(10, 200, len(modules)),
            'pass_rate': np.random.uniform(0.6, 0.95, len(modules))
        }

        return pd.DataFrame(data)

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
