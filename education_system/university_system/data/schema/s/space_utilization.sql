CREATE TABLE IF NOT EXISTS space_utilization (
                utilization_id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id INTEGER NOT NULL,
                measurement_date TEXT NOT NULL,
                occupancy_rate REAL,
                booking_rate REAL,
                peak_usage_time TEXT,
                average_attendees REAL,
                total_booking_hours REAL,
                FOREIGN KEY (room_id) REFERENCES rooms (id)
            );
