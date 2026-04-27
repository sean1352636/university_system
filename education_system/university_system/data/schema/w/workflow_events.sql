CREATE TABLE IF NOT EXISTS workflow_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        workflow_id INTEGER NOT NULL,
                        event_id INTEGER NOT NULL,
                        sequence_order INTEGER NOT NULL,
                        FOREIGN KEY (workflow_id) REFERENCES event_workflows(id) ON DELETE CASCADE,
                        FOREIGN KEY (event_id) REFERENCES calendar_events(id) ON DELETE CASCADE
                    );
