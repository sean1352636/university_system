CREATE TABLE IF NOT EXISTS ethics_reviews (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            review_type TEXT NOT NULL,
            submission_date TEXT NOT NULL,
            review_date TEXT,
            decision TEXT DEFAULT 'pending',
            decision_date TEXT,
            reviewer_comments TEXT,
            conditions TEXT,
            approval_expiry_date TEXT,
            FOREIGN KEY (project_id) REFERENCES research_projects (project_id)
        );
