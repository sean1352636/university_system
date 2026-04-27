CREATE TABLE IF NOT EXISTS office_hour_bookings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        office_hour_id INTEGER NOT NULL,
                        student_id TEXT NOT NULL,
                        booking_date TEXT NOT NULL,
                        notes TEXT DEFAULT '',
                        status TEXT DEFAULT 'confirmed',
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (office_hour_id) REFERENCES office_hours(id)
                    );
