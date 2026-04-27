CREATE TABLE IF NOT EXISTS biometric_enrollments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        enrollment_id TEXT UNIQUE,
                        user_id TEXT NOT NULL,
                        biometric_type TEXT NOT NULL,
                        template_data BLOB,
                        template_hash TEXT,
                        device_name TEXT DEFAULT 'Unknown Device',
                        quality_score REAL,
                        created_at TEXT NOT NULL,
                        last_verified_at TEXT,
                        is_active INTEGER DEFAULT 1,
                        verification_count INTEGER DEFAULT 0,
                        failure_count INTEGER DEFAULT 0,
                        metadata TEXT DEFAULT '{}',
                        revoked_at TEXT
                    );
