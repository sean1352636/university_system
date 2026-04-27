CREATE TABLE IF NOT EXISTS sla_policies (
            sla_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            priority TEXT,
            impact TEXT,
            urgency TEXT,
            first_response_hours INTEGER,
            resolution_hours INTEGER,
            escalation_hours INTEGER,
            business_hours_only BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        );
