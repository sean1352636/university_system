CREATE TABLE IF NOT EXISTS dentist_patients (
                    patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_number TEXT UNIQUE NOT NULL,
                    user_id TEXT NOT NULL,
                    user_name TEXT NOT NULL,
                    user_email TEXT,
                    user_phone TEXT,
                    date_of_birth DATE,
                    address TEXT,
                    emergency_contact TEXT,
                    emergency_phone TEXT,
                    medical_history TEXT,
                    allergies TEXT,
                    insurance_provider TEXT,
                    insurance_number TEXT,
                    last_visit DATE,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
