CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    referring_provider TEXT,
                    specialist_provider TEXT,
                    specialty TEXT,
                    reason TEXT,
                    urgency TEXT,
                    referral_date TEXT,
                    appointment_date TEXT,
                    status TEXT DEFAULT 'pending',
                    notes TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                );
