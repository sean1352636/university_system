CREATE TABLE IF NOT EXISTS qr_scans (
                scan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_number TEXT,
                scan_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                customer_id INTEGER,
                device_type TEXT
            );
