CREATE TABLE IF NOT EXISTS cash_transactions (
                        transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        order_id INTEGER,
                        cash_tendered REAL,
                        change_given REAL,
                        transaction_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (order_id) REFERENCES orders(order_id)
                    );
