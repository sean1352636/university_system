CREATE TABLE IF NOT EXISTS book_recommendations (
            recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            book_id TEXT NOT NULL,
            recommendation_type TEXT NOT NULL,
            confidence_score REAL DEFAULT 0.0,
            generated_date TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            clicked BOOLEAN DEFAULT FALSE
        );
