CREATE TABLE IF NOT EXISTS nailbar_technicians (
                technician_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                employee_id TEXT UNIQUE,
                specialties TEXT,
                phone TEXT,
                email TEXT,
                certification TEXT,
                is_active INTEGER DEFAULT 1,
                hire_date TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
