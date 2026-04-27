CREATE TABLE IF NOT EXISTS mentoring_outcomes (
                    outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pair_id INTEGER NOT NULL,
                    confidence_pre INTEGER,
                    confidence_post INTEGER,
                    goals_met INTEGER,
                    satisfaction INTEGER,
                    would_recommend INTEGER,
                    narrative TEXT,
                    recorded_at TEXT
                );
