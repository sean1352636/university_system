CREATE TABLE IF NOT EXISTS dentist_treatments (
                    treatment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    appointment_id INTEGER,
                    patient_id INTEGER NOT NULL,
                    dentist_id TEXT NOT NULL,
                    dentist_name TEXT NOT NULL,
                    treatment_type TEXT NOT NULL,
                    treatment_date DATE NOT NULL,
                    tooth_number TEXT,
                    description TEXT,
                    fee DECIMAL(10,2) NOT NULL,
                    payment_status TEXT DEFAULT 'pending',
                    notes TEXT,
                    follow_up_required INTEGER DEFAULT 0,
                    follow_up_date DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (appointment_id) REFERENCES dentist_appointments(appointment_id),
                    FOREIGN KEY (patient_id) REFERENCES dentist_patients(patient_id)
                );
