CREATE TABLE IF NOT EXISTS barber_commissions (
                commission_id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_id INTEGER NOT NULL,
                commission_type TEXT DEFAULT 'percentage',
                rate DECIMAL(5,2) NOT NULL,
                service_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (staff_id) REFERENCES barber_staff(staff_id)
            );
