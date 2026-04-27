CREATE TABLE IF NOT EXISTS integration_usage_analytics (
            analytics_id INTEGER PRIMARY KEY AUTOINCREMENT,
            install_id INTEGER NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            measurement_date TEXT DEFAULT CURRENT_DATE,
            FOREIGN KEY (install_id) REFERENCES installed_integrations (install_id)
        );
