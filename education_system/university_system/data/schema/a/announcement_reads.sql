CREATE TABLE IF NOT EXISTS announcement_reads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                announcement_id INTEGER,
                parent_id TEXT,
                read_date TEXT,
                acknowledged BOOLEAN DEFAULT 0,
                FOREIGN KEY (announcement_id) REFERENCES school_announcements (id),
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
            );
