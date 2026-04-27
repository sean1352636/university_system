CREATE TABLE IF NOT EXISTS contract_renewal_alerts (
                    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contract_id INTEGER NOT NULL,
                    alert_type TEXT NOT NULL,
                    alert_date TEXT NOT NULL,
                    days_before_expiry INTEGER,
                    sent BOOLEAN DEFAULT 0,
                    sent_date TEXT,
                    recipient_id TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (contract_id) REFERENCES staff_contracts(contract_id)
                );
