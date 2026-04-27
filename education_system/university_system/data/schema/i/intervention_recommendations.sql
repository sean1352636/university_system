CREATE TABLE IF NOT EXISTS intervention_recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            intervention_type TEXT NOT NULL,
            priority INTEGER,
            description TEXT,
            timeline TEXT,
            risk_score REAL,
            risk_level TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
