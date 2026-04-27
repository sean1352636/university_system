CREATE TABLE IF NOT EXISTS savings_goals (
                        goal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        goal_name TEXT NOT NULL,
                        target_amount REAL NOT NULL,
                        current_amount REAL DEFAULT 0.0,
                        target_date TEXT,
                        priority TEXT CHECK(priority IN ('low', 'medium', 'high')),
                        status TEXT DEFAULT 'active' CHECK(status IN ('active', 'completed', 'cancelled')),
                        category TEXT,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (student_id) REFERENCES students(student_id)
                    );
