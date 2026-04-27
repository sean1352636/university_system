CREATE TABLE IF NOT EXISTS student_id_cards (
                    card_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL UNIQUE,
                    card_number TEXT NOT NULL,
                    issue_date TEXT DEFAULT (date('now')),
                    expiry_date TEXT,
                    status TEXT DEFAULT 'active',
                    photo_path TEXT DEFAULT '',
                    qr_data TEXT DEFAULT ''
                );
