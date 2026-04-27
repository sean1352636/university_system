CREATE TABLE IF NOT EXISTS degree_programs_test (
                program_id INTEGER PRIMARY KEY AUTOINCREMENT,
                program_code TEXT UNIQUE NOT NULL,
                program_name TEXT NOT NULL
            );
