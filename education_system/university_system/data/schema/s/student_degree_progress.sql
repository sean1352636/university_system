CREATE TABLE IF NOT EXISTS student_degree_progress (
                progress_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                program_id INTEGER NOT NULL,
                enrollment_year INTEGER NOT NULL,
                total_credits_earned INTEGER DEFAULT 0,
                current_gpa REAL DEFAULT 0.0,
                completion_percentage REAL DEFAULT 0.0,
                expected_graduation_date TEXT,
                last_updated TEXT NOT NULL DEFAULT (datetime('now')), "status" TEXT DEFAULT 'in_progress',
                FOREIGN KEY (program_id) REFERENCES degree_programs(program_id),
                UNIQUE(student_id, program_id)
            );
