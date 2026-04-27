CREATE TABLE IF NOT EXISTS trip_calendar_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trip_id INTEGER NOT NULL,
                    event_id TEXT NOT NULL,
                    event_type TEXT DEFAULT 'trip_event',
                    created_at TEXT NOT NULL, "description" TEXT, "end_date" TEXT, "location" TEXT, "organizer" TEXT, "participants" TEXT, "start_date" TEXT, "status" TEXT DEFAULT 'planned', "title" TEXT, "updated_at" TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (trip_id, event_id)
                );
