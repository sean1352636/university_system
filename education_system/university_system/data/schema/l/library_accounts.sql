CREATE TABLE IF NOT EXISTS library_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                book_title TEXT,
                author TEXT,
                isbn TEXT,
                checkout_date TEXT,
                due_date TEXT,
                return_date TEXT,
                fine_amount DECIMAL(10,2) DEFAULT 0.00,
                status TEXT DEFAULT 'checked_out',
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            );
