CREATE TABLE IF NOT EXISTS nailbar_payments (
                        payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        booking_ref TEXT NOT NULL,
                        appointment_id INTEGER,
                        amount REAL NOT NULL,
                        tip_amount REAL DEFAULT 0.0,
                        total_amount REAL NOT NULL,
                        payment_method TEXT NOT NULL,
                        payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        technician_id INTEGER,
                        technician_name TEXT,
                        receipt_number TEXT UNIQUE NOT NULL,
                        status TEXT DEFAULT 'completed',
                        FOREIGN KEY (appointment_id) REFERENCES nailbar_appointments(appointment_id),
                        FOREIGN KEY (technician_id) REFERENCES nailbar_technicians(technician_id)
                    );
