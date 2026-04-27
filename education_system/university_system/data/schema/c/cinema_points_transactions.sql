CREATE TABLE IF NOT EXISTS cinema_points_transactions (
                    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    booking_ref TEXT,
                    transaction_type TEXT NOT NULL,
                    points INTEGER NOT NULL,
                    description TEXT,
                    transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES cinema_memberships(user_id)
                );
