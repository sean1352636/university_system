CREATE TABLE IF NOT EXISTS taxi_booking_services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_name TEXT NOT NULL,
                vehicle_type TEXT NOT NULL,
                capacity INTEGER NOT NULL,
                price_per_km REAL NOT NULL,
                base_fare REAL NOT NULL,
                description TEXT,
                available INTEGER DEFAULT 1
            );
