CREATE TABLE IF NOT EXISTS event_income (
                income_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_name TEXT NOT NULL,
                source TEXT NOT NULL,
                amount REAL NOT NULL,
                date TEXT NOT NULL,
                payment_method TEXT,
                notes TEXT,
                recorded_by TEXT,
                recorded_date TEXT
            );
