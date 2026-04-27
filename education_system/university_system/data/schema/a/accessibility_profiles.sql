CREATE TABLE IF NOT EXISTS accessibility_profiles (
            profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            disabilities TEXT,
            accommodations TEXT,
            assistive_technologies TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "student_id" TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
