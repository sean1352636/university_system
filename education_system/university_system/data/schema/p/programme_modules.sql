CREATE TABLE IF NOT EXISTS programme_modules (
                    mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    programme_id INTEGER NOT NULL,
                    module_code TEXT NOT NULL,
                    module_name TEXT,
                    year_of_study INTEGER NOT NULL DEFAULT 1,
                    semester INTEGER NOT NULL DEFAULT 1,
                    is_core INTEGER DEFAULT 1,
                    credits INTEGER DEFAULT 20,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (programme_id) REFERENCES programmes(programme_id)
                );
