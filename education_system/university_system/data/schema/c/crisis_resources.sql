CREATE TABLE IF NOT EXISTS crisis_resources (
                    resource_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    resource_name TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    contact_info TEXT NOT NULL,
                    description TEXT,
                    availability TEXT DEFAULT '24/7',
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
