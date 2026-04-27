CREATE TABLE IF NOT EXISTS biometric_auth_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        biometric_type TEXT NOT NULL,
                        match_score REAL,
                        success INTEGER NOT NULL,
                        device_info TEXT,
                        ip_address TEXT,
                        enrollment_id TEXT,
                        error_message TEXT,
                        attempt_at TEXT NOT NULL
                    );
