CREATE TABLE IF NOT EXISTS plan_schedule_conflicts (
                    conflict_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id INTEGER NOT NULL,
                    conflict_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    description TEXT NOT NULL,
                    affected_courses_json TEXT,
                    affected_semester INTEGER,
                    resolution_suggestions_json TEXT,
                    is_resolved BOOLEAN DEFAULT 0,
                    detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (plan_id) REFERENCES semester_plans(plan_id) ON DELETE CASCADE
                );
