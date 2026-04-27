CREATE TABLE IF NOT EXISTS roommate_profiles (
                    profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT UNIQUE NOT NULL,
                    display_name TEXT NOT NULL,
                    bio TEXT,
                    budget_min INTEGER,
                    budget_max INTEGER,
                    move_in_date TEXT,
                    preferred_gender TEXT,
                    age INTEGER,
                    major TEXT,
                    year_of_study TEXT,
                    smoking_preference TEXT DEFAULT 'No',
                    pet_preference TEXT DEFAULT 'No pets',
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                );
