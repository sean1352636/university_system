CREATE TABLE IF NOT EXISTS privacy_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                student_id TEXT,
                user_id INTEGER,
                data_accessed TEXT,
                timestamp TEXT NOT NULL,
                ip_address TEXT
            );
