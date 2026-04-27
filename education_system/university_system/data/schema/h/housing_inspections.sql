CREATE TABLE IF NOT EXISTS housing_inspections (
            inspection_id TEXT PRIMARY KEY,
            room_id TEXT NOT NULL,
            inspector TEXT NOT NULL,
            inspection_date TEXT NOT NULL,
            inspection_type TEXT NOT NULL,
            status TEXT NOT NULL,
            findings TEXT,
            action_required TEXT,
            follow_up_date TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (room_id) REFERENCES housing_rooms (room_id)
        );
