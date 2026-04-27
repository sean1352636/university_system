CREATE TABLE IF NOT EXISTS stage_submissions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        stage_id INTEGER NOT NULL,
                        student_id TEXT NOT NULL,
                        content TEXT,
                        file_path TEXT,
                        status TEXT NOT NULL DEFAULT 'draft',
                        feedback TEXT,
                        submitted_at TEXT,
                        reviewed_at TEXT,
                        FOREIGN KEY (stage_id) REFERENCES assignment_stages(id)
                    );
