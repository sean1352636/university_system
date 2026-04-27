CREATE TABLE IF NOT EXISTS grant_applications (
            application_id INTEGER PRIMARY KEY AUTOINCREMENT,
            grant_name TEXT NOT NULL,
            funding_agency TEXT NOT NULL,
            project_id INTEGER,
            principal_investigator_id TEXT NOT NULL,
            co_investigators TEXT,
            requested_amount REAL NOT NULL,
            application_deadline TEXT NOT NULL,
            submission_date TEXT,
            decision_date TEXT,
            decision_status TEXT DEFAULT 'pending',
            awarded_amount REAL,
            grant_period_start TEXT,
            grant_period_end TEXT,
            application_documents TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES research_projects (project_id)
        );
