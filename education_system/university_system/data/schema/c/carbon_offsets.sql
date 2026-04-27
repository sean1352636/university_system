CREATE TABLE IF NOT EXISTS carbon_offsets (
                offset_id INTEGER PRIMARY KEY AUTOINCREMENT,
                program_name TEXT NOT NULL,
                description TEXT,
                offset_kg REAL DEFAULT 0,
                cost REAL DEFAULT 0,
                status TEXT DEFAULT 'pending',
                purchased_by TEXT,
                purchase_date TEXT
            );
