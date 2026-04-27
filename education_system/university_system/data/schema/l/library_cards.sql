CREATE TABLE IF NOT EXISTS library_cards (
                card_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                card_number TEXT UNIQUE,
                issue_date TEXT,
                expiry_date TEXT,
                status TEXT DEFAULT 'active'
            );
