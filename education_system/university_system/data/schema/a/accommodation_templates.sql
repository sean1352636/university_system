CREATE TABLE IF NOT EXISTS accommodation_templates (
                    name TEXT PRIMARY KEY,
                    accommodation_type TEXT NOT NULL,
                    description TEXT,
                    start_offset_days INTEGER,
                    duration_days INTEGER,
                    created_by TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );
