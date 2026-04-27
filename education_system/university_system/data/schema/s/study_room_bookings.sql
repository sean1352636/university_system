CREATE TABLE IF NOT EXISTS study_room_bookings (
                    booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id INTEGER NOT NULL,
                    booked_by TEXT NOT NULL,
                    booking_date TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    purpose TEXT DEFAULT 'study',
                    group_size INTEGER DEFAULT 1,
                    notes TEXT DEFAULT '',
                    status TEXT DEFAULT 'confirmed',
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (room_id) REFERENCES study_rooms(room_id)
                );
