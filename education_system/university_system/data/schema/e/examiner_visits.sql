CREATE TABLE IF NOT EXISTS examiner_visits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    examiner_id INTEGER NOT NULL,
                    visit_date TEXT NOT NULL,
                    department TEXT,
                    purpose TEXT,
                    modules_reviewed TEXT,
                    findings TEXT,
                    recommendations TEXT,
                    overall_rating TEXT,
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (examiner_id) REFERENCES external_examiners(id)
                );
