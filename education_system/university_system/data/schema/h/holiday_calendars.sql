CREATE TABLE IF NOT EXISTS holiday_calendars (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    country_code TEXT NOT NULL,
                    region TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    date_added TEXT NOT NULL
                );
