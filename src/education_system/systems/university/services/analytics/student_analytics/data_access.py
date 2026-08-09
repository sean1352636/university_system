"""Data access and simulation methods for StudentAnalytics."""

import numpy as np
from education_system.systems.university.infrastructure.database.db import sqlite3


class DataAccessMixin:
    def get_all_students(self, filters=None):
        """Retrieve all student records with optional filtering"""
        import pandas as pd
        try:
            conn = self.get_connection()
            query = "SELECT * FROM students"
            params = []

            if filters:
                conditions = []
                for field, value in filters.items():
                    if field == 'age_range':
                        conditions.append("age BETWEEN ? AND ?")
                        params.extend(value)
                    elif field == 'date_range':
                        conditions.append("registration_datetime BETWEEN ? AND ?")
                        params.extend(value)
                    elif isinstance(value, list):
                        placeholders = ','.join(['?' for _ in value])
                        conditions.append(f"{field} IN ({placeholders})")
                        params.extend(value)
                    else:
                        conditions.append(f"{field} = ?")
                        params.append(value)

                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

            students_df = pd.read_sql_query(query, conn, params=params)
            conn.close()

            # Simulate additional data fields for enhanced analytics
            if not students_df.empty:
                students_df = self.simulate_additional_data(students_df)

            return students_df
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return pd.DataFrame()

    def simulate_additional_data(self, df):
        """Simulate additional data fields for demonstration"""
        np.random.seed(42)
        n = len(df)

        # Simulate grades (A-F scale)
        grades = np.random.choice(['A', 'B', 'C', 'D', 'F'], n, p=[0.2, 0.3, 0.3, 0.15, 0.05])
        df['overall_grade'] = grades

        # Simulate GPA (0.0-4.0)
        grade_mapping = {'A': 4.0, 'B': 3.0, 'C': 2.0, 'D': 1.0, 'F': 0.0}
        df['gpa'] = df['overall_grade'].map(grade_mapping) + np.random.normal(0, 0.3, n)
        df['gpa'] = np.clip(df['gpa'], 0.0, 4.0)

        # Simulate completion status
        df['completion_status'] = np.random.choice(['Active', 'Completed', 'Dropped', 'On Hold'],
                                                  n, p=[0.6, 0.25, 0.1, 0.05])

        # Simulate engagement score (0-100)
        df['engagement_score'] = np.random.beta(2, 2, n) * 100

        # Simulate location data
        locations = ['London', 'Manchester', 'Birmingham', 'Leeds', 'Liverpool', 'Bristol']
        df['location'] = np.random.choice(locations, n)

        # Simulate previous education
        education_levels = ['High School', 'Bachelor', 'Master', 'PhD', 'Professional']
        df['previous_education'] = np.random.choice(education_levels, n, p=[0.4, 0.3, 0.2, 0.05, 0.05])

        return df

    def get_all_modules(self, filters=None):
        """Retrieve all module assignments with optional filtering"""
        import pandas as pd
        try:
            conn = self.get_connection()
            query = """
            SELECT sm.id, sm.student_id, sm.module_code, sm.enrollment_date,
                   sm.grade, sm.completion_date, sm.status,
                   s.course, s.age, s.gender,
                   m.module_name, m.module_type, m.credits, m.department
            FROM student_modules sm
            JOIN students s ON sm.student_id = s.student_id
            LEFT JOIN modules m ON sm.module_code = m.module_code
            """
            params = []

            if filters:
                conditions = []
                for field, value in filters.items():
                    if field in ['course', 'age', 'gender']:
                        conditions.append(f"s.{field} = ?")
                        params.append(value)
                    elif field in ['module_name', 'module_type', 'department']:
                        conditions.append(f"m.{field} = ?")
                        params.append(value)
                    else:
                        conditions.append(f"sm.{field} = ?")
                        params.append(value)

                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

            modules_df = pd.read_sql_query(query, conn, params=params)
            conn.close()

            # Simulate additional module data only for missing columns
            if not modules_df.empty:
                modules_df = self.simulate_module_data(modules_df)

            return modules_df
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return pd.DataFrame()

    def simulate_module_data(self, df):
        """Add only missing columns based on actual database data"""
        n = len(df)

        # Only add module_grade if missing and try to derive from status
        if 'module_grade' not in df.columns:
            if 'status' in df.columns:
                # Map status to grades where possible
                grade_map = {'Completed': 'B', 'In Progress': 'C', 'Failed': 'F'}
                df['module_grade'] = df['status'].map(grade_map).fillna('C')
            else:
                # Last resort: use placeholder
                df['module_grade'] = 'B'

        # Only add module_completion if missing
        if 'module_completion' not in df.columns:
            if 'status' in df.columns:
                df['module_completion'] = df['status']
            else:
                df['module_completion'] = 'Completed'

        # Only add module_type if missing from modules join
        if 'module_type' not in df.columns:
            df['module_type'] = 'Standard'
        else:
            # Fill any NaN values with 'Standard'
            df['module_type'] = df['module_type'].fillna('Standard')

        # Only add difficulty_rating if missing
        if 'difficulty_rating' not in df.columns:
            df['difficulty_rating'] = 3  # Medium difficulty default

        # Only add attendance_rate if missing
        if 'attendance_rate' not in df.columns:
            df['attendance_rate'] = 85.0  # Default good attendance

        return df
