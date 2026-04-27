CREATE TABLE IF NOT EXISTS care_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    condition_id INTEGER,
                    plan_name TEXT,
                    description TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    provider TEXT,
                    status TEXT DEFAULT 'active',
                    goals TEXT,
                    interventions TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (condition_id) REFERENCES medical_conditions (id)
                );
