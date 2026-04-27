CREATE TABLE IF NOT EXISTS ai_sentiment_analysis (
            analysis_id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id TEXT NOT NULL,
            content_type TEXT NOT NULL,
            content_text TEXT NOT NULL,
            sentiment_score REAL,
            sentiment_category TEXT,
            emotions_detected TEXT,
            key_phrases TEXT,
            analyzed_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
