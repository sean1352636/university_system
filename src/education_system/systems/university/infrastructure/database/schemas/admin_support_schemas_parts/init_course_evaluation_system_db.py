"""Extracted function implementation."""

from .. import admin_support_schemas_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def init_course_evaluation_system_db():
    """Initialize the Course Evaluation System database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="Course Evaluation System"))

        # Evaluation templates
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS evaluation_templates (
            template_id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_name TEXT NOT NULL,
            template_type TEXT NOT NULL,
            description TEXT,
            is_default BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Evaluation questions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS evaluation_questions (
            question_id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            question_type TEXT NOT NULL,
            question_category TEXT NOT NULL,
            is_required BOOLEAN DEFAULT 1,
            scale_min INTEGER,
            scale_max INTEGER,
            options TEXT,
            display_order INTEGER,
            FOREIGN KEY (template_id) REFERENCES evaluation_templates (template_id)
        )
        ''')

        # Course evaluations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS course_evaluations (
            evaluation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT NOT NULL,
            academic_year TEXT NOT NULL,
            semester TEXT NOT NULL,
            instructor_id TEXT NOT NULL,
            template_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            is_anonymous BOOLEAN DEFAULT 1,
            is_active BOOLEAN DEFAULT 1,
            response_count INTEGER DEFAULT 0,
            completion_rate REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (template_id) REFERENCES evaluation_templates (template_id)
        )
        ''')

        # Evaluation responses
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS evaluation_responses (
            response_id INTEGER PRIMARY KEY AUTOINCREMENT,
            evaluation_id INTEGER NOT NULL,
            student_id TEXT,
            response_date TEXT DEFAULT CURRENT_TIMESTAMP,
            is_complete BOOLEAN DEFAULT 0,
            time_taken_minutes INTEGER,
            FOREIGN KEY (evaluation_id) REFERENCES course_evaluations (evaluation_id)
        )
        ''')

        # Response answers
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS evaluation_answers (
            answer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            response_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            answer_value TEXT,
            numeric_value REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (response_id) REFERENCES evaluation_responses (response_id),
            FOREIGN KEY (question_id) REFERENCES evaluation_questions (question_id)
        )
        ''')

        # Evaluation results/analytics
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS evaluation_results (
            result_id INTEGER PRIMARY KEY AUTOINCREMENT,
            evaluation_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            average_score REAL,
            median_score REAL,
            mode_score REAL,
            standard_deviation REAL,
            response_count INTEGER,
            percentile_25 REAL,
            percentile_75 REAL,
            calculated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (evaluation_id) REFERENCES course_evaluations (evaluation_id),
            FOREIGN KEY (question_id) REFERENCES evaluation_questions (question_id)
        )
        ''')

        # Instructor performance tracking
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS instructor_performance_history (
            performance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            instructor_id TEXT NOT NULL,
            academic_year TEXT NOT NULL,
            semester TEXT NOT NULL,
            avg_overall_rating REAL,
            avg_teaching_effectiveness REAL,
            avg_course_organization REAL,
            avg_student_engagement REAL,
            total_evaluations INTEGER,
            total_responses INTEGER,
            calculated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="Course Evaluation System"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="Course Evaluation", error=str(e)))
        if 'conn' in locals():
            conn.close()
