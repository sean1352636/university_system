CREATE TABLE IF NOT EXISTS grievance_actions (
                    action_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    grievance_id INTEGER NOT NULL,
                    action_type TEXT NOT NULL,
                    action_date TEXT NOT NULL,
                    taken_by TEXT NOT NULL,
                    details TEXT,
                    outcome TEXT,
                    next_action TEXT,
                    next_action_date TEXT,
                    documents_path TEXT,
                    is_visible_to_complainant BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (grievance_id) REFERENCES grievances(grievance_id)
                );
