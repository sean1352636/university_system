CREATE TABLE IF NOT EXISTS timetable_time_slots (
            slot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_name TEXT NOT NULL,
            day_of_week TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            is_available BOOLEAN DEFAULT 1,
            priority_level INTEGER DEFAULT 3
        );
