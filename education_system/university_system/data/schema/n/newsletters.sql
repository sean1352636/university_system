CREATE TABLE IF NOT EXISTS newsletters (
            newsletter_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            content TEXT,
            template_id INTEGER,
            target_audience TEXT,
            send_date TEXT,
            created_date TEXT,
            created_by TEXT,
            status TEXT DEFAULT 'draft',
            open_rate REAL DEFAULT 0.0,
            click_rate REAL DEFAULT 0.0
        );
