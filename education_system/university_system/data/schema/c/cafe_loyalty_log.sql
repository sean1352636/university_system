CREATE TABLE IF NOT EXISTS cafe_loyalty_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                points_change INTEGER NOT NULL,
                transaction_type TEXT NOT NULL,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES cafe_loyalty(student_id)
            );
