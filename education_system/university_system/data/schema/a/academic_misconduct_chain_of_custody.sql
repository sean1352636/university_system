CREATE TABLE IF NOT EXISTS academic_misconduct_chain_of_custody (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evidence_id INTEGER NOT NULL,
                handler TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT DEFAULT '',
                timestamp TEXT NOT NULL,
                FOREIGN KEY (evidence_id) REFERENCES academic_misconduct_evidence(id) ON DELETE CASCADE
            );
