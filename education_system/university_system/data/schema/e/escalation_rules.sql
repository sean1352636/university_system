CREATE TABLE IF NOT EXISTS escalation_rules (
            rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            priority TEXT,
            condition_type TEXT NOT NULL,  -- time_based, status_based, keyword_based
            condition_value TEXT NOT NULL,
            action_type TEXT NOT NULL,  -- escalate, reassign, notify
            action_target TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            created_by TEXT NOT NULL,
            created_datetime TEXT NOT NULL
        );
