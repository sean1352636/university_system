CREATE TABLE IF NOT EXISTS legal_cases (
                    case_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_number TEXT UNIQUE NOT NULL,
                    client_id TEXT NOT NULL,
                    client_name TEXT NOT NULL,
                    client_email TEXT,
                    case_type TEXT NOT NULL,
                    case_title TEXT NOT NULL,
                    case_description TEXT,
                    status TEXT DEFAULT 'open',
                    priority TEXT DEFAULT 'normal',
                    assigned_lawyer TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    closed_at TIMESTAMP,
                    total_fees DECIMAL(10,2) DEFAULT 0.00,
                    amount_paid DECIMAL(10,2) DEFAULT 0.00,
                    created_by TEXT
                );
