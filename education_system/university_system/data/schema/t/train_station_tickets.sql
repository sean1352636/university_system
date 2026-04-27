CREATE TABLE IF NOT EXISTS train_station_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_number TEXT UNIQUE NOT NULL,
                service_id INTEGER NOT NULL,
                passenger_name TEXT NOT NULL,
                payment_method TEXT NOT NULL,
                price_paid REAL NOT NULL,
                purchase_date TEXT NOT NULL, status TEXT DEFAULT 'active',
                FOREIGN KEY (service_id) REFERENCES train_station_services (id)
            );
