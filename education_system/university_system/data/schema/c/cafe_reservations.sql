CREATE TABLE IF NOT EXISTS cafe_reservations (
                reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                student_id TEXT,
                reservation_date DATE NOT NULL,
                reservation_time TIME NOT NULL,
                party_size INTEGER NOT NULL,
                status TEXT DEFAULT 'confirmed',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
