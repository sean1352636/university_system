CREATE TABLE IF NOT EXISTS event_timezones (
                    event_id TEXT PRIMARY KEY,
                    timezone_name TEXT NOT NULL,
                    utc_offset_hours INTEGER NOT NULL,
                    is_dst_active BOOLEAN DEFAULT FALSE,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (event_id) REFERENCES "academic_calendar_events" (id) ON DELETE CASCADE
                );
