CREATE TABLE IF NOT EXISTS alumni_donations (
            donation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumni_id INTEGER NOT NULL,
            donation_amount REAL NOT NULL,
            donation_date TEXT DEFAULT CURRENT_DATE,
            donation_type TEXT NOT NULL,
            fund_designation TEXT,
            campaign_id INTEGER,
            payment_method TEXT,
            is_recurring BOOLEAN DEFAULT 0,
            recurrence_frequency TEXT,
            tax_receipt_sent BOOLEAN DEFAULT 0,
            acknowledgment_sent BOOLEAN DEFAULT 0,
            FOREIGN KEY (alumni_id) REFERENCES alumni_profiles (alumni_id)
        );
