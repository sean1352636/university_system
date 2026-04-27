CREATE TABLE IF NOT EXISTS degree_what_if_scenarios (
                scenario_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                scenario_name TEXT NOT NULL,
                target_program_id INTEGER NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (target_program_id) REFERENCES degree_programs(program_id)
            );
