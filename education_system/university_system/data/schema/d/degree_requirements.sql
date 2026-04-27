CREATE TABLE IF NOT EXISTS degree_requirements (
                requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                program_id INTEGER NOT NULL,
                requirement_type TEXT NOT NULL,
                requirement_name TEXT NOT NULL,
                credits_required INTEGER NOT NULL,
                description TEXT,
                min_grade TEXT,
                is_mandatory INTEGER DEFAULT 1,
                display_order INTEGER DEFAULT 0,
                FOREIGN KEY (program_id) REFERENCES degree_programs(program_id) ON DELETE CASCADE
            );
