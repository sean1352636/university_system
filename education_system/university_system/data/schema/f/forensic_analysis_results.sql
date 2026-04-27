CREATE TABLE IF NOT EXISTS forensic_analysis_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evidence_id TEXT NOT NULL,
                analysis_type TEXT NOT NULL,
                results_json TEXT,
                performed_by INTEGER,
                performed_at TEXT NOT NULL,
                FOREIGN KEY (evidence_id) REFERENCES forensic_evidence(evidence_id),
                FOREIGN KEY (performed_by) REFERENCES users(id)
            );
