from education_system.university_system.infrastructure.database.db import sqlite3, get_connection


def init_enhanced_grades_db():
    """Initialize the enhanced grades database with all required tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Create base grade tables if they don't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS grades (
            grade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            assessment_id INTEGER,
            score REAL,
            letter_grade TEXT,
            submission_date TEXT,
            comments TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS module_grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            module_code TEXT,
            final_score REAL,
            final_grade TEXT,
            completion_date TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')

        # 1. Grade Curve Analysis Tables
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS grade_statistics (
            stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id INTEGER,
            mean REAL,
            median REAL,
            std_dev REAL,
            min_score REAL,
            max_score REAL,
            q1 REAL,
            q3 REAL,
            skewness REAL,
            kurtosis REAL,
            date_calculated TEXT,
            FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS normalized_grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grade_id INTEGER,
            z_score REAL,
            percentile REAL,
            curved_score REAL,
            curved_letter TEXT,
            FOREIGN KEY (grade_id) REFERENCES grades (grade_id)
        )
        ''')

        # 2. Learning Outcome Tracking Tables
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS learning_outcomes (
            outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
            course TEXT,
            outcome_code TEXT,
            description TEXT,
            category TEXT,
            importance INTEGER
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS assessment_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id INTEGER,
            outcome_id INTEGER,
            weight REAL,
            FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id),
            FOREIGN KEY (outcome_id) REFERENCES learning_outcomes (outcome_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS outcome_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            outcome_id INTEGER,
            achievement_level REAL,
            evidence TEXT,
            date_assessed TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (outcome_id) REFERENCES learning_outcomes (outcome_id)
        )
        ''')

        # 3. Competency-Based Assessment Tables
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS competencies (
            competency_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            category TEXT
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS competency_levels (
            level_id INTEGER PRIMARY KEY AUTOINCREMENT,
            competency_id INTEGER,
            level_name TEXT,
            level_value INTEGER,
            description TEXT,
            FOREIGN KEY (competency_id) REFERENCES competencies (competency_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS assessment_competencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id INTEGER,
            competency_id INTEGER,
            weight REAL,
            FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id),
            FOREIGN KEY (competency_id) REFERENCES competencies (competency_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_competencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            competency_id INTEGER,
            level_id INTEGER,
            evidence TEXT,
            assessment_date TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (competency_id) REFERENCES competencies (competency_id),
            FOREIGN KEY (level_id) REFERENCES competency_levels (level_id)
        )
        ''')

        # 4. Predictive Analytics Tables
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS risk_factors (
            factor_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            weight REAL
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_risk_assessment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            risk_score REAL,
            risk_level TEXT,
            assessment_date TEXT,
            prediction_model TEXT,
            confidence REAL,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS risk_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            risk_assessment_id INTEGER,
            factor_id INTEGER,
            factor_value REAL,
            factor_contribution REAL,
            FOREIGN KEY (risk_assessment_id) REFERENCES student_risk_assessment (id),
            FOREIGN KEY (factor_id) REFERENCES risk_factors (factor_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS intervention_types (
            type_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS recommended_interventions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            risk_assessment_id INTEGER,
            intervention_type_id INTEGER,
            priority INTEGER,
            notes TEXT,
            FOREIGN KEY (risk_assessment_id) REFERENCES student_risk_assessment (id),
            FOREIGN KEY (intervention_type_id) REFERENCES intervention_types (type_id)
        )
        ''')

        # Insert default risk factors if they don't exist
        cursor.execute('SELECT COUNT(*) FROM risk_factors')
        if cursor.fetchone()[0] == 0:
            risk_factors = [
                ('Low GPA', 'Overall GPA below 2.0', 1.0),
                ('Failed Assessments', 'Multiple failed assessments', 0.8),
                ('Missed Submissions', 'Assignments not submitted', 0.7),
                ('Late Submissions', 'Consistently late submissions', 0.5),
                ('Low Attendance', 'Poor attendance record', 0.6),
                ('Declining Performance', 'Grades dropping over time', 0.7)
            ]
            cursor.executemany('''
            INSERT INTO risk_factors (name, description, weight)
            VALUES (?, ?, ?)
            ''', risk_factors)

        # Insert default intervention types if they don't exist
        cursor.execute('SELECT COUNT(*) FROM intervention_types')
        if cursor.fetchone()[0] == 0:
            intervention_types = [
                ('Academic Advising', 'Schedule a meeting with academic advisor'),
                ('Tutoring', 'Recommend tutoring sessions for specific subjects'),
                ('Study Skills Workshop', 'Workshop on time management and study techniques'),
                ('Mentoring', 'Pair with a peer mentor or faculty mentor'),
                ('Counseling', 'Refer to academic or personal counseling services'),
                ('Modified Schedule', 'Suggest course load reduction or schedule adjustment')
            ]
            cursor.executemany('''
            INSERT INTO intervention_types (name, description)
            VALUES (?, ?)
            ''', intervention_types)

        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
