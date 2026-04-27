CREATE TABLE IF NOT EXISTS trip_registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            registration_date TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            notes TEXT,
            FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            UNIQUE(trip_id, user_id)
        );
