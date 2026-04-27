CREATE TABLE IF NOT EXISTS application_reviews (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            reviewer_id TEXT NOT NULL,
            review_stage TEXT NOT NULL,
            score INTEGER,
            recommendation TEXT,
            comments TEXT,
            review_date TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (application_id) REFERENCES admission_applications (application_id)
        );
