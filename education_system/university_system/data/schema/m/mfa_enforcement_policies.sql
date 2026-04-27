CREATE TABLE IF NOT EXISTS mfa_enforcement_policies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_name TEXT NOT NULL UNIQUE,
                mfa_required BOOLEAN DEFAULT 0,
                allowed_methods TEXT,  -- JSON array: ["totp", "sms", "email"]
                minimum_methods INTEGER DEFAULT 1,  -- Require at least N methods
                grace_period_days INTEGER DEFAULT 7,  -- Days to enable MFA after enforcement
                enforce_on_login BOOLEAN DEFAULT 1,
                enforce_on_sensitive_actions BOOLEAN DEFAULT 1,
                allow_device_trust BOOLEAN DEFAULT 1,
                device_trust_duration_days INTEGER DEFAULT 30,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
