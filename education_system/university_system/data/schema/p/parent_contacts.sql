CREATE TABLE IF NOT EXISTS parent_contacts (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            student_id TEXT NOT NULL,
                            parent_name TEXT NOT NULL,
                            relationship TEXT,
                            email TEXT,
                            phone TEXT,
                            preferred_contact TEXT DEFAULT 'email',
                            created_at TEXT DEFAULT CURRENT_TIMESTAMP, "contact_type" TEXT, "contact_value" TEXT, "is_primary" INTEGER DEFAULT 0, "parent_id" INTEGER, "verified" INTEGER DEFAULT 0,
                            FOREIGN KEY (student_id) REFERENCES students (student_id)
                        );
