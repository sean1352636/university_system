CREATE TABLE IF NOT EXISTS student_supervisions (
                supervision_id INTEGER PRIMARY KEY AUTOINCREMENT,
                supervisor_id TEXT NOT NULL,
                student_id TEXT NOT NULL,
                student_name TEXT,
                program_type TEXT,
                thesis_title TEXT,
                start_date TEXT,
                expected_end_date TEXT,
                actual_end_date TEXT,
                status TEXT DEFAULT 'active',
                supervision_role TEXT DEFAULT 'primary',
                progress_notes TEXT,
                milestones TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
