"""
Database schema initialization for Course Evaluation System
"""

from university_system.infrastructure.database.db import transaction


def initialize_evaluation_database():
    """Initialize all database tables for the Course Evaluation System"""

    with transaction() as conn:
        cursor = conn.cursor()

        # Evaluation Templates Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_templates (
                template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_name TEXT NOT NULL,
                template_type TEXT NOT NULL,
                description TEXT,
                created_by TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                is_active INTEGER DEFAULT 1
            )
        ''')

        # Evaluation Questions Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_questions (
                question_id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id INTEGER NOT NULL,
                question_text TEXT NOT NULL,
                question_type TEXT NOT NULL,
                question_category TEXT,
                scale_min INTEGER DEFAULT 1,
                scale_max INTEGER DEFAULT 5,
                display_order INTEGER DEFAULT 0,
                is_required INTEGER DEFAULT 1,
                FOREIGN KEY (template_id) REFERENCES evaluation_templates(template_id) ON DELETE CASCADE
            )
        ''')

        # Course Evaluations Table
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
                response_count INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (template_id) REFERENCES evaluation_templates(template_id)
            )
        ''')

        # Evaluation Responses Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_responses (
                response_id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluation_id INTEGER NOT NULL,
                student_id TEXT,
                is_complete INTEGER DEFAULT 0,
                is_anonymous INTEGER DEFAULT 1,
                time_taken_minutes INTEGER,
                submitted_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (evaluation_id) REFERENCES course_evaluations(evaluation_id) ON DELETE CASCADE
            )
        ''')

        # Evaluation Answers Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_answers (
                answer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                response_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                answer_value TEXT,
                numeric_value REAL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (response_id) REFERENCES evaluation_responses(response_id) ON DELETE CASCADE,
                FOREIGN KEY (question_id) REFERENCES evaluation_questions(question_id) ON DELETE CASCADE
            )
        ''')

        # Evaluation Results Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_results (
                result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluation_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                average_score REAL,
                response_count INTEGER,
                calculated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (evaluation_id) REFERENCES course_evaluations(evaluation_id) ON DELETE CASCADE,
                FOREIGN KEY (question_id) REFERENCES evaluation_questions(question_id) ON DELETE CASCADE,
                UNIQUE(evaluation_id, question_id)
            )
        ''')

        # Create indexes for better performance
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_eval_module
            ON course_evaluations(module_code, academic_year, semester)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_eval_instructor
            ON course_evaluations(instructor_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_response_evaluation
            ON evaluation_responses(evaluation_id)
        ''')

        print("✅ Course Evaluation database schema initialized successfully")


__all__ = ['initialize_evaluation_database']
