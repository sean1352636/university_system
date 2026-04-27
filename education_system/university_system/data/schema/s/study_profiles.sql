CREATE TABLE IF NOT EXISTS study_profiles (
                    profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL UNIQUE,
                    study_style TEXT DEFAULT 'Visual',
                    preferred_time TEXT DEFAULT 'Evening',
                    group_size_preference TEXT DEFAULT 'Small',
                    communication_style TEXT DEFAULT 'Collaborative',
                    noise_preference TEXT DEFAULT 'Quiet',
                    availability_json TEXT,
                    interests_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
