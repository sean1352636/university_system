CREATE TABLE IF NOT EXISTS abs_tracker_scheduled_reports (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT,
            frequency   TEXT,
            recipients  TEXT,
            report_type TEXT,
            last_run    TEXT,
            enabled     INTEGER DEFAULT 1
        );
