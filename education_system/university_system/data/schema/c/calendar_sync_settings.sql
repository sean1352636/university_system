CREATE TABLE IF NOT EXISTS calendar_sync_settings (
                        id INTEGER PRIMARY KEY,
                        platform TEXT,
                        calendar_url TEXT,
                        auth_token TEXT,
                        auto_create_events INTEGER,
                        include_attendance INTEGER,
                        set_reminders INTEGER,
                        reminder_time INTEGER
                    );
