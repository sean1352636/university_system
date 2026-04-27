CREATE TABLE IF NOT EXISTS gym_memberships (
                    membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    member_number TEXT UNIQUE NOT NULL,
                    user_id TEXT NOT NULL,
                    user_name TEXT NOT NULL,
                    user_email TEXT,
                    user_phone TEXT,
                    membership_type TEXT NOT NULL,
                    monthly_fee DECIMAL(10,2) NOT NULL,
                    start_date DATE NOT NULL,
                    end_date DATE,
                    status TEXT DEFAULT 'active',
                    auto_renew INTEGER DEFAULT 1,
                    emergency_contact TEXT,
                    emergency_phone TEXT,
                    health_conditions TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT
                );
