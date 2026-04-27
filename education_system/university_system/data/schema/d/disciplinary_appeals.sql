CREATE TABLE IF NOT EXISTS disciplinary_appeals (
                    appeal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_id INTEGER NOT NULL,
                    appellant_id TEXT NOT NULL,
                    appeal_date TEXT NOT NULL,
                    grounds TEXT NOT NULL,
                    supporting_documents TEXT,
                    status TEXT DEFAULT 'submitted',
                    hearing_date TEXT,
                    panel_members TEXT,
                    outcome TEXT,
                    outcome_date TEXT,
                    outcome_details TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (action_id) REFERENCES disciplinary_actions(action_id)
                );
