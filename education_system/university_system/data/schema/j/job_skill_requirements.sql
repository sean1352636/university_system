CREATE TABLE IF NOT EXISTS job_skill_requirements (
                        requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        job_id INTEGER NOT NULL,
                        skill_name TEXT NOT NULL,
                        is_required BOOLEAN DEFAULT 1,
                        minimum_proficiency TEXT CHECK(minimum_proficiency IN ('beginner', 'intermediate', 'advanced', 'expert')),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (job_id) REFERENCES campus_job_postings(job_id),
                        UNIQUE(job_id, skill_name)
                    );
