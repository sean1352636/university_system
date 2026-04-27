CREATE TABLE IF NOT EXISTS irb_applications (
                            application_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            project_id INTEGER NOT NULL,
                            protocol_number TEXT,
                            submission_date TEXT NOT NULL,
                            review_type TEXT NOT NULL,
                            decision TEXT DEFAULT 'Pending',
                            decision_date TEXT,
                            status TEXT DEFAULT 'Submitted',
                            study_description TEXT,
                            risk_assessment TEXT,
                            reviewer_comments TEXT,
                            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (project_id) REFERENCES research_projects (project_id)
                        );
