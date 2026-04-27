CREATE TABLE IF NOT EXISTS recurring_events (
                    id TEXT PRIMARY KEY,
                    base_event_id TEXT NOT NULL,
                    frequency TEXT NOT NULL,
                    interval_count INTEGER DEFAULT 1,
                    days_of_week TEXT,
                    day_of_month INTEGER,
                    month_of_year INTEGER,
                    end_date TEXT,
                    occurrence_count INTEGER,
                    timezone TEXT DEFAULT 'UTC',
                    exceptions TEXT,
                    date_added TEXT NOT NULL,
                    FOREIGN KEY (base_event_id) REFERENCES "academic_calendar_events" (id) ON DELETE CASCADE
                );
