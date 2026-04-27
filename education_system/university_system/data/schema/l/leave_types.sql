CREATE TABLE IF NOT EXISTS leave_types (
                    leave_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    max_days_per_year INTEGER DEFAULT 0,
                    requires_approval BOOLEAN DEFAULT 1,
                    is_paid BOOLEAN DEFAULT 1,
                    color_code TEXT DEFAULT '#3498db',
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
