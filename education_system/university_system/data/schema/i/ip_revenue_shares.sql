CREATE TABLE IF NOT EXISTS ip_revenue_shares (
                    revenue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    license_id INTEGER NOT NULL,
                    period TEXT NOT NULL,
                    total_revenue REAL DEFAULT 0,
                    university_share REAL DEFAULT 0,
                    inventor_share REAL DEFAULT 0,
                    department_share REAL DEFAULT 0,
                    payment_date TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (license_id) REFERENCES ip_licenses(license_id)
                );
