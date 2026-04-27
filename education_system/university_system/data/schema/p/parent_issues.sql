CREATE TABLE IF NOT EXISTS parent_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id TEXT,
                category TEXT,
                subject TEXT,
                description TEXT,
                priority TEXT,
                status TEXT DEFAULT 'open',
                created_date TEXT,
                resolved_date TEXT,
                response TEXT,
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
            );
