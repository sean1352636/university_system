CREATE TABLE IF NOT EXISTS textbooks (
                    textbook_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    isbn TEXT DEFAULT '',
                    title TEXT NOT NULL,
                    author TEXT DEFAULT '',
                    edition TEXT DEFAULT '',
                    publisher TEXT DEFAULT '',
                    year INTEGER,
                    module_code TEXT DEFAULT '',
                    required INTEGER DEFAULT 1,
                    price REAL DEFAULT 0.0,
                    description TEXT DEFAULT ''
                );
