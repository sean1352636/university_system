CREATE TABLE IF NOT EXISTS committee_agenda_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    meeting_id INTEGER NOT NULL,
                    item_order INTEGER NOT NULL DEFAULT 1,
                    title TEXT NOT NULL,
                    description TEXT,
                    item_type TEXT DEFAULT 'discussion',
                    presenter_id TEXT,
                    duration_minutes INTEGER DEFAULT 15,
                    resolution TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (meeting_id) REFERENCES committee_meetings(id)
                );
