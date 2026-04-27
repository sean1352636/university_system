CREATE TABLE IF NOT EXISTS lms_settings (
                        id INTEGER PRIMARY KEY,
                        platform TEXT,
                        api_url TEXT,
                        api_key TEXT,
                        username TEXT,
                        auto_sync INTEGER,
                        sync_grades INTEGER,
                        bidirectional INTEGER,
                        sync_frequency TEXT
                    );
