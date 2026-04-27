CREATE TABLE IF NOT EXISTS academic_misconduct_evidence_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evidence_id INTEGER NOT NULL,
                tag TEXT NOT NULL,
                FOREIGN KEY (evidence_id) REFERENCES academic_misconduct_evidence(id) ON DELETE CASCADE
            );
