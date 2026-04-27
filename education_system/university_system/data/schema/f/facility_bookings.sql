CREATE TABLE IF NOT EXISTS facility_bookings (
                    booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    facility_name TEXT,
                    user_id INTEGER,
                    booking_date TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    purpose TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT, "booker_id" TEXT, "club_id" INTEGER, "notes" TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                );
