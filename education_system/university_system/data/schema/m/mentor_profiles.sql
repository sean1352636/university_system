CREATE TABLE IF NOT EXISTS mentor_profiles (
                    mentor_id INTEGER PRIMARY KEY,
                    year_of_study INTEGER,
                    course TEXT,
                    strengths_csv TEXT,
                    availability_csv TEXT,
                    languages_csv TEXT,
                    max_mentees INTEGER DEFAULT 3,
                    bio TEXT,
                    updated_at TEXT
                );
