CREATE TABLE IF NOT EXISTS ukvi_engagement_events (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         student_id TEXT NOT NULL, event_type TEXT NOT NULL,
         event_date TEXT NOT NULL, notes TEXT, recorded_by TEXT,
         recorded_at TEXT DEFAULT CURRENT_TIMESTAMP
       );
