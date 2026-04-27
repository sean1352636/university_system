CREATE TABLE IF NOT EXISTS security_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                event_type TEXT NOT NULL,
                severity TEXT DEFAULT 'medium',
                details TEXT,
                ip_address TEXT,
                event_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "source" TEXT, "created_at" TIMESTAMP DEFAULT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
