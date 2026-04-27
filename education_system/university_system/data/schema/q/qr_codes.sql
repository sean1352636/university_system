CREATE TABLE IF NOT EXISTS qr_codes (
                        qr_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        table_number TEXT,
                        qr_data TEXT,
                        generated_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                        image_path TEXT
                    );
