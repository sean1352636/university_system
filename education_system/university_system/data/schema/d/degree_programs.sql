CREATE TABLE IF NOT EXISTS degree_programs (
                program_id INTEGER PRIMARY KEY AUTOINCREMENT,
                program_code TEXT UNIQUE NOT NULL,
                program_name TEXT NOT NULL,
                degree_type TEXT NOT NULL,
                department TEXT,
                total_credits_required INTEGER NOT NULL,
                min_gpa_required REAL DEFAULT 2.0,
                max_years_allowed INTEGER DEFAULT 4,
                description TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            , "updated_at" TIMESTAMP DEFAULT NULL);
