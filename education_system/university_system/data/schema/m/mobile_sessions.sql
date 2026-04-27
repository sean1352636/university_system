CREATE TABLE IF NOT EXISTS mobile_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                device_id INTEGER,
                login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                logout_time TIMESTAMP,
                session_token TEXT, ip_address TEXT, location TEXT, "expires_at" TIMESTAMP, "is_active" BOOLEAN DEFAULT 1, "last_activity" TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "started_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (device_id) REFERENCES mobile_devices(device_id)
            );
