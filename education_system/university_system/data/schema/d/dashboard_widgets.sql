CREATE TABLE IF NOT EXISTS dashboard_widgets (
            widget_id INTEGER PRIMARY KEY AUTOINCREMENT,
            dashboard_id INTEGER NOT NULL,
            widget_type TEXT NOT NULL,
            widget_title TEXT NOT NULL,
            data_source TEXT,
            chart_type TEXT,
            position_x INTEGER,
            position_y INTEGER,
            width INTEGER DEFAULT 4,
            height INTEGER DEFAULT 3,
            config TEXT,
            FOREIGN KEY (dashboard_id) REFERENCES analytics_dashboards (dashboard_id)
        );
