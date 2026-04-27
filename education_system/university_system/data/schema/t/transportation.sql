CREATE TABLE IF NOT EXISTS transportation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                route_name TEXT,
                bus_number TEXT,
                pickup_time TEXT,
                dropoff_time TEXT,
                pickup_location TEXT,
                dropoff_location TEXT,
                driver_name TEXT,
                driver_phone TEXT,
                active BOOLEAN DEFAULT 1,
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            );
