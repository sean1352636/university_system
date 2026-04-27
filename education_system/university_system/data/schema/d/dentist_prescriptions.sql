CREATE TABLE IF NOT EXISTS dentist_prescriptions (
                    prescription_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id INTEGER NOT NULL,
                    dentist_id TEXT NOT NULL,
                    dentist_name TEXT NOT NULL,
                    treatment_id INTEGER,
                    medication TEXT NOT NULL,
                    dosage TEXT NOT NULL,
                    frequency TEXT NOT NULL,
                    duration TEXT NOT NULL,
                    instructions TEXT,
                    prescribed_date DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (patient_id) REFERENCES dentist_patients(patient_id),
                    FOREIGN KEY (treatment_id) REFERENCES dentist_treatments(treatment_id)
                );
