CREATE TABLE IF NOT EXISTS mentee_preferences (
                    mentee_id INTEGER PRIMARY KEY,
                    course TEXT,
                    learning_goals_csv TEXT,
                    preferred_languages_csv TEXT,
                    availability_csv TEXT,
                    preferred_year_min INTEGER,
                    updated_at TEXT
                );
