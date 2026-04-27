CREATE TABLE IF NOT EXISTS student_milestone_progress (
                    progress_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    milestone_id INTEGER NOT NULL,
                    achieved BOOLEAN DEFAULT 0,
                    achieved_date TEXT,
                    achieved_semester INTEGER,
                    notes TEXT,
                    FOREIGN KEY (milestone_id) REFERENCES degree_milestones(milestone_id),
                    UNIQUE(student_id, milestone_id)
                );
