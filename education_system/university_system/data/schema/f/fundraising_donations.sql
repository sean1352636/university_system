CREATE TABLE IF NOT EXISTS fundraising_donations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER,
                parent_id TEXT,
                student_id TEXT,
                amount DECIMAL(10,2),
                donation_date TEXT,
                anonymous BOOLEAN DEFAULT 0,
                FOREIGN KEY (campaign_id) REFERENCES fundraising_campaigns (id),
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            );
