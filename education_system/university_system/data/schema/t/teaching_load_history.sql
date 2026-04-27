CREATE TABLE IF NOT EXISTS teaching_load_history (
                    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    academic_year TEXT NOT NULL,
                    semester TEXT NOT NULL,
                    total_courses INTEGER DEFAULT 0,
                    total_credits REAL DEFAULT 0,
                    total_contact_hours REAL DEFAULT 0,
                    total_weighted_hours REAL DEFAULT 0,
                    total_students INTEGER DEFAULT 0,
                    release_hours REAL DEFAULT 0,
                    net_load_credits REAL DEFAULT 0,
                    is_overloaded INTEGER DEFAULT 0,
                    overload_credits REAL DEFAULT 0,
                    snapshot_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, academic_year, semester)
                );
