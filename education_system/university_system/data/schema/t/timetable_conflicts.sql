CREATE TABLE IF NOT EXISTS timetable_conflicts (
            conflict_id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_id INTEGER NOT NULL,
            conflict_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            description TEXT NOT NULL,
            affected_schedules TEXT,
            resolution_status TEXT DEFAULT 'unresolved',
            resolution_notes TEXT,
            detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
            resolved_at TEXT,
            FOREIGN KEY (config_id) REFERENCES timetable_configurations (config_id)
        );
