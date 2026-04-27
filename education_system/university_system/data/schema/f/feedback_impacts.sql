CREATE TABLE IF NOT EXISTS feedback_impacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id INTEGER NOT NULL,
                    implementation_date DATE,
                    users_affected INTEGER,
                    satisfaction_increase REAL,
                    cost_savings REAL,
                    description TEXT,
                    metrics TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (submission_id) REFERENCES feedback_submissions(id) ON DELETE CASCADE
                );
