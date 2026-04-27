CREATE TABLE IF NOT EXISTS booked_seats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER NOT NULL,
            seat_id INTEGER NOT NULL,
            ticket_type TEXT DEFAULT 'Adult',
            FOREIGN KEY (booking_id) REFERENCES bookings(id),
            FOREIGN KEY (seat_id) REFERENCES seats(id)
        );
