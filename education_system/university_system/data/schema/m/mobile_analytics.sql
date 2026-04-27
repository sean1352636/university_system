CREATE TABLE IF NOT EXISTS mobile_analytics (
                analytics_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                event_type TEXT NOT NULL,
                event_data TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, device_id INTEGER REFERENCES mobile_devices(device_id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
