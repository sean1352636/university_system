CREATE TABLE IF NOT EXISTS requirement_courses (
                req_course_id INTEGER PRIMARY KEY AUTOINCREMENT,
                requirement_id INTEGER NOT NULL,
                module_code TEXT NOT NULL,
                is_alternative INTEGER DEFAULT 0,
                alternative_group INTEGER,
                FOREIGN KEY (requirement_id) REFERENCES degree_requirements(requirement_id) ON DELETE CASCADE
            );
