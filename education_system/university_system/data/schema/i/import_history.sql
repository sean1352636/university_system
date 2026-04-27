CREATE TABLE IF NOT EXISTS import_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        operation_type TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        total_records INTEGER DEFAULT 0,
                        successful_imports INTEGER DEFAULT 0,
                        failed_imports INTEGER DEFAULT 0,
                        duplicates_found INTEGER DEFAULT 0,
                        validation_errors INTEGER DEFAULT 0,
                        error_details TEXT,
                        duration_seconds REAL,
                        status TEXT DEFAULT 'completed'
                    );
