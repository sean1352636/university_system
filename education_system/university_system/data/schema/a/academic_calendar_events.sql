CREATE TABLE IF NOT EXISTS "academic_calendar_events" (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    date TEXT,
                    date_start TEXT,
                    date_end TEXT,
                    description TEXT,
                    event_type TEXT DEFAULT 'Academic',
                    date_added TEXT NOT NULL,
                    last_modified TEXT,
                    created_by TEXT,
                    CONSTRAINT valid_event_dates CHECK (
                        (date IS NOT NULL AND date_start IS NULL AND date_end IS NULL) OR
                        (date IS NULL AND date_start IS NOT NULL AND date_end IS NOT NULL AND date_start <= date_end)
                    )
                );
