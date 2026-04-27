CREATE TABLE IF NOT EXISTS ai_model_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT,
                weights_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 0
            );
