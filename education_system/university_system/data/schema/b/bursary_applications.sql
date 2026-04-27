CREATE TABLE IF NOT EXISTS bursary_applications (
                    application_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    fund_id INTEGER NOT NULL,
                    requested_amount REAL NOT NULL DEFAULT 0,
                    household_income REAL,
                    circumstances TEXT,
                    status TEXT NOT NULL DEFAULT 'submitted',
                    decision_notes TEXT,
                    submitted_at TEXT DEFAULT (datetime('now')),
                    decided_at TEXT,
                    FOREIGN KEY (fund_id) REFERENCES bursary_funds (fund_id)
                );
