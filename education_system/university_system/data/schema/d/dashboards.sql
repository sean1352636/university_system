CREATE TABLE IF NOT EXISTS dashboards (
                        dashboard_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        description TEXT,
                        owner_id TEXT NOT NULL,
                        shared BOOLEAN DEFAULT 0,
                        layout_config TEXT,
                        refresh_interval INTEGER DEFAULT 300,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
