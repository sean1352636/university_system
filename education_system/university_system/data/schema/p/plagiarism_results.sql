CREATE TABLE IF NOT EXISTS plagiarism_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL,
                    matched_document_id INTEGER,
                    similarity_score REAL NOT NULL CHECK(similarity_score >= 0 AND similarity_score <= 1),
                    check_date TEXT NOT NULL,
                    checked_by INTEGER,
                    status TEXT NOT NULL,
                    report TEXT,
                    threshold_used REAL DEFAULT 0.3,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (document_id) REFERENCES document_repository (id) ON DELETE CASCADE,
                    FOREIGN KEY (matched_document_id) REFERENCES document_repository (id) ON DELETE SET NULL,
                    FOREIGN KEY (checked_by) REFERENCES users (id) ON DELETE SET NULL
                );
