CREATE TABLE IF NOT EXISTS authorized_pickup (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        relationship TEXT,
                        phone TEXT,
                        id_number TEXT,
                        photo_on_file INTEGER DEFAULT 0,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
