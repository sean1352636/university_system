CREATE TABLE IF NOT EXISTS nailbar_treatments (
                treatment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                duration_minutes INTEGER DEFAULT 45,
                price DECIMAL(10,2) NOT NULL,
                is_available INTEGER DEFAULT 1,
                requires_appointment INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
