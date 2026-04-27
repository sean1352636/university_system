CREATE TABLE IF NOT EXISTS academic_years (
                    id TEXT PRIMARY KEY,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    date_added TEXT NOT NULL,
                    CONSTRAINT valid_dates CHECK (start_date < end_date)
                );
