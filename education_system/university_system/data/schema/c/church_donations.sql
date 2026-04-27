CREATE TABLE IF NOT EXISTS church_donations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    donor_name TEXT,
    donor_email TEXT,
    amount REAL,
    donation_type TEXT,
    payment_method TEXT,
    transaction_ref TEXT,
    date TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
