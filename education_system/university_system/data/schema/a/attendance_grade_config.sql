CREATE TABLE IF NOT EXISTS attendance_grade_config (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        module_code TEXT NOT NULL UNIQUE,
                        attendance_weight REAL NOT NULL DEFAULT 10.0,
                        min_attendance_pct REAL NOT NULL DEFAULT 75.0,
                        created_by TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    );
