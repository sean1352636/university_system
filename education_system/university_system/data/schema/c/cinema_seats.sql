CREATE TABLE IF NOT EXISTS cinema_seats (
                    seat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    screening_id INTEGER NOT NULL,
                    row_letter TEXT NOT NULL,
                    seat_number INTEGER NOT NULL,
                    seat_type TEXT DEFAULT 'standard',
                    status TEXT DEFAULT 'available',
                    booking_ref TEXT,
                    FOREIGN KEY (screening_id) REFERENCES cinema_screenings(screening_id),
                    UNIQUE(screening_id, row_letter, seat_number)
                );
