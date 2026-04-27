CREATE TABLE IF NOT EXISTS workload_norms (
                    norm_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    department TEXT,
                    role TEXT,
                    teaching_pct REAL DEFAULT 40,
                    research_pct REAL DEFAULT 40,
                    admin_pct REAL DEFAULT 10,
                    service_pct REAL DEFAULT 10,
                    total_hours_per_week REAL DEFAULT 40,
                    is_default INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
