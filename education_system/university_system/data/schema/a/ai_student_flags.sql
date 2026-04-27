CREATE TABLE IF NOT EXISTS ai_student_flags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        flag_reason TEXT,
        flagged_by TEXT,
        flagged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'active',
        resolved_at TIMESTAMP,
        resolution_notes TEXT
    );
