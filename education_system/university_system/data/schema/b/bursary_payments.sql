CREATE TABLE IF NOT EXISTS bursary_payments (
                    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    award_id INTEGER NOT NULL,
                    scheduled_date TEXT NOT NULL,
                    amount REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'scheduled',
                    paid_date TEXT,
                    reference TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (award_id) REFERENCES bursary_awards (award_id)
                );
