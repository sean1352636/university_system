CREATE TABLE IF NOT EXISTS workload_allocations (
                    allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    academic_year TEXT NOT NULL,
                    semester TEXT,
                    activity_name TEXT NOT NULL,
                    activity_type TEXT NOT NULL DEFAULT 'teaching',
                    hours_per_week REAL DEFAULT 0,
                    weighting_factor REAL DEFAULT 1.0,
                    weighted_hours REAL DEFAULT 0,
                    notes TEXT,
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
