CREATE TABLE IF NOT EXISTS timetable_configurations (
            config_id INTEGER PRIMARY KEY AUTOINCREMENT,
            academic_year TEXT NOT NULL,
            semester TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            optimization_status TEXT DEFAULT 'pending',
            last_optimized_date TEXT,
            conflicts_detected INTEGER DEFAULT 0,
            conflicts_resolved INTEGER DEFAULT 0,
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
