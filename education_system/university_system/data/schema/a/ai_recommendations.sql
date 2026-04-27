CREATE TABLE IF NOT EXISTS ai_recommendations (
            recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            recommendation_type TEXT NOT NULL,
            recommendation_content TEXT NOT NULL,
            algorithm_used TEXT,
            confidence_score REAL,
            context_data TEXT,
            was_accepted BOOLEAN,
            feedback_rating INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
