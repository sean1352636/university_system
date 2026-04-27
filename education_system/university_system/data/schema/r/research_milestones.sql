CREATE TABLE IF NOT EXISTS research_milestones (
            milestone_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            milestone_name TEXT NOT NULL,
            milestone_description TEXT,
            target_date TEXT NOT NULL,
            completion_date TEXT,
            status TEXT DEFAULT 'pending',
            deliverables TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES research_projects (project_id)
        );
