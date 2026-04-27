CREATE TABLE IF NOT EXISTS research_projects (
            project_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_title TEXT NOT NULL,
            project_description TEXT,
            principal_investigator_id TEXT NOT NULL,
            department TEXT NOT NULL,
            project_type TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT,
            status TEXT DEFAULT 'active',
            total_budget REAL DEFAULT 0,
            funding_source TEXT,
            ethics_approval_status TEXT DEFAULT 'pending',
            ethics_approval_date TEXT,
            publications_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
