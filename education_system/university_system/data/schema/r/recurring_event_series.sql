CREATE TABLE IF NOT EXISTS recurring_event_series (
                series_id INTEGER PRIMARY KEY AUTOINCREMENT,
                series_name TEXT NOT NULL,
                pattern TEXT NOT NULL,
                day_of_week TEXT,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                duration_hours REAL,
                location TEXT,
                description TEXT,
                created_by TEXT,
                created_date TEXT,
                status TEXT DEFAULT 'active'
            );
