CREATE TABLE IF NOT EXISTS print_quotas (
                    quota_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL UNIQUE,
                    total_pages INTEGER DEFAULT 500,
                    used_pages INTEGER DEFAULT 0,
                    color_pages_used INTEGER DEFAULT 0,
                    semester TEXT DEFAULT '',
                    last_reset TEXT DEFAULT (date('now'))
                );
