CREATE TABLE IF NOT EXISTS ai_content_suggestions (
            suggestion_id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_type TEXT NOT NULL,
            context TEXT NOT NULL,
            suggested_content TEXT NOT NULL,
            relevance_score REAL,
            source TEXT,
            was_used BOOLEAN DEFAULT 0,
            created_for TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
