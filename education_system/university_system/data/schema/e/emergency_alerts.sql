CREATE TABLE IF NOT EXISTS emergency_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_title TEXT,
                alert_message TEXT,
                alert_type TEXT,
                created_date TEXT,
                created_by INTEGER,
                active BOOLEAN DEFAULT 1,
                FOREIGN KEY (created_by) REFERENCES users (id)
            );
