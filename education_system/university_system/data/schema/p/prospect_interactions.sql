CREATE TABLE IF NOT EXISTS prospect_interactions (
            interaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            prospect_id INTEGER NOT NULL,
            interaction_type TEXT NOT NULL,
            interaction_date TEXT DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            next_followup_date TEXT,
            staff_member TEXT,
            FOREIGN KEY (prospect_id) REFERENCES admission_prospects (prospect_id)
        );
