CREATE TABLE IF NOT EXISTS attendance_policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            policy_id TEXT UNIQUE,
            name TEXT,
            description TEXT,
            module_code TEXT,
            course TEXT,
            min_attendance_percentage REAL,
            max_consecutive_absences INTEGER,
            late_tolerance_minutes INTEGER DEFAULT 15,
            makeup_allowed BOOLEAN DEFAULT 1,
            auto_fail_threshold REAL,
            grace_period_days INTEGER DEFAULT 0,
            effective_from TEXT,
            effective_until TEXT,
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active'
        );
