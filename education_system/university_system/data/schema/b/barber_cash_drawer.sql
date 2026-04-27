CREATE TABLE IF NOT EXISTS barber_cash_drawer (
                drawer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                opening_amount DECIMAL(10,2) NOT NULL,
                closing_amount DECIMAL(10,2),
                expected_amount DECIMAL(10,2),
                discrepancy DECIMAL(10,2),
                opened_by TEXT NOT NULL,
                closed_by TEXT,
                opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TEXT,
                notes TEXT,
                status TEXT DEFAULT 'open'
            );
