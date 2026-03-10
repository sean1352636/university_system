from __future__ import annotations
from datetime import datetime
from education_system.university_system.infrastructure.database.db import get_connection, sqlite3
from education_system.university_system.core.i18n import get_text as _t, init_i18n

# Initialize i18n
init_i18n()

def init_lms_system_db():
    """Initialize the Learning Management System database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="LMS system"))

        # Courses table (extends existing courses)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lms_courses (
            lms_course_id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT NOT NULL,
            instructor_id TEXT NOT NULL,
            course_description TEXT,
            syllabus_url TEXT,
            start_date TEXT,
            end_date TEXT,
            is_published BOOLEAN DEFAULT 0,
            enrollment_limit INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')

        # Course content/materials
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lms_course_content (
            content_id INTEGER PRIMARY KEY AUTOINCREMENT,
            lms_course_id INTEGER NOT NULL,
            content_type TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            content_url TEXT,
            content_order INTEGER DEFAULT 0,
            is_published BOOLEAN DEFAULT 1,
            release_date TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lms_course_id) REFERENCES lms_courses (lms_course_id)
        )
        ''')

        # Video lectures
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lms_video_lectures (
            video_id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id INTEGER NOT NULL,
            video_url TEXT NOT NULL,
            duration_minutes INTEGER,
            thumbnail_url TEXT,
            transcript_url TEXT,
            video_quality TEXT DEFAULT '720p',
            view_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (content_id) REFERENCES lms_course_content (content_id)
        )
        ''')

        # Discussion forums
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lms_discussion_forums (
            forum_id INTEGER PRIMARY KEY AUTOINCREMENT,
            lms_course_id INTEGER NOT NULL,
            topic TEXT NOT NULL,
            description TEXT,
            created_by TEXT NOT NULL,
            is_pinned BOOLEAN DEFAULT 0,
            is_locked BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lms_course_id) REFERENCES lms_courses (lms_course_id)
        )
        ''')

        # Discussion posts
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lms_discussion_posts (
            post_id INTEGER PRIMARY KEY AUTOINCREMENT,
            forum_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            parent_post_id INTEGER,
            content TEXT NOT NULL,
            attachments TEXT,
            likes_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (forum_id) REFERENCES lms_discussion_forums (forum_id),
            FOREIGN KEY (parent_post_id) REFERENCES lms_discussion_posts (post_id)
        )
        ''')

        # Quizzes
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lms_quizzes (
            quiz_id INTEGER PRIMARY KEY AUTOINCREMENT,
            lms_course_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            duration_minutes INTEGER,
            passing_score DECIMAL(5,2),
            max_attempts INTEGER DEFAULT 1,
            randomize_questions BOOLEAN DEFAULT 0,
            show_correct_answers BOOLEAN DEFAULT 1,
            available_from TEXT,
            available_until TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lms_course_id) REFERENCES lms_courses (lms_course_id)
        )
        ''')

        # Quiz questions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lms_quiz_questions (
            question_id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            question_type TEXT NOT NULL,
            points INTEGER DEFAULT 1,
            correct_answer TEXT NOT NULL,
            options TEXT,
            explanation TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (quiz_id) REFERENCES lms_quizzes (quiz_id)
        )
        ''')

        # Quiz submissions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lms_quiz_submissions (
            submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            attempt_number INTEGER NOT NULL,
            score DECIMAL(5,2),
            total_points INTEGER,
            time_taken_minutes INTEGER,
            submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            graded_at TEXT,
            graded_by TEXT,
            FOREIGN KEY (quiz_id) REFERENCES lms_quizzes (quiz_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Gradebook entries
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lms_gradebook (
            grade_entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
            lms_course_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            assignment_type TEXT NOT NULL,
            assignment_id INTEGER,
            score DECIMAL(5,2),
            max_score DECIMAL(5,2),
            weight DECIMAL(5,2) DEFAULT 1.0,
            feedback TEXT,
            graded_by TEXT,
            graded_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lms_course_id) REFERENCES lms_courses (lms_course_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="LMS system"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="LMS system", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# ADVANCED ATTENDANCE SYSTEM SCHEMAS
# ============================================================================


