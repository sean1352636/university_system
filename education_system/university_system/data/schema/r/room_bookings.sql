CREATE TABLE IF NOT EXISTS room_bookings (
                booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id INTEGER NOT NULL,
                booked_by TEXT NOT NULL,
                booking_type TEXT NOT NULL,
                purpose TEXT,
                start_datetime TEXT NOT NULL,
                end_datetime TEXT NOT NULL,
                setup_required TEXT,
                equipment_needed TEXT,
                expected_attendees INTEGER,
                recurrence_pattern TEXT,
                booking_status TEXT DEFAULT 'confirmed',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (room_id) REFERENCES rooms (id)
            );
