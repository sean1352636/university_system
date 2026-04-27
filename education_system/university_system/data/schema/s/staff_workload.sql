CREATE TABLE IF NOT EXISTS staff_workload (
                workload_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                academic_year TEXT NOT NULL,
                semester TEXT,
                teaching_hours REAL DEFAULT 0,
                research_hours REAL DEFAULT 0,
                admin_hours REAL DEFAULT 0,
                service_hours REAL DEFAULT 0,
                total_fte REAL DEFAULT 1.0,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, academic_year, semester)
            );
