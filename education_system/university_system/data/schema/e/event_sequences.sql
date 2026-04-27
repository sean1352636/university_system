CREATE TABLE IF NOT EXISTS event_sequences (
                    id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    sequence_order INTEGER NOT NULL,
                    completion_status TEXT DEFAULT 'pending',
                    completion_date TEXT,
                    FOREIGN KEY (workflow_id) REFERENCES event_workflows (id) ON DELETE CASCADE,
                    FOREIGN KEY (event_id) REFERENCES "academic_calendar_events" (id) ON DELETE CASCADE
                );
