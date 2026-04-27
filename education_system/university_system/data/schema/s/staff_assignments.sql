CREATE TABLE IF NOT EXISTS staff_assignments (
            assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id TEXT NOT NULL,
            category TEXT NOT NULL,
            is_primary BOOLEAN DEFAULT 0,
            max_concurrent_tickets INTEGER DEFAULT 10,
            current_ticket_count INTEGER DEFAULT 0,
            expertise_level INTEGER DEFAULT 1,  -- 1-5 scale
            auto_assign_enabled BOOLEAN DEFAULT 1
        );
