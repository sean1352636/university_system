CREATE TABLE IF NOT EXISTS privacy_consent (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                consent_type TEXT NOT NULL,
                granted INTEGER NOT NULL,
                granted_at TEXT NOT NULL,
                expires_at TEXT,
                version TEXT NOT NULL,
                UNIQUE(student_id, consent_type)
            );
