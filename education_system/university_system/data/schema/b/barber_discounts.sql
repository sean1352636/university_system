CREATE TABLE IF NOT EXISTS barber_discounts (
                discount_id INTEGER PRIMARY KEY AUTOINCREMENT,
                appointment_id INTEGER NOT NULL,
                discount_type TEXT NOT NULL,
                value DECIMAL(10,2) NOT NULL,
                original_price DECIMAL(10,2) NOT NULL,
                final_price DECIMAL(10,2) NOT NULL,
                reason TEXT,
                applied_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (appointment_id) REFERENCES barber_appointments(appointment_id)
            );
