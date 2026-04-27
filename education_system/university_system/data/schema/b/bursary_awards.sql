CREATE TABLE IF NOT EXISTS bursary_awards (
                    award_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id INTEGER NOT NULL UNIQUE,
                    awarded_amount REAL NOT NULL,
                    payment_frequency TEXT NOT NULL,
                    num_payments INTEGER NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (application_id) REFERENCES bursary_applications (application_id)
                );
