CREATE TABLE IF NOT EXISTS intervention_sessions (
                    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    intervention_id INTEGER NOT NULL,
                    session_date TEXT NOT NULL,
                    duration_minutes INTEGER,
                    status TEXT DEFAULT 'attended',
                    notes TEXT,
                    recorded_by TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (intervention_id)
                        REFERENCES early_warning_interventions (intervention_id)
                );
