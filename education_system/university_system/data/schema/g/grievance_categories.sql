CREATE TABLE IF NOT EXISTS grievance_categories (
                    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    severity_level INTEGER DEFAULT 1,
                    requires_investigation BOOLEAN DEFAULT 1,
                    sla_days INTEGER DEFAULT 30,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
