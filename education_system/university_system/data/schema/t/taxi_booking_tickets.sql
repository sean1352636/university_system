CREATE TABLE IF NOT EXISTS taxi_booking_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_number TEXT UNIQUE NOT NULL,
                service_id INTEGER NOT NULL,
                customer_name TEXT NOT NULL,
                pickup_location TEXT NOT NULL,
                dropoff_location TEXT NOT NULL,
                distance_km REAL NOT NULL,
                total_fare REAL NOT NULL,
                payment_method TEXT NOT NULL,
                payment_status TEXT DEFAULT 'Completed',
                booking_date TEXT NOT NULL,
                booking_time TEXT NOT NULL,
                FOREIGN KEY (service_id) REFERENCES taxi_booking_services (id)
            );
