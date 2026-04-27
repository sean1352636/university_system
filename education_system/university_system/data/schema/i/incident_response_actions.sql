CREATE TABLE IF NOT EXISTS incident_response_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                action_details TEXT,
                performed_by INTEGER,
                performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (incident_id) REFERENCES security_incidents(id),
                FOREIGN KEY (performed_by) REFERENCES users(id)
            );
