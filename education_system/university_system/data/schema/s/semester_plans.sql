CREATE TABLE IF NOT EXISTS semester_plans (
                        plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        plan_name TEXT NOT NULL,
                        program_code TEXT,
                        start_semester TEXT NOT NULL,
                        total_semesters INTEGER DEFAULT 8,
                        credits_per_semester INTEGER DEFAULT 15,
                        include_summer BOOLEAN DEFAULT 0,
                        status TEXT DEFAULT 'Draft',
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    );
