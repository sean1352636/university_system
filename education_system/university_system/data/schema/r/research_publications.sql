CREATE TABLE IF NOT EXISTS research_publications (
            publication_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            title TEXT NOT NULL,
            authors TEXT NOT NULL,
            publication_type TEXT NOT NULL,
            journal_name TEXT,
            conference_name TEXT,
            publication_date TEXT,
            doi TEXT,
            url TEXT,
            abstract TEXT,
            keywords TEXT,
            citation_count INTEGER DEFAULT 0,
            is_peer_reviewed BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES research_projects (project_id)
        );
