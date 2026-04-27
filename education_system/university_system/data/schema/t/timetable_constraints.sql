CREATE TABLE IF NOT EXISTS timetable_constraints (
            constraint_id INTEGER PRIMARY KEY AUTOINCREMENT,
            constraint_type TEXT NOT NULL,
            constraint_name TEXT NOT NULL,
            applies_to TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            constraint_rule TEXT NOT NULL,
            priority INTEGER DEFAULT 5,
            is_hard_constraint BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
