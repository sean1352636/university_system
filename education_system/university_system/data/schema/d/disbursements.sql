CREATE TABLE IF NOT EXISTS disbursements (
    disbursement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    award_id INTEGER,
    component_id INTEGER,
    student_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    disbursement_type TEXT,  -- scholarship, grant, loan, work_study
    disbursement_date DATE NOT NULL,
    scheduled_date DATE,
    academic_term TEXT,  -- Fall, Spring, Summer
    status TEXT DEFAULT 'pending',  -- pending, processed, failed, cancelled
    payment_method TEXT DEFAULT 'account_credit',
    transaction_id TEXT,
    processed_by INTEGER,
    processed_at TIMESTAMP,
    error_message TEXT,
    FOREIGN KEY (award_id) REFERENCES scholarship_awards(award_id),
    FOREIGN KEY (component_id) REFERENCES aid_components(component_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);
