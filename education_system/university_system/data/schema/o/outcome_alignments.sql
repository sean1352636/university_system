CREATE TABLE IF NOT EXISTS outcome_alignments (
                    alignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    programme_outcome_id INTEGER NOT NULL,
                    module_outcome_id INTEGER NOT NULL,
                    alignment_strength TEXT DEFAULT 'moderate',
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (programme_outcome_id) REFERENCES learning_outcomes(outcome_id),
                    FOREIGN KEY (module_outcome_id) REFERENCES learning_outcomes(outcome_id)
                );
