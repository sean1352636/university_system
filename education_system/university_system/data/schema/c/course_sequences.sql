CREATE TABLE IF NOT EXISTS course_sequences (
                    sequence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sequence_name TEXT NOT NULL,
                    program_code TEXT,
                    sequence_type TEXT DEFAULT 'Linear',
                    courses_json TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
