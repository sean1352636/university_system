CREATE TABLE IF NOT EXISTS train_station_receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                receipt_number TEXT UNIQUE NOT NULL,
                ticket_id INTEGER NOT NULL,
                total_amount REAL NOT NULL,
                payment_method TEXT NOT NULL,
                transaction_date TEXT NOT NULL,
                FOREIGN KEY (ticket_id) REFERENCES train_station_tickets (id)
            );
