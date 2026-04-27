CREATE TABLE IF NOT EXISTS barber_services (
                service_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                service_type TEXT NOT NULL,
                description TEXT,
                duration_minutes INTEGER DEFAULT 30,
                price DECIMAL(10,2) NOT NULL,
                is_available INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
