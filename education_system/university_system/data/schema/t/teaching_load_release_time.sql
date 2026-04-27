CREATE TABLE IF NOT EXISTS teaching_load_release_time (
                    release_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    academic_year TEXT NOT NULL,
                    semester TEXT NOT NULL,
                    release_type TEXT DEFAULT 'other',
                    title TEXT NOT NULL,
                    hours_per_week REAL DEFAULT 0,
                    credit_equivalent REAL DEFAULT 0,
                    start_date TEXT,
                    end_date TEXT,
                    funding_source TEXT,
                    status TEXT DEFAULT 'pending',
                    approved_by TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
