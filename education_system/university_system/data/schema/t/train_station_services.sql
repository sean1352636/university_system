CREATE TABLE IF NOT EXISTS train_station_services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_number TEXT UNIQUE NOT NULL,
                departure_station TEXT NOT NULL,
                arrival_station TEXT NOT NULL,
                departure_time TEXT NOT NULL,
                arrival_time TEXT NOT NULL,
                price REAL NOT NULL,
                available_seats INTEGER NOT NULL
            );
