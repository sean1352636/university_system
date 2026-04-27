CREATE TABLE IF NOT EXISTS cinema_memberships (
                    membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT UNIQUE NOT NULL,
                    user_name TEXT,
                    user_email TEXT,
                    membership_type TEXT DEFAULT 'standard',
                    points_balance INTEGER DEFAULT 0,
                    total_points_earned INTEGER DEFAULT 0,
                    total_spent REAL DEFAULT 0.00,
                    join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    renewal_date DATE,
                    status TEXT DEFAULT 'active',
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
