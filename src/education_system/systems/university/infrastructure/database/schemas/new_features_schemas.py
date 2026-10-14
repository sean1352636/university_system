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
        # 8.117.102: ``student_payments`` removed. Audit confirmed
        # zero production writers — only an archive routine read from
        # it (now also gone) and a one-shot bootstrap script touched
        # it. The canonical payments ledger is the ``payments`` table.
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
    }
