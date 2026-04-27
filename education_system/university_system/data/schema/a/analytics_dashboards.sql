CREATE TABLE IF NOT EXISTS analytics_dashboards (
            dashboard_id INTEGER PRIMARY KEY AUTOINCREMENT,
            dashboard_name TEXT NOT NULL,
            dashboard_type TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            is_public BOOLEAN DEFAULT 0,
            layout_config TEXT,
            widget_config TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
