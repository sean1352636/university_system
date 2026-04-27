CREATE TABLE IF NOT EXISTS mail_po_boxes (
                    box_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    box_number TEXT UNIQUE NOT NULL,
                    holder_id TEXT,
                    holder_name TEXT,
                    holder_email TEXT,
                    size TEXT DEFAULT 'standard',
                    monthly_fee DECIMAL(10,2) DEFAULT 10.00,
                    status TEXT DEFAULT 'available',
                    rental_start DATE,
                    rental_end DATE,
                    auto_renew INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
