CREATE TABLE IF NOT EXISTS ai_detector_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,
                ai_score REAL NOT NULL,
                confidence REAL NOT NULL,
                detailed_results TEXT,
                created_at TEXT NOT NULL,
                style_deviation REAL,
                FOREIGN KEY (submission_id) REFERENCES ai_detector_submissions (id)
            );
