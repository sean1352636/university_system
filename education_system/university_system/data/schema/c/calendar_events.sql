CREATE TABLE IF NOT EXISTS calendar_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                start_date TEXT NOT NULL,
                end_date TEXT,
                event_type TEXT NOT NULL,
                assignment_id INTEGER,
                created_by INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY (assignment_id) REFERENCES assignments (id),
                FOREIGN KEY (created_by) REFERENCES users (id)
            );
