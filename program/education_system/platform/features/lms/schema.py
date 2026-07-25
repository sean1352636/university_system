"""LMS database schema — call create_lms_tables(conn) during each subsystem's
schema initialisation to add the shared LMS tables to that system's database."""

import logging

logger = logging.getLogger(__name__)

LMS_TABLES = {
    "lms_modules": """
        CREATE TABLE IF NOT EXISTS lms_modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            order_index INTEGER NOT NULL DEFAULT 0,
            published INTEGER NOT NULL DEFAULT 0,
            created_by TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "lms_lessons": """
        CREATE TABLE IF NOT EXISTS lms_lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content_type TEXT NOT NULL DEFAULT 'text',
            content TEXT,
            order_index INTEGER NOT NULL DEFAULT 0,
            duration_mins INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (module_id) REFERENCES lms_modules(id)
        )
    """,
    "lms_progress": """
        CREATE TABLE IF NOT EXISTS lms_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            lesson_id INTEGER NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            completed_at TEXT,
            FOREIGN KEY (lesson_id) REFERENCES lms_lessons(id),
            UNIQUE (student_id, lesson_id)
        )
    """,
    "lms_quizzes": """
        CREATE TABLE IF NOT EXISTS lms_quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            pass_mark REAL NOT NULL DEFAULT 50.0,
            time_limit_mins INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (lesson_id) REFERENCES lms_lessons(id)
        )
    """,
    "lms_questions": """
        CREATE TABLE IF NOT EXISTS lms_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            question_type TEXT NOT NULL DEFAULT 'multiple_choice',
            options_json TEXT,
            correct_answer TEXT NOT NULL,
            marks REAL NOT NULL DEFAULT 1.0,
            order_index INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (quiz_id) REFERENCES lms_quizzes(id)
        )
    """,
    "lms_quiz_attempts": """
        CREATE TABLE IF NOT EXISTS lms_quiz_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            answers_json TEXT,
            score REAL,
            passed INTEGER NOT NULL DEFAULT 0,
            attempted_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (quiz_id) REFERENCES lms_quizzes(id)
        )
    """,
    "lms_resources": """
        CREATE TABLE IF NOT EXISTS lms_resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            file_path TEXT,
            resource_type TEXT NOT NULL DEFAULT 'document',
            course_id INTEGER,
            uploaded_by TEXT,
            download_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "lms_courses": """
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
            updated_at TEXT
        )
    """,
    "lms_course_content": """
        CREATE TABLE IF NOT EXISTS lms_course_content (
            content_id INTEGER PRIMARY KEY AUTOINCREMENT,
            lms_course_id INTEGER NOT NULL,
            content_type TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            content_url TEXT,
            content_order INTEGER DEFAULT 0,
            release_date TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (lms_course_id) REFERENCES lms_courses(lms_course_id)
        )
    """,
    "lms_video_lectures": """
        CREATE TABLE IF NOT EXISTS lms_video_lectures (
            video_id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id INTEGER NOT NULL,
            video_url TEXT NOT NULL,
            duration_minutes INTEGER DEFAULT 0,
            thumbnail_url TEXT,
            transcript_url TEXT,
            video_quality TEXT DEFAULT '720p',
            views_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (content_id) REFERENCES lms_course_content(content_id)
        )
    """,
    "lms_discussion_forums": """
        CREATE TABLE IF NOT EXISTS lms_discussion_forums (
            forum_id INTEGER PRIMARY KEY AUTOINCREMENT,
            lms_course_id INTEGER NOT NULL,
            topic TEXT NOT NULL,
            description TEXT,
            created_by TEXT,
            is_pinned INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (lms_course_id) REFERENCES lms_courses(lms_course_id)
        )
    """,
    "lms_discussion_posts": """
        CREATE TABLE IF NOT EXISTS lms_discussion_posts (
            post_id INTEGER PRIMARY KEY AUTOINCREMENT,
            forum_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            content TEXT NOT NULL,
            parent_post_id INTEGER,
            likes_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (forum_id) REFERENCES lms_discussion_forums(forum_id)
        )
    """,
    "lms_student_enrollment": """
        CREATE TABLE IF NOT EXISTS lms_student_enrollment (
            enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            lms_course_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            enrolled_at TEXT NOT NULL DEFAULT (datetime('now')),
            last_accessed TEXT,
            progress_percent REAL DEFAULT 0,
            FOREIGN KEY (lms_course_id) REFERENCES lms_courses(lms_course_id),
            UNIQUE (lms_course_id, student_id)
        )
    """,
    "lms_gradebook": """
        CREATE TABLE IF NOT EXISTS lms_gradebook (
            entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
            lms_course_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            assignment_type TEXT NOT NULL,
            assignment_id INTEGER,
            score REAL NOT NULL,
            max_score REAL NOT NULL,
            weight REAL NOT NULL DEFAULT 1.0,
            feedback TEXT,
            graded_by TEXT,
            graded_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (lms_course_id) REFERENCES lms_courses(lms_course_id)
        )
    """,
}

LMS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_lms_lessons_module ON lms_lessons(module_id)",
    "CREATE INDEX IF NOT EXISTS idx_lms_progress_student ON lms_progress(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_lms_progress_lesson ON lms_progress(lesson_id)",
    "CREATE INDEX IF NOT EXISTS idx_lms_questions_quiz ON lms_questions(quiz_id)",
    "CREATE INDEX IF NOT EXISTS idx_lms_attempts_quiz ON lms_quiz_attempts(quiz_id)",
    "CREATE INDEX IF NOT EXISTS idx_lms_attempts_student ON lms_quiz_attempts(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_lms_resources_course ON lms_resources(course_id)",
    "CREATE INDEX IF NOT EXISTS idx_lms_modules_course ON lms_modules(course_id)",
    "CREATE INDEX IF NOT EXISTS idx_lms_course_instructor ON lms_courses(instructor_id)",
    "CREATE INDEX IF NOT EXISTS idx_lms_course_content ON lms_course_content(lms_course_id)",
    "CREATE INDEX IF NOT EXISTS idx_lms_forums_course ON lms_discussion_forums(lms_course_id)",
    "CREATE INDEX IF NOT EXISTS idx_lms_posts_forum ON lms_discussion_posts(forum_id)",
    "CREATE INDEX IF NOT EXISTS idx_lms_enrollment_student ON lms_student_enrollment(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_lms_gradebook_student ON lms_gradebook(lms_course_id, student_id)",
]


def create_lms_tables(conn):
    """Create all LMS tables and indexes on the given connection.

    Designed to be called from each subsystem's ``initialise_database`` /
    ``init_db`` function, passing the already-open connection so the LMS
    tables live in the same database as the rest of that system's data.
    """
    try:
        for table_name, ddl in LMS_TABLES.items():
            conn.execute(ddl)
            logger.debug("LMS table ensured: %s", table_name)

        for idx_sql in LMS_INDEXES:
            conn.execute(idx_sql)

        conn.commit()
        logger.info("LMS tables initialised successfully")
    except Exception as e:
        logger.error("Failed to create LMS tables: %s", e)
        raise
