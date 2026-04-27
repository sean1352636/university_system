CREATE TABLE IF NOT EXISTS knowledge_transfer (
                    transfer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    departing_user_id TEXT NOT NULL,
                    receiving_user_id TEXT,
                    topic TEXT NOT NULL,
                    description TEXT,
                    documentation_path TEXT,
                    priority TEXT DEFAULT 'medium',
                    status TEXT DEFAULT 'pending',
                    scheduled_date TEXT,
                    completed_date TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
