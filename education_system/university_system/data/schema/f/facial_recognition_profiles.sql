CREATE TABLE IF NOT EXISTS facial_recognition_profiles (
            profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL UNIQUE,
            face_encoding TEXT NOT NULL,
            photo_url TEXT,
            last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        );
