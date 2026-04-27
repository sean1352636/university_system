CREATE TABLE IF NOT EXISTS parent_notification_settings (
                        id INTEGER PRIMARY KEY,
                        auto_absence INTEGER,
                        auto_low_attendance INTEGER,
                        low_attendance_threshold INTEGER,
                        absence_template TEXT,
                        low_attendance_template TEXT
                    );
