CREATE TABLE IF NOT EXISTS barber_customer_preferences (
                preference_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                preferred_barber_id INTEGER,
                preferred_service_id INTEGER,
                hair_type TEXT,
                style_notes TEXT,
                allergies TEXT,
                last_visit TEXT,
                visit_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
