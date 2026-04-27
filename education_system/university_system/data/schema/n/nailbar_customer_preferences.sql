CREATE TABLE IF NOT EXISTS nailbar_customer_preferences (
                preference_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL UNIQUE,
                preferred_technician_id INTEGER,
                favorite_colors TEXT,
                nail_type TEXT,
                allergies TEXT,
                last_visit TEXT,
                visit_count INTEGER DEFAULT 0,
                loyalty_points INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
