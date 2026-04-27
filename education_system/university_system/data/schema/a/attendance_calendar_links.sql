CREATE TABLE IF NOT EXISTS attendance_calendar_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attendance_record_id INTEGER,
                event_id TEXT,
                module_code TEXT,
                date TEXT,
                created_at TEXT,
                FOREIGN KEY (attendance_record_id) REFERENCES attendance_records (id),
                FOREIGN KEY (event_id) REFERENCES "academic_calendar_events" (id)
            );
