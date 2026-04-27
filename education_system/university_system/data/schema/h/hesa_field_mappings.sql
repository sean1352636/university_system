CREATE TABLE IF NOT EXISTS hesa_field_mappings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    return_type TEXT NOT NULL,
                    hesa_field TEXT NOT NULL,
                    local_field TEXT NOT NULL,
                    transform_rule TEXT,
                    is_active INTEGER DEFAULT 1
                );
