CREATE TABLE IF NOT EXISTS research_profiles (
                profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE NOT NULL,
                research_interests TEXT,
                h_index INTEGER DEFAULT 0,
                total_citations INTEGER DEFAULT 0,
                total_publications INTEGER DEFAULT 0,
                orcid_id TEXT,
                google_scholar_id TEXT,
                researchgate_url TEXT,
                scopus_id TEXT,
                last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
