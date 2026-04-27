CREATE TABLE IF NOT EXISTS skill_endorsements (
                    endorsement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    skill_id INTEGER NOT NULL,
                    endorser_id TEXT NOT NULL,
                    endorser_role TEXT CHECK(endorser_role IN (
                        'faculty', 'peer', 'employer', 'mentor'
                    )),
                    comment TEXT,
                    relationship TEXT,
                    endorsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (skill_id) REFERENCES student_skills(skill_id) ON DELETE CASCADE,
                    UNIQUE(skill_id, endorser_id)
                );
