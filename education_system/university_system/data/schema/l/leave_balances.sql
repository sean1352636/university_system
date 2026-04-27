CREATE TABLE IF NOT EXISTS leave_balances (
                    balance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    leave_type_id INTEGER NOT NULL,
                    year INTEGER NOT NULL,
                    allocated_days REAL DEFAULT 0,
                    used_days REAL DEFAULT 0,
                    carried_over REAL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, leave_type_id, year),
                    FOREIGN KEY (leave_type_id) REFERENCES leave_types(leave_type_id)
                );
