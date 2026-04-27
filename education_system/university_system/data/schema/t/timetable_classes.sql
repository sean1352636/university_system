CREATE TABLE IF NOT EXISTS timetable_classes (
            schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_id INTEGER NOT NULL,
            module_code TEXT NOT NULL,
            class_type TEXT NOT NULL,
            instructor_id TEXT,
            room_id INTEGER,
            slot_id INTEGER NOT NULL,
            capacity INTEGER DEFAULT 30,
            enrolled_count INTEGER DEFAULT 0,
            recurrence_pattern TEXT DEFAULT 'weekly',
            status TEXT DEFAULT 'scheduled',
            FOREIGN KEY (config_id) REFERENCES timetable_configurations (config_id),
            FOREIGN KEY (slot_id) REFERENCES timetable_time_slots (slot_id)
        );
