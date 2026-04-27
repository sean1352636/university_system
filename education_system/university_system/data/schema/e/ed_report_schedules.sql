CREATE TABLE IF NOT EXISTS ed_report_schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        cadence TEXT NOT NULL,
        field TEXT NOT NULL,
        format TEXT NOT NULL DEFAULT 'pdf',
        output_dir TEXT NOT NULL,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        last_run_at TEXT,
        next_run_at TEXT
    );
