CREATE TABLE IF NOT EXISTS event_expenses (
                expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_name TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                date TEXT NOT NULL,
                vendor TEXT,
                receipt_number TEXT,
                has_receipt BOOLEAN,
                notes TEXT,
                recorded_by TEXT,
                recorded_date TEXT
            );
