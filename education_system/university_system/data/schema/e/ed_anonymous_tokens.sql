CREATE TABLE IF NOT EXISTS ed_anonymous_tokens (
        token TEXT PRIMARY KEY,
        issued_by TEXT,
        issued_at TEXT NOT NULL,
        used_at TEXT,
        expires_at TEXT
    );
