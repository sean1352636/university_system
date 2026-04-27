CREATE TABLE IF NOT EXISTS dashboard_permissions (
                        permission_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        dashboard_id INTEGER NOT NULL,
                        user_id TEXT,
                        role TEXT,
                        can_view BOOLEAN DEFAULT 1,
                        can_edit BOOLEAN DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (dashboard_id) REFERENCES dashboards(dashboard_id) ON DELETE CASCADE
                    );
