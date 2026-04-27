CREATE TABLE IF NOT EXISTS union_trip_registrations (
            registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            registered_at TEXT NOT NULL,
            FOREIGN KEY (trip_id) REFERENCES union_trips (trip_id),
            UNIQUE (trip_id, user_id)
        );
