CREATE TABLE IF NOT EXISTS gpa_simulations (
                    simulation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    simulation_name TEXT NOT NULL,
                    current_gpa REAL NOT NULL,
                    simulated_courses_json TEXT NOT NULL,
                    projected_gpa REAL NOT NULL,
                    projection_type TEXT DEFAULT 'What-If',
                    credits_simulated INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
