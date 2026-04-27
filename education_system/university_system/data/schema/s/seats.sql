CREATE TABLE IF NOT EXISTS seats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            screening_id INTEGER NOT NULL,
            row TEXT NOT NULL,
            seat_number INTEGER NOT NULL,
            seat_type TEXT DEFAULT 'standard',
            status TEXT DEFAULT 'available', is_wheelchair INTEGER DEFAULT 0, is_companion INTEGER DEFAULT 0, is_couple INTEGER DEFAULT 0,
            FOREIGN KEY (screening_id) REFERENCES screenings(id),
            UNIQUE(screening_id, row, seat_number)
        );
