CREATE TABLE IF NOT EXISTS event_tag_assignments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL,
                    tag_id INTEGER NOT NULL,
                    date_added TEXT NOT NULL,
                    FOREIGN KEY (event_id) REFERENCES "academic_calendar_events" (id) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES event_tags (id) ON DELETE CASCADE,
                    UNIQUE(event_id, tag_id)
                );
