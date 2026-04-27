CREATE TABLE IF NOT EXISTS "user_resumes" (
                            resume_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            student_id TEXT NOT NULL,
                            resume_name TEXT NOT NULL,
                            template_id INTEGER,
                            content TEXT NOT NULL,
                            last_generated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            format TEXT DEFAULT 'pdf' CHECK(format IN ('pdf', 'docx', 'html')),
                            FOREIGN KEY (template_id) REFERENCES resume_templates(template_id)
                        );
