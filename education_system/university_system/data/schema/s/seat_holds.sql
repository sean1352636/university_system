CREATE TABLE IF NOT EXISTS seat_holds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seat_id INTEGER NOT NULL,
            session_id TEXT NOT NULL,
            held_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (seat_id) REFERENCES seats(id)
        );
