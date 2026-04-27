CREATE TABLE IF NOT EXISTS ai_detector_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,
                time_taken INTEGER,
                browser_info TEXT,
                device_fingerprint TEXT,
                ip_address TEXT,
                location_data TEXT,
                keystroke_data TEXT,
                FOREIGN KEY (submission_id) REFERENCES ai_detector_submissions (id)
            );
