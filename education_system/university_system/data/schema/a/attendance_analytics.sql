CREATE TABLE IF NOT EXISTS attendance_analytics (
            analytics_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            attendance_percentage REAL,
            consecutive_absences INTEGER
        , "attended_sessions" INTEGER DEFAULT 0, "last_updated" TEXT DEFAULT CURRENT_TIMESTAMP, "late_arrivals" INTEGER DEFAULT 0, "module_code" TEXT, "total_sessions" INTEGER DEFAULT 0);
