CREATE TABLE IF NOT EXISTS progress_snapshots (
                    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    semester TEXT NOT NULL,
                    overall_gpa REAL DEFAULT 0.0,
                    semester_gpa REAL DEFAULT 0.0,
                    total_credits INTEGER DEFAULT 0,
                    credits_this_semester INTEGER DEFAULT 0,
                    degree_completion_percentage REAL DEFAULT 0.0,
                    class_standing TEXT,
                    academic_status TEXT DEFAULT 'Good Standing',
                    warnings_count INTEGER DEFAULT 0,
                    snapshot_date TEXT DEFAULT CURRENT_TIMESTAMP
                );
