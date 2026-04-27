CREATE TABLE IF NOT EXISTS bi_visualizations (
            visualization_id INTEGER PRIMARY KEY AUTOINCREMENT,
            visualization_name TEXT NOT NULL,
            chart_type TEXT NOT NULL,
            data_source TEXT NOT NULL,
            x_axis TEXT,
            y_axis TEXT,
            filters TEXT,
            color_scheme TEXT,
            configuration TEXT,
            created_by TEXT,
            is_public BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
