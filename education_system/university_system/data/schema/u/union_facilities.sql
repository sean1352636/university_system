CREATE TABLE IF NOT EXISTS union_facilities (
            facility_id INTEGER PRIMARY KEY AUTOINCREMENT,
            facility_name TEXT UNIQUE,
            location TEXT,
            capacity INTEGER,
            description TEXT,
            status TEXT DEFAULT 'available',
            equipment TEXT,
            booking_fee REAL DEFAULT 0.0
        );
