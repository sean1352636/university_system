CREATE TABLE IF NOT EXISTS degree_milestones (
                    milestone_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    program_code TEXT NOT NULL,
                    milestone_name TEXT NOT NULL,
                    milestone_type TEXT NOT NULL,
                    required_credits INTEGER DEFAULT 0,
                    required_gpa REAL DEFAULT 0.0,
                    typical_semester INTEGER DEFAULT 1,
                    description TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
