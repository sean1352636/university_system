CREATE TABLE IF NOT EXISTS bi_report_definitions (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_name TEXT NOT NULL,
            report_category TEXT NOT NULL,
            description TEXT,
            sql_query TEXT,
            data_source TEXT,
            parameters TEXT,
            visualization_type TEXT,
            created_by TEXT,
            is_public BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT
        );
