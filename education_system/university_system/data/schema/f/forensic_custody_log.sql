CREATE TABLE IF NOT EXISTS forensic_custody_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evidence_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                user_id INTEGER,
                notes TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (evidence_id) REFERENCES forensic_evidence(evidence_id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
