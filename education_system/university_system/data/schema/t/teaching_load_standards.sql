CREATE TABLE IF NOT EXISTS teaching_load_standards (
                    standard_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    department TEXT,
                    role TEXT,
                    standard_credits REAL DEFAULT 12,
                    standard_courses INTEGER DEFAULT 4,
                    max_credits REAL DEFAULT 15,
                    max_new_preps INTEGER DEFAULT 2,
                    large_class_threshold INTEGER DEFAULT 50,
                    large_class_factor REAL DEFAULT 1.25,
                    overload_rate REAL DEFAULT 0,
                    is_default INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
