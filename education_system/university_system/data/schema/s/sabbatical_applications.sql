CREATE TABLE IF NOT EXISTS sabbatical_applications (
                    application_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    sabbatical_type TEXT DEFAULT 'research',
                    title TEXT NOT NULL,
                    research_proposal TEXT,
                    host_institution TEXT,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    pay_percentage REAL DEFAULT 100,
                    cover_arrangements TEXT,
                    funding_details TEXT,
                    status TEXT DEFAULT 'draft',
                    department TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
