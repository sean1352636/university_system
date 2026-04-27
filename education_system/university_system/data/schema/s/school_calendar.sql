CREATE TABLE IF NOT EXISTS school_calendar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_name TEXT,
                event_description TEXT,
                event_date TEXT,
                start_time TEXT,
                end_time TEXT,
                location TEXT,
                event_type TEXT,
                audience TEXT
            );
