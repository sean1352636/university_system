CREATE TABLE IF NOT EXISTS immutable_audit_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        user_id TEXT,
                        action TEXT NOT NULL,
                        resource_type TEXT,
                        resource_id TEXT,
                        details TEXT,
                        ip_address TEXT,
                        user_agent TEXT,
                        session_id TEXT,
                        previous_hash TEXT,
                        current_hash TEXT NOT NULL,
                        hmac_signature TEXT NOT NULL,
                        UNIQUE(current_hash)
                    );
