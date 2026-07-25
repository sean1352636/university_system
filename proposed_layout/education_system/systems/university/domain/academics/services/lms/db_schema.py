"""
Database schema initialization for Learning Management System (LMS)
"""

from education_system.systems.university.infrastructure.database.db import transaction


def initialize_lms_database():
    """Initialize all database tables for the LMS"""

    with transaction() as conn:
        cursor = conn.cursor()

        # LMS Courses Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lms_courses (
                lms_course_id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_code TEXT NOT NULL,
                instructor_id TEXT NOT NULL,
                course_description TEXT,
                syllabus_url TEXT,
                start_date TEXT,
                end_date TEXT,
                enrollment_limit INTEGER DEFAULT 0,
                is_published INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        ''')

        # Course Content Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lms_course_content (
                content_id INTEGER PRIMARY KEY AUTOINCREMENT,
                lms_course_id INTEGER NOT NULL,
                content_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                content_url TEXT,
                content_order INTEGER DEFAULT 0,
                release_date TEXT,
                is_published INTEGER DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (lms_course_id) REFERENCES lms_courses(lms_course_id) ON DELETE CASCADE
            )
        ''')

        # Video Lectures Table
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
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (content_id) REFERENCES lms_course_content(content_id) ON DELETE CASCADE
            )
        ''')

        # Discussion Forums Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lms_discussion_forums (
                forum_id INTEGER PRIMARY KEY AUTOINCREMENT,
                lms_course_id INTEGER NOT NULL,
                topic TEXT NOT NULL,
                description TEXT,
                created_by TEXT NOT NULL,
                is_pinned INTEGER DEFAULT 0,
                is_locked INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (lms_course_id) REFERENCES lms_courses(lms_course_id) ON DELETE CASCADE
            )
        ''')

        # Discussion Posts Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lms_discussion_posts (
                post_id INTEGER PRIMARY KEY AUTOINCREMENT,
                forum_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                content TEXT NOT NULL,
                parent_post_id INTEGER,
                attachments TEXT,
                likes_count INTEGER DEFAULT 0,
                is_instructor_post INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (forum_id) REFERENCES lms_discussion_forums(forum_id) ON DELETE CASCADE,
                FOREIGN KEY (parent_post_id) REFERENCES lms_discussion_posts(post_id) ON DELETE CASCADE
            )
        ''')

        # Quizzes Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lms_quizzes (
                quiz_id INTEGER PRIMARY KEY AUTOINCREMENT,
                lms_course_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                duration_minutes INTEGER DEFAULT 60,
                passing_score REAL DEFAULT 70.0,
                max_attempts INTEGER DEFAULT 1,
                available_from TEXT,
                available_until TEXT,
                is_published INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (lms_course_id) REFERENCES lms_courses(lms_course_id) ON DELETE CASCADE
            )
        ''')

        # Quiz Questions Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lms_quiz_questions (
                question_id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id INTEGER NOT NULL,
                question_text TEXT NOT NULL,
                question_type TEXT NOT NULL,
                correct_answer TEXT NOT NULL,
                points INTEGER DEFAULT 1,
                options TEXT,
                explanation TEXT,
                display_order INTEGER DEFAULT 0,
                FOREIGN KEY (quiz_id) REFERENCES lms_quizzes(quiz_id) ON DELETE CASCADE
            )
        ''')

        # Quiz Submissions Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lms_quiz_submissions (
                submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                attempt_number INTEGER NOT NULL,
                score REAL NOT NULL,
                total_points INTEGER NOT NULL,
                time_taken_minutes INTEGER,
                submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (quiz_id) REFERENCES lms_quizzes(quiz_id) ON DELETE CASCADE
            )
        ''')

        # Gradebook Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lms_gradebook (
                entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                lms_course_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                assignment_type TEXT NOT NULL,
                assignment_id INTEGER,
                score REAL,
                max_score REAL,
                weight REAL DEFAULT 1.0,
                feedback TEXT,
                graded_by TEXT,
                graded_at TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (lms_course_id) REFERENCES lms_courses(lms_course_id) ON DELETE CASCADE
            )
        ''')

        # Student Course Enrollment (for LMS tracking)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lms_student_enrollment (
                enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                lms_course_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                enrollment_date TEXT NOT NULL DEFAULT (datetime('now')),
                last_accessed TEXT,
                progress_percentage REAL DEFAULT 0.0,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (lms_course_id) REFERENCES lms_courses(lms_course_id) ON DELETE CASCADE,
                UNIQUE(lms_course_id, student_id)
            )
        ''')

        # Create indexes
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_lms_course_instructor
            ON lms_courses(instructor_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_lms_content
            ON lms_course_content(lms_course_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_lms_forums
            ON lms_discussion_forums(lms_course_id)
        ''')


        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_lms_gradebook
            ON lms_gradebook(lms_course_id, student_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_lms_enrollment
            ON lms_student_enrollment(student_id)
        ''')

        print("✅ LMS database schema initialized successfully")


__all__ = ['initialize_lms_database']
