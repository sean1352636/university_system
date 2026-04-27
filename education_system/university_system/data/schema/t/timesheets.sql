CREATE TABLE IF NOT EXISTS timesheets (
                    timesheet_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    week_start TEXT NOT NULL,
                    week_end TEXT NOT NULL,
                    total_hours REAL DEFAULT 0,
                    regular_hours REAL DEFAULT 0,
                    overtime_hours REAL DEFAULT 0,
                    status TEXT DEFAULT 'draft',
                    submitted_date TEXT,
                    approved_by TEXT,
                    approved_date TEXT,
                    rejection_reason TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, week_start)
                );
