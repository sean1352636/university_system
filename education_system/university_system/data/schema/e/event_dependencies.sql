CREATE TABLE IF NOT EXISTS event_dependencies (
                    id TEXT PRIMARY KEY,
                    prerequisite_event_id TEXT NOT NULL,
                    dependent_event_id TEXT NOT NULL,
                    dependency_type TEXT NOT NULL,
                    delay_days INTEGER DEFAULT 0,
                    delay_hours INTEGER DEFAULT 0,
                    is_mandatory BOOLEAN DEFAULT TRUE,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (prerequisite_event_id) REFERENCES "academic_calendar_events" (id) ON DELETE CASCADE,
                    FOREIGN KEY (dependent_event_id) REFERENCES "academic_calendar_events" (id) ON DELETE CASCADE,
                    UNIQUE(prerequisite_event_id, dependent_event_id)
                );
