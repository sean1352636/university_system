CREATE TABLE IF NOT EXISTS social_activities (
                activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_name TEXT NOT NULL,
                activity_type TEXT NOT NULL,
                description TEXT,
                location TEXT,
                activity_date DATE,
                activity_time TIME,
                max_participants INTEGER,
                current_participants INTEGER DEFAULT 0,
                interests_matched TEXT,
                created_by TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users(username)
            );
