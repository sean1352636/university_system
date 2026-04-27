CREATE TABLE IF NOT EXISTS sc_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        event_date TEXT,
        event_time TEXT,
        venue TEXT,
        organiser TEXT,
        description TEXT,
        calendar_event_id TEXT,
        created_at TEXT
    );
