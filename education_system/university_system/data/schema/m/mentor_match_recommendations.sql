CREATE TABLE IF NOT EXISTS mentor_match_recommendations (
                    recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mentee_id INTEGER NOT NULL,
                    mentor_id INTEGER NOT NULL,
                    score INTEGER NOT NULL,
                    reasons_json TEXT,
                    created_at TEXT,
                    status TEXT DEFAULT 'suggested'
                );
