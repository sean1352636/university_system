CREATE TABLE IF NOT EXISTS submissions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            content     TEXT NOT NULL,
            submitted_at TEXT NOT NULL,
            severity    TEXT NOT NULL,
            categories  TEXT NOT NULL,      -- JSON
            status      TEXT NOT NULL DEFAULT 'Pending',
            reviewer    TEXT,
            review_note TEXT,
            reviewed_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
