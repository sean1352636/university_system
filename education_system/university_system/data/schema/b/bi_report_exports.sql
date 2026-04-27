CREATE TABLE IF NOT EXISTS bi_report_exports (
            export_id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            export_format TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            generated_by TEXT NOT NULL,
            generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            parameters_used TEXT,
            row_count INTEGER,
            FOREIGN KEY (report_id) REFERENCES bi_report_definitions (report_id)
        );
