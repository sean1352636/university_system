CREATE TABLE IF NOT EXISTS eco_suppliers (
                supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT,
                certifications TEXT,
                description TEXT,
                contact_email TEXT,
                rating REAL DEFAULT 0,
                added_by TEXT,
                added_date TEXT
            );
