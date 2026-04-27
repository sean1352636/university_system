CREATE TABLE IF NOT EXISTS submission_receipts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        submission_id INTEGER NOT NULL,
                        student_id INTEGER NOT NULL,
                        assignment_title TEXT,
                        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        receipt_hash TEXT,
                        email_sent INTEGER DEFAULT 0,
                        confirmation_code TEXT
                    );
