CREATE TABLE IF NOT EXISTS barber_customer_profiles (
                profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                preferences TEXT,
                allergies TEXT,
                notes TEXT,
                is_vip INTEGER DEFAULT 0,
                total_visits INTEGER DEFAULT 0,
                total_spent DECIMAL(10,2) DEFAULT 0,
                no_show_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
