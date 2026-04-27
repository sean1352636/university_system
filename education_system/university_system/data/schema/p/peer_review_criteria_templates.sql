CREATE TABLE IF NOT EXISTS peer_review_criteria_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_id INTEGER NOT NULL,
                    criteria_name TEXT NOT NULL,
                    max_score INTEGER DEFAULT 5,
                    order_index INTEGER NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (config_id) REFERENCES peer_review_config (id)
                );
