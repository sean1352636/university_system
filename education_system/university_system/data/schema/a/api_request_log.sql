CREATE TABLE IF NOT EXISTS api_request_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_key_id INTEGER,
                user_id INTEGER,
                endpoint TEXT NOT NULL,
                method TEXT NOT NULL,
                ip_address TEXT,
                request_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                response_status INTEGER,
                response_time_ms INTEGER,
                FOREIGN KEY (api_key_id) REFERENCES api_keys(id) ON DELETE SET NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            );
