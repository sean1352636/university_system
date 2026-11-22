"""Data access methods for StudentAnalytics.

Every analytics column is derived from live tables (students, module_grades,
student_modules, modules, attendance_records). Nothing is simulated: where a
student has no underlying data the column is left NULL/NaN and the consumers
tolerate it.
"""

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.domains.assessment.domain.grading.grade_calculation.conversions import (
    letter_to_gpa,
    percentage_to_letter,
)

# attendance_records.status values counted as attended (case-insensitive)
_ATTENDED_STATUSES = ('present', 'late')


def _letter_bucket(letter):
    """Collapse a signed letter ('A+', 'B-') to the A-F bucket the dashboards use."""
    if letter is None or letter != letter:  # None or NaN
        return None
    letter = str(letter).strip().upper()
    return letter[0] if letter and letter[0] in 'ABCDF' else None


def _table_exists(conn, name):
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (name,)
        ).fetchone()
        return isinstance(row, tuple)
    except Exception:  # stubbed/closed connection: treat as absent
        return False


def _column_exists(conn, table, column):
    try:
        return any(r[1] == column for r in conn.execute(f"PRAGMA table_info({table})").fetchall())
    except Exception:  # stubbed/closed connection: treat as absent
        return False


def _frame_with(df, columns):
    """Return df only if it carries the expected columns, else an empty frame of them."""
    import pandas as pd
    if set(columns) <= set(df.columns):
        return df
    return pd.DataFrame(columns=columns)


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

            # Derive the analytics columns from the tables that actually hold the data
            if not students_df.empty:
                students_df = self.derive_additional_data(students_df, conn)
            conn.close()

            return students_df
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return pd.DataFrame()

    def derive_additional_data(self, df, conn):
        """Attach real per-student analytics columns.

        gpa               students.gpa, else mean GPA points of module_grades.final_grade
        overall_grade     A-F bucket of the mean module_grades.final_score
        completion_status students.status
        engagement_score  attendance percentage from attendance_records (NaN if none)
        previous_education students.entry_qualifications
        """
        import pandas as pd

        marks = _frame_with(pd.read_sql_query(
            "SELECT student_id, final_score, final_grade FROM module_grades "
            "WHERE final_score IS NOT NULL OR final_grade IS NOT NULL",
            conn,
        ), ['student_id', 'final_score', 'final_grade'])
        if not marks.empty:
            letters = marks['final_grade'].where(
                marks['final_grade'].notna(),
                marks['final_score'].map(lambda s: percentage_to_letter(s) if pd.notna(s) else None),
            )
            marks['gpa_points'] = letters.map(lambda L: letter_to_gpa(L) if L else None)
            per_student = marks.groupby('student_id').agg(
                avg_mark=('final_score', 'mean'), gpa_derived=('gpa_points', 'mean')
            )
            df = df.merge(per_student, left_on='student_id', right_index=True, how='left')
        else:
            df['avg_mark'] = float('nan')
            df['gpa_derived'] = float('nan')

        if 'gpa' in df.columns:
            df['gpa'] = df['gpa'].fillna(df['gpa_derived'])
        else:
            df['gpa'] = df['gpa_derived']
        df = df.drop(columns=['gpa_derived'])

        df['overall_grade'] = df['avg_mark'].map(
            lambda m: _letter_bucket(percentage_to_letter(m)) if pd.notna(m) else None
        )

        df['completion_status'] = df['status'] if 'status' in df.columns else None

        df['engagement_score'] = float('nan')
        if _table_exists(conn, 'attendance_records'):
            attendance = _frame_with(pd.read_sql_query(
                "SELECT student_id, "
                "100.0 * SUM(CASE WHEN lower(status) IN (?, ?) THEN 1 ELSE 0 END) / COUNT(*) "
                "AS engagement_score FROM attendance_records GROUP BY student_id",
                conn, params=_ATTENDED_STATUSES,
            ), ['student_id', 'engagement_score'])
            if not attendance.empty:
                df = df.drop(columns=['engagement_score']).merge(
                    attendance, on='student_id', how='left'
                )

        df['previous_education'] = (
            df['entry_qualifications'] if 'entry_qualifications' in df.columns else None
        )

        return df

    def simulate_additional_data(self, df, conn=None):
        """Deprecated name kept for existing callers; values are derived, not simulated."""
        own_conn = conn is None
        if own_conn:
            conn = self.get_connection()
        try:
            return self.derive_additional_data(df, conn)
        finally:
            if own_conn:
                conn.close()

    def get_all_modules(self, filters=None):
        """Retrieve all module enrolments with marks and attendance joined in."""
        import pandas as pd
        try:
            conn = self.get_connection()
            has_difficulty = _column_exists(conn, 'modules', 'difficulty_level')
            has_attendance = _table_exists(conn, 'attendance_records')

            difficulty_col = (
                "m.difficulty_level AS difficulty_rating" if has_difficulty
                else "NULL AS difficulty_rating"
            )
            attendance_col = "att.attendance_rate" if has_attendance else "NULL AS attendance_rate"
            attendance_join = (
                "LEFT JOIN (SELECT student_id, module_code, "
                "100.0 * SUM(CASE WHEN lower(status) IN (?, ?) THEN 1 ELSE 0 END) / COUNT(*) "
                "AS attendance_rate FROM attendance_records GROUP BY student_id, module_code) att "
                "ON att.student_id = sm.student_id AND att.module_code = sm.module_code"
            ) if has_attendance else ""

            query = f"""
            SELECT sm.id, sm.student_id, sm.module_code, sm.enrollment_date,
                   COALESCE(mg.final_grade, sm.grade) AS grade, mg.final_score,
                   sm.completion_date, sm.status,
                   s.course, s.age, s.gender,
                   m.module_name, m.module_type, m.credits, m.department,
                   {difficulty_col}, {attendance_col}
            FROM student_modules sm
            JOIN students s ON sm.student_id = s.student_id
            LEFT JOIN modules m ON sm.module_code = m.module_code
            LEFT JOIN (SELECT student_id, module_code, final_score, final_grade, MAX(id) AS id
                       FROM module_grades GROUP BY student_id, module_code) mg
                   ON mg.student_id = sm.student_id AND mg.module_code = sm.module_code
            {attendance_join}
            """
            params = list(_ATTENDED_STATUSES) if has_attendance else []

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

            if not modules_df.empty:
                modules_df = self.derive_module_data(modules_df)

            return modules_df
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return pd.DataFrame()

    def derive_module_data(self, df):
        """Add the per-enrolment analytics columns from the joined data.

        module_grade      A-F bucket of the recorded letter, else of final_score (NaN if neither)
        module_completion student_modules.status
        module_type       modules.module_type (DB default 'Standard' when unset)
        difficulty_rating modules.difficulty_level (NaN when unset)
        attendance_rate   attendance_records percentage for the enrolment (NaN when none)
        """
        import pandas as pd

        for col in ('grade', 'final_score', 'status', 'module_type',
                    'difficulty_rating', 'attendance_rate'):
            if col not in df.columns:
                df[col] = None
        letters = df['grade'].where(
            df['grade'].notna(),
            df['final_score'].map(lambda s: percentage_to_letter(s) if pd.notna(s) else None),
        )
        df['module_grade'] = letters.map(_letter_bucket)
        df['module_completion'] = df['status']
        df['module_type'] = df['module_type'].fillna('Standard')
        return df

    # Deprecated name kept for existing callers; values are derived, not simulated.
    simulate_module_data = derive_module_data
