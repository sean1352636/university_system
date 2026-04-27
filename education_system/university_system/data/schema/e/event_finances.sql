CREATE TABLE IF NOT EXISTS event_finances (
            finance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            expense_type TEXT,
            amount REAL,
            description TEXT,
            date_recorded TEXT,
            receipt_path TEXT,
            revenue_type TEXT,
            FOREIGN KEY (event_id) REFERENCES union_events (event_id)
        );
