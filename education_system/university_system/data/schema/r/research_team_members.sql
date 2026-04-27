CREATE TABLE IF NOT EXISTS research_team_members (
            member_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            staff_id TEXT NOT NULL,
            role TEXT NOT NULL,
            join_date TEXT DEFAULT CURRENT_DATE,
            leave_date TEXT,
            contribution_percentage REAL,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (project_id) REFERENCES research_projects (project_id)
        );
