CREATE TABLE IF NOT EXISTS allergies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    allergen TEXT,
                    severity TEXT,
                    reaction_description TEXT,
                    diagnosed_date TEXT,
                    provider TEXT,
                    verified INTEGER DEFAULT 0,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                );
