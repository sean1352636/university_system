CREATE TABLE IF NOT EXISTS holidays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                holiday_name TEXT,
                start_date DATE,
                end_date DATE,
                description TEXT,
                recurring BOOLEAN DEFAULT 0
            );
