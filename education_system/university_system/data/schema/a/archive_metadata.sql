CREATE TABLE IF NOT EXISTS archive_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name TEXT,
                    records_archived INTEGER,
                    archive_date TEXT,
                    archived_by TEXT,
                    date_range_start TEXT,
                    date_range_end TEXT
                );
