CREATE TABLE IF NOT EXISTS payment_risk_scores (
            score_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            risk_score DECIMAL(5,2) NOT NULL, -- 0-100
            risk_level TEXT NOT NULL, -- 'low', 'medium', 'high'
            factors TEXT, -- JSON with risk factors
            last_calculated TEXT,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        );
