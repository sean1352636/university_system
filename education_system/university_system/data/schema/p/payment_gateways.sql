CREATE TABLE IF NOT EXISTS payment_gateways (
            gateway_id INTEGER PRIMARY KEY AUTOINCREMENT,
            gateway_name TEXT NOT NULL,
            gateway_type TEXT NOT NULL, -- 'stripe', 'paypal', 'bank_transfer', etc.
            configuration TEXT, -- JSON with gateway config
            is_active BOOLEAN DEFAULT 1,
            transaction_fee_percentage DECIMAL(5,4),
            transaction_fee_fixed DECIMAL(10,2),
            supported_currencies TEXT, -- JSON array
            webhook_url TEXT,
            created_at TEXT,
            updated_at TEXT
        );
