CREATE TABLE IF NOT EXISTS payment_schedules (
    schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    award_id INTEGER,
    component_id INTEGER,
    student_id INTEGER NOT NULL,
    total_amount REAL NOT NULL,
    payment_date DATE NOT NULL,
    amount REAL NOT NULL,
    academic_term TEXT,
    status TEXT DEFAULT 'scheduled',  -- scheduled, paid, cancelled
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "plan_id" INTEGER, "installment_number" INTEGER, "due_date" TEXT, "paid_date" TEXT, "paid_amount" REAL,
    FOREIGN KEY (award_id) REFERENCES scholarship_awards(award_id),
    FOREIGN KEY (component_id) REFERENCES aid_components(component_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);
