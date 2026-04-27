CREATE TABLE IF NOT EXISTS resource_bookings (
                    id TEXT PRIMARY KEY,
                    resource_id TEXT NOT NULL,
                    event_id TEXT,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    status TEXT DEFAULT 'confirmed',
                    notes TEXT,
                    date_added TEXT NOT NULL,
                    FOREIGN KEY (resource_id) REFERENCES resources (id) ON DELETE CASCADE,
                    FOREIGN KEY (event_id) REFERENCES "academic_calendar_events" (id) ON DELETE CASCADE
                );
