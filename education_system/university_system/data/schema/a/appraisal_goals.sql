CREATE TABLE IF NOT EXISTS appraisal_goals (
                    goal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    cycle_id INTEGER,
                    title TEXT NOT NULL,
                    description TEXT,
                    category TEXT DEFAULT 'performance',
                    target_date TEXT,
                    progress INTEGER DEFAULT 0,
                    weight REAL DEFAULT 1.0,
                    status TEXT DEFAULT 'active',
                    completion_notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (cycle_id) REFERENCES appraisal_cycles(cycle_id)
                );
