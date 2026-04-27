CREATE TABLE IF NOT EXISTS teaching_assistants (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        instructor_id TEXT NOT NULL,
                        module_code TEXT NOT NULL,
                        role_type TEXT DEFAULT 'ta',
                        hours_per_week REAL DEFAULT 10,
                        status TEXT DEFAULT 'active',
                        start_date TEXT DEFAULT CURRENT_TIMESTAMP,
                        end_date TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(student_id, module_code)
                    );
