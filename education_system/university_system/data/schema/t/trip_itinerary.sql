CREATE TABLE IF NOT EXISTS trip_itinerary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER NOT NULL,
                day_number INTEGER NOT NULL,
                activity TEXT NOT NULL,
                location TEXT,
                start_time TEXT,
                end_time TEXT,
                notes TEXT,
                FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
                UNIQUE (trip_id, day_number, start_time)
            );
