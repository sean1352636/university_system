CREATE TABLE IF NOT EXISTS mental_health_crisis_contacts (
            contact_id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_name TEXT NOT NULL,
            hotline_number TEXT NOT NULL,
            availability TEXT NOT NULL,
            description TEXT,
            is_emergency BOOLEAN DEFAULT 0,
            display_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1
        );
