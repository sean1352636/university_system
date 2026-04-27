CREATE TABLE IF NOT EXISTS schedule_conflicts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conflict_type TEXT,
                    description TEXT,
                    affected_schedules TEXT,
                    resolved BOOLEAN DEFAULT 0,
                    resolution_notes TEXT,
                    detected_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved_date TIMESTAMP
                );
