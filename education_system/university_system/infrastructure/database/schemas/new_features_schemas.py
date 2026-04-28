"""Schema definitions for new university features: assignments, student finance, wellbeing, LMS."""


def get_new_features_tables():
    return {
        "assignments": """
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_id TEXT,
                title TEXT NOT NULL,
                description TEXT,
                due_date TEXT,
                max_marks INTEGER DEFAULT 100,
                assignment_type TEXT DEFAULT 'essay',
                created_by TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """,
        "assignment_submissions": """
            CREATE TABLE IF NOT EXISTS assignment_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assignment_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                submission_text TEXT,
                file_path TEXT,
                submitted_at TEXT DEFAULT (datetime('now')),
                is_late INTEGER DEFAULT 0
            )
        """,
        "submission_grades": """
            CREATE TABLE IF NOT EXISTS submission_grades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,
                marks INTEGER,
                feedback TEXT,
                graded_by TEXT,
                graded_at TEXT DEFAULT (datetime('now'))
            )
        """,
        "student_fees": """
            CREATE TABLE IF NOT EXISTS student_fees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                fee_type TEXT NOT NULL,
                amount REAL NOT NULL,
                due_date TEXT,
                description TEXT,
                status TEXT DEFAULT 'unpaid',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """,
        "student_payments": """
            CREATE TABLE IF NOT EXISTS student_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fee_id INTEGER,
                student_id TEXT NOT NULL,
                amount_paid REAL NOT NULL,
                payment_method TEXT,
                reference TEXT,
                payment_date TEXT DEFAULT (date('now'))
            )
        """,
        "scholarships": """
            CREATE TABLE IF NOT EXISTS scholarships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                name TEXT NOT NULL,
                amount REAL NOT NULL,
                academic_year TEXT,
                status TEXT DEFAULT 'active',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """,
        "wellbeing_referrals": """
            CREATE TABLE IF NOT EXISTS wellbeing_referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                referred_by TEXT NOT NULL,
                concern_type TEXT NOT NULL,
                description TEXT,
                urgency TEXT DEFAULT 'normal',
                status TEXT DEFAULT 'open',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """,
        "wellbeing_checkins": """
            CREATE TABLE IF NOT EXISTS wellbeing_checkins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                mood_rating INTEGER,
                notes TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """,
        "counselling_sessions": """
            CREATE TABLE IF NOT EXISTS counselling_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                counsellor TEXT,
                session_date TEXT,
                notes TEXT,
                outcome TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """,
        # Must match the canonical definition in
        # modules/domain/student_affairs/student_id/services/student_id_service.py.
        # The runtime INSERTs only supply (student_id, card_number,
        # expiry_date, qr_data), so any extra columns must be nullable
        # or have defaults. The earlier schema with `full_name NOT NULL`
        # would have rejected every insert from the actual service.
        "student_id_cards": """
            CREATE TABLE IF NOT EXISTS student_id_cards (
                card_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL UNIQUE,
                card_number TEXT NOT NULL,
                issue_date TEXT DEFAULT (date('now')),
                expiry_date TEXT,
                status TEXT DEFAULT 'active',
                photo_path TEXT DEFAULT '',
                qr_data TEXT DEFAULT ''
            )
        """,
        "lms_modules": """CREATE TABLE IF NOT EXISTS lms_modules (id INTEGER PRIMARY KEY AUTOINCREMENT, course_id TEXT, title TEXT NOT NULL, description TEXT, order_index INTEGER DEFAULT 0, published INTEGER DEFAULT 0, created_by TEXT, created_at TEXT DEFAULT (datetime('now')))""",
        "lms_lessons": """CREATE TABLE IF NOT EXISTS lms_lessons (id INTEGER PRIMARY KEY AUTOINCREMENT, module_id INTEGER NOT NULL, title TEXT NOT NULL, content_type TEXT DEFAULT 'text', content TEXT, order_index INTEGER DEFAULT 0, duration_mins INTEGER, created_at TEXT DEFAULT (datetime('now')))""",
        "lms_progress": """CREATE TABLE IF NOT EXISTS lms_progress (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL, lesson_id INTEGER NOT NULL, completed INTEGER DEFAULT 0, completed_at TEXT)""",
        "lms_quizzes": """CREATE TABLE IF NOT EXISTS lms_quizzes (id INTEGER PRIMARY KEY AUTOINCREMENT, lesson_id INTEGER NOT NULL, title TEXT NOT NULL, pass_mark INTEGER DEFAULT 50, time_limit_mins INTEGER, created_at TEXT DEFAULT (datetime('now')))""",
        "lms_questions": """CREATE TABLE IF NOT EXISTS lms_questions (id INTEGER PRIMARY KEY AUTOINCREMENT, quiz_id INTEGER NOT NULL, question_text TEXT NOT NULL, question_type TEXT DEFAULT 'multiple_choice', options_json TEXT, correct_answer TEXT NOT NULL, marks INTEGER DEFAULT 1, order_index INTEGER DEFAULT 0)""",
        "lms_quiz_attempts": """CREATE TABLE IF NOT EXISTS lms_quiz_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, quiz_id INTEGER NOT NULL, student_id TEXT NOT NULL, answers_json TEXT, score INTEGER, passed INTEGER DEFAULT 0, attempted_at TEXT DEFAULT (datetime('now')))""",
        "lms_resources": """CREATE TABLE IF NOT EXISTS lms_resources (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT, file_path TEXT, resource_type TEXT DEFAULT 'document', course_id TEXT, uploaded_by TEXT, download_count INTEGER DEFAULT 0, created_at TEXT DEFAULT (datetime('now')))""",
    }
