CREATE TABLE IF NOT EXISTS travel_itinerary (
                    leg_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER NOT NULL,
                    leg_order INTEGER NOT NULL DEFAULT 1,
                    transport_type TEXT NOT NULL DEFAULT 'flight',
                    departure_location TEXT,
                    arrival_location TEXT,
                    departure_datetime TEXT,
                    arrival_datetime TEXT,
                    booking_reference TEXT,
                    carrier TEXT,
                    cost REAL DEFAULT 0,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (request_id) REFERENCES travel_requests(request_id)
                );
