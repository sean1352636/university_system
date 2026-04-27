CREATE TABLE IF NOT EXISTS intervention_outcomes (
                    intervention_id INTEGER PRIMARY KEY,
                    subject_area TEXT,
                    sessions_total INTEGER DEFAULT 0,
                    sessions_completed INTEGER DEFAULT 0,
                    pre_assessment_score REAL,
                    pre_assessment_date TEXT,
                    post_assessment_score REAL,
                    post_assessment_date TEXT,
                    value_added REAL,
                    impact_notes TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (intervention_id)
                        REFERENCES early_warning_interventions (intervention_id)
                );
